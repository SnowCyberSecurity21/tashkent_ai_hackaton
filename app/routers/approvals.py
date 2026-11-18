from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from .. import audit
from ..analogs import composition_checklist
from ..auth import Actor, get_actor, require_roles
from ..db import get_session
from ..models import Approval, Patient
from ..passport import summarize
from ..trust import product_trust
from .common import get_product

router = APIRouter(prefix="/api", tags=["approvals"])


def _out(session: Session, a: Approval) -> dict:
    f, t = get_product(session, a.from_product_id), get_product(session, a.to_product_id)
    pat = session.get(Patient, a.patient_id)
    tf, tt = product_trust(session, f), product_trust(session, t)
    checklist = composition_checklist(f, t)
    return {
        "id": a.id, "status": a.status, "note": a.note, "ts": a.ts.isoformat(timespec="seconds"),
        "decided_at": a.decided_at.isoformat(timespec="seconds") if a.decided_at else None,
        "patient": {"id": pat.id, "name": pat.name, "conditions": pat.conditions} if pat else None,
        "from": {**summarize(f), "trust": {"score": tf["score"], "color": tf["color"], "color_word": tf["color_word"]}},
        "to": {**summarize(t), "trust": {"score": tt["score"], "color": tt["color"], "color_word": tt["color_word"]}},
        "composition_match": all(c["ok"] for c in checklist), "checklist": checklist,
        "savings_uzs": f.price_uzs - t.price_uzs,
    }


class ApprovalIn(BaseModel):
    from_product_id: int
    to_product_id: int
    note: Optional[str] = Field(default=None, max_length=300)


@router.post("/approvals")
def create_approval(body: ApprovalIn, session: Session = Depends(get_session), actor: Actor = Depends(require_roles("patient"))):
    get_product(session, body.from_product_id)
    get_product(session, body.to_product_id)
    existing = session.exec(select(Approval).where(
        Approval.patient_id == actor.patient_id, Approval.from_product_id == body.from_product_id,
        Approval.to_product_id == body.to_product_id, Approval.status == "pending")).first()
    if existing:
        return _out(session, existing)
    a = Approval(patient_id=actor.patient_id, from_product_id=body.from_product_id, to_product_id=body.to_product_id,
                 note=body.note)
    session.add(a)
    session.commit()
    session.refresh(a)
    audit.log(session, actor, "approval.create", f"approval:{a.id}")
    return _out(session, a)


@router.get("/approvals")
def list_approvals(status: Optional[str] = None, session: Session = Depends(get_session), actor: Actor = Depends(get_actor)):
    q = select(Approval).order_by(Approval.ts.desc())
    if actor.role == "patient":
        q = q.where(Approval.patient_id == actor.patient_id)
    elif actor.role not in ("pharmacist", "admin"):
        raise HTTPException(403, "Bu amal uchun ruxsat yo'q")
    if status:
        q = q.where(Approval.status == status)
    return [_out(session, a) for a in session.exec(q).all()]


@router.get("/approvals/{approval_id}")
def get_approval(approval_id: int, session: Session = Depends(get_session), actor: Actor = Depends(get_actor)):
    a = session.get(Approval, approval_id)
    if not a or (actor.role == "patient" and a.patient_id != actor.patient_id):
        raise HTTPException(404, "So'rov topilmadi")
    return _out(session, a)


class DecideIn(BaseModel):
    decision: Literal["approved", "rejected"]
    note: Optional[str] = Field(default=None, max_length=300)


@router.post("/approvals/{approval_id}/decide")
def decide(approval_id: int, body: DecideIn, session: Session = Depends(get_session),
           actor: Actor = Depends(require_roles("pharmacist"))):
    a = session.get(Approval, approval_id)
    if not a:
        raise HTTPException(404, "So'rov topilmadi")
    if a.status != "pending":
        raise HTTPException(409, "Bu so'rov allaqachon ko'rib chiqilgan")
    a.status, a.decided_at = body.decision, datetime.now()
    if body.note:
        a.note = body.note
    session.add(a)
    audit.log(session, actor, f"approval.{body.decision}", f"approval:{a.id}")
    session.refresh(a)
    return _out(session, a)
