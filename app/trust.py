"""Trust Index: 0.25R + 0.25L + 0.20M + 0.15F + 0.15U (each 0–100).

`compute()` is a pure function over `TrustInputs` (unit-tested); `gather()` collects inputs from the DB.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Optional

from sqlmodel import Session, func, select

from .models import Batch, Document, LabResult, Product, Rating, Report, Scan

WEIGHTS = {"R": 0.25, "L": 0.25, "M": 0.20, "F": 0.15, "U": 0.15}
LABELS = {"R": "Rasmiy holat", "L": "Laboratoriya", "M": "Markirovka", "F": "Farmakonazorat", "U": "Baholar"}
COLOR_WORD = {"green": "Yashil", "amber": "Sariq", "red": "Qizil", "gray": "Kulrang"}


@dataclass
class TrustInputs:
    reg_status: str = "registered"
    conformity_expired: bool = False
    gmp: bool = True
    bioequivalence: Optional[bool] = None
    is_original: bool = False
    has_coa: bool = False
    coa_out_count: int = 0
    coa_batch: Optional[str] = None
    coa_date: Optional[str] = None
    coa_other_batch: bool = False
    clone: bool = False
    recalled: bool = False
    code_unknown: bool = False
    serious_reports: int = 0
    total_reports: int = 0
    ratings: list[int] = field(default_factory=list)
    scan_count: int = 0
    as_of: str = field(default_factory=lambda: date.today().isoformat())


def _comp(key: str, score: float, reason: str, source: str, as_of: str) -> dict:
    score = max(0, min(100, round(score)))
    return {"key": key, "label": LABELS[key], "score": score, "weight": WEIGHTS[key],
            "reason": reason, "source": source, "date": as_of}


def compute(t: TrustInputs) -> dict:
    # R — official status
    r, parts = 0, []
    if t.reg_status == "registered":
        r += 40
        parts.append("ro'yxatdan o'tgan (+40)")
    else:
        parts.append("ro'yxatdan o'tish amal qilmaydi (0)")
    if not t.conformity_expired:
        r += 30
        parts.append("muvofiqlik hujjati amal qiladi (+30)")
    else:
        parts.append("muvofiqlik hujjati muddati tugagan (0)")
    if t.gmp:
        r += 30
        parts.append("GMP sertifikati bor (+30)")
    else:
        parts.append("GMP ma'lumoti yo'q (0)")
    R = _comp("R", r, "; ".join(parts).capitalize(), "Asl Belgisi rasmiy ma'lumoti (demo)", t.as_of)

    # L — laboratory
    if not t.has_coa:
        L = _comp("L", 0, "Laboratoriya sertifikati (CoA) hali yuklanmagan", "Mezon hujjatlar bazasi", t.as_of)
    else:
        l, parts = 40, ["CoA mavjud (+40)"]
        if t.coa_out_count == 0:
            l += 40
            parts.append("barcha ko'rsatkichlar me'yorda (+40)")
        else:
            parts.append(f"{t.coa_out_count} ta ko'rsatkich me'yordan tashqarida (0)")
        if t.is_original or t.bioequivalence is None:
            l += 20
            parts.append("original preparat — bioekvivalentlik talab qilinmaydi (+20)")
        elif t.bioequivalence:
            l += 20
            parts.append("bioekvivalentlik tasdiqlangan (+20)")
        else:
            parts.append("bioekvivalentlik tasdiqlanmagan (0)")
        src = f"CoA, partiya {t.coa_batch}" + (" (boshqa partiya)" if t.coa_other_batch else "")
        L = _comp("L", l, "; ".join(parts).capitalize(), src, t.coa_date or t.as_of)

    # M — marking
    if t.recalled:
        M = _comp("M", 0, "Partiya qaytarib olingan (0)", "Asl Belgisi rasmiy ma'lumoti (demo)", t.as_of)
    else:
        m, parts = 100, []
        if t.clone:
            m -= 60
            parts.append("klon kod: seriya boshqa shaharda ham skanerlangan (−60)")
        if t.code_unknown:
            m -= 60
            parts.append("kod rasmiy bazada topilmadi (−60)")
        reason = "; ".join(parts).capitalize() if parts else "Kod haqiqiy, klon belgisi yo'q"
        M = _comp("M", m, reason, "Markirovka tekshiruvi (Asl Belgisi demo) va Mezon skanlari", t.as_of)

    # F — pharmacovigilance
    if t.total_reports == 0:
        F = _comp("F", 70, "Xabarlar hali yo'q — boshlang'ich qiymat 70", "Mezon farmakonazorat xabarlari", t.as_of)
    else:
        F = _comp("F", 100 - 10 * t.serious_reports,
                  f"{t.total_reports} ta xabar, shundan {t.serious_reports} tasi jiddiy (har biri −10)",
                  "Mezon farmakonazorat xabarlari", t.as_of)

    # U — ratings
    if not t.ratings:
        U = _comp("U", 60, "Baholar hali yo'q — boshlang'ich qiymat 60", "Farmatsevt va bemor baholari", t.as_of)
    else:
        avg = sum(t.ratings) / len(t.ratings)
        U = _comp("U", avg * 20, f"{len(t.ratings)} ta baho, o'rtacha {avg:.1f} / 5", "Farmatsevt va bemor baholari", t.as_of)

    comps = [R, L, M, F, U]
    score = round(sum(c["score"] * c["weight"] for c in comps))
    if not t.has_coa and t.scan_count < 5:
        color, label = "gray", "Ma'lumot yetarli emas"
    elif score >= 80:
        color, label = "green", "Ishonchli"
    elif score >= 60:
        color, label = "amber", "O'rtacha"
    else:
        color, label = "red", "Past"
    return {
        "score": score, "color": color, "color_word": COLOR_WORD[color], "label": label,
        "components": comps,
        "sources": sorted({c["source"] for c in comps}),
        "formula": "0.25·R + 0.25·L + 0.20·M + 0.15·F + 0.15·U",
    }


def coa_for(session: Session, product: Product, batch_no: Optional[str]):
    """Return (document, results, other_batch) preferring the scanned batch, else the newest CoA."""
    docs = session.exec(
        select(Document).where(Document.product_id == product.id, Document.type == "CoA",
                               Document.verified == True).order_by(Document.ts.desc())  # noqa: E712
    ).all()
    if not docs:
        return None, [], False
    doc = next((d for d in docs if batch_no and d.batch_no == batch_no), None)
    other = False
    if doc is None:
        doc, other = docs[0], bool(batch_no)
    results = session.exec(select(LabResult).where(LabResult.document_id == doc.id)).all()
    return doc, results, other


def gather(session: Session, product: Product, batch: Optional[Batch] = None, clone: bool = False,
           code_unknown: bool = False, recalled: Optional[bool] = None) -> TrustInputs:
    batch_no = batch.batch_no if batch else None
    doc, results, other = coa_for(session, product, batch_no)
    reports = session.exec(select(Report).where(Report.product_id == product.id)).all()
    ratings = [r.stars for r in session.exec(select(Rating).where(Rating.product_id == product.id)).all()]
    scan_count = session.exec(select(func.count()).select_from(Scan).where(Scan.gtin == product.gtin)).one()
    if recalled is None:
        recalled = bool(batch and batch.recalled)
    coa_date = None
    if doc is not None:
        coa_date = doc.ts.date().isoformat()
    return TrustInputs(
        reg_status=product.reg_status, conformity_expired=product.conformity_expired, gmp=product.gmp,
        bioequivalence=product.bioequivalence, is_original=product.is_original,
        has_coa=doc is not None, coa_out_count=sum(1 for r in results if r.status == "out"),
        coa_batch=doc.batch_no if doc else None, coa_date=coa_date, coa_other_batch=other,
        clone=clone, recalled=recalled, code_unknown=code_unknown,
        serious_reports=sum(1 for r in reports if r.severity == "danger"), total_reports=len(reports),
        ratings=ratings, scan_count=int(scan_count),
    )


def product_trust(session: Session, product: Product, **kw) -> dict:
    return compute(gather(session, product, **kw))
