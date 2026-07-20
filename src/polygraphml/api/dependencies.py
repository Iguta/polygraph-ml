from __future__ import annotations

from typing import Annotated, cast

from fastapi import Depends, Header, Request

from polygraphml.api.container import AppContainer
from polygraphml.domain.models import Audit, Project, Question, Session
from polygraphml.errors import PolygraphError


def get_container(request: Request) -> AppContainer:
    return cast(AppContainer, request.app.state.container)


def get_session(
    authorization: Annotated[str | None, Header()] = None,
    container: AppContainer = Depends(get_container),
) -> Session:
    if not authorization or not authorization.startswith("Bearer "):
        raise PolygraphError("INVALID_REQUEST", "A bearer session token is required.", 401)
    session = container.repository.get_session_by_token(authorization.removeprefix("Bearer "))
    if session is None:
        raise PolygraphError("INVALID_REQUEST", "Session is invalid or expired.", 401)
    return session


def owned_project(
    project_id: str,
    session: Session = Depends(get_session),
    container: AppContainer = Depends(get_container),
) -> Project:
    project = container.repository.get(Project, project_id)
    if project is None or project.session_id != session.session_id:
        raise PolygraphError("PROJECT_NOT_FOUND", "Project was not found.", 404)
    return project


def owned_audit(
    audit_id: str,
    session: Session = Depends(get_session),
    container: AppContainer = Depends(get_container),
) -> Audit:
    audit = container.repository.get(Audit, audit_id)
    if audit is None or audit.session_id != session.session_id:
        raise PolygraphError("AUDIT_NOT_FOUND", "Audit was not found.", 404)
    return audit


def audit_question(
    question_id: str,
    audit: Audit,
    container: AppContainer,
) -> Question:
    question = container.repository.get(Question, question_id)
    if question is None or question.audit_id != audit.audit_id:
        raise PolygraphError("QUESTION_NOT_FOUND", "Question was not found.", 404)
    return question
