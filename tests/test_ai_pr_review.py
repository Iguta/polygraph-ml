from __future__ import annotations

import importlib.util
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    "ai_pr_review", Path(__file__).parents[1] / "scripts" / "ai_pr_review.py"
)
assert SPEC and SPEC.loader
reviewer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(reviewer)


def test_review_prompt_treats_patch_as_untrusted_and_requests_json() -> None:
    messages = reviewer.review_prompt("--- src/example.py\nprint('hello')", truncated=False)
    assert messages[0]["role"] == "system"
    assert "untrusted data" in messages[0]["content"][0]["text"]
    assert "JSON" in messages[0]["content"][0]["text"]


def test_blocking_policy_catches_high_findings_even_with_approve_verdict() -> None:
    review = {
        "verdict": "approve",
        "summary": "Looks good.",
        "findings": [
            {
                "path": "src/example.py",
                "line": 10,
                "severity": "high",
                "title": "Authorization bypass",
                "body": "A caller can bypass the ownership check.",
                "blocking": False,
            }
        ],
    }
    assert reviewer.is_blocking(review) is True


def test_comment_is_markered_and_avoids_blocking_for_low_advice() -> None:
    review = {
        "verdict": "approve",
        "summary": "No merge blockers found.",
        "findings": [
            {
                "path": "docs/README.md",
                "line": 1,
                "severity": "low",
                "title": "Clarify wording",
                "body": "This is an optional readability improvement.",
                "blocking": False,
            }
        ],
    }
    assert reviewer.is_blocking(review) is False
    comment = reviewer.render_comment(review, truncated=False)
    assert reviewer.MARKER in comment
    assert "advisory" in comment
