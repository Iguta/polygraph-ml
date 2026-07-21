from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from contextlib import suppress
from pathlib import Path
from typing import Literal

from polygraphml.adapters.datasets import TabularDatasetAdapter
from polygraphml.adapters.notebooks import NotebookInspector
from polygraphml.agent.runtime import (
    AgentInvestigationPlan,
    AgentInvestigationResult,
    AuditAgentContext,
    fixture_investigation,
    run_live_investigation,
    sanitize_dataset_profile,
)
from polygraphml.benchmarks.catalog import TARGET_PROXY_BENCHMARK_ID
from polygraphml.config import Settings
from polygraphml.domain.ids import new_id
from polygraphml.domain.models import (
    Actor,
    AgentExecutionProvenance,
    Artifact,
    ArtifactKind,
    Audit,
    AuditEvent,
    AuditStatus,
    Correction,
    DatasetProfile,
    EventType,
    Evidence,
    Finding,
    FindingMechanism,
    FindingStatus,
    Hypothesis,
    JobMessage,
    ProbeKind,
    Project,
    Question,
    Severity,
    TrustState,
    Verdict,
    utc_now,
)
from polygraphml.domain.policy import ConfirmationEvidence, decide_finding_status
from polygraphml.engine.probes import (
    duplicate_overlap_evidence,
    feature_availability_evidence,
    feature_provenance_evidence,
    group_overlap_evidence,
    metric_contract_evidence,
    preprocessing_order_evidence,
    target_proxy_association_evidence,
)
from polygraphml.engine.reproduction import ReproductionEngine
from polygraphml.errors import PolygraphError
from polygraphml.queueing import AuditQueue, ClaimedJob
from polygraphml.storage.artifacts import ArtifactStore
from polygraphml.storage.base import DomainRepository

LOGGER = logging.getLogger(__name__)


