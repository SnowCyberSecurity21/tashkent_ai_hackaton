"""Audit log: every write action is recorded."""
from __future__ import annotations

from sqlmodel import Session

from .models import AuditLog


def log(session: Session, actor, action: str, entity: str, commit: bool = True) -> None:
    session.add(AuditLog(actor=actor.name, role=actor.role, action=action, entity=entity))
    if commit:
        session.commit()
