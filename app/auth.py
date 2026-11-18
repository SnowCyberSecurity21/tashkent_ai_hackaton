"""Demo auth. One dependency (`get_actor`) so a real login can replace it later.

# MOCK: in DEMO_MODE the role comes from the `X-Demo-Role` header. Without DEMO_MODE only the
# patient role is available until a real login (e.g. Telegram initData HMAC) is plugged in here.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from fastapi import Depends, Header, HTTPException
from sqlmodel import Session, select

from . import config
from .db import get_session
from .models import Patient

ROLES = ("patient", "pharmacist", "maker", "admin")
STAFF_NAMES = {"pharmacist": "Farmatsevt (demo)", "maker": "Ishlab chiqaruvchi (demo)", "admin": "Admin (demo)"}


@dataclass
class Actor:
    role: str
    name: str
    patient_id: Optional[int] = None


def get_actor(
    x_demo_role: Optional[str] = Header(default=None),
    session: Session = Depends(get_session),
) -> Actor:
    role = (x_demo_role or "patient").strip().lower()
    if role not in ROLES:
        raise HTTPException(400, "Noma'lum rol")
    if role != "patient" and not config.DEMO_MODE:
        raise HTTPException(401, "Kirish talab qilinadi")
    if role == "patient":
        patient = session.exec(select(Patient).order_by(Patient.id)).first()
        if not patient:
            raise HTTPException(503, "Demo bemor topilmadi. `python scripts/seed.py` ni ishga tushiring.")
        return Actor(role="patient", name=patient.name, patient_id=patient.id)
    return Actor(role=role, name=STAFF_NAMES[role])


def require_roles(*roles: str):
    def dep(actor: Actor = Depends(get_actor)) -> Actor:
        if actor.role != "admin" and actor.role not in roles:
            raise HTTPException(403, "Bu amal uchun ruxsat yo'q")
        return actor

    return dep
