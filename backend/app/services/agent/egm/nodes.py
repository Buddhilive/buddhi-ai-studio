from __future__ import annotations

import logging
import re
from typing import Any

from app.core import settings_store
from app.core.config import settings
from app.schemas.agent import Finding, ReviewReport, SpecContract
from app.services.agent.egm.runner import GoldfishReviewInput, GoldfishRunner, GoldfishVerifyInput, ReviewerOutput
from app.services.agent.egm.storage import rehydrate_egm_sandbox_if_needed, sync_egm_artifact_to_sandbox
from app.services.agent.egm.synthesizer import Synthesizer
from app.services.agent.events import AgentEventEmitter
from app.services.agent.nodes import generate_with_streaming
from app.services.agent.prompts import build_draft_messages, build_resolve_messages
from app.services.agent.state import AgentState
from app.services.sandbox_service import sandbox_service

logger = logging.getLogger(__name__)


def extract_target_scope_files(spec_text: str) -> list[str]:
    """Extract list of allowed file paths from 'Target Scope & File Boundary' section."""
    scope_files: list[str] = []
    match = re.search(r"##\s*Target Scope & File Boundary(.*?)(?=\n##|\Z)", spec_text, re.DOTALL | re.IGNORECASE)
    if match:
        section = match.group(1)
        for line in section.splitlines():
            line = line.strip()
            # Look for bullet points with paths
            m_file = re.match(r"^[-*]\s*`?([a-zA-Z0-9_\-\./\\]+\.[a-zA-Z0-9]+)`?", line)
            if m_file:
                path = m_file.group(1).replace("\\", "/").strip()
                if not path.startswith("/"):
                    scope_files.append(path)
    return scope_files


