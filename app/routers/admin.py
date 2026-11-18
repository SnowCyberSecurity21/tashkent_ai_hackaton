from __future__ import annotations

import time
from functools import lru_cache
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from pydantic import BaseModel
from sqlmodel import Session, select

from .. import audit, config, llm
from ..auth import Actor, require_roles
from ..db import get_session
from ..models import AuditLog, Document, SafetyRule
from .maker import pdf_text

router = APIRouter(prefix="/api", tags=["admin"])
staff = require_roles("pharmacist")
LEAFLET = config.DATA_DIR / "leaflets" / "tylol-hot.pdf"


@lru_cache(maxsize=1)
def bundled_leaflet_text() -> str:
    if not LEAFLET.exists():
        return ""
    return pdf_text(LEAFLET.read_bytes())


def _rule_out(r: SafetyRule) -> dict:
    return r.model_dump(mode="json")


@router.post("/admin/llm/leaflet-rules")
async def leaflet_rules(fresh: bool = Query(False), file: Optional[UploadFile] = File(None),
                        session: Session = Depends(get_session), actor: Actor = Depends(staff)):
    t0 = time.time()
    if file is not None:
        data = await file.read()
        if not data.startswith(b"%PDF"):
            raise HTTPException(415, "Faqat PDF fayl qabul qilinadi")
        text, origin = pdf_text(data), file.filename
    else:
        text, origin = bundled_leaflet_text(), "data/leaflets/tylol-hot.pdf"
    res = llm.leaflet_to_rules(text, live=bool(text), force=True, use_cache=not fresh)
    # replace previous *unapproved* proposals; approved rules stay in force
    for old in session.exec(select(SafetyRule).where(SafetyRule.origin == "llm", SafetyRule.approved == False)).all():  # noqa: E712
        session.delete(old)
    rows = []
    for r in res["data"]:
        row = SafetyRule(kind=r["kind"], a=r["a"], b=r.get("b"), threshold_mg=r.get("threshold_mg"), severity=r["severity"],
                         message_uz=r["message_uz"], source=r["source"], approved=False, origin="llm")
        session.add(row)
        rows.append(row)
    session.commit()
    for row in rows:
        session.refresh(row)
    out_rules = [_rule_out(r) for r in rows]  # serialize before audit.log commits (commit expires rows)
    audit.log(session, actor, "llm.leaflet_rules", f"rules:{len(rows)}")
    return {"rules": out_rules, "source": res["source"], "model": res["model"], "error": res["error"],
            "document": origin, "leaflet_found": bool(text), "elapsed_ms": round((time.time() - t0) * 1000),
            "note_uz": "Taklif qilingan qoidalar farmatsevt tasdiqlamaguncha ishlamaydi."}


class CoaIn(BaseModel):
    document_id: int


@router.post("/admin/llm/coa")
def coa_extract(body: CoaIn, session: Session = Depends(get_session), actor: Actor = Depends(staff)):
    doc = session.get(Document, body.document_id)
    if not doc or not doc.path:
        raise HTTPException(404, "Hujjat topilmadi")
    path = config.ROOT / doc.path
    if not path.exists():
        raise HTTPException(404, "Hujjat fayli topilmadi")
    res = llm.extract_coa(pdf_text(path.read_bytes()), force=True)
    audit.log(session, actor, "llm.extract_coa", f"document:{doc.id}")
    return {"document_id": doc.id, **res}


@router.get("/rules")
def list_rules(origin: Optional[str] = None, approved: Optional[bool] = None, session: Session = Depends(get_session),
               actor: Actor = Depends(staff)):
    q = select(SafetyRule).order_by(SafetyRule.id.desc())
    if origin:
        q = q.where(SafetyRule.origin == origin)
    if approved is not None:
        q = q.where(SafetyRule.approved == approved)
    return [_rule_out(r) for r in session.exec(q).all()]


@router.post("/rules/{rule_id}/approve")
def approve_rule(rule_id: int, session: Session = Depends(get_session), actor: Actor = Depends(staff)):
    r = session.get(SafetyRule, rule_id)
    if not r:
        raise HTTPException(404, "Qoida topilmadi")
    r.approved = True
    session.add(r)
    audit.log(session, actor, "rule.approve", f"rule:{r.id}")
    session.refresh(r)
    return _rule_out(r)


@router.post("/rules/{rule_id}/reject")
def reject_rule(rule_id: int, session: Session = Depends(get_session), actor: Actor = Depends(staff)):
    r = session.get(SafetyRule, rule_id)
    if not r:
        raise HTTPException(404, "Qoida topilmadi")
    if r.origin != "llm":
        raise HTTPException(409, "Faqat AI taklif qilgan qoidani rad etish mumkin")
    session.delete(r)
    audit.log(session, actor, "rule.reject", f"rule:{rule_id}")
    return {"ok": True}


@router.get("/admin/audit")
def audit_log(limit: int = 50, session: Session = Depends(get_session), actor: Actor = Depends(staff)):
    rows = session.exec(select(AuditLog).order_by(AuditLog.id.desc()).limit(limit)).all()
    return [r.model_dump(mode="json") for r in rows]


@router.post("/admin/reset-demo")
def reset_demo(session: Session = Depends(get_session), actor: Actor = Depends(staff)):
    """One-click reset between mentor demos. Keeps LlmCache, products and seed rules (see scripts/seed.reset_demo)."""
    from scripts.seed import reset_demo as do_reset

    try:
        removed = do_reset(session)
    except RuntimeError as exc:
        raise HTTPException(409, str(exc))
    audit.log(session, actor, "demo.reset", "demo")
    return {"ok": True, "removed": removed, "message_uz": "Demo boshlang'ich holatga qaytarildi."}
