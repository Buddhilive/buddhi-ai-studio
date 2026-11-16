from __future__ import annotations

import asyncio
import base64
import logging
import os
import posixpath
import re
import shlex
import shutil
import uuid
from pathlib import Path
from typing import Any

import httpx
from fastapi import HTTPException, Request, Response, status

from app.core.config import settings
from app.schemas.build import (
    BuildFileContentResponse,
    BuildFileNode,
    BuildFileTreeResponse,
    BuildFileWriteResponse,
    BuildHistoryPayload,
    BuildPreviewStatusResponse,
    BuildProjectCreateRequest,
    BuildProjectResponse,
    BuildProjectStartResponse,
)
from app.schemas.sandbox import (
    SandboxExecutionRequest,
    SandboxExecutionResult,
    SandboxSessionCreateRequest,
)
from app.services.agent.redaction import redact_text
from app.services.agent.tools import validate_workspace_path
from app.services.agent.vibe_starter import ensure_vibe_starter_workspace
from app.services.build_project_storage import BuildProjectStorage
from app.services.sandbox_service import sandbox_service
from app.services.storage_service import StorageError, storage_service

logger = logging.getLogger(__name__)

_PROJECT_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")
_MAX_FILE_BYTES = 5 * 1024 * 1024  # 5 MiB
_EXCLUDED_DIRS = frozenset({
    "node_modules",
    ".next",
    ".venv",
    "__pycache__",
    ".cache",
    "dist",
    "build",
})


def _is_excluded_rel_path(rel_path: str) -> bool:
    norm = rel_path.replace("\\", "/").lstrip("/")
    if not norm:
        return True
    parts = norm.split("/")
    if any(p in _EXCLUDED_DIRS for p in parts):
        return True
    if ".git" in parts:
        git_idx = parts.index(".git")
        if git_idx + 1 < len(parts) and parts[git_idx + 1] == "objects":
            return True
    return False


def _validate_project_id(project_id: str) -> str:
    if not _PROJECT_ID_RE.match(project_id):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid project_id format",
        )
    return project_id


def _build_file_tree(paths: list[str]) -> list[BuildFileNode]:
    root_children: dict[str, Any] = {}
    for raw_path in sorted(set(paths)):
        parts = [p for p in raw_path.strip("/").split("/") if p]
        if not parts:
            continue
        cursor = root_children
        acc: list[str] = []
        for idx, part in enumerate(parts):
            acc.append(part)
            full_path = "/".join(acc)
            is_last = idx == len(parts) - 1
            if part not in cursor:
                cursor[part] = {
                    "name": part,
                    "path": full_path,
                    "type": "file" if is_last else "directory",
                    "children": {},
                }
            elif not is_last:
                cursor[part]["type"] = "directory"
            cursor = cursor[part]["children"]

    def _to_nodes(node_map: dict[str, Any]) -> list[BuildFileNode]:
        items = sorted(
            node_map.values(),
            key=lambda item: (0 if item["type"] == "directory" else 1, item["name"].lower()),
        )
        return [
            BuildFileNode(
                name=item["name"],
                path=item["path"],
                type=item["type"],
                children=_to_nodes(item["children"]),
            )
            for item in items
        ]

    return _to_nodes(root_children)


