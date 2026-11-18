"""Shared DB helpers for routers."""
from __future__ import annotations

from fastapi import HTTPException
from sqlmodel import Session, select

from .. import safety
from ..db import classes, conditions
from ..models import Patient, Product, Regimen, SafetyRule
from ..passport import summarize


def get_product(session: Session, product_id: int) -> Product:
    p = session.get(Product, product_id)
    if not p:
        raise HTTPException(404, "Dori topilmadi")
    return p


def approved_rules(session: Session) -> list[dict]:
    rows = session.exec(select(SafetyRule).where(SafetyRule.approved == True)).all()  # noqa: E712
    return [r.model_dump() for r in rows]


def product_ref(p: Product) -> dict:
    return {"id": p.id, "trade_name": p.trade_name, "inn_list": p.inn_list}


def regimen_items(session: Session, patient_id: int) -> list[dict]:
    rows = session.exec(select(Regimen).where(Regimen.patient_id == patient_id).order_by(Regimen.id)).all()
    out = []
    for r in rows:
        p = session.get(Product, r.product_id)
        if p:
            out.append({"id": r.id, "product": product_ref(p), "units_per_day": r.units_per_day, "_summary": summarize(p)})
    return out


def patient_dict(p: Patient) -> dict:
    return {"id": p.id, "name": p.name, "conditions": list(p.conditions or []), "alcohol": p.alcohol}


def condition_labels() -> dict[str, str]:
    return {c["key"]: c["label_uz"] for c in conditions()}


def evaluate_for(session: Session, patient: Patient, candidate: dict | None = None) -> dict:
    items = regimen_items(session, patient.id)
    engine_items = [{"product": it["product"], "units_per_day": it["units_per_day"]} for it in items]
    if candidate is None:
        return safety.evaluate(patient_dict(patient), engine_items, approved_rules(session), classes(), None, condition_labels())
    return safety.what_if(patient_dict(patient), engine_items, approved_rules(session), classes(), candidate, condition_labels())
