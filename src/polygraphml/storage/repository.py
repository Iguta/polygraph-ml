from __future__ import annotations

import hashlib
import secrets
import sqlite3
import threading
from collections.abc import Iterable, Sequence
from datetime import timedelta
from pathlib import Path
from typing import ClassVar, TypeVar

from pydantic import BaseModel

from polygraphml.domain.ids import new_id
from polygraphml.domain.models import (
    Artifact,
    Audit,
    AuditEvent,
    AuditReport,
    Correction,
    Evidence,
    Finding,
    Hypothesis,
    JobMessage,
    Project,
    Question,
    Session,
    utc_now,
)

ModelT = TypeVar("ModelT", bound=BaseModel)


class SqliteRepository:
    """Durable local repository used by the API, worker, tests, and fixture mode."""

    _model_kinds: ClassVar[dict[type[BaseModel], str]] = {
        Project: "project",
        Artifact: "artifact",
        Audit: "audit",
        Question: "question",
        Hypothesis: "hypothesis",
        Evidence: "evidence",
        Finding: "finding",
        Correction: "correction",
        AuditReport: "report",
    }
    _id_fields: ClassVar[dict[type[BaseModel], str]] = {
        Project: "project_id",
        Artifact: "artifact_id",
        Audit: "audit_id",
        Question: "question_id",
        Hypothesis: "hypothesis_id",
        Evidence: "evidence_id",
        Finding: "finding_id",
        Correction: "correction_id",
        AuditReport: "report_id",
    }

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._connection = sqlite3.connect(path, check_same_thread=False, timeout=30)
        self._connection.row_factory = sqlite3.Row
        self._initialize()

    def close(self) -> None:
        with self._lock:
            self._connection.close()

    def _initialize(self) -> None:
        with self._lock, self._connection:
            self._connection.execute("PRAGMA journal_mode=WAL")
            self._connection.execute("PRAGMA foreign_keys=ON")
            self._connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    token_hash TEXT UNIQUE NOT NULL,
                    payload TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS objects (
                    kind TEXT NOT NULL,
                    object_id TEXT NOT NULL,
                    parent_id TEXT,
                    payload TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (kind, object_id)
                );
                CREATE INDEX IF NOT EXISTS objects_parent_idx
                    ON objects(kind, parent_id);
                CREATE TABLE IF NOT EXISTS events (
                    audit_id TEXT NOT NULL,
                    sequence INTEGER NOT NULL,
                    event_id TEXT UNIQUE NOT NULL,
                    payload TEXT NOT NULL,
                    PRIMARY KEY (audit_id, sequence)
                );
                CREATE TABLE IF NOT EXISTS idempotency (
                    scope TEXT NOT NULL,
                    key TEXT NOT NULL,
                    result_id TEXT NOT NULL,
                    PRIMARY KEY (scope, key)
                );
                CREATE TABLE IF NOT EXISTS jobs (
                    job_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    audit_id TEXT NOT NULL,
                    idempotency_key TEXT UNIQUE NOT NULL,
                    payload TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'queued',
                    attempts INTEGER NOT NULL DEFAULT 0,
                    available_at TEXT NOT NULL,
                    lease_until TEXT,
                    last_error TEXT
                );
                CREATE INDEX IF NOT EXISTS jobs_claim_idx
                    ON jobs(status, available_at, lease_until, job_id);
                """
            )

    @staticmethod
    def token_hash(token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()

    def create_session(self, ttl_seconds: int) -> tuple[Session, str]:
        token = secrets.token_urlsafe(32)
        session = Session(
            session_id=new_id("ses"),
            token_hash=self.token_hash(token),
            expires_at=utc_now() + timedelta(seconds=ttl_seconds),
        )
        with self._lock, self._connection:
            self._connection.execute(
                "INSERT INTO sessions(session_id, token_hash, payload) VALUES (?, ?, ?)",
                (session.session_id, session.token_hash, session.model_dump_json()),
            )
        return session, token

    def get_session_by_token(self, token: str) -> Session | None:
        digest = self.token_hash(token)
        with self._lock:
            row = self._connection.execute(
                "SELECT payload FROM sessions WHERE token_hash = ?", (digest,)
            ).fetchone()
        if row is None:
            return None
        session = Session.model_validate_json(row["payload"])
        if session.expires_at <= utc_now():
            return None
        return session

    def _parent_id(self, model: BaseModel) -> str | None:
        for name in ("project_id", "audit_id", "session_id"):
            if hasattr(model, name):
                value = getattr(model, name)
                if isinstance(value, str):
                    return value
        return None

    def put(self, model: ModelT) -> ModelT:
        kind = self._model_kinds[type(model)]
        object_id = str(getattr(model, self._id_fields[type(model)]))
        with self._lock, self._connection:
            self._connection.execute(
                """
                INSERT INTO objects(kind, object_id, parent_id, payload, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(kind, object_id) DO UPDATE SET
                    parent_id = excluded.parent_id,
                    payload = excluded.payload,
                    updated_at = excluded.updated_at
                """,
                (
                    kind,
                    object_id,
                    self._parent_id(model),
                    model.model_dump_json(),
                    utc_now().isoformat(),
                ),
            )
        return model

    def get(self, model_type: type[ModelT], object_id: str) -> ModelT | None:
        kind = self._model_kinds[model_type]
        with self._lock:
            row = self._connection.execute(
                "SELECT payload FROM objects WHERE kind = ? AND object_id = ?",
                (kind, object_id),
            ).fetchone()
        return model_type.model_validate_json(row["payload"]) if row else None

    def list(self, model_type: type[ModelT], parent_id: str | None = None) -> list[ModelT]:
        kind = self._model_kinds[model_type]
        query = "SELECT payload FROM objects WHERE kind = ?"
        parameters: tuple[str, ...] = (kind,)
        if parent_id is not None:
            query += " AND parent_id = ?"
            parameters = (kind, parent_id)
        query += " ORDER BY updated_at, object_id"
        with self._lock:
            rows = self._connection.execute(query, parameters).fetchall()
        return [model_type.model_validate_json(row["payload"]) for row in rows]

    def count_projects(self, session_id: str) -> int:
        return sum(1 for project in self.list(Project) if project.session_id == session_id)

    def count_active_audits(self, session_id: str) -> int:
        terminal = {"complete", "failed_partial", "failed", "waiting_for_user"}
        return sum(
            1
            for audit in self.list(Audit)
            if audit.session_id == session_id and audit.status.value not in terminal
        )

    def get_idempotent_result(self, scope: str, key: str) -> str | None:
        with self._lock:
            row = self._connection.execute(
                "SELECT result_id FROM idempotency WHERE scope = ? AND key = ?", (scope, key)
            ).fetchone()
        return str(row["result_id"]) if row else None

    def record_idempotent_result(self, scope: str, key: str, result_id: str) -> None:
        with self._lock, self._connection:
            self._connection.execute(
                "INSERT OR IGNORE INTO idempotency(scope, key, result_id) VALUES (?, ?, ?)",
                (scope, key, result_id),
            )

    def append_event(
        self,
        audit: Audit,
        event: AuditEvent,
    ) -> AuditEvent:
        with self._lock, self._connection:
            current = self.get(Audit, audit.audit_id)
            if current is None:
                raise KeyError(audit.audit_id)
            row = self._connection.execute(
                "SELECT COALESCE(MAX(sequence), 0) AS sequence FROM events WHERE audit_id = ?",
                (audit.audit_id,),
            ).fetchone()
            sequence = int(row["sequence"]) + 1
            committed = event.model_copy(update={"sequence": sequence})
            self._connection.execute(
                "INSERT INTO events(audit_id, sequence, event_id, payload) VALUES (?, ?, ?, ?)",
                (audit.audit_id, sequence, committed.event_id, committed.model_dump_json()),
            )
            current.last_event_sequence = sequence
            current.updated_at = utc_now()
            self.put(current)
            audit.last_event_sequence = sequence
        return committed

    def list_events(self, audit_id: str, after_sequence: int = 0) -> Sequence[AuditEvent]:
        with self._lock:
            rows = self._connection.execute(
                """
                SELECT payload FROM events
                WHERE audit_id = ? AND sequence > ?
                ORDER BY sequence
                """,
                (audit_id, after_sequence),
            ).fetchall()
        return [AuditEvent.model_validate_json(row["payload"]) for row in rows]

    def event_sequence(self, audit_id: str, event_id: str) -> int | None:
        with self._lock:
            row = self._connection.execute(
                "SELECT sequence FROM events WHERE audit_id = ? AND event_id = ?",
                (audit_id, event_id),
            ).fetchone()
        return int(row["sequence"]) if row else None

    def acquire_audit_lease(self, audit_id: str, owner: str, lease_seconds: int) -> bool:
        with self._lock:
            audit = self.get(Audit, audit_id)
            if audit is None:
                return False
            now = utc_now()
            if (
                audit.lease_owner
                and audit.lease_owner != owner
                and audit.lease_expires_at
                and audit.lease_expires_at > now
            ):
                return False
            audit.lease_owner = owner
            audit.lease_expires_at = now + timedelta(seconds=lease_seconds)
            self.put(audit)
            return True

    def release_audit_lease(self, audit_id: str, owner: str) -> None:
        with self._lock:
            audit = self.get(Audit, audit_id)
            if audit is None or audit.lease_owner != owner:
                return
            audit.lease_owner = None
            audit.lease_expires_at = None
            self.put(audit)

    def enqueue(self, message: JobMessage) -> bool:
        with self._lock, self._connection:
            cursor = self._connection.execute(
                """
                INSERT OR IGNORE INTO jobs(
                    audit_id, idempotency_key, payload, status, available_at
                ) VALUES (?, ?, ?, 'queued', ?)
                """,
                (
                    message.audit_id,
                    message.idempotency_key,
                    message.model_dump_json(),
                    utc_now().isoformat(),
                ),
            )
        return cursor.rowcount == 1

    def claim_job(self, lease_seconds: int) -> tuple[int, JobMessage] | None:
        now = utc_now()
        lease_until = now + timedelta(seconds=lease_seconds)
        with self._lock, self._connection:
            row = self._connection.execute(
                """
                SELECT job_id, payload FROM jobs
                WHERE (status = 'queued' AND available_at <= ?)
                   OR (status = 'leased' AND lease_until < ?)
                ORDER BY job_id
                LIMIT 1
                """,
                (now.isoformat(), now.isoformat()),
            ).fetchone()
            if row is None:
                return None
            cursor = self._connection.execute(
                """
                UPDATE jobs
                SET status = 'leased', attempts = attempts + 1, lease_until = ?
                WHERE job_id = ? AND (status = 'queued' OR lease_until < ?)
                """,
                (lease_until.isoformat(), row["job_id"], now.isoformat()),
            )
            if cursor.rowcount != 1:
                return None
        return int(row["job_id"]), JobMessage.model_validate_json(row["payload"])

    def extend_job(self, job_id: int, lease_seconds: int) -> None:
        with self._lock, self._connection:
            self._connection.execute(
                "UPDATE jobs SET lease_until = ? WHERE job_id = ? AND status = 'leased'",
                ((utc_now() + timedelta(seconds=lease_seconds)).isoformat(), job_id),
            )

    def acknowledge_job(self, job_id: int) -> None:
        with self._lock, self._connection:
            self._connection.execute(
                "UPDATE jobs SET status = 'complete', lease_until = NULL WHERE job_id = ?",
                (job_id,),
            )

    def release_job(self, job_id: int, delay_seconds: float = 0) -> None:
        available = utc_now() + timedelta(seconds=delay_seconds)
        with self._lock, self._connection:
            self._connection.execute(
                """
                UPDATE jobs SET status = 'queued', available_at = ?, lease_until = NULL
                WHERE job_id = ?
                """,
                (available.isoformat(), job_id),
            )

    def fail_job(self, job_id: int, error_code: str, max_attempts: int = 3) -> str:
        with self._lock, self._connection:
            row = self._connection.execute(
                "SELECT attempts FROM jobs WHERE job_id = ?", (job_id,)
            ).fetchone()
            if row is None:
                raise KeyError(job_id)
            status = "dead" if int(row["attempts"]) >= max_attempts else "queued"
            self._connection.execute(
                """
                UPDATE jobs
                SET status = ?, lease_until = NULL, last_error = ?, available_at = ?
                WHERE job_id = ?
                """,
                (
                    status,
                    error_code[:200],
                    (utc_now() + timedelta(seconds=1)).isoformat(),
                    job_id,
                ),
            )
        return status

    def job_rows(self, audit_id: str | None = None) -> Sequence[dict[str, object]]:
        query = "SELECT * FROM jobs"
        parameters: tuple[str, ...] = ()
        if audit_id is not None:
            query += " WHERE audit_id = ?"
            parameters = (audit_id,)
        query += " ORDER BY job_id"
        with self._lock:
            rows = self._connection.execute(query, parameters).fetchall()
        return [dict(row) for row in rows]

    def delete_project(self, project_id: str) -> None:
        artifact_ids = [artifact.artifact_id for artifact in self.list(Artifact, project_id)]
        audits = [audit for audit in self.list(Audit) if audit.project_id == project_id]
        with self._lock, self._connection:
            for audit in audits:
                self._connection.execute("DELETE FROM events WHERE audit_id = ?", (audit.audit_id,))
                self._connection.execute("DELETE FROM jobs WHERE audit_id = ?", (audit.audit_id,))
                self._connection.execute(
                    "DELETE FROM objects WHERE parent_id = ?", (audit.audit_id,)
                )
                owned_ids = {
                    "hypothesis": audit.hypothesis_ids,
                    "evidence": audit.evidence_ids,
                    "finding": audit.finding_ids,
                    "correction": audit.correction_ids,
                    "question": audit.question_ids,
                }
                for kind, object_ids in owned_ids.items():
                    for object_id in object_ids:
                        self._connection.execute(
                            "DELETE FROM objects WHERE kind = ? AND object_id = ?",
                            (kind, object_id),
                        )
                self._connection.execute(
                    "DELETE FROM objects WHERE kind = 'audit' AND object_id = ?", (audit.audit_id,)
                )
            for artifact_id in artifact_ids:
                self._connection.execute(
                    "DELETE FROM objects WHERE kind = 'artifact' AND object_id = ?", (artifact_id,)
                )
            self._connection.execute(
                "DELETE FROM objects WHERE kind = 'project' AND object_id = ?", (project_id,)
            )

    def seed(self, models: Iterable[BaseModel]) -> None:
        for model in models:
            self.put(model)