async def draft_node(state: AgentState, emitter: AgentEventEmitter | None = None) -> dict[str, Any]:
    if emitter:
        await emitter.emit_node_start("draft")
        await emitter.emit_egm_phase("draft", round_num=state.get("egm_round", 1), max_rounds=state.get("egm_max_rounds", 3))

    user_msgs = state.get("messages", [])
    brief = state.get("concepts_brief")
    draft_messages = build_draft_messages(user_msgs, concepts_brief=brief)

    # Elephant drafts the design spec
    content, reasoning = await generate_with_streaming(
        messages=draft_messages,
        model_id=settings.agent_default_model,
        node_name="draft",
        emitter=emitter,
    )

    run_id = state.get("run_id", "default_run")
    spec_path = f".buddhi/specs/{run_id}/spec.md"

    # Extract target scope
    target_files = extract_target_scope_files(content)
    if not target_files:
        target_files = ["src/app/page.tsx"]  # default fallback if not explicitly declared

    spec_contract: dict[str, Any] = {
        "path": spec_path,
        "content": content,
        "feature_range": (1, len(content.splitlines()) // 2),
        "detailed_range": (len(content.splitlines()) // 2 + 1, len(content.splitlines())),
        "target_scope_files": target_files,
        "approved": False,
    }

    # Dual storage persistence
    await sync_egm_artifact_to_sandbox(state, "spec.md", content)

    if emitter:
        await emitter.emit_egm_artifact("spec", spec_path, round_num=state.get("egm_round", 1))
        await emitter.emit_node_end("draft", {"spec_path": spec_path, "target_files": target_files})

    return {
        "egm_phase": "draft",
        "spec_contract": spec_contract,
        "allowed_write_paths": [f".buddhi/specs/{run_id}/"],
    }


async def goldfish_review_node(state: AgentState, emitter: AgentEventEmitter | None = None) -> dict[str, Any]:
    if emitter:
        await emitter.emit_node_start("goldfish_review")
        await emitter.emit_egm_phase("review", round_num=state.get("egm_round", 1), max_rounds=state.get("egm_max_rounds", 3))

    spec_contract = state.get("spec_contract") or {}
    spec_content = spec_contract.get("content") or ""
    spec_path = spec_contract.get("path") or "spec.md"

    # Configure runner
    egm_settings = settings_store.get_egm_settings()
    concurrency = int(egm_settings.get("goldfish_concurrency", 1))
    runner = GoldfishRunner(concurrency=concurrency)

    # 5-stage pipeline: zoom_out -> comprehension -> design_critic -> zoom_out (pass 2) -> implementation_readiness
    pipeline_stages = [
        ("zoom_out", "zoom-out-standard", "Stage 1: Zoom Out Simplicity"),
        ("comprehension", "feature-spec-standard", "Stage 2: Comprehension & Background"),
        ("design_critic", "feature-spec-standard", "Stage 3: Design & Scale Critic"),
        ("zoom_out", "zoom-out-standard", "Stage 4: Intermediate Zoom Out"),
        ("implementation_readiness", "implementation-readiness-standard", "Stage 5: Implementation Readiness"),
    ]

    outputs: list[ReviewerOutput] = []

    for persona_id, standard_name, stage_label in pipeline_stages:
        if emitter:
            await emitter.emit_egm_reviewer_status(stage_label, persona_id, "running", round_num=state.get("egm_round", 1))

        inp = GoldfishReviewInput(
            persona_id=persona_id,
            standard_name=standard_name,
            target_document=spec_content,
        )

        out = await runner.run_single_reviewer(inp, stage=stage_label)
        outputs.append(out)

        if emitter:
            findings_cnt = len(Synthesizer.parse_raw_findings(out.raw_content, persona_id)) if out.status == "completed" else None
            await emitter.emit_egm_reviewer_status(
                stage_label, persona_id, out.status, round_num=state.get("egm_round", 1), findings_count=findings_cnt
            )

    # Synthesize findings
    round_num = state.get("egm_round", 1)
    report_model, report_md = Synthesizer.compile_review_report(round_num, outputs, target_path=spec_path)

    # Dual storage persistence
    report_filename = f"round_{round_num}_review_report.md"
    report_path = await sync_egm_artifact_to_sandbox(state, report_filename, report_md)

    if emitter:
        await emitter.emit_egm_artifact("review_report", report_path, round_num=round_num)
        await emitter.emit_node_end("goldfish_review", {"findings_count": len(report_model.findings)})

    return {
        "egm_phase": "goldfish_review",
        "review_report": report_model.model_dump(),
    }


async def resolve_node(state: AgentState, emitter: AgentEventEmitter | None = None) -> dict[str, Any]:
    if emitter:
        await emitter.emit_node_start("resolve")
        await emitter.emit_egm_phase("resolve", round_num=state.get("egm_round", 1), max_rounds=state.get("egm_max_rounds", 3))

    decisions = state.get("resolution_decisions") or []
    spec_contract = state.get("spec_contract") or {}
    current_spec = spec_contract.get("content") or ""
    review_report = state.get("review_report") or {}
    round_num = state.get("egm_round", 1)

    # If user approved plan
    if state.get("egm_approved"):
        if emitter:
            await emitter.emit_node_end("resolve", {"approved": True, "target_scope": spec_contract.get("target_scope_files")})
        return {
            "egm_phase": "act",
            "allowed_write_paths": spec_contract.get("target_scope_files", []),
        }

    # If accepted revisions exist, Elephant applies patches to spec
    accept_decisions = [d for d in decisions if d.get("decision") == "accept"]
    if accept_decisions:
        user_msgs = state.get("messages", [])
        resolve_messages = build_resolve_messages(user_msgs, current_spec, str(review_report), accept_decisions)
        revised_content, _ = await generate_with_streaming(
            messages=resolve_messages,
            model_id=settings.agent_default_model,
            node_name="resolve",
            emitter=emitter,
        )
        spec_contract["content"] = revised_content
        spec_contract["target_scope_files"] = extract_target_scope_files(revised_content)
        await sync_egm_artifact_to_sandbox(state, "spec.md", revised_content)

    new_round = round_num + 1

    if emitter:
        await emitter.emit_node_end("resolve", {"next_round": new_round})

    return {
        "egm_phase": "resolve",
        "egm_round": new_round,
        "spec_contract": spec_contract,
    }


async def goldfish_verify_node(state: AgentState, emitter: AgentEventEmitter | None = None) -> dict[str, Any]:
    if emitter:
        await emitter.emit_node_start("goldfish_verify")
        await emitter.emit_egm_phase("verify", round_num=state.get("egm_round", 1), max_rounds=state.get("egm_max_rounds", 3))

    sid = state.get("session_id")
    spec_contract = state.get("spec_contract") or {}
    target_scope = tuple(spec_contract.get("target_scope_files") or ())

    # Fail closed if sandbox session is missing
    if not sid:
        logger.warning("Verification failed closed: missing sandbox session_id")
        return {"verdict": "retry", "error": "Verification failed closed: no active sandbox session."}

    # 1. Collect git diff from sandbox
    from app.schemas.sandbox import SandboxExecutionRequest
    diff_req = SandboxExecutionRequest(code="git diff HEAD", language="bash", timeout_s=30)
    diff_res = await sandbox_service.execute_in_session(sid, diff_req)
    git_diff = diff_res.stdout or ""

    # 2. Check for out-of-boundary modified files directly
    status_req = SandboxExecutionRequest(code="git status --porcelain", language="bash", timeout_s=15)
    status_res = await sandbox_service.execute_in_session(sid, status_req)
    changed_files = [line.strip().split()[-1] for line in (status_res.stdout or "").splitlines() if line.strip()]

    out_of_boundary_files = [
        f for f in changed_files
        if not (f in target_scope or any(f.startswith(t) for t in target_scope) or f.startswith(".buddhi/specs/"))
    ]

    if out_of_boundary_files:
        logger.warning("Verification fail closed: out of boundary files modified: %s", out_of_boundary_files)
        if emitter:
            await emitter.emit_node_end("goldfish_verify", {"verdict": "retry", "violation": out_of_boundary_files})
        return {
            "verdict": "retry",
            "error": f"Verification failed: files modified outside Target Scope & File Boundary: {out_of_boundary_files}",
        }

    # 3. Collect test output
    test_req = SandboxExecutionRequest(code="pytest -q || npm test || echo 'No tests detected'", language="bash", timeout_s=60)
    test_res = await sandbox_service.execute_in_session(sid, test_req)
    test_output = f"{test_res.stdout}\n{test_res.stderr}".strip()

    # 4. Run stateless Goldfish verifier
    runner = GoldfishRunner(concurrency=1)
    inp = GoldfishVerifyInput(
        spec_contract=spec_contract.get("content", ""),
        git_diff=git_diff,
        test_output=test_output,
        target_scope_files=target_scope,
    )
    verify_msgs = runner.build_verify_messages(inp)

    output_parts: list[str] = []
    async for delta in inference_engine_manager.generate_stream(
        messages=verify_msgs,
        max_tokens=settings.chat_max_tokens_default,
        enable_thinking=False,
        model_id=settings.agent_default_model,
        tools=None,
    ):
        if delta.content:
            output_parts.append(delta.content)

    verifier_text = "".join(output_parts)

    # Strict verdict parse (fails closed to retry)
    m = re.search(r"VERDICT:\s*(pass|retry|continue)", verifier_text, re.IGNORECASE)
    verdict = m.group(1).lower() if m else "retry"

    if emitter:
        await emitter.emit_node_end("goldfish_verify", {"verdict": verdict})

    return {
        "verdict": verdict,
        "final_output": verifier_text if verdict == "pass" else None,
    }


async def brainstorm_node(state: AgentState, emitter: AgentEventEmitter | None = None) -> dict[str, Any]:
    if emitter:
        await emitter.emit_node_start("brainstorm")
        await emitter.emit_egm_phase("brainstorm")

    # Upstream 7-lens shootdown personas & standards
    lenses = [
        ("design_critic", "feature-spec-standard"),
        ("codebase_details", "implementation-readiness-standard"),
        ("zoom_out", "zoom-out-standard"),
        ("comprehension", "feature-spec-standard"),
        ("implementation_readiness", "implementation-readiness-standard"),
        ("structural", "feature-spec-standard"),
        ("inventive_catalyst", "heilmeier-standard"),
    ]

    user_msgs = state.get("messages", [])
    concept_text = user_msgs[-1].content if user_msgs else "New feature concept"
    runner = GoldfishRunner(concurrency=1)
    outputs: list[ReviewerOutput] = []

    for lens, std in lenses:
        if emitter:
            await emitter.emit_reviewer_status("brainstorm", lens, "running", round_num=1)

        inp = GoldfishReviewInput(persona_id=lens, standard_name=std, target_document=concept_text)
        out = await runner.run_single_reviewer(inp, stage="brainstorm")
        outputs.append(out)

        if emitter:
            status_str = "completed" if out.status == "completed" else "not run"
            await emitter.emit_reviewer_status("brainstorm", lens, status_str, round_num=1, findings_count=len(out.findings))

    _, brief_md = Synthesizer.compile_review_report(1, outputs, target_path="concepts_brief.md")
    await sync_egm_artifact_to_sandbox(state, "concepts_brief.md", brief_md)

    if emitter:
        await emitter.emit_artifact("concepts_brief.md", brief_md)
        await emitter.emit_node_end("brainstorm", {"lenses_count": len(outputs)})

    return {
        "egm_phase": "brainstorm",
        "concepts_brief": brief_md,
    }


async def drift_report_node(state: AgentState, emitter: AgentEventEmitter | None = None) -> dict[str, Any]:
    if emitter:
        await emitter.emit_node_start("drift_report")
        await emitter.emit_egm_phase("drift_report")

    sid = await rehydrate_egm_sandbox_if_needed(state)
    from app.schemas.sandbox import SandboxExecutionRequest

    # Check git status and diff inside sandbox
    git_cmd = "git status --porcelain && echo '===DIFF===' && git diff --stat HEAD"
    req = SandboxExecutionRequest(code=git_cmd, language="bash", timeout_s=30)
    res = await sandbox_service.execute_in_session(sid, req)

    raw_output = res.stdout or ""
    git_status_part = raw_output
    diff_part = ""
    if "===DIFF===" in raw_output:
        parts = raw_output.split("===DIFF===", 1)
        git_status_part = parts[0].strip()
        diff_part = parts[1].strip()

    # Determine modified files from git status
    modified_files: list[str] = []
    for line in git_status_part.splitlines():
        line = line.strip()
        if not line:
            continue
        # porcelain format: XY filename or XY orig -> renamed
        parts = line.split(maxsplit=1)
        if len(parts) == 2:
            fpath = parts[1].strip().strip('"').replace("\\", "/")
            if "->" in fpath:
                fpath = fpath.split("->")[-1].strip()
            modified_files.append(fpath)

    # Get target scope files from spec_contract or state
    spec_contract = state.get("spec_contract")
    target_files: list[str] = []
    spec_path = "spec.md"
    if isinstance(spec_contract, SpecContract):
        target_files = spec_contract.target_scope_files
        spec_path = spec_contract.path
    elif isinstance(spec_contract, dict):
        target_files = spec_contract.get("target_scope_files", [])
        spec_path = spec_contract.get("path", "spec.md")

    # Detect divergences
    unauthorized_drifts = [f for f in modified_files if f not in target_files]
    unmodified_declared = [f for f in target_files if f not in modified_files]

    # Generate Markdown report
    lines: list[str] = [
        "# EGM Spec-to-Codebase Drift Report",
        "",
        f"- **Reference Spec**: `{spec_path}`",
        f"- **Target Scope Files Declared**: {len(target_files)}",
        f"- **Modified Files Detected**: {len(modified_files)}",
        f"- **Unauthorized Drift Files**: {len(unauthorized_drifts)}",
        "",
        "## Divergence Summary",
        "",
    ]

    if unauthorized_drifts:
        lines.append("### 🔴 Out-of-Boundary Modifications (Blocker Drift)")
        lines.append("Files modified that are NOT authorized in the approved Spec Contract:")
        for uf in unauthorized_drifts:
            lines.append(f"- `[BLOCKER DRIFT]` `{uf}`")
        lines.append("")
    else:
        lines.append("### 🟢 Boundary Conformance")
        lines.append("All modified files match the approved Spec Contract target scope.")
        lines.append("")

    if unmodified_declared:
        lines.append("### 🟡 Incomplete Target Implementation (Pending Drift)")
        lines.append("Files declared in Spec Contract target scope with no detected modifications:")
        for mf in unmodified_declared:
            lines.append(f"- `[PENDING]` `{mf}`")
        lines.append("")

    if diff_part:
        lines.append("## Diff Statistics")
        lines.append("```text")
        lines.append(diff_part)
        lines.append("```")
        lines.append("")

    lines.append("## Remediation Recommendations")
    if unauthorized_drifts:
        lines.append("1. Revert out-of-boundary modifications or update `spec.md` Target Scope through a formal EGM review round.")
    if unmodified_declared:
        lines.append("2. Implement missing changes for declared target files or prune from `spec.md`.")
    if not unauthorized_drifts and not unmodified_declared:
        lines.append("No action needed. Codebase is in complete alignment with the Spec Contract.")

    drift_md = "\n".join(lines)
    await sync_egm_artifact_to_sandbox(state, "drift_report.md", drift_md)

    if emitter:
        await emitter.emit_artifact("drift_report.md", drift_md)
        await emitter.emit_node_end("drift_report", {
            "unauthorized_count": len(unauthorized_drifts),
            "unmodified_count": len(unmodified_declared),
        })

    return {
        "egm_phase": "drift_report",
        "drift_report": drift_md,
        "final_output": drift_md,
    }
