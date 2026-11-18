from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlmodel import Session

from ..auth import Actor, require_roles
from ..db import get_session
from ..passport import summarize
from .common import evaluate_for, get_product, product_ref
from .patient import _patient

router = APIRouter(prefix="/api", tags=["safety"])


@router.get("/safety")
def current_safety(session: Session = Depends(get_session), actor: Actor = Depends(require_roles("patient"))):
    return evaluate_for(session, _patient(session, actor))


class CheckIn(BaseModel):
    product_id: int
    units_per_day: int = Field(default=1, ge=1, le=12)


@router.post("/safety/check")
def what_if(body: CheckIn, session: Session = Depends(get_session), actor: Actor = Depends(require_roles("patient"))):
    patient = _patient(session, actor)
    prod = get_product(session, body.product_id)
    res = evaluate_for(session, patient, {"product": product_ref(prod), "units_per_day": body.units_per_day})
    res["candidate"] = {**summarize(prod), "units_per_day": body.units_per_day}
    return res
