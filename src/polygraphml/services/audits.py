from __future__ import annotations

from polygraphml.domain.ids import new_id
from polygraphml.domain.models import (
    Actor,
    Audit,
    AuditEvent,
    AuditMode,
    AuditReport,
    AuditStatus,
    EventType,
    Finding,
    JobMessage,
    Project,
    ProjectStatus,
    Question,
    Session,
    utc_now,
)
from polygraphml.errors import PolygraphError
from polygraphml.queueing import AuditQueue
from polygraphml.services.reporting import render_report
from polygraphml.storage.base import DomainRepository


class AuditService:
    def __init__(self, repository: DomainRepository, queue: AuditQueue) -> None:
        self.repository = repository
        self.queue = queue

    def start(
        self,
        session: Session,
        project: Project,
        scenario_revision: int,
        mode: AuditMode,
        idempotency_key: str,
    ) -> Audit:
        scope = f"audit:start:{session.session_id}"
        existing_id = self.repository.get_idempotent_result(scope, idempotency_key)
        if existing_id:
            existing = self.repository.get(Audit, existing_id)
            if existing is not None:
                return existing
        if self.repository.count_active_audits(session.session_id) >= session.max_live_audits:
            raise PolygraphError(
                "RATE_LIMITED", "Live audit quota has been reached.", status_code=429
            )
        if mode == AuditMode.COMPLETE and project.status != ProjectStatus.READY:
            raise PolygraphError(
                "MAPPING_INCOMPLETE",
                "A complete audit requires mapped model, data, and notebook evidence.",
            )
        if scenario_revision < 1 or scenario_revision > len(project.scenarios):
            raise PolygraphError("SCENARIO_INCOMPLETE", "Scenario revision does not exist.")
        audit = Audit(
            audit_id=new_id("aud"),
            project_id=project.project_id,
            session_id=session.session_id,
            scenario_revision=scenario_revision,
            mode=mode,
            status=AuditStatus.QUEUED,
        )
        self.repository.put(audit)
        self.repository.record_idempotent_result(scope, idempotency_key, audit.audit_id)
        self.repository.append_event(
            audit,
            AuditEvent(
                event_id=new_id("evt"),
                audit_id=audit.audit_id,
                sequence=1,
                type=EventType.AUDIT_STATE,
                actor=Actor.SYSTEM,
                payload={"status": AuditStatus.QUEUED.value, "checkpoint": "enqueued"},
            ),
        )
        self.queue.send(
            JobMessage(
                audit_id=audit.audit_id,
                operation="start",
                idempotency_key=f"start:{audit.audit_id}",
            )
        )
        return self.repository.get(Audit, audit.audit_id) or audit

    def answer(
        self,
        session: Session,
        audit: Audit,
        question: Question,
        answer: str,
        idempotency_key: str,
    ) -> Audit:
        scope = f"audit:answer:{audit.audit_id}"
        existing = self.repository.get_idempotent_result(scope, idempotency_key)
        if existing:
            return self.repository.get(Audit, audit.audit_id) or audit
        if audit.session_id != session.session_id or question.audit_id != audit.audit_id:
            raise PolygraphError("AUDIT_NOT_FOUND", "Audit was not found.", status_code=404)
        if audit.status != AuditStatus.WAITING_FOR_USER or question.status != "open":
            raise PolygraphError("AUDIT_NOT_RESUMABLE", "Audit is not waiting for this answer.")
        if question.options and answer not in question.options:
            raise PolygraphError(
                "INVALID_REQUEST",
                "Answer must be one of the declared options.",
                detail={"options": question.options},
            )
        question.status = "answered"
        question.answer = answer
        question.answered_at = utc_now()
        self.repository.put(question)
        self.repository.append_event(
            audit,
            AuditEvent(
                event_id=new_id("evt"),
                audit_id=audit.audit_id,
                sequence=1,
                type=EventType.ANSWER,
                actor=Actor.USER,
                payload={"question_id": question.question_id, "answer": answer},
                provenance_refs=[f"question:{question.question_id}"],
            ),
        )
        audit.status = AuditStatus.QUEUED
        audit.checkpoint = "answer_received"
        audit.updated_at = utc_now()
        self.repository.put(audit)
        self.repository.record_idempotent_result(scope, idempotency_key, question.question_id)
        self.queue.send(
            JobMessage(
                audit_id=audit.audit_id,
                operation="resume",
                idempotency_key=f"resume:{question.question_id}",
            )
        )
        return self.repository.get(Audit, audit.audit_id) or audit

    def create_report(self, audit: Audit, project: Project, audience: str) -> AuditReport:
        existing = next(
            (
                report
                for report in self.repository.list(AuditReport, audit.audit_id)
                if report.audience == audience
            ),
            None,
        )
        if existing:
            return existing
        if audit.status != AuditStatus.COMPLETE:
            raise PolygraphError(
                "AUDIT_IN_PROGRESS", "Report requires a completed audit.", status_code=409
            )
        findings = [
            finding
            for finding_id in audit.finding_ids
            if (finding := self.repository.get(Finding, finding_id)) is not None
        ]
        report = AuditReport(
            report_id=new_id("rpt"),
            audit_id=audit.audit_id,
            audience=audience,  # type: ignore[arg-type]
            content=render_report(audit, project, findings, audience),
        )
        return self.repository.put(report)
