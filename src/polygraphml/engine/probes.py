from __future__ import annotations

import hashlib
from collections.abc import Sequence
from typing import Any

import pandas as pd
from sklearn.base import clone
from sklearn.metrics import roc_auc_score

from polygraphml.domain.ids import new_id
from polygraphml.domain.models import Evidence


def feature_availability_evidence(
    hypothesis_id: str,
    feature: str,
    answer: str,
    source_refs: list[str],
) -> Evidence:
    normalized = answer.strip().lower()
    unavailable = any(token in normalized for token in ("after", "only after", "not available"))
    observation = (
        f"The user confirmed {feature} is available only after the decision point."
        if unavailable
        else f"The supplied answer did not establish that {feature} is unavailable at decision time."
    )
    return Evidence(
        evidence_id=new_id("evd"),
        hypothesis_id=hypothesis_id,
        probe="feature_availability",
        tool_version="feature_availability@1",
        observation=observation,
        metrics={"unavailable_at_decision": unavailable},
        source_refs=source_refs,
        limitations=[] if unavailable else ["Feature availability remains scenario-dependent."],
    )


def group_overlap_evidence(
    groups: pd.Series,
    train_mask: pd.Series,
    test_mask: pd.Series,
) -> Evidence:
    train_groups = set(groups[train_mask].dropna().astype(str))
    test_groups = set(groups[test_mask].dropna().astype(str))
    overlap = train_groups & test_groups
    return Evidence(
        evidence_id=new_id("evd"),
        probe="group_overlap",
        tool_version="group_overlap@1",
        observation=f"Found {len(overlap)} entity identifiers in both train and test.",
        metrics={"overlap_count": len(overlap), "has_overlap": bool(overlap)},
        source_refs=[],
    )


def duplicate_overlap_evidence(frame: pd.DataFrame, split_column: str) -> Evidence:
    feature_columns = [column for column in frame.columns if column != split_column]
    train_hashes = {
        hashlib.sha256("|".join(map(str, row)).encode()).hexdigest()
        for row in frame.loc[frame[split_column] == "train", feature_columns].itertuples(
            index=False, name=None
        )
    }
    test_hashes = {
        hashlib.sha256("|".join(map(str, row)).encode()).hexdigest()
        for row in frame.loc[frame[split_column] == "test", feature_columns].itertuples(
            index=False, name=None
        )
    }
    overlap = train_hashes & test_hashes
    return Evidence(
        evidence_id=new_id("evd"),
        probe="exact_duplicate_overlap",
        tool_version="exact_duplicate_overlap@1",
        observation=f"Found {len(overlap)} exact row hashes across the declared split.",
        metrics={"overlap_count": len(overlap), "has_overlap": bool(overlap)},
        source_refs=[f"dataset:{split_column}"],
    )


def preprocessing_order_evidence(
    preprocessing_before_split: bool,
    source_refs: list[str],
) -> Evidence:
    return Evidence(
        evidence_id=new_id("evd"),
        probe="preprocessing_order",
        tool_version="preprocessing_order@1",
        observation=(
            "A preprocessing fit operation appears before split construction."
            if preprocessing_before_split
            else "No preprocessing-fit-before-split pattern was found in inspected cells."
        ),
        metrics={"fit_before_split": preprocessing_before_split},
        source_refs=source_refs,
        limitations=["Static notebook order does not prove runtime execution order."],
    )


def ablation_scores(
    estimator: Any,
    frame: pd.DataFrame,
    target_column: str,
    split_column: str,
    feature_columns: Sequence[str],
    removed_features: Sequence[str],
) -> tuple[float, float, Any]:
    train_mask = frame[split_column].astype(str) == "train"
    test_mask = frame[split_column].astype(str) == "test"
    kept = [feature for feature in feature_columns if feature not in set(removed_features)]
    challenger = clone(estimator)
    challenger.fit(frame.loc[train_mask, kept], frame.loc[train_mask, target_column])
    original_probabilities = estimator.predict_proba(frame.loc[test_mask, feature_columns])[:, 1]
    corrected_probabilities = challenger.predict_proba(frame.loc[test_mask, kept])[:, 1]
    baseline = float(roc_auc_score(frame.loc[test_mask, target_column], original_probabilities))
    corrected = float(roc_auc_score(frame.loc[test_mask, target_column], corrected_probabilities))
    return baseline, corrected, challenger
