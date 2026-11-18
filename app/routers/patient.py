from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from .. import audit
from ..auth import Actor, require_roles
from ..db import conditions, get_session
from ..models import Patient, Regimen
from .common import get_product, patient_dict, regimen_items

router = APIRouter(prefix="/api", tags=["patient"])
patient_only = require_roles("patient")


def _patient(session: Session, actor: Actor) -> Patient:
    p = session.get(Patient, actor.patient_id) if actor.patient_id else None
    if not p:
        raise HTTPException(404, "Bemor profili topilmadi")
    return p


@router.get("/patient")
def get_patient(session: Session = Depends(get_session), actor: Actor = Depends(patient_only)):
    return patient_dict(_patient(session, actor))


class PatientIn(BaseModel):
    name: Optional[str] = Field(default=None, max_length=60)
    conditions: Optional[list[str]] = None
    alcohol: Optional[bool] = None


@router.put("/patient")
def put_patient(body: PatientIn, session: Session = Depends(get_session), actor: Actor = Depends(patient_only)):
    p = _patient(session, actor)
    if body.name is not None:
        name = body.name.strip()
        if not name:
            raise HTTPException(422, "Ism bo'sh bo'lmasin")
        p.name = name
    if body.conditions is not None:
        valid = {c["key"] for c in conditions()}
        bad = [c for c in body.conditions if c not in valid]
        if bad:
            raise HTTPException(422, f"Noma'lum holat: {', '.join(bad)}")
        p.conditions = list(dict.fromkeys(body.conditions))
    if body.alcohol is not None:
        p.alcohol = body.alcohol
    session.add(p)
    audit.log(session, actor, "patient.update", f"patient:{p.id}")
    session.refresh(p)
    return patient_dict(p)


@router.get("/regimen")
def get_regimen(session: Session = Depends(get_session), actor: Actor = Depends(patient_only)):
    p = _patient(session, actor)
    return [{"id": it["id"], "units_per_day": it["units_per_day"], "product": it["_summary"]}
            for it in regimen_items(session, p.id)]


class RegimenIn(BaseModel):
    product_id: int
    units_per_day: int = Field(default=1, ge=1, le=12)


@router.post("/regimen")
def add_regimen(body: RegimenIn, session: Session = Depends(get_session), actor: Actor = Depends(patient_only)):
    p = _patient(session, actor)
    prod = get_product(session, body.product_id)
    row = session.exec(select(Regimen).where(Regimen.patient_id == p.id, Regimen.product_id == prod.id)).first()
    if row:
        row.units_per_day = min(12, row.units_per_day + body.units_per_day)
    else:
        row = Regimen(patient_id=p.id, product_id=prod.id, units_per_day=body.units_per_day)
    session.add(row)
    audit.log(session, actor, "regimen.add", f"product:{prod.id}")
    return get_regimen(session, actor)


class UnitsIn(BaseModel):
    units_per_day: int = Field(ge=1, le=12)


@router.patch("/regimen/{item_id}")
def update_regimen(item_id: int, body: UnitsIn, session: Session = Depends(get_session), actor: Actor = Depends(patient_only)):
    p = _patient(session, actor)
    row = session.get(Regimen, item_id)
    if not row or row.patient_id != p.id:
        raise HTTPException(404, "Dori ro'yxatda topilmadi")
    row.units_per_day = body.units_per_day
    session.add(row)
    audit.log(session, actor, "regimen.update", f"regimen:{item_id}")
    return get_regimen(session, actor)


@router.delete("/regimen/{item_id}")
def delete_regimen(item_id: int, session: Session = Depends(get_session), actor: Actor = Depends(patient_only)):
    p = _patient(session, actor)
    row = session.get(Regimen, item_id)
    if not row or row.patient_id != p.id:
        raise HTTPException(404, "Dori ro'yxatda topilmadi")
    session.delete(row)
    audit.log(session, actor, "regimen.delete", f"regimen:{item_id}")
    return get_regimen(session, actor)
