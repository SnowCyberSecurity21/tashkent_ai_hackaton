from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from .. import audit, llm
from ..auth import Actor, get_actor
from ..db import get_session
from ..models import Product, Rating, Report
from .common import get_product

router = APIRouter(prefix="/api", tags=["reports"])
SEV_UZ = {"info": "Yengil", "warn": "O'rtacha", "danger": "Jiddiy"}


class ReportIn(BaseModel):
    product_id: int
    batch_no: Optional[str] = Field(default=None, max_length=30)
    text: str = Field(min_length=3, max_length=2000)


@router.post("/reports")
def create_report(body: ReportIn, session: Session = Depends(get_session), actor: Actor = Depends(get_actor)):
    get_product(session, body.product_id)
    res = llm.classify_report(body.text)
    rep = Report(product_id=body.product_id, batch_no=body.batch_no, text=body.text.strip(),
                 category=res["data"]["category"], severity=res["data"]["severity"],
                 classified_by="ai" if res["source"] in ("live", "cache") else "rules")
    session.add(rep)
    session.commit()
    session.refresh(rep)
    audit.log(session, actor, "report.create", f"report:{rep.id}")
    return {"id": rep.id, "category": rep.category, "severity": rep.severity, "severity_uz": SEV_UZ[rep.severity],
            "classified_by": rep.classified_by, "model": res["model"],
            "message_uz": "Rahmat! Xabaringiz qabul qilindi va farmakonazorat bo'limiga yuborildi."}


@router.get("/reports")
def list_reports(limit: int = 20, session: Session = Depends(get_session), actor: Actor = Depends(get_actor)):
    if actor.role == "patient":
        raise HTTPException(403, "Bu amal uchun ruxsat yo'q")
    rows = session.exec(select(Report).order_by(Report.ts.desc()).limit(limit)).all()
    out = []
    for r in rows:
        p = session.get(Product, r.product_id)
        out.append({"id": r.id, "product": p.trade_name if p else "?", "manufacturer": p.manufacturer if p else "?",
                    "batch_no": r.batch_no, "text": r.text, "category": r.category, "severity": r.severity,
                    "severity_uz": SEV_UZ.get(r.severity, r.severity), "classified_by": r.classified_by,
                    "ts": r.ts.isoformat(timespec="minutes")})
    return out


class RatingIn(BaseModel):
    product_id: int
    stars: int = Field(ge=1, le=5)


@router.post("/ratings")
def rate(body: RatingIn, session: Session = Depends(get_session), actor: Actor = Depends(get_actor)):
    get_product(session, body.product_id)
    role = "pharmacist" if actor.role == "pharmacist" else "patient"
    session.add(Rating(product_id=body.product_id, role=role, stars=body.stars))
    audit.log(session, actor, "rating.create", f"product:{body.product_id}")
    return {"ok": True, "message_uz": "Bahoyingiz uchun rahmat!"}
