from __future__ import annotations

import hashlib
from collections.abc import Sequence
from typing import Any

import pandas as pd
from pandas.api.types import is_numeric_dtype
from sklearn.base import clone
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

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
    available_before = (
        any(token in normalized for token in ("before", "available before", "at decision"))
        and not unavailable
    )
    observation = (
        f"The user confirmed {feature} is available only after the decision point."
        if unavailable
        else f"The user confirmed {feature} is available at the decision point."
        if available_before
        else f"The supplied answer did not establish that {feature} is unavailable at decision time."
    )
    return Evidence(
        evidence_id=new_id("evd"),
        hypothesis_id=hypothesis_id,
        probe="feature_availability",
        tool_version="feature_availability@1",
        observation=observation,
        metrics={
            "unavailable_at_decision": unavailable,
            "available_at_decision": available_before,
        },
        source_refs=source_refs,
        limitations=(
            []
            if unavailable or available_before
            else ["Feature availability remains scenario-dependent."]
        ),
    )


def feature_provenance_evidence(
    hypothesis_id: str,
    feature: str,
    answer: str,
    source_refs: list[str],
) -> Evidence:
    normalized = answer.strip().lower().replace(" ", "_")
    derived = any(
        token in normalized
        for token in ("derived_from_target", "assigned_after_outcome", "contains_target")
    )
    independent = "independent" in normalized and not derived
    if derived:
        observation = (
            f"The supplied provenance states that {feature} is derived from or assigned after "
            "the target outcome."
        )
    elif independent:
        observation = f"The supplied provenance states that {feature} is an independent input."
    else:
        observation = f"The supplied provenance did not establish how {feature} relates to target."
    return Evidence(
        evidence_id=new_id("evd"),
        hypothesis_id=hypothesis_id,
        probe="feature_provenance",
        tool_version="feature_provenance@1",
        observation=observation,
        metrics={"target_derived": derived, "independent_input": independent},
        source_refs=source_refs,
        limitations=[] if derived or independent else ["Feature provenance remains unresolved."],
    )


def target_proxy_association_evidence(
    hypothesis_id: str,
    frame: pd.DataFrame,
    target_column: str,
    split_column: str,
    feature: str,
    source_refs: list[str],
) -> Evidence:
    required = {target_column, split_column, feature}
    missing = sorted(required - set(str(column) for column in frame.columns))
    if missing:
        return Evidence(
            evidence_id=new_id("evd"),
            hypothesis_id=hypothesis_id,
            probe="target_proxy_association",
            tool_version="target_proxy_association@1",
            observation="The target-proxy association probe could not run.",
            metrics={"computed": False},
            source_refs=source_refs,
            limitations=[f"Missing required columns: {', '.join(missing)}."],
        )
    train_mask = frame[split_column].astype(str) == "train"
    test_mask = frame[split_column].astype(str) == "test"
    train_target = frame.loc[train_mask, target_column]
    test_target = frame.loc[test_mask, target_column]
    if train_target.nunique(dropna=True) < 2 or test_target.nunique(dropna=True) < 2:
        return Evidence(
            evidence_id=new_id("evd"),
            hypothesis_id=hypothesis_id,
            probe="target_proxy_association",
            tool_version="target_proxy_association@1",
            observation="The target-proxy association probe requires both target classes.",
            metrics={"computed": False},
            source_refs=source_refs,
            limitations=["Train and test partitions must each contain both target classes."],
        )

    if is_numeric_dtype(frame[feature]):
        feature_pipeline: Pipeline = Pipeline(
            [
                ("impute", SimpleImputer(strategy="median")),
                ("scale", StandardScaler()),
            ]
        )
    else:
        feature_pipeline = Pipeline(
            [
                ("impute", SimpleImputer(strategy="most_frequent")),
                ("encode", OneHotEncoder(handle_unknown="ignore")),
            ]
        )
    estimator = Pipeline(
        [
            (
                "prepare",
                ColumnTransformer([("feature", feature_pipeline, [feature])], remainder="drop"),
            ),
            ("model", LogisticRegression(max_iter=1000, random_state=42)),
        ]
    )
    try:
        estimator.fit(frame.loc[train_mask, [feature]], train_target)
        probabilities = estimator.predict_proba(frame.loc[test_mask, [feature]])[:, 1]
        raw_auc = float(roc_auc_score(test_target, probabilities))
    except (TypeError, ValueError) as exc:
        return Evidence(
            evidence_id=new_id("evd"),
            hypothesis_id=hypothesis_id,
            probe="target_proxy_association",
            tool_version="target_proxy_association@1",
            observation="The target-proxy association probe could not score the feature.",
            metrics={"computed": False},
            source_refs=source_refs,
            limitations=[f"Probe failed with {type(exc).__name__}."],
        )
    directional_auc = max(raw_auc, 1.0 - raw_auc)
    return Evidence(
        evidence_id=new_id("evd"),
        hypothesis_id=hypothesis_id,
        probe="target_proxy_association",
        tool_version="target_proxy_association@1",
        observation=(
            f"A train-only univariate challenger using {feature} achieved held-out ROC AUC "
            f"{directional_auc:.4f}."
        ),
        metrics={
            "computed": True,
            "single_feature_auc": directional_auc,
            "raw_auc": raw_auc,
            "train_rows": int(train_mask.sum()),
            "test_rows": int(test_mask.sum()),
        },
        source_refs=source_refs,
        limitations=[
            "Strong association demonstrates predictiveness, not target leakage or availability."
        ],
    )


def metric_contract_evidence(
    hypothesis_id: str,
    intended_metric: str,
    notebook_metrics: Sequence[str],
    source_refs: list[str],
) -> Evidence:
    observed = sorted(set(notebook_metrics))
    matches = intended_metric in observed
    return Evidence(
        evidence_id=new_id("evd"),
        hypothesis_id=hypothesis_id,
        probe="metric_contract",
        tool_version="metric_contract@1",
        observation=(
            f"The notebook reports the declared {intended_metric} metric."
            if matches
            else f"The notebook does not report the declared {intended_metric} metric."
        ),
        metrics={
            "metric_matches": matches,
            "intended_metric": intended_metric,
            "observed_metrics": ",".join(observed),
        },
        source_refs=source_refs,
        limitations=[
            "Static metric-name matching does not establish complete protocol equivalence."
        ],
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