class BuildProjectService:
    """Manages Build projects, OpenSandbox lifecycle, and RustFS/local workspace snapshots."""

    def __init__(
        self,
        storage: BuildProjectStorage | None = None,
        local_dir: Path | None = None,
    ) -> None:
        self.storage = storage or BuildProjectStorage()
        self.local_dir = local_dir or settings.build_projects_local_dir

    async def start(self) -> None:
        self.local_dir.mkdir(parents=True, exist_ok=True)
        try:
            await storage_service.ensure_bucket(settings.build_projects_bucket)
        except Exception as exc:
            logger.warning(
                "RustFS bucket '%s' unavailable at startup (falling back to local snapshot cache): %s",
                settings.build_projects_bucket,
                exc,
            )

    def _local_files_dir(self, project_id: str) -> Path:
        return self.local_dir / project_id / "files"

    def _snapshot_key(self, project_id: str, rel_path: str) -> str:
        clean = rel_path.lstrip("/")
        return f"{project_id}/files/{clean}"

    async def _write_snapshot_file(self, project_id: str, rel_path: str, content: str) -> bool:
        if _is_excluded_rel_path(rel_path):
            return False
        if len(content.encode("utf-8", errors="ignore")) > _MAX_FILE_BYTES:
            logger.warning("Skipping snapshot of '%s' (>5 MiB)", rel_path)
            return False

        # Local atomic cache write
        local_target = self._local_files_dir(project_id) / rel_path
        local_target.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = local_target.with_suffix(local_target.suffix + ".tmp")
        tmp_path.write_text(content, encoding="utf-8")
        os.replace(tmp_path, local_target)

        # Primary RustFS S3 write
        try:
            await storage_service.ensure_bucket(settings.build_projects_bucket)
            await storage_service.put_text(
                settings.build_projects_bucket,
                self._snapshot_key(project_id, rel_path),
                content,
            )
            return True
        except StorageError as exc:
            logger.warning("RustFS snapshot write failed for %s/%s: %s", project_id, rel_path, exc)
            return False

    async def _list_snapshot_files(self, project_id: str) -> list[str]:
        prefix = f"{project_id}/files/"
        try:
            keys = await storage_service.list_keys(settings.build_projects_bucket, prefix=prefix)
            rels = [k[len(prefix):] for k in keys if k.startswith(prefix) and len(k) > len(prefix)]
            filtered = [r for r in rels if not _is_excluded_rel_path(r)]
            if filtered:
                return sorted(filtered)
        except StorageError as exc:
            logger.debug("RustFS list_keys unavailable for %s: %s", project_id, exc)

        local_root = self._local_files_dir(project_id)
        if not local_root.exists():
            return []
        rels: list[str] = []
        for fp in local_root.rglob("*"):
            if fp.is_file() and not fp.is_symlink():
                rel = fp.relative_to(local_root).as_posix()
                if not _is_excluded_rel_path(rel):
                    rels.append(rel)
        return sorted(rels)

    async def _read_snapshot_file(self, project_id: str, rel_path: str) -> str | None:
        try:
            text = await storage_service.get_text(
                settings.build_projects_bucket,
                self._snapshot_key(project_id, rel_path),
            )
            if text is not None:
                return text
        except StorageError as exc:
            logger.debug("RustFS get_text unavailable for %s/%s: %s", project_id, rel_path, exc)

        local_target = self._local_files_dir(project_id) / rel_path
        if local_target.exists() and local_target.is_file() and not local_target.is_symlink():
            return local_target.read_text(encoding="utf-8", errors="replace")
        return None

    async def _to_response(self, row: dict[str, Any]) -> BuildProjectResponse:
        sid = row.get("active_session_id")
        session_active = False
        if sid:
            try:
                sess = await sandbox_service.get_session(sid)
                session_active = sess is not None and not sess.is_expired()
            except Exception:
                session_active = False
        return BuildProjectResponse(
            id=row["id"],
            name=row["name"],
            description=row.get("description", ""),
            template=row.get("template", "nextjs-vibe"),
            db_dialect=row.get("db_dialect", "postgresql"),
            active_session_id=sid if session_active else row.get("active_session_id"),
            session_active=session_active,
            runtime_image=row.get("runtime_image", settings.sandbox_default_image),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    async def list_projects(self) -> list[BuildProjectResponse]:
        rows = await self.storage.alist_projects()
        return [await self._to_response(r) for r in rows]

    async def get_project(self, project_id: str) -> BuildProjectResponse:
        _validate_project_id(project_id)
        row = await self.storage.aget_project(project_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
        return await self._to_response(row)

    async def create_project(self, request: BuildProjectCreateRequest) -> BuildProjectStartResponse:
        slug_base = re.sub(r"[^a-z0-9]+", "-", request.name.lower()).strip("-")[:32] or "project"
        project_id = f"{slug_base}-{uuid.uuid4().hex[:8]}"
        runtime_image = settings.sandbox_default_image

        await self.storage.acreate_project(
            project_id=project_id,
            name=request.name.strip(),
            description=request.description.strip(),
            template=request.template,
            db_dialect=request.db_dialect,
            runtime_image=runtime_image,
            active_session_id=None,
        )

        try:
            return await self.start_or_restore_project(project_id)
        except Exception:
            await self.storage.adelete_project(project_id)
            raise

    async def delete_project(self, project_id: str) -> dict[str, Any]:
        _validate_project_id(project_id)
        row = await self.storage.aget_project(project_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

        sid = row.get("active_session_id")
        if sid:
            try:
                await sandbox_service.terminate_session(sid)
            except Exception as exc:
                logger.warning("Failed terminating session %s on project delete: %s", sid, exc)

        try:
            await storage_service.delete_prefix(settings.build_projects_bucket, f"{project_id}/")
        except StorageError as exc:
            logger.warning("RustFS prefix delete failed for %s: %s", project_id, exc)

        local_proj = self.local_dir / project_id
        if local_proj.exists():
            shutil.rmtree(local_proj, ignore_errors=True)

        await self.storage.adelete_project(project_id)
        return {"deleted": True, "project_id": project_id}

    async def _hydrate_blank_template(self, session_id: str, template: str, name: str) -> None:
        if template == "python-blank":
            await sandbox_service.write_session_file(
                session_id,
                "main.py",
                f'"""{name}"""\n\ndef main() -> None:\n    print("Hello from {name}!")\n\nif __name__ == "__main__":\n    main()\n',
            )
            await sandbox_service.write_session_file(
                session_id,
                "README.md",
                f"# {name}\n\nPython OpenSandbox workspace.\n",
            )
        elif template == "node-blank":
            pkg = (
                '{\n'
                f'  "name": "{re.sub(r"[^a-z0-9-]", "-", name.lower()).strip("-") or "node-app"}",\n'
                '  "version": "0.1.0",\n'
                '  "private": true,\n'
                '  "type": "module",\n'
                '  "scripts": {\n'
                '    "start": "node index.js"\n'
                '  }\n'
                '}\n'
            )
            await sandbox_service.write_session_file(session_id, "package.json", pkg)
            await sandbox_service.write_session_file(
                session_id,
                "index.js",
                f'console.log("Hello from {name}!");\n',
            )

    async def _ensure_env_dialect(self, session_id: str, db_dialect: str) -> None:
        try:
            existing = await sandbox_service.read_session_file(session_id, ".env")
        except Exception:
            existing = ""
        lines = [line for line in existing.splitlines() if not line.startswith("DB_DIALECT=")]
        lines.append(f"DB_DIALECT={db_dialect}")
        await sandbox_service.write_session_file(session_id, ".env", "\n".join(lines).strip() + "\n")

    async def start_or_restore_project(self, project_id: str) -> BuildProjectStartResponse:
        _validate_project_id(project_id)
        row = await self.storage.aget_project(project_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

        existing_sid = row.get("active_session_id")
        if existing_sid:
            try:
                active = await sandbox_service.get_session(existing_sid)
                if active is not None and not active.is_expired():
                    project_resp = await self._to_response(row)
                    return BuildProjectStartResponse(
                        project=project_resp,
                        session_id=existing_sid,
                        restored_files_count=0,
                        hydrated_from="active_session",
                    )
            except Exception:
                pass

        try:
            session = await sandbox_service.create_session(
                SandboxSessionCreateRequest(
                    runtime_image=row.get("runtime_image") or settings.sandbox_default_image,
                    timeout_s=settings.sandbox_session_inactivity_ttl_s,
                    allow_network=settings.sandbox_default_allow_network,
                    memory_limit_mb=settings.sandbox_default_memory_mb,
                    purpose="build",
                )
            )
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"OpenSandbox unavailable: {exc}",
            ) from exc

        new_sid = session.session_id
        snapshot_files = await self._list_snapshot_files(project_id)
        restored_count = 0

        if snapshot_files:
            for rel_path in snapshot_files:
                try:
                    norm_path = validate_workspace_path(rel_path)
                except ValueError:
                    continue
                content = await self._read_snapshot_file(project_id, norm_path)
                if content is None:
                    continue
                await sandbox_service.write_session_file(new_sid, norm_path, content)
                restored_count += 1
            if row.get("template", "nextjs-vibe") == "nextjs-vibe":
                await sandbox_service.execute_in_session(
                    new_sid,
                    SandboxExecutionRequest(
                        code="if [ ! -e /workspace/node_modules ] && [ -d /opt/vibe-starter/node_modules ]; then ln -sfn /opt/vibe-starter/node_modules /workspace/node_modules; fi",
                        language="bash",
                        timeout_s=5,
                    ),
                )
            hydrated_from = "snapshot"
        else:
            template = row.get("template", "nextjs-vibe")
            if template == "nextjs-vibe":
                await ensure_vibe_starter_workspace(new_sid)
            else:
                await self._hydrate_blank_template(new_sid, template, row["name"])
            await self._ensure_env_dialect(new_sid, row.get("db_dialect", "postgresql"))
            await self.sync_workspace_to_storage(project_id, new_sid)
            hydrated_from = "template"

        await self.storage.aupdate_session(project_id, new_sid)
        updated_row = await self.storage.aget_project(project_id)
        assert updated_row is not None
        return BuildProjectStartResponse(
            project=await self._to_response(updated_row),
            session_id=new_sid,
            restored_files_count=restored_count,
            hydrated_from=hydrated_from,
        )

    async def ensure_project_session(self, project_id: str) -> str:
        started = await self.start_or_restore_project(project_id)
        return started.session_id

    async def sync_file_to_storage(self, project_id: str, rel_path: str, content: str) -> bool:
        _validate_project_id(project_id)
        norm_path = validate_workspace_path(rel_path)
        synced = await self._write_snapshot_file(project_id, norm_path, content)
        await self.storage.atouch_project(project_id)
        return synced

    async def sync_workspace_to_storage(self, project_id: str, session_id: str) -> int:
        _validate_project_id(project_id)
        files = await self._list_session_files(session_id)
        synced_count = 0
        for rel_path in files:
            try:
                norm_path = validate_workspace_path(rel_path)
                content = await sandbox_service.read_session_file(session_id, norm_path)
                if len(content.encode("utf-8", errors="ignore")) <= _MAX_FILE_BYTES:
                    await self._write_snapshot_file(project_id, norm_path, content)
                    synced_count += 1
            except Exception as exc:
                logger.debug("Skipping workspace sync for %s: %s", rel_path, exc)
        await self.storage.atouch_project(project_id)
        return synced_count

    async def _list_session_files(self, session_id: str) -> list[str]:
        cmd = (
            "cd /workspace && find . "
            "\\( -name node_modules -o -name .next -o -name .venv -o -name __pycache__ "
            "-o -name .cache -o -name dist -o -name build -o -path './.git/objects' \\) -prune "
            "-o -type f -not -type l -print"
        )
        result = await sandbox_service.execute_in_session(
            session_id,
            SandboxExecutionRequest(code=cmd, language="bash", timeout_s=15),
        )
        paths: list[str] = []
        for line in (result.stdout or "").splitlines():
            clean = line.strip()
            if clean.startswith("./"):
                clean = clean[2:]
            if clean and not _is_excluded_rel_path(clean):
                paths.append(clean)
        return sorted(paths)

    async def list_files(self, project_id: str) -> BuildFileTreeResponse:
        _validate_project_id(project_id)
        row = await self.storage.aget_project(project_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

        sid = row.get("active_session_id")
        files: list[str] = []
        if sid:
            sess = await sandbox_service.get_session(sid)
            if sess is not None and not sess.is_expired():
                files = await self._list_session_files(sid)
        if not files:
            files = await self._list_snapshot_files(project_id)

        return BuildFileTreeResponse(
            project_id=project_id,
            root="/workspace",
            files=files,
            tree=_build_file_tree(files),
        )

    async def read_file(self, project_id: str, path: str) -> BuildFileContentResponse:
        _validate_project_id(project_id)
        try:
            norm_path = validate_workspace_path(path)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

        session_id = await self.ensure_project_session(project_id)
        try:
            content = await sandbox_service.read_session_file(session_id, norm_path)
        except Exception as exc:
            snapshot_content = await self._read_snapshot_file(project_id, norm_path)
            if snapshot_content is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"File not found: {norm_path}",
                ) from exc
            content = snapshot_content

        raw_bytes = len(content.encode("utf-8", errors="ignore"))
        if raw_bytes > _MAX_FILE_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="File exceeds 5 MiB IDE limit",
            )
        return BuildFileContentResponse(
            project_id=project_id,
            path=norm_path,
            content=content,
            size=raw_bytes,
        )

    async def write_file(
        self, project_id: str, path: str, content: str, is_base64: bool = False
    ) -> BuildFileWriteResponse:
        _validate_project_id(project_id)
        try:
            norm_path = validate_workspace_path(path)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

        if norm_path == ".buddhi/harness" or norm_path.startswith(".buddhi/harness/"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="'.buddhi/harness/' is protected and cannot be modified",
            )

        decoded_text = (
            base64.b64decode(content).decode("utf-8", errors="replace") if is_base64 else content
        )
        if len(decoded_text.encode("utf-8", errors="ignore")) > _MAX_FILE_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="File exceeds 5 MiB IDE limit",
            )

        session_id = await self.ensure_project_session(project_id)
        await sandbox_service.write_session_file(session_id, norm_path, content, is_base64=is_base64)
        synced = await self.sync_file_to_storage(project_id, norm_path, decoded_text)
        return BuildFileWriteResponse(
            project_id=project_id,
            path=norm_path,
            saved=True,
            synced_to_storage=synced,
        )

    async def execute_command(
        self, project_id: str, request: SandboxExecutionRequest
    ) -> SandboxExecutionResult:
        _validate_project_id(project_id)
        session_id = await self.ensure_project_session(project_id)
        result = await sandbox_service.execute_in_session(session_id, request)
        return SandboxExecutionResult(
            status=result.status,
            stdout=redact_text(result.stdout or ""),
            stderr=redact_text(result.stderr or ""),
            exit_code=result.exit_code,
            execution_time_ms=result.execution_time_ms,
        )

    async def get_history(self, project_id: str) -> BuildHistoryPayload:
        _validate_project_id(project_id)
        row = await self.storage.aget_project(project_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
        data = await self.storage.aget_history(project_id)
        return BuildHistoryPayload(**data)

    async def save_history(self, project_id: str, payload: BuildHistoryPayload) -> BuildHistoryPayload:
        _validate_project_id(project_id)
        row = await self.storage.aget_project(project_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
        saved = await self.storage.asave_history(
            project_id, payload.messages, payload.trajectory_events
        )
        return BuildHistoryPayload(**saved)

    async def get_preview_status(self, project_id: str, port: int = 3000) -> BuildPreviewStatusResponse:
        _validate_project_id(project_id)
        row = await self.storage.aget_project(project_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
        sid = row.get("active_session_id")
        if not sid:
            return BuildPreviewStatusResponse(running=False, port=port, url=None)
        sess = await sandbox_service.get_session(sid)
        if not sess or sess.is_expired():
            return BuildPreviewStatusResponse(running=False, port=port, url=None)
        try:
            probe = await sandbox_service.execute_in_session(
                sid,
                SandboxExecutionRequest(
                    code=f"curl -s -o /dev/null -w '%{{http_code}}' http://127.0.0.1:{int(port)}/ || true",
                    language="bash",
                    timeout_s=5,
                ),
            )
            code = (probe.stdout or "").strip()
            running = code.isdigit() and int(code) > 0
            return BuildPreviewStatusResponse(
                running=running,
                port=port,
                url=f"/api/build/projects/{project_id}/preview/" if running else None,
            )
        except Exception:
            return BuildPreviewStatusResponse(running=False, port=port, url=None)

    async def start_preview(self, project_id: str, port: int = 3000) -> BuildPreviewStatusResponse:
        _validate_project_id(project_id)
        row = await self.storage.aget_project(project_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

        current = await self.get_preview_status(project_id, port=port)
        if current.running:
            return current

        sid = await self.ensure_project_session(project_id)
        p = int(port)
        launch_cmd = (
            "cd /workspace && "
            "if [ ! -f package.json ]; then echo 'NO_PACKAGE_JSON'; exit 1; fi; "
            "if [ ! -e node_modules ] && [ -d /opt/vibe-starter/node_modules ]; then "
            "  ln -sfn /opt/vibe-starter/node_modules /workspace/node_modules; "
            "fi; "
            f"PORT={p} HOSTNAME=0.0.0.0; export PORT HOSTNAME; "
            "if node -e \"const p=require('./package.json'); process.exit(p.scripts && p.scripts.dev ? 0 : 1)\" 2>/dev/null; then "
            f"  if grep -q '\"next\"' package.json 2>/dev/null; then "
            f"    nohup npm run dev -- --webpack --port {p} --hostname 0.0.0.0 >/tmp/dev-preview.log 2>&1 </dev/null & "
            "  else "
            "    nohup npm run dev >/tmp/dev-preview.log 2>&1 </dev/null & "
            "  fi; "
            "elif node -e \"const p=require('./package.json'); process.exit(p.scripts && p.scripts.start ? 0 : 1)\" 2>/dev/null; then "
            "  nohup npm start >/tmp/dev-preview.log 2>&1 </dev/null & "
            "else "
            "  echo 'NO_START_SCRIPT'; exit 1; "
            "fi"
        )
        launch = await sandbox_service.execute_in_session(
            sid,
            SandboxExecutionRequest(code=launch_cmd, language="bash", timeout_s=15),
        )
        if launch.exit_code != 0:
            reason = (launch.stdout or launch.stderr or "Failed to launch preview server").strip()
            return BuildPreviewStatusResponse(running=False, port=port, url=None, detail=reason)

        for _ in range(20):
            await asyncio.sleep(1.0)
            check = await self.get_preview_status(project_id, port=port)
            if check.running:
                return check

        tail = await sandbox_service.execute_in_session(
            sid,
            SandboxExecutionRequest(
                code="tail -n 20 /tmp/dev-preview.log 2>/dev/null || true",
                language="bash",
                timeout_s=5,
            ),
        )
        log_tail = (tail.stdout or "").strip()
        detail = f"Preview server on port {port} did not become ready in time."
        if log_tail:
            detail = f"{detail} Log: {log_tail[-400:]}"
        return BuildPreviewStatusResponse(running=False, port=port, url=None, detail=detail)

    async def proxy_preview(
        self, project_id: str, rel_path: str, request: Request, port: int = 3000
    ) -> Response:
        _validate_project_id(project_id)
        row = await self.storage.aget_project(project_id)
        if not row or not row.get("active_session_id"):
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Sandbox not active")
        sess = await sandbox_service.get_session(row["active_session_id"])
        if not sess or sess.is_expired():
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Sandbox session expired")

        try:
            endpoint = await sess.sandbox.get_endpoint(port)
            base_url = getattr(endpoint, "endpoint", None) or str(endpoint)
            if not base_url.startswith("http"):
                base_url = f"http://{base_url}"
            upstream_rel_path = rel_path.lstrip("/")
            if upstream_rel_path.startswith("_pnext/"):
                upstream_rel_path = "_next/" + upstream_rel_path[len("_pnext/"):]
            elif upstream_rel_path == "_pnext":
                upstream_rel_path = "_next"
            elif upstream_rel_path.startswith("_pnextjs"):
                upstream_rel_path = "__nextjs" + upstream_rel_path[len("_pnextjs"):]
            target_url = f"{base_url.rstrip('/')}/{upstream_rel_path}"
            if request.url.query:
                target_url = f"{target_url}?{request.url.query}"

            body = await request.body()
            stripped_headers = {
                "host",
                "cookie",
                "authorization",
                "content-length",
                "origin",
                "referer",
                "x-preview-prefix",
            }
            forward_headers = {
                k: v
                for k, v in request.headers.items()
                if k.lower() not in stripped_headers and not k.lower().startswith("sec-fetch-")
            }
            conn_cfg = getattr(sess.sandbox, "connection_config", None)
            if conn_cfg is not None and hasattr(endpoint, "build_request_headers"):
                for hk, hv in endpoint.build_request_headers(conn_cfg).items():
                    if hk.lower() != "user-agent":
                        forward_headers[hk] = hv
            else:
                endpoint_headers = getattr(endpoint, "headers", None)
                if isinstance(endpoint_headers, dict):
                    forward_headers.update(endpoint_headers)

            async with httpx.AsyncClient(timeout=15.0) as client:
                upstream = await client.request(
                    request.method,
                    target_url,
                    headers=forward_headers,
                    content=body if body else None,
                )
            if upstream.status_code >= 500:
                logger.warning(
                    "Preview upstream returned %d for %s: %s",
                    upstream.status_code,
                    target_url,
                    upstream.text[:500],
                )
            resp_headers = {
                k: v
                for k, v in upstream.headers.items()
                if k.lower() not in {"content-encoding", "transfer-encoding", "content-length"}
            }
            preview_prefix = (
                request.headers.get("x-preview-prefix")
                or f"/v1/build/projects/{project_id}/preview"
            ).rstrip("/")
            content = _rewrite_preview_body(
                upstream.content,
                resp_headers.get("content-type", ""),
                preview_prefix,
            )
            resp_headers["X-Content-Type-Options"] = "nosniff"
            resp_headers["Content-Security-Policy"] = "frame-ancestors 'self'"
            resp_headers["Access-Control-Allow-Origin"] = "*"
            return Response(
                content=content,
                status_code=upstream.status_code,
                headers=resp_headers,
            )
        except Exception as exc:
            logger.warning("Preview proxy failed for %s (port %d): %s", project_id, port, exc)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Preview server on port {port} is unreachable: {exc}",
            ) from exc


_HTML_ATTR_RE = re.compile(r'((?:href|src|action)=["\'])/(?!/)')
_CSS_URL_RE = re.compile(r'(url\(\s*["\']?)/(?!/)')
_NEXT_PATH_RE = re.compile(r'(?<![A-Za-z0-9_./-])/_next/')
_NEXTJS_INTERNAL_RE = re.compile(r'(?<![A-Za-z0-9_./-])/__nextjs')


def _rewrite_preview_body(content: bytes, content_type: str, prefix: str) -> bytes:
    """Rewrite root-relative asset URLs so proxied preview assets resolve under `prefix`.

    Next.js dev server's cross-site guard blocks any URL containing `/_next` or `/__nextjs`
    when requested from a sandboxed iframe's opaque origin, so those segments are aliased
    to `/_pnext` and `/_pnextjs` through the host proxy and restored upstream.
    """
    if not prefix or not content:
        return content
    ct = content_type.lower()
    if "text/html" in ct:
        text = content.decode("utf-8", errors="replace")
        text = _HTML_ATTR_RE.sub(rf"\1{prefix}/", text)
        text = _NEXT_PATH_RE.sub(f"{prefix}/_pnext/", text)
        text = text.replace(f"{prefix}/_next/", f"{prefix}/_pnext/")
        text = _NEXTJS_INTERNAL_RE.sub(f"{prefix}/_pnextjs", text)
        text = text.replace(f"{prefix}/__nextjs", f"{prefix}/_pnextjs")
        return text.encode("utf-8")
    if "text/css" in ct:
        text = content.decode("utf-8", errors="replace")
        text = _CSS_URL_RE.sub(rf"\1{prefix}/", text)
        text = text.replace(f"{prefix}/_next/", f"{prefix}/_pnext/")
        return text.encode("utf-8")
    if "javascript" in ct or "ecmascript" in ct:
        text = content.decode("utf-8", errors="replace")
        text = _NEXT_PATH_RE.sub(f"{prefix}/_pnext/", text)
        text = _NEXTJS_INTERNAL_RE.sub(f"{prefix}/_pnextjs", text)
        return text.encode("utf-8")
    return content


build_project_service = BuildProjectService()