class AuditCoordinator:
    def __init__(
        self,
        settings: Settings,
        repository: DomainRepository,
        artifact_store: ArtifactStore,
        queue: AuditQueue,
    ) -> None:
        self.settings = settings
        self.repository = repository
        self.artifact_store = artifact_store
        self.queue = queue
        self.reproduction = ReproductionEngine(settings)
        self.worker_id = new_id("wrk")

    async def process(self, job: ClaimedJob) -> None:
        audit = self.repository.get(Audit, job.message.audit_id)
        if audit is None:
            self.queue.acknowledge(job)
            return
        if not self.repository.acquire_audit_lease(
            audit.audit_id, self.worker_id, self.settings.worker_lease_seconds
        ):
            self.queue.acknowledge(job)
            return
        heartbeat = asyncio.create_task(self._heartbeat(job))
        try:
            try:
                if job.message.operation == "start":
                    await self._start(audit)
                else:
                    await self._resume(audit)
                self.queue.acknowledge(job)
            except PolygraphError as exc:
                if exc.code == "EXECUTION_TIMEOUT":
                    self.queue.acknowledge(job)
                    current = self.repository.get(Audit, audit.audit_id) or audit
                    self._mark_compute_inconclusive(current, exc)
                    return
                status = self.queue.retry(job, exc.code)
                current = self.repository.get(Audit, audit.audit_id) or audit
                if status == "queued":
                    current.status = AuditStatus.QUEUED
                    current.updated_at = utc_now()
                    self.repository.put(current)
                self._emit(
                    current,
                    EventType.ERROR,
                    Actor.SYSTEM,
                    {"code": exc.code, "message": exc.message, "retry_status": status},
                )
                if status == "dead":
                    current.status = AuditStatus.FAILED_PARTIAL
                    current.checkpoint = "dead_lettered"
                    current.updated_at = utc_now()
                    self.repository.put(current)
            except Exception as exc:
                status = self.queue.retry(job, type(exc).__name__)
                current = self.repository.get(Audit, audit.audit_id) or audit
                if status == "queued":
                    current.status = AuditStatus.QUEUED
                    current.updated_at = utc_now()
                    self.repository.put(current)
                self._emit(
                    current,
                    EventType.ERROR,
                    Actor.SYSTEM,
                    {
                        "code": "INTERNAL",
                        "message": "An internal audit step failed.",
                        "retry_status": status,
                    },
                )
                if status == "dead":
                    current.status = AuditStatus.FAILED_PARTIAL
                    current.checkpoint = "dead_lettered"
                    current.updated_at = utc_now()
                    self.repository.put(current)
        finally:
            heartbeat.cancel()
            with suppress(asyncio.CancelledError):
                await heartbeat
            self.repository.release_audit_lease(audit.audit_id, self.worker_id)

    def reconcile_queued_audits(self) -> int:
        """Re-enqueue stale persisted audits after an API/SQS interleaving failure."""
        recovered = 0
        now = utc_now()
        for audit in self.repository.list(Audit):
            age = (now - audit.updated_at).total_seconds()
            if (
                audit.status != AuditStatus.QUEUED
                or audit.lease_owner is not None
                or age < self.settings.enqueue_recovery_seconds
            ):
                continue
            operation: Literal["start", "resume"] = (
                "resume"
                if audit.question_ids and audit.checkpoint == "enqueue_pending"
                else "start"
            )
            key = (
                f"resume:{audit.question_ids[-1]}"
                if operation == "resume"
                else f"start:{audit.audit_id}"
            )
            try:
                self.queue.send(
                    JobMessage(audit_id=audit.audit_id, operation=operation, idempotency_key=key)
                )
            except Exception:
                LOGGER.warning("Queued audit recovery enqueue failed for %s", audit.audit_id)
                continue
            audit.checkpoint = "enqueued"
            audit.updated_at = now
            self.repository.put(audit)
            recovered += 1
        return recovered

    async def _heartbeat(self, job: ClaimedJob) -> None:
        interval = max(1.0, min(60.0, self.settings.worker_lease_seconds / 3))
        while True:
            await asyncio.sleep(interval)
            self.queue.heartbeat(job)

    async def _start(self, audit: Audit) -> None:
        if audit.status not in {AuditStatus.QUEUED, AuditStatus.VALIDATING}:
            return
        project = self._project(audit)
        artifacts, paths = self._artifacts(project)
        self._transition(audit, AuditStatus.RECONSTRUCTING, "artifact_reconstruction")
        dataset = self._artifact_by_kind(artifacts, ArtifactKind.DATASET)
        notebook = self._artifact_by_kind(artifacts, ArtifactKind.NOTEBOOK)
        profile = TabularDatasetAdapter().profile(
            paths[dataset.artifact_id],
            dataset.artifact_id,
            dataset.sha256,
            project.mapping.target_column,
        )
        notebook_summary = NotebookInspector().inspect(paths[notebook.artifact_id])
        self._emit(
            audit,
            EventType.TOOL_RESULT,
            Actor.TOOL,
            {
                "tool": "artifact_reconstruction@1",
                "dataset_profile": profile.model_dump(mode="json"),
                "notebook": notebook_summary.model_dump(mode="json"),
            },
            [f"artifact:{dataset.artifact_id}", f"artifact:{notebook.artifact_id}"],
        )

        self._transition(audit, AuditStatus.REPRODUCING, "metric_reproduction")
        result = self.reproduction.reproduce(
            project.mapping,
            {artifact.artifact_id: artifact for artifact in artifacts},
            paths,
            project.current_scenario.intended_metric if project.current_scenario else "roc_auc",
        )
        audit.reproduction_tier = result.tier
        audit.metric_comparison = result.metric_comparison
        audit.provenance = result.provenance.model_copy(
            update={"source_commit": project.source.resolved_commit}
        )
        audit.checkpoint = "metric_reproduced"
        audit.updated_at = utc_now()
        self.repository.put(audit)
        self._emit(
            audit,
            EventType.TOOL_RESULT,
            Actor.TOOL,
            {
                "tool": "metric_reproduction@1",
                "reproduction_tier": result.tier.value,
                "metric_comparison": result.metric_comparison.model_dump(mode="json"),
            },
            ["compute:reproduction@1"],
        )

        self._transition(audit, AuditStatus.INTERROGATING, "semantic_investigation")
        plan, actor, degraded, execution = await self._investigation_plan(
            audit, project, profile, notebook_summary
        )
        audit.provenance.agent_model = execution.requested_model
        audit.provenance.prompt_schema_version = execution.harness_version
        audit.provenance.agent_execution = execution
        self.repository.put(audit)
        if degraded:
            self._emit(
                audit,
                EventType.WARNING,
                Actor.SYSTEM,
                {
                    "code": "SEMANTIC_DEGRADED",
                    "message": "Fixture policy generated the investigation plan; no live model call ran.",
                },
            )
        self._emit(
            audit,
            EventType.REASONING_SUMMARY,
            actor,
            {
                "summary": plan.reasoning_summary,
                "source": execution.mode,
                "harness_version": execution.harness_version,
            },
        )
        question_proposal = plan.question
        if question_proposal is None:
            raise PolygraphError(
                "MODEL_OUTPUT_INVALID", "Investigation did not provide a question."
            )
        hypotheses_by_key = self._persist_hypotheses(audit, plan, actor)
        affected_key = question_proposal.affected_hypothesis_keys[0]
        affected_hypothesis = hypotheses_by_key[affected_key]
        for key, hypothesis in hypotheses_by_key.items():
            affected = key == affected_key
            finding = Finding(
                finding_id=new_id("fnd"),
                mechanism=hypothesis.mechanism,
                features=hypothesis.features,
                status=FindingStatus.NEEDS_CONTEXT if affected else FindingStatus.SUSPECTED,
                severity=Severity.HIGH if affected else Severity.MEDIUM,
                confidence=0.6 if affected else 0.4,
                conclusion=(
                    "Material scenario or provenance context is required before this hypothesis "
                    "can be tested."
                    if affected
                    else "This ranked hypothesis remains untested in the current bounded audit."
                ),
                hypothesis_ids=[hypothesis.hypothesis_id],
                what_would_change_this=hypothesis.falsification_condition,
            )
            self.repository.put(finding)
            audit.finding_ids.append(finding.finding_id)
        question = Question(
            question_id=new_id("qst"),
            audit_id=audit.audit_id,
            text=question_proposal.text,
            why_it_matters=question_proposal.why_it_matters,
            affected_hypothesis_ids=[affected_hypothesis.hypothesis_id],
            answer_type=question_proposal.answer_type,  # type: ignore[arg-type]
            options=question_proposal.options,
            blocking=question_proposal.blocking,
        )
        self.repository.put(question)
        audit.question_ids.append(question.question_id)
        self.repository.put(audit)
        self._emit(
            audit,
            EventType.QUESTION,
            actor,
            question.model_dump(mode="json"),
            [f"hypothesis:{affected_hypothesis.hypothesis_id}"],
        )
        self._transition(audit, AuditStatus.WAITING_FOR_USER, "waiting_for_user")

    async def _resume(self, audit: Audit) -> None:
        if audit.status not in {AuditStatus.QUEUED, AuditStatus.WAITING_FOR_USER}:
            return
        project = self._project(audit)
        artifacts, paths = self._artifacts(project)
        questions = [
            question
            for question_id in audit.question_ids
            if (question := self.repository.get(Question, question_id)) is not None
        ]
        answered = next(
            (question for question in reversed(questions) if question.status == "answered"), None
        )
        if answered is None or answered.answer is None:
            raise PolygraphError(
                "QUESTION_NOT_FOUND", "The audit has no answered question to resume."
            )
        hypothesis = self.repository.get(Hypothesis, answered.affected_hypothesis_ids[0])
        if hypothesis is None:
            raise PolygraphError(
                "INTERNAL", "The affected hypothesis was not found.", status_code=500
            )
        finding = next(
            (
                item
                for finding_id in audit.finding_ids
                if (item := self.repository.get(Finding, finding_id)) is not None
                and hypothesis.hypothesis_id in item.hypothesis_ids
            ),
            None,
        )
        if finding is None:
            raise PolygraphError("INTERNAL", "The affected finding was not found.", status_code=500)

        self._transition(audit, AuditStatus.PROBING, "deterministic_probes")
        result = self.reproduction.reproduce(
            project.mapping,
            {artifact.artifact_id: artifact for artifact in artifacts},
            paths,
            project.current_scenario.intended_metric if project.current_scenario else "roc_auc",
        )
        frame = result.frame
        split_column = str(project.mapping.split_column)
        target_column = str(project.mapping.target_column)
        feature = hypothesis.features[0]
        answer_refs = [f"user_answer:{answered.question_id}", *hypothesis.source_refs]
        semantic_evidence_ids: list[str] = []
        mechanism_established = False
        mechanism_cleared = False
        protocol_invalidating = False

        if hypothesis.requested_probe == ProbeKind.FEATURE_AVAILABILITY:
            availability = feature_availability_evidence(
                hypothesis.hypothesis_id,
                feature,
                answered.answer,
                answer_refs,
            )
            self._record_evidence(audit, finding, availability)
            semantic_evidence_ids.append(availability.evidence_id)
            mechanism_established = bool(availability.metrics["unavailable_at_decision"])
            mechanism_cleared = bool(availability.metrics["available_at_decision"])
            association = target_proxy_association_evidence(
                hypothesis.hypothesis_id,
                frame,
                target_column,
                split_column,
                feature,
                [f"artifact:{project.mapping.dataset_artifact_id}"],
            )
            self._record_evidence(audit, finding, association)
        elif hypothesis.requested_probe == ProbeKind.TARGET_PROXY_ASSOCIATION:
            provenance = feature_provenance_evidence(
                hypothesis.hypothesis_id,
                feature,
                answered.answer,
                answer_refs,
            )
            self._record_evidence(audit, finding, provenance)
            semantic_evidence_ids.append(provenance.evidence_id)
            mechanism_established = bool(provenance.metrics["target_derived"])
            mechanism_cleared = bool(provenance.metrics["independent_input"])
            association = target_proxy_association_evidence(
                hypothesis.hypothesis_id,
                frame,
                target_column,
                split_column,
                feature,
                [f"artifact:{project.mapping.dataset_artifact_id}"],
            )
            self._record_evidence(audit, finding, association)
        elif hypothesis.requested_probe == ProbeKind.METRIC_CONTRACT:
            metric_contract = metric_contract_evidence(
                hypothesis.hypothesis_id,
                project.current_scenario.intended_metric if project.current_scenario else "roc_auc",
                [claim.metric for claim in result.notebook.claims],
                [claim.source_ref for claim in result.notebook.claims],
            )
            self._record_evidence(audit, finding, metric_contract)
            semantic_evidence_ids.append(metric_contract.evidence_id)
            metric_matches = bool(metric_contract.metrics["metric_matches"])
            mechanism_established = not metric_matches
            mechanism_cleared = metric_matches
            protocol_invalidating = not metric_matches
        else:
            raise PolygraphError(
                "EXECUTION_UNSUPPORTED",
                f"Probe {hypothesis.requested_probe.value} is not dispatched.",
            )

        duplication = duplicate_overlap_evidence(frame, split_column)
        self.repository.put(duplication)
        audit.evidence_ids.append(duplication.evidence_id)
        self._emit(audit, EventType.EVIDENCE, Actor.TOOL, duplication.model_dump(mode="json"))
        if bool(duplication.metrics["has_overlap"]):
            self._persist_probe_finding(
                audit,
                mechanism=FindingMechanism.SPLIT_CONTAMINATION,
                status=FindingStatus.CONFIRMED,
                severity=Severity.HIGH,
                evidence_id=duplication.evidence_id,
                conclusion="Exact evaluation rows occur on both sides of the declared split.",
                what_changes="A row-level split with no matching row hashes across train and test.",
            )
        else:
            self._persist_clearance(
                audit,
                mechanism="split_contamination",
                evidence_id=duplication.evidence_id,
                conclusion="No exact row hashes overlap across the declared split.",
                what_changes="Evidence of an identical evaluation row in both train and test.",
            )

        if project.mapping.entity_column:
            groups = group_overlap_evidence(
                frame[project.mapping.entity_column],
                frame[split_column].astype(str) == "train",
                frame[split_column].astype(str) == "test",
            )
            self.repository.put(groups)
            audit.evidence_ids.append(groups.evidence_id)
            self._emit(audit, EventType.EVIDENCE, Actor.TOOL, groups.model_dump(mode="json"))
            if bool(groups.metrics["has_overlap"]):
                self._persist_probe_finding(
                    audit,
                    mechanism=FindingMechanism.GROUP_CONTAMINATION,
                    status=FindingStatus.CONFIRMED,
                    severity=Severity.HIGH,
                    evidence_id=groups.evidence_id,
                    conclusion="Declared entity groups overlap between train and test.",
                    what_changes="A group-aware split with no entity present on both sides.",
                    features=[str(project.mapping.entity_column)],
                )
            else:
                self._persist_clearance(
                    audit,
                    mechanism="group_contamination",
                    evidence_id=groups.evidence_id,
                    conclusion="No entity identifiers overlap across the declared split.",
                    what_changes="Evidence of an entity present in both train and test.",
                )

        notebook = self._artifact_by_kind(artifacts, ArtifactKind.NOTEBOOK)
        inspection = NotebookInspector().inspect(paths[notebook.artifact_id])
        preprocessing = preprocessing_order_evidence(
            inspection.preprocessing_before_split,
            inspection.preprocessing_cells + inspection.split_cells,
        )
        self.repository.put(preprocessing)
        audit.evidence_ids.append(preprocessing.evidence_id)
        self._emit(audit, EventType.EVIDENCE, Actor.TOOL, preprocessing.model_dump(mode="json"))
        if not inspection.preprocessing_before_split:
            self._persist_clearance(
                audit,
                mechanism="preprocessing",
                evidence_id=preprocessing.evidence_id,
                conclusion="No fit-before-split pattern was found in the inspected notebook cells.",
                what_changes="Runtime evidence or source showing preprocessing fit before splitting.",
            )
        else:
            self._persist_probe_finding(
                audit,
                mechanism=FindingMechanism.PREPROCESSING,
                status=FindingStatus.TESTED,
                severity=Severity.MEDIUM,
                evidence_id=preprocessing.evidence_id,
                conclusion=(
                    "Static notebook order suggests preprocessing may be fit before the split; "
                    "runtime order is required before confirmation."
                ),
                what_changes="A runtime trace proving the transformer was fit on training rows only.",
            )

        should_correct = mechanism_established and hypothesis.requested_probe in {
            ProbeKind.FEATURE_AVAILABILITY,
            ProbeKind.TARGET_PROXY_ASSOCIATION,
        }
        if should_correct:
            self._transition(audit, AuditStatus.CORRECTING, "corrected_evaluation")
            audit.metric_comparison = self.reproduction.correct(
                result, project.mapping, hypothesis.features
            )
            correction = Correction(
                correction_id=new_id("cor"),
                kind=(
                    "remove_target_proxy"
                    if hypothesis.mechanism == FindingMechanism.TARGET_PROXY
                    else "remove_unavailable_feature"
                ),
                description=(
                    f"Retrained the evaluation estimator without {', '.join(hypothesis.features)}."
                ),
                features_removed=hypothesis.features,
                protocol_id="proto_corrected_v1",
                evidence_ids=semantic_evidence_ids,
            )
            self.repository.put(correction)
            audit.correction_ids.append(correction.correction_id)
            finding.correction_id = correction.correction_id
            status = decide_finding_status(
                ConfirmationEvidence(
                    scenario_established=True,
                    mechanism_evidence_count=1,
                    impact_measured=True,
                    protocol_invalidating=protocol_invalidating,
                    contradictions_resolved=True,
                    ablation_delta=(
                        audit.metric_comparison.reproduced.value
                        - audit.metric_comparison.corrected.value
                    )
                    if audit.metric_comparison.reproduced and audit.metric_comparison.corrected
                    else None,
                )
            )
            finding.status = status
            finding.confidence = 0.96
            finding.conclusion = self._confirmed_conclusion(hypothesis)
            self._emit(
                audit,
                EventType.CORRECTION,
                Actor.TOOL,
                {
                    **correction.model_dump(mode="json"),
                    "metric_comparison": audit.metric_comparison.model_dump(mode="json"),
                },
                [*semantic_evidence_ids, "compute:correction@1"],
            )
        elif mechanism_established:
            finding.status = decide_finding_status(
                ConfirmationEvidence(
                    scenario_established=True,
                    mechanism_evidence_count=1,
                    impact_measured=False,
                    protocol_invalidating=protocol_invalidating,
                    contradictions_resolved=True,
                )
            )
            finding.confidence = 0.92
            finding.conclusion = self._confirmed_conclusion(hypothesis)
        elif mechanism_cleared:
            finding.status = FindingStatus.CLEARED
            finding.confidence = 0.82
            finding.conclusion = self._cleared_conclusion(hypothesis)
        else:
            finding.status = FindingStatus.INCONCLUSIVE
            finding.confidence = 0.5
            finding.conclusion = "The supplied context did not establish or falsify the mechanism."

        self.repository.put(finding)
        self.repository.put(audit)
        self._emit(
            audit,
            EventType.FINDING_CHANGED,
            Actor.SYSTEM,
            finding.model_dump(mode="json"),
            finding.evidence_ids,
        )
        self._transition(audit, AuditStatus.COMPOSING, "verdict")
        findings = [
            item
            for finding_id in audit.finding_ids
            if (item := self.repository.get(Finding, finding_id)) is not None
        ]
        counts = {
            status.value: sum(1 for item in findings if item.status == status)
            for status in FindingStatus
            if any(item.status == status for item in findings)
        }
        confirmed = any(item.status == FindingStatus.CONFIRMED for item in findings)
        audit.verdict = Verdict(
            trust_state=TrustState.MATERIALLY_INFLATED
            if confirmed
            else TrustState.PARTIALLY_SUPPORTED,
            summary=(
                "The reported score is reproducible under the submitted split but materially "
                "inflated for the declared decision scenario."
                if confirmed
                else "The tested semantic mechanism was not confirmed under the supplied context."
            ),
            finding_counts=counts,
            unsupported_checks=[
                "near_duplicate_similarity",
                "temporal_backtesting",
            ],
        )
        self.repository.put(audit)
        self._emit(
            audit,
            EventType.VERDICT,
            Actor.SYSTEM,
            {
                "verdict": audit.verdict.model_dump(mode="json"),
                "metric_comparison": audit.metric_comparison.model_dump(mode="json")
                if audit.metric_comparison
                else None,
            },
        )
        self._transition(audit, AuditStatus.COMPLETE, "complete")

    async def _investigation_plan(
        self,
        audit: Audit,
        project: Project,
        profile: object,
        notebook: object,
    ) -> tuple[AgentInvestigationPlan, Actor, bool, AgentExecutionProvenance]:
        scenario = project.current_scenario
        if scenario is None:
            raise PolygraphError("SCENARIO_INCOMPLETE", "A scenario is required.")
        excluded = {
            project.mapping.target_column,
            project.mapping.split_column,
            project.mapping.entity_column,
            project.mapping.time_column,
        }
        candidate_features = tuple(
            audit.provenance.feature_order
            or [
                column.name
                for column in profile.columns  # type: ignore[attr-defined]
                if column.name not in excluded
            ]
        )
        if self.settings.live_agent_ready:
            try:
                outcome = await run_live_investigation(
                    self.settings,
                    AuditAgentContext(
                        scenario=scenario,
                        dataset_profile=sanitize_dataset_profile(profile),  # type: ignore[arg-type]
                        notebook_summary=notebook.model_dump(mode="json"),  # type: ignore[attr-defined]
                        supported_probes=(
                            ProbeKind.FEATURE_AVAILABILITY,
                            ProbeKind.TARGET_PROXY_ASSOCIATION,
                            ProbeKind.METRIC_CONTRACT,
                        ),
                        candidate_features=candidate_features,
                        feature_context={
                            name: context.description
                            for name, context in project.feature_context.items()
                        },
                    ),
                    audit.audit_id,
                )
                if isinstance(outcome, AgentInvestigationResult):
                    return outcome.plan, Actor.AGENT, False, outcome.execution
                # Compatibility for deterministic test doubles at the model boundary.
                return (
                    outcome,
                    Actor.AGENT,
                    False,
                    AgentExecutionProvenance(
                        provider="openai",
                        mode="live",
                        requested_model=self.settings.openai_model,
                        resolved_model=self.settings.openai_model,
                    ),
                )
            except PolygraphError as exc:
                fallback = fixture_investigation(
                    self._fixture_feature(profile, project, audit),
                    self._fixture_mechanism(project),
                )
                return (
                    fallback,
                    Actor.SYSTEM,
                    True,
                    AgentExecutionProvenance(
                        provider="fixture",
                        mode="degraded",
                        requested_model=self.settings.openai_model,
                        failure_code=exc.code,
                    ),
                )
        fallback = fixture_investigation(
            self._fixture_feature(profile, project, audit), self._fixture_mechanism(project)
        )
        return (
            fallback,
            Actor.SYSTEM,
            True,
            AgentExecutionProvenance(
                provider="fixture",
                mode="fixture",
                requested_model=self.settings.openai_model,
            ),
        )

    @staticmethod
    def _fixture_feature(profile: object, project: Project, audit: Audit) -> str:
        if not isinstance(profile, DatasetProfile):
            return "call_duration"
        excluded = {
            project.mapping.target_column,
            project.mapping.split_column,
            project.mapping.entity_column,
            project.mapping.time_column,
        }
        candidates = audit.provenance.feature_order or [
            column.name for column in profile.columns if column.name not in excluded
        ]
        semantic = next(
            (
                name
                for name in candidates
                if any(token in name.lower() for token in ("duration", "outcome", "result", "post"))
            ),
            None,
        )
        return semantic or (candidates[-1] if candidates else "unknown_feature")

    @staticmethod
    def _fixture_mechanism(project: Project) -> FindingMechanism:
        if project.source.benchmark_id == TARGET_PROXY_BENCHMARK_ID:
            return FindingMechanism.TARGET_PROXY
        return FindingMechanism.POST_OUTCOME

    def _persist_hypotheses(
        self,
        audit: Audit,
        plan: AgentInvestigationPlan,
        actor: Actor,
    ) -> dict[str, Hypothesis]:
        persisted: dict[str, Hypothesis] = {}
        for proposal in plan.hypotheses:
            hypothesis = Hypothesis(
                hypothesis_id=new_id("hyp"),
                mechanism=proposal.mechanism,
                features=proposal.features,
                assumptions=proposal.assumptions,
                rationale_summary=proposal.rationale_summary,
                requested_probe=proposal.requested_probe,
                falsification_condition=proposal.falsification_condition,
                source_refs=proposal.source_refs,
            )
            self.repository.put(hypothesis)
            audit.hypothesis_ids.append(hypothesis.hypothesis_id)
            persisted[proposal.hypothesis_key] = hypothesis
            self._emit(
                audit,
                EventType.HYPOTHESIS,
                actor,
                {
                    **hypothesis.model_dump(mode="json"),
                    "hypothesis_key": proposal.hypothesis_key,
                },
                hypothesis.source_refs,
            )
        return persisted

    def _record_evidence(
        self,
        audit: Audit,
        finding: Finding,
        evidence: Evidence,
    ) -> None:
        self.repository.put(evidence)
        audit.evidence_ids.append(evidence.evidence_id)
        finding.evidence_ids.append(evidence.evidence_id)
        self._emit(
            audit,
            EventType.EVIDENCE,
            Actor.TOOL,
            evidence.model_dump(mode="json"),
            evidence.source_refs,
        )

    @staticmethod
    def _confirmed_conclusion(hypothesis: Hypothesis) -> str:
        feature = hypothesis.features[0]
        if hypothesis.mechanism == FindingMechanism.TARGET_PROXY:
            return (
                f"{feature} is derived from or assigned after the target outcome, and its measured "
                "evaluation impact is recorded in the correction evidence."
            )
        if hypothesis.mechanism == FindingMechanism.METRIC_MISMATCH:
            return "The notebook's reported metric does not match the declared evaluation contract."
        return (
            f"{feature} is unavailable at the stated decision point, and its measured evaluation "
            "impact is recorded in the correction evidence."
        )

    @staticmethod
    def _cleared_conclusion(hypothesis: Hypothesis) -> str:
        feature = hypothesis.features[0]
        if hypothesis.mechanism == FindingMechanism.TARGET_PROXY:
            return f"The supplied provenance establishes {feature} as an independent input."
        if hypothesis.mechanism == FindingMechanism.METRIC_MISMATCH:
            return "The notebook reports the metric declared by the evaluation scenario."
        return f"The supplied scenario establishes {feature} as available at the decision point."

    def _persist_clearance(
        self,
        audit: Audit,
        mechanism: str,
        evidence_id: str,
        conclusion: str,
        what_changes: str,
        features: list[str] | None = None,
    ) -> None:
        finding = Finding(
            finding_id=new_id("fnd"),
            mechanism=FindingMechanism(mechanism),
            features=features or [],
            status=FindingStatus.CLEARED,
            severity=Severity.INFO,
            confidence=0.9,
            conclusion=conclusion,
            evidence_ids=[evidence_id],
            what_would_change_this=what_changes,
        )
        self.repository.put(finding)
        audit.finding_ids.append(finding.finding_id)
        self._emit(
            audit,
            EventType.FINDING_CHANGED,
            Actor.SYSTEM,
            finding.model_dump(mode="json"),
            [evidence_id],
        )

    def _persist_probe_finding(
        self,
        audit: Audit,
        mechanism: FindingMechanism,
        status: FindingStatus,
        severity: Severity,
        evidence_id: str,
        conclusion: str,
        what_changes: str,
        features: list[str] | None = None,
    ) -> None:
        finding = Finding(
            finding_id=new_id("fnd"),
            mechanism=mechanism,
            features=features or [],
            status=status,
            severity=severity,
            confidence=0.98 if status == FindingStatus.CONFIRMED else 0.7,
            conclusion=conclusion,
            evidence_ids=[evidence_id],
            what_would_change_this=what_changes,
        )
        self.repository.put(finding)
        audit.finding_ids.append(finding.finding_id)
        self._emit(
            audit,
            EventType.FINDING_CHANGED,
            Actor.SYSTEM,
            finding.model_dump(mode="json"),
            [evidence_id],
        )

    def _transition(self, audit: Audit, status: AuditStatus, checkpoint: str) -> None:
        current = self.repository.get(Audit, audit.audit_id) or audit
        current.status = status
        current.checkpoint = checkpoint
        current.updated_at = utc_now()
        self.repository.put(current)
        audit.status = status
        audit.checkpoint = checkpoint
        self._emit(
            current,
            EventType.AUDIT_STATE,
            Actor.SYSTEM,
            {"status": status.value, "checkpoint": checkpoint},
        )
        audit.last_event_sequence = current.last_event_sequence

    def _emit(
        self,
        audit: Audit,
        event_type: EventType,
        actor: Actor,
        payload: dict[str, object],
        provenance_refs: list[str] | None = None,
    ) -> None:
        self.repository.append_event(
            audit,
            AuditEvent(
                event_id=new_id("evt"),
                audit_id=audit.audit_id,
                sequence=1,
                type=event_type,
                actor=actor,
                payload=payload,
                provenance_refs=provenance_refs or [],
            ),
        )

    def _mark_compute_inconclusive(self, audit: Audit, error: PolygraphError) -> None:
        findings = [
            finding
            for finding_id in audit.finding_ids
            if (finding := self.repository.get(Finding, finding_id)) is not None
        ]
        if findings:
            for finding in findings:
                if finding.status not in {FindingStatus.CONFIRMED, FindingStatus.CLEARED}:
                    finding.status = FindingStatus.INCONCLUSIVE
                    finding.conclusion = (
                        "The bounded model computation timed out before this mechanism could be "
                        "decided."
                    )
                    finding.what_would_change_this = (
                        "A smaller supported artifact or an evaluation that completes within the "
                        "published compute limits."
                    )
                    self.repository.put(finding)
                    self._emit(
                        audit,
                        EventType.FINDING_CHANGED,
                        Actor.SYSTEM,
                        finding.model_dump(mode="json"),
                        finding.evidence_ids,
                    )
        else:
            finding = Finding(
                finding_id=new_id("fnd"),
                mechanism=FindingMechanism.OTHER,
                features=[],
                status=FindingStatus.INCONCLUSIVE,
                severity=Severity.MEDIUM,
                confidence=1.0,
                conclusion=(
                    "The bounded model computation timed out before model evaluation completed."
                ),
                what_would_change_this=(
                    "A smaller supported artifact or an evaluation that completes within the "
                    "published compute limits."
                ),
            )
            self.repository.put(finding)
            audit.finding_ids.append(finding.finding_id)
            findings.append(finding)
        audit.status = AuditStatus.FAILED_PARTIAL
        audit.checkpoint = "compute_inconclusive"
        audit.verdict = Verdict(
            trust_state=TrustState.INCONCLUSIVE,
            summary="Model quality could not be decided within the bounded compute budget.",
            finding_counts={
                "inconclusive": sum(
                    finding.status == FindingStatus.INCONCLUSIVE for finding in findings
                )
            },
            unsupported_checks=["model_evaluation_after_timeout"],
        )
        audit.updated_at = utc_now()
        self.repository.put(audit)
        self._emit(
            audit,
            EventType.ERROR,
            Actor.SYSTEM,
            {
                "code": error.code,
                "message": error.message,
                "retry_status": "not_retried",
            },
        )
        self._emit(
            audit,
            EventType.VERDICT,
            Actor.SYSTEM,
            {"verdict": audit.verdict.model_dump(mode="json"), "metric_comparison": None},
        )

    def _project(self, audit: Audit) -> Project:
        project = self.repository.get(Project, audit.project_id)
        if project is None:
            raise PolygraphError("PROJECT_NOT_FOUND", "Project was not found.", status_code=404)
        return project

    def _artifacts(self, project: Project) -> tuple[list[Artifact], dict[str, Path]]:
        artifacts = [
            artifact
            for artifact_id in project.artifact_ids
            if (artifact := self.repository.get(Artifact, artifact_id)) is not None
        ]
        paths = {
            artifact.artifact_id: self.artifact_store.path_for_key(artifact.storage_key)
            for artifact in artifacts
        }
        return artifacts, paths

    @staticmethod
    def _artifact_by_kind(artifacts: list[Artifact], kind: ArtifactKind) -> Artifact:
        artifact = next((item for item in artifacts if item.kind == kind), None)
        if artifact is None:
            raise PolygraphError("MAPPING_INCOMPLETE", f"A {kind.value} artifact is required.")
        return artifact


async def run_polling_worker(
    coordinator: AuditCoordinator,
    queue: AuditQueue,
    poll_seconds: float,
    should_stop: Callable[[], bool] | None = None,
) -> None:
    stop = should_stop or (lambda: False)
    while not stop():
        coordinator.reconcile_queued_audits()
        job = queue.receive()
        if job is None:
            await asyncio.sleep(poll_seconds)
            continue
        await coordinator.process(job)
