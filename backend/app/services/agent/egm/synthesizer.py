from __future__ import annotations

import re
import uuid
from typing import Any
from app.schemas.agent import Finding, ReviewReport


class Synthesizer:
    """Deterministic aggregator and report compiler for EGM findings."""

    @staticmethod
    def parse_raw_findings(raw_text: str, reviewer_lens: str) -> list[Finding]:
        """Extract structured findings from natural language reviewer output."""
        findings: list[Finding] = []
        if not raw_text:
            return findings

        # Matches sections or bullet points with severity badges: 🔴 Blocker, 🟡 Major, 🟢 Nit
        pattern = re.compile(
            r"(?:###|\*|-)\s*(?:\[?(?:🔴|Blocker|BLOCKER)\]?|\[?(?:🟡|Major|MAJOR)\]?|\[?(?:🟢|Nit|NIT)\]?)\s*(.*?)(?=\n(?:###|\*|-)|\Z)",
            re.DOTALL | re.IGNORECASE,
        )

        matches = pattern.findall(raw_text)
        for block in matches:
            block = block.strip()
            if not block:
                continue

            sev: Any = "nit"
            lower = block.lower()
            if "blocker" in lower or "🔴" in block:
                sev = "blocker"
            elif "major" in lower or "🟡" in block:
                sev = "major"

            # Extract scope / line numbers if available
            scope_match = re.search(r"(?:scope|line[s]?|affected)[:\s]+([^\n]+)", block, re.IGNORECASE)
            scope = scope_match.group(1).strip() if scope_match else "General"

            # Extract rationale / recommendation
            rec_match = re.search(r"(?:recommendation|rationale|fix)[:\s]+([^\n]+)", block, re.IGNORECASE)
            recommendation = rec_match.group(1).strip() if rec_match else "Review against standard rubric."

            # Description is the first paragraph or block header
            lines = [l.strip() for l in block.splitlines() if l.strip()]
            desc = lines[0] if lines else block[:120]

            findings.append(
                Finding(
                    id=f"F-{uuid.uuid4().hex[:6].upper()}",
                    lens=reviewer_lens,
                    severity=sev,
                    scope=scope[:60],
                    description=desc,
                    recommendation=recommendation,
                )
            )

        return findings

    @staticmethod
    def deduplicate_findings(findings: list[Finding]) -> list[Finding]:
        """Deduplicate findings with similar lens and scope."""
        seen: set[str] = set()
        deduped: list[Finding] = []

        for f in findings:
            # Normalized key: lens + simplified scope + severity
            clean_scope = re.sub(r"[^a-zA-Z0-9]", "", f.scope.lower())[:20]
            key = f"{f.lens.lower()}:{clean_scope}:{f.severity}"
            if key not in seen:
                seen.add(key)
                deduped.append(f)

        return deduped

    @classmethod
    def compile_review_report(
        cls,
        round_num: int,
        reviewer_outputs: list[Any],
        target_path: str = "",
    ) -> tuple[ReviewReport, str]:
        """Aggregate findings, sort by severity, and render deliverable markdown artifact."""
        all_findings: list[Finding] = []
        statuses: dict[str, Any] = {}

        for out in reviewer_outputs:
            statuses[out.persona] = out.status
            if out.status == "completed" and out.raw_content:
                parsed = cls.parse_raw_findings(out.raw_content, out.persona)
                all_findings.extend(parsed)

        deduped = cls.deduplicate_findings(all_findings)

        # Sort: blockers -> majors -> nits
        severity_order = {"blocker": 0, "major": 1, "nit": 2}
        sorted_findings = sorted(deduped, key=lambda f: severity_order.get(f.severity, 3))

        report_model = ReviewReport(
            round=round_num,
            artifact_path=target_path,
            reviewer_statuses=statuses,
            findings=sorted_findings,
        )

        # Format Markdown Report
        md_lines = [
            f"# Goldfish Review Report (Round {round_num})",
            "",
            f"**Target Specification**: `{target_path}`",
            "",
            "## Reviewer Status",
            "",
            "| Reviewer Lens | Status |",
            "| :--- | :--- |",
        ]
        for lens, st in statuses.items():
            status_display = "Completed" if st == "completed" else "Not Run (Retried)"
            md_lines.append(f"| `{lens}` | {status_display} |")

        md_lines.extend([
            "",
            f"## Prioritized Findings ({len(sorted_findings)} Total)",
            "",
        ])

        if not sorted_findings:
            md_lines.append("*No blocking issues or major discrepancies found across evaluated lenses.*")
        else:
            for f in sorted_findings:
                sev_icon = "🔴 Blocker" if f.severity == "blocker" else ("🟡 Major" if f.severity == "major" else "🟢 Nit")
                md_lines.extend([
                    f"### [{f.id}] {f.description} - Severity: {sev_icon}",
                    f"- **Lens**: `{f.lens}`",
                    f"- **Scope**: `{f.scope}`",
                    f"- **Recommendation**: {f.recommendation}",
                    "",
                ])

        return report_model, "\n".join(md_lines)
