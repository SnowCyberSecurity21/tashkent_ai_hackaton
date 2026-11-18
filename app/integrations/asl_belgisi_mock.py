"""Asl Belgisi (national drug-marking system) client — MOCK.

# MOCK: there is no public Asl Belgisi API available to us. This client has the shape of a real
# HTTP client (base URL, token, `check()` returning the same structure the real service would), but it
# reads the seeded `Code` / `Batch` / `Product` tables instead of calling the network.
# To integrate for real: replace `_lookup()` with an HTTP call and keep `check()`'s return shape.
"""
from __future__ import annotations

from typing import Optional

from sqlmodel import Session, select

from ..models import Batch, Code, Product


class AslBelgisiClient:
    base_url = "https://aslbelgisi.uz/api/v1"  # MOCK: illustrative only, never called

    def __init__(self, session: Session, token: Optional[str] = None):
        self.session = session
        self.token = token

    def _lookup(self, gtin: str, serial: Optional[str]):
        product = self.session.exec(select(Product).where(Product.gtin == gtin)).first()
        code = self.session.get(Code, serial) if serial else None
        return product, code

    def check(self, gtin: str, serial: Optional[str] = None, batch: Optional[str] = None) -> dict:
        """Return {authentic, reg_status, conformity_expired, recalled, raw_official, code_status, batch_no}.

        authentic: True (code registered for this GTIN), False (unknown/mismatched serial),
        None (no serial was supplied, e.g. EAN-13 only — authenticity cannot be checked).
        """
        product, code = self._lookup(gtin, serial)
        if product is None:
            return {"authentic": False, "reg_status": "unknown", "conformity_expired": None, "recalled": None,
                    "raw_official": {}, "code_status": "unknown", "batch_no": batch, "found": False}

        authentic: Optional[bool]
        if serial is None:
            authentic, code_status = None, None
        elif code is None or code.gtin != gtin:
            authentic, code_status = False, "unknown"
        else:
            authentic, code_status = code.status != "unknown", code.status

        batch_no = (code.batch_no if code else None) or batch
        batch_row = None
        if batch_no:
            batch_row = self.session.exec(
                select(Batch).where(Batch.product_id == product.id, Batch.batch_no == batch_no)
            ).first()
        recalled = bool((batch_row and batch_row.recalled) or code_status == "withdrawn")
        return {
            "authentic": authentic,
            "reg_status": product.reg_status,
            "conformity_expired": product.conformity_expired,
            "recalled": recalled,
            "raw_official": product.raw_official or {},
            "code_status": code_status,
            "batch_no": batch_no,
            "found": True,
        }
