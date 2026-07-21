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


def test_collect_diff_splits_a_complete_large_pr_into_safe_chunks(monkeypatch) -> None:
    files = [
        {"filename": f"src/file_{index}.py", "patch": "+" + "x" * 40}
        for index in range(reviewer.MAX_FILES_PER_CHUNK + 1)
    ]

    def fake_github_api(path: str, *, token: str, method: str = "GET", body=None):
        assert "/pulls/1/files?" in path
        return files

    monkeypatch.setattr(reviewer, "github_api", fake_github_api)

    chunks, truncated = reviewer.collect_diff("owner/repo", 1, "token")

    assert truncated is False
    assert len(chunks) == 2
    assert "src/file_0.py" in chunks[0]
    assert f"src/file_{reviewer.MAX_FILES_PER_CHUNK}.py" in chunks[1]


def test_collect_diff_inventories_non_executable_artifact_without_truncating(
    monkeypatch,
) -> None:
    files = [
        {
            "filename": "src/polygraphml/benchmarks/data/uci_bank/bank_marketing_model.skops",
            "patch": None,
            "status": "added",
            "additions": 0,
            "deletions": 0,
        },
        {"filename": "src/reviewable.py", "patch": "+safe = True"},
    ]
    monkeypatch.setattr(reviewer, "github_api", lambda *args, **kwargs: files)

    chunks, truncated = reviewer.collect_diff("owner/repo", 1, "token")

    assert truncated is False
    assert "Binary/large non-executable content omitted" in chunks[0]
    assert "safe adapter inspects untrusted types" in chunks[0]
    assert "src/reviewable.py" in chunks[0]


def test_collect_diff_reviews_generated_executable_client_in_full(monkeypatch) -> None:
    files = [{"filename": "frontend/src/generated/api.ts", "patch": "+export const safe = true"}]
    monkeypatch.setattr(reviewer, "github_api", lambda *args, **kwargs: files)

    chunks, truncated = reviewer.collect_diff("owner/repo", 1, "token")

    assert truncated is False
    assert "+export const safe = true" in chunks[0]


def test_collect_diff_fails_closed_for_unexpected_binary(monkeypatch) -> None:
    files = [{"filename": "src/unexpected.bin", "patch": None}]
    monkeypatch.setattr(reviewer, "github_api", lambda *args, **kwargs: files)

    chunks, truncated = reviewer.collect_diff("owner/repo", 1, "token")

    assert chunks == []
    assert truncated is True


def test_combine_reviews_preserves_a_block_from_any_chunk() -> None:
    approval = {"verdict": "approve", "summary": "Chunk one is clear.", "findings": []}
    block = {
        "verdict": "changes_requested",
        "summary": "Chunk two has a defect.",
        "findings": [
            {
                "path": "src/worker.py",
                "line": 4,
                "severity": "high",
                "title": "Unsafe retry",
                "body": "This can duplicate a terminal transition.",
                "blocking": True,
            }
        ],
    }

    combined = reviewer.combine_reviews([approval, block])

    assert combined["verdict"] == "changes_requested"
    assert combined["findings"] == block["findings"]
