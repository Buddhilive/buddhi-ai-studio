import sys
from app.services.agent.egm.runner import GoldfishReviewInput, GoldfishRunner, ReviewerOutput
from app.services.agent.egm.synthesizer import Synthesizer


def test_goldfish_runner_zero_context_messages():
    runner = GoldfishRunner(concurrency=1)
    inp = GoldfishReviewInput(
        persona_id="zoom_out",
        standard_name="zoom-out-standard",
        target_document="# Feature Spec\n\nSome spec content here.",
        permitted_context="Existing service definitions.",
    )
    msgs = runner.build_review_messages(inp, inp.target_document, 1, 3)
    assert len(msgs) == 2
    assert msgs[0].role == "system"
    assert msgs[1].role == "user"
    # Verify no leaked chat history or external state
    assert "zoom_out" in msgs[0].content or "Zoom Out" in msgs[0].content or "Evaluation" in msgs[0].content
    assert "TARGET SPECIFICATION DOCUMENT SLICE" in msgs[1].content


def test_goldfish_runner_slicing():
    runner = GoldfishRunner(concurrency=1)
    content = "\n".join([f"Line {i}: test specification details" for i in range(100)])
    # Budget of 20 tokens -> approx 80 chars per slice
    chunks = runner.slice_target_document(content, budget_tokens=20)
    assert len(chunks) > 1
    # Check line continuity
    assert chunks[0][0] == 1
    assert chunks[-1][1] == 100


def test_synthesizer_deduplication_and_sorting():
    raw_output = """
### [🔴 Blocker] Missing error handling in auth
* Scope: L40-L55
* Recommendation: Add try-catch and specific exception class.

* 🟡 Major: Unbounded in-memory queue
* Scope: L100-L120
* Recommendation: Bound queue size to 1000 items.

* [🟢 Nit] Inconsistent naming
* Scope: L12
* Recommendation: Use snake_case.

* [🔴 Blocker] Missing error handling in auth
* Scope: L40-L55
* Recommendation: Add try-catch.
"""
    outputs = [
        ReviewerOutput(
            persona="zoom_out",
            stage="stage_1",
            status="completed",
            raw_content=raw_output,
            findings=[],
        ),
        ReviewerOutput(
            persona="codebase_details",
            stage="stage_2",
            status="not run",
            raw_content="",
            findings=[],
        ),
    ]

    report, md = Synthesizer.compile_review_report(1, outputs, ".buddhi/specs/009/spec.md")
    assert report.round == 1
    assert report.reviewer_statuses["zoom_out"] == "completed"
    assert report.reviewer_statuses["codebase_details"] == "not run"

    # Verify deduplication: 4 items reduced to 3 unique items
    assert len(report.findings) == 3

    # Verify sorting: blocker first, then major, then nit
    assert report.findings[0].severity == "blocker"
    assert report.findings[1].severity == "major"
    assert report.findings[2].severity == "nit"

    # Verify markdown artifact formatting
    assert "# Goldfish Review Report (Round 1)" in md
    assert "Not Run (Retried)" in md
    assert "🔴 Blocker" in md
