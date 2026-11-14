from __future__ import annotations

import asyncio
import json
import logging
import os
import threading
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import duckdb

from app.core.config import BACKEND_ROOT, settings
from app.services.agent.harness.models import (
    CalibrationReport,
    ExperienceEntry,
    HarnessComponents,
    HarnessOverlay,
    ProbeResult,
)
from app.services.agent.harness.validator import sanitize_experience_text, validate_workspace_id

logger = logging.getLogger(__name__)


class HarnessStorageService:
    """DuckDB + atomic .buddhi/harness/ persistence for Harness2 overlays and EXPERIENCE."""

    def __init__(
        self,
        db_path: str | None = None,
        mirror_root: Path | None = None,
    ) -> None:
        self.db_path = db_path or str(settings.harness_db_path)
        self.mirror_root = mirror_root or (BACKEND_ROOT.parent / ".buddhi" / "harness")
        self._lock = threading.RLock()
        self._is_in_memory = self.db_path == ":memory:"
        self._in_memory_conn: duckdb.DuckDBPyConnection | None = None
        if self._is_in_memory:
            self._in_memory_conn = duckdb.connect(":memory:")
        self._init_db()

    def _get_connection(self) -> duckdb.DuckDBPyConnection:
        if self._is_in_memory and self._in_memory_conn is not None:
            return self._in_memory_conn
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        return duckdb.connect(self.db_path)

    def _init_db(self) -> None:
        with self._lock:
            if self._is_in_memory and self._in_memory_conn is not None:
                self._create_tables(self._in_memory_conn)
            else:
                with self._get_connection() as conn:
                    self._create_tables(conn)

    def _create_tables(self, conn: duckdb.DuckDBPyConnection) -> None:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS harness_overlays (
                version_id VARCHAR PRIMARY KEY,
                workspace_id VARCHAR NOT NULL,
                parent_version_id VARCHAR,
                is_active BOOLEAN NOT NULL DEFAULT FALSE,
                is_pinned BOOLEAN NOT NULL DEFAULT FALSE,
                components_json VARCHAR NOT NULL,
                content_hash VARCHAR NOT NULL,
                source_run_id VARCHAR,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_overlays_workspace_active "
            "ON harness_overlays (workspace_id, is_active, created_at DESC)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_overlays_workspace_created "
            "ON harness_overlays (workspace_id, created_at DESC)"
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS harness_experiences (
                entry_id VARCHAR PRIMARY KEY,
                workspace_id VARCHAR NOT NULL,
                task_signature VARCHAR NOT NULL,
                lesson VARCHAR NOT NULL,
                evidence_run_id VARCHAR NOT NULL,
                components_affected_json VARCHAR NOT NULL,
                confidence_score DOUBLE NOT NULL DEFAULT 0.5,
                hit_count INTEGER NOT NULL DEFAULT 0,
                is_pinned BOOLEAN NOT NULL DEFAULT FALSE,
                is_active BOOLEAN NOT NULL DEFAULT TRUE,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                last_used_at TIMESTAMP
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_exp_workspace_active_score "
            "ON harness_experiences (workspace_id, is_active, is_pinned DESC, confidence_score DESC, created_at DESC)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_exp_workspace_sig "
            "ON harness_experiences (workspace_id, task_signature)"
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS harness_calibrations (
                calibration_id VARCHAR PRIMARY KEY,
                workspace_id VARCHAR NOT NULL,
                run_id VARCHAR NOT NULL,
                round INTEGER NOT NULL,
                trigger_reason VARCHAR NOT NULL,
                baseline_overlay_id VARCHAR,
                baseline_score DOUBLE NOT NULL,
                winning_candidate_id VARCHAR,
                adopted_overlay_id VARCHAR,
                status VARCHAR NOT NULL,
                adopted_components_json VARCHAR NOT NULL,
                rejected_reasons_json VARCHAR NOT NULL,
                rlm_used BOOLEAN NOT NULL DEFAULT FALSE,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_cal_workspace_run "
            "ON harness_calibrations (workspace_id, run_id, round)"
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS harness_probe_results (
                probe_id VARCHAR PRIMARY KEY,
                calibration_id VARCHAR NOT NULL,
                workspace_id VARCHAR NOT NULL,
                candidate_id VARCHAR NOT NULL,
                target_components_json VARCHAR NOT NULL,
                status VARCHAR NOT NULL,
                steps_taken INTEGER NOT NULL DEFAULT 0,
                tool_error_count INTEGER NOT NULL DEFAULT 0,
                test_pass_rate DOUBLE NOT NULL DEFAULT 0.0,
                wall_clock_ms INTEGER NOT NULL DEFAULT 0,
                trajectory_summary VARCHAR NOT NULL,
                guardrail_violations_json VARCHAR NOT NULL,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_probe_calibration "
            "ON harness_probe_results (calibration_id, candidate_id)"
        )

    def _workspace_dir(self, workspace_id: str) -> Path:
        if not validate_workspace_id(workspace_id):
            raise ValueError(f"Invalid workspace_id: {workspace_id!r}")
        return self.mirror_root / workspace_id

    @staticmethod
    def _atomic_write(path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + f".tmp.{uuid.uuid4().hex[:8]}")
        tmp.write_text(content, encoding="utf-8")
        os.replace(tmp, path)

    def _mirror_overlay(self, overlay: HarnessOverlay) -> None:
        ws_dir = self._workspace_dir(overlay.workspace_id)
        payload = overlay.model_dump_json(indent=2)
        if overlay.is_active:
            self._atomic_write(ws_dir / "overlay.json", payload)
        self._atomic_write(ws_dir / "history" / f"{overlay.version_id}.json", payload)

    def _mirror_experience(self, workspace_id: str, entries: list[ExperienceEntry]) -> None:
        ws_dir = self._workspace_dir(workspace_id)
        lines = [f"# Workspace Experience Library (`{workspace_id}`)", ""]
        for entry in entries:
            pin_tag = " [PINNED]" if entry.is_pinned else ""
            lines.append(
                f"- **{entry.task_signature}**{pin_tag} (confidence={entry.confidence_score:.2f}, "
                f"run=`{entry.evidence_run_id}`, components={','.join(entry.components_affected) or 'none'}): "
                f"{entry.lesson}"
            )
        self._atomic_write(ws_dir / "EXPERIENCE.md", "\n".join(lines) + "\n")

    @staticmethod
    def _row_to_overlay(row: tuple[Any, ...]) -> HarnessOverlay:
        return HarnessOverlay(
            version_id=row[0],
            workspace_id=row[1],
            parent_version_id=row[2],
            is_active=bool(row[3]),
            is_pinned=bool(row[4]),
            components=HarnessComponents.model_validate_json(row[5]),
            source_run_id=row[7],
            created_at=str(row[8]),
        )

    def get_active_overlay(self, workspace_id: str) -> HarnessOverlay | None:
        if not validate_workspace_id(workspace_id):
            raise ValueError(f"Invalid workspace_id: {workspace_id!r}")
        with self._lock:
            conn = self._get_connection()
            try:
                row = conn.execute(
                    """
                    SELECT version_id, workspace_id, parent_version_id, is_active, is_pinned,
                           components_json, content_hash, source_run_id, created_at
                    FROM harness_overlays
                    WHERE workspace_id = ? AND is_active = TRUE
                    ORDER BY created_at DESC
                    LIMIT 1
                    """,
                    (workspace_id,),
                ).fetchone()
            finally:
                if not self._is_in_memory:
                    conn.close()
        return self._row_to_overlay(row) if row else None

    async def aget_active_overlay(self, workspace_id: str) -> HarnessOverlay | None:
        return await asyncio.to_thread(self.get_active_overlay, workspace_id)

    def save_overlay_snapshot(self, overlay: HarnessOverlay, activate: bool = True) -> HarnessOverlay:
        if not validate_workspace_id(overlay.workspace_id):
            raise ValueError(f"Invalid workspace_id: {overlay.workspace_id!r}")
        to_save = overlay.model_copy(update={"is_active": activate})
        comp_json = to_save.components.model_dump_json()
        with self._lock:
            conn = self._get_connection()
            try:
                conn.execute("BEGIN TRANSACTION")
                if activate:
                    conn.execute(
                        "UPDATE harness_overlays SET is_active = FALSE WHERE workspace_id = ? AND is_active = TRUE",
                        (to_save.workspace_id,),
                    )
                conn.execute(
                    """
                    INSERT OR REPLACE INTO harness_overlays
                    (version_id, workspace_id, parent_version_id, is_active, is_pinned,
                     components_json, content_hash, source_run_id, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        to_save.version_id,
                        to_save.workspace_id,
                        to_save.parent_version_id,
                        to_save.is_active,
                        to_save.is_pinned,
                        comp_json,
                        to_save.content_hash,
                        to_save.source_run_id,
                        to_save.created_at,
                    ),
                )
                self._prune_overlay_history_conn(conn, to_save.workspace_id)
                conn.execute("COMMIT")
            except Exception:
                conn.execute("ROLLBACK")
                raise
            finally:
                if not self._is_in_memory:
                    conn.close()
        self._mirror_overlay(to_save)
        return to_save

    def _prune_overlay_history_conn(self, conn: duckdb.DuckDBPyConnection, workspace_id: str) -> None:
        keep = settings.harness_max_overlay_history
        rows = conn.execute(
            """
            SELECT version_id FROM harness_overlays
            WHERE workspace_id = ? AND is_active = FALSE AND is_pinned = FALSE
            ORDER BY created_at DESC
            OFFSET ?
            """,
            (workspace_id, keep),
        ).fetchall()
        for (vid,) in rows:
            conn.execute("DELETE FROM harness_overlays WHERE version_id = ?", (vid,))
            hist_file = self._workspace_dir(workspace_id) / "history" / f"{vid}.json"
            if hist_file.exists():
                hist_file.unlink(missing_ok=True)

    def rollback_overlay(self, workspace_id: str, target_version_id: str) -> HarnessOverlay:
        if not validate_workspace_id(workspace_id) or not validate_workspace_id(target_version_id):
            raise ValueError("Invalid workspace_id or version_id")
        with self._lock:
            conn = self._get_connection()
            try:
                conn.execute("BEGIN TRANSACTION")
                row = conn.execute(
                    """
                    SELECT version_id, workspace_id, parent_version_id, is_active, is_pinned,
                           components_json, content_hash, source_run_id, created_at
                    FROM harness_overlays
                    WHERE workspace_id = ? AND version_id = ?
                    """,
                    (workspace_id, target_version_id),
                ).fetchone()
                if not row:
                    conn.execute("ROLLBACK")
                    raise KeyError(f"Overlay version '{target_version_id}' not found for '{workspace_id}'")
                conn.execute(
                    "UPDATE harness_overlays SET is_active = FALSE WHERE workspace_id = ? AND is_active = TRUE",
                    (workspace_id,),
                )
                conn.execute(
                    "UPDATE harness_overlays SET is_active = TRUE WHERE workspace_id = ? AND version_id = ?",
                    (workspace_id, target_version_id),
                )
                conn.execute("COMMIT")
                restored = self._row_to_overlay(row).model_copy(update={"is_active": True})
            except Exception:
                try:
                    conn.execute("ROLLBACK")
                except Exception:
                    pass
                raise
            finally:
                if not self._is_in_memory:
                    conn.close()
        self._mirror_overlay(restored)
        return restored

    def reset_workspace(self, workspace_id: str) -> None:
        if not validate_workspace_id(workspace_id):
            raise ValueError(f"Invalid workspace_id: {workspace_id!r}")
        with self._lock:
            conn = self._get_connection()
            try:
                conn.execute(
                    "UPDATE harness_overlays SET is_active = FALSE WHERE workspace_id = ? AND is_active = TRUE",
                    (workspace_id,),
                )
            finally:
                if not self._is_in_memory:
                    conn.close()
        overlay_file = self._workspace_dir(workspace_id) / "overlay.json"
        if overlay_file.exists():
            overlay_file.unlink(missing_ok=True)

    def list_overlay_history(self, workspace_id: str, limit: int = 20) -> list[HarnessOverlay]:
        if not validate_workspace_id(workspace_id):
            raise ValueError(f"Invalid workspace_id: {workspace_id!r}")
        with self._lock:
            conn = self._get_connection()
            try:
                rows = conn.execute(
                    """
                    SELECT version_id, workspace_id, parent_version_id, is_active, is_pinned,
                           components_json, content_hash, source_run_id, created_at
                    FROM harness_overlays
                    WHERE workspace_id = ?
                    ORDER BY created_at DESC
                    LIMIT ?
                    """,
                    (workspace_id, limit),
                ).fetchall()
            finally:
                if not self._is_in_memory:
                    conn.close()
        return [self._row_to_overlay(r) for r in rows]

    def upsert_experience(self, entry: ExperienceEntry, max_entries: int | None = None) -> ExperienceEntry:
        if not validate_workspace_id(entry.workspace_id):
            raise ValueError(f"Invalid workspace_id: {entry.workspace_id!r}")
        sanitized_lesson = sanitize_experience_text(entry.lesson)
        sanitized_sig = sanitize_experience_text(entry.task_signature, max_chars=160)
        clean_entry = entry.model_copy(update={"lesson": sanitized_lesson, "task_signature": sanitized_sig})
        cap = max_entries or settings.harness_max_experiences_per_workspace

        with self._lock:
            conn = self._get_connection()
            try:
                conn.execute("BEGIN TRANSACTION")
                conn.execute(
                    """
                    INSERT OR REPLACE INTO harness_experiences
                    (entry_id, workspace_id, task_signature, lesson, evidence_run_id,
                     components_affected_json, confidence_score, hit_count, is_pinned,
                     is_active, created_at, last_used_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        clean_entry.entry_id,
                        clean_entry.workspace_id,
                        clean_entry.task_signature,
                        clean_entry.lesson,
                        clean_entry.evidence_run_id,
                        json.dumps(clean_entry.components_affected),
                        clean_entry.confidence_score,
                        clean_entry.hit_count,
                        clean_entry.is_pinned,
                        clean_entry.is_active,
                        clean_entry.created_at,
                        clean_entry.last_used_at,
                    ),
                )
                # Bounded retention: evict lowest confidence / oldest unpinned entries beyond cap
                excess = conn.execute(
                    """
                    SELECT entry_id FROM harness_experiences
                    WHERE workspace_id = ? AND is_active = TRUE AND is_pinned = FALSE
                    ORDER BY confidence_score DESC, COALESCE(last_used_at, created_at) DESC
                    OFFSET ?
                    """,
                    (clean_entry.workspace_id, cap),
                ).fetchall()
                for (eid,) in excess:
                    conn.execute("DELETE FROM harness_experiences WHERE entry_id = ?", (eid,))
                conn.execute("COMMIT")
            except Exception:
                conn.execute("ROLLBACK")
                raise
            finally:
                if not self._is_in_memory:
                    conn.close()

        entries = self.get_active_experiences(clean_entry.workspace_id, limit=cap)
        self._mirror_experience(clean_entry.workspace_id, entries)
        return clean_entry

    def get_active_experiences(
        self,
        workspace_id: str,
        limit: int = 20,
        token_budget: int | None = None,
    ) -> list[ExperienceEntry]:
        if not validate_workspace_id(workspace_id):
            raise ValueError(f"Invalid workspace_id: {workspace_id!r}")
        budget_chars = (token_budget or settings.harness_experience_token_budget) * 4
        with self._lock:
            conn = self._get_connection()
            try:
                rows = conn.execute(
                    """
                    SELECT entry_id, workspace_id, task_signature, lesson, evidence_run_id,
                           components_affected_json, confidence_score, hit_count, is_pinned,
                           is_active, created_at, last_used_at
                    FROM harness_experiences
                    WHERE workspace_id = ? AND is_active = TRUE
                    ORDER BY is_pinned DESC, confidence_score DESC, created_at DESC
                    LIMIT ?
                    """,
                    (workspace_id, limit),
                ).fetchall()
            finally:
                if not self._is_in_memory:
                    conn.close()

        results: list[ExperienceEntry] = []
        used_chars = 0
        for row in rows:
            entry = ExperienceEntry(
                entry_id=row[0],
                workspace_id=row[1],
                task_signature=row[2],
                lesson=row[3],
                evidence_run_id=row[4],
                components_affected=json.loads(row[5] or "[]"),
                confidence_score=float(row[6]),
                hit_count=int(row[7]),
                is_pinned=bool(row[8]),
                is_active=bool(row[9]),
                created_at=str(row[10]),
                last_used_at=str(row[11]) if row[11] else None,
            )
            entry_chars = len(entry.lesson) + len(entry.task_signature) + 32
            if results and used_chars + entry_chars > budget_chars:
                break
            used_chars += entry_chars
            results.append(entry)
        return results

    async def aget_active_experiences(
        self,
        workspace_id: str,
        limit: int = 20,
        token_budget: int | None = None,
    ) -> list[ExperienceEntry]:
        return await asyncio.to_thread(self.get_active_experiences, workspace_id, limit, token_budget)

    def set_experience_pin(self, workspace_id: str, entry_id: str, pinned: bool) -> bool:
        if not validate_workspace_id(workspace_id):
            raise ValueError(f"Invalid workspace_id: {workspace_id!r}")
        with self._lock:
            conn = self._get_connection()
            try:
                existing = conn.execute(
                    "SELECT 1 FROM harness_experiences WHERE workspace_id = ? AND entry_id = ?",
                    (workspace_id, entry_id),
                ).fetchone()
                if not existing:
                    return False
                conn.execute(
                    "UPDATE harness_experiences SET is_pinned = ? WHERE workspace_id = ? AND entry_id = ?",
                    (pinned, workspace_id, entry_id),
                )
            finally:
                if not self._is_in_memory:
                    conn.close()
        self._mirror_experience(workspace_id, self.get_active_experiences(workspace_id))
        return True

    def delete_experience(self, workspace_id: str, entry_id: str) -> bool:
        if not validate_workspace_id(workspace_id):
            raise ValueError(f"Invalid workspace_id: {workspace_id!r}")
        with self._lock:
            conn = self._get_connection()
            try:
                existing = conn.execute(
                    "SELECT 1 FROM harness_experiences WHERE workspace_id = ? AND entry_id = ?",
                    (workspace_id, entry_id),
                ).fetchone()
                if not existing:
                    return False
                conn.execute(
                    "DELETE FROM harness_experiences WHERE workspace_id = ? AND entry_id = ?",
                    (workspace_id, entry_id),
                )
            finally:
                if not self._is_in_memory:
                    conn.close()
        self._mirror_experience(workspace_id, self.get_active_experiences(workspace_id))
        return True

    def record_calibration(self, report: CalibrationReport, probes: list[ProbeResult]) -> None:
        if not validate_workspace_id(report.workspace_id):
            raise ValueError(f"Invalid workspace_id: {report.workspace_id!r}")
        cutoff = (
            datetime.now(timezone.utc) - timedelta(days=settings.harness_calibration_retention_days)
        ).isoformat()
        with self._lock:
            conn = self._get_connection()
            try:
                conn.execute("BEGIN TRANSACTION")
                conn.execute(
                    """
                    INSERT OR REPLACE INTO harness_calibrations
                    (calibration_id, workspace_id, run_id, round, trigger_reason,
                     baseline_overlay_id, baseline_score, winning_candidate_id, adopted_overlay_id,
                     status, adopted_components_json, rejected_reasons_json, rlm_used, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        report.calibration_id,
                        report.workspace_id,
                        report.run_id,
                        report.round,
                        report.trigger_reason,
                        report.baseline_overlay_id,
                        report.baseline_score,
                        report.winning_candidate_id,
                        report.adopted_overlay_id,
                        report.status,
                        json.dumps(report.adopted_components),
                        json.dumps(report.rejected_reasons),
                        report.rlm_used,
                        report.created_at,
                    ),
                )
                for p in probes:
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO harness_probe_results
                        (probe_id, calibration_id, workspace_id, candidate_id, target_components_json,
                         status, steps_taken, tool_error_count, test_pass_rate, wall_clock_ms,
                         trajectory_summary, guardrail_violations_json, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            p.probe_id,
                            report.calibration_id,
                            report.workspace_id,
                            p.candidate_id,
                            json.dumps(p.target_components),
                            p.status,
                            p.steps_taken,
                            p.tool_error_count,
                            p.test_pass_rate,
                            p.wall_clock_ms,
                            p.trajectory_summary,
                            json.dumps(p.guardrail_violations),
                            p.created_at,
                        ),
                    )
                # Prune expired calibrations (child probes first, then parents)
                expired = conn.execute(
                    "SELECT calibration_id FROM harness_calibrations WHERE created_at < ?",
                    (cutoff,),
                ).fetchall()
                for (cid,) in expired:
                    conn.execute("DELETE FROM harness_probe_results WHERE calibration_id = ?", (cid,))
                    conn.execute("DELETE FROM harness_calibrations WHERE calibration_id = ?", (cid,))
                conn.execute("COMMIT")
            except Exception:
                conn.execute("ROLLBACK")
                raise
            finally:
                if not self._is_in_memory:
                    conn.close()


harness_storage_service = HarnessStorageService()
