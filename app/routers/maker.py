from __future__ import annotations

import hashlib
import re
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlmodel import Session, select

from .. import audit, config, llm
from ..auth import Actor, require_roles
from ..db import get_session
from ..models import Batch, Document, Product, Report, Scan
from ..trust import product_trust
from .common import get_product

router = APIRouter(prefix="/api/maker", tags=["maker"])
maker_only = require_roles("maker", "pharmacist")


@router.get("/manufacturers")
def manufacturers(session: Session = Depends(get_session), actor: Actor = Depends(maker_only)):
    rows = session.exec(select(Product)).all()
    c = Counter(p.manufacturer for p in rows)
    return [{"name": n, "products": k} for n, k in sorted(c.items())]


@router.get("/stats")
def stats(manufacturer: Optional[str] = None, session: Session = Depends(get_session), actor: Actor = Depends(maker_only)):
    products = session.exec(select(Product)).all()
    if manufacturer:
        products = [p for p in products if p.manufacturer == manufacturer]
    by_gtin = {p.gtin: p for p in products}
    by_id = {p.id: p for p in products}
    since = datetime.combine(date.today() - timedelta(days=29), datetime.min.time())
    scans = [s for s in session.exec(select(Scan).where(Scan.ts >= since)).all() if s.gtin in by_gtin]
    days = [(date.today() - timedelta(days=29 - i)) for i in range(30)]
    per_day = Counter(s.ts.date() for s in scans)

    index = []
    for p in products:
        t = product_trust(session, p)
        index.append({"id": p.id, "name": p.trade_name, "score": t["score"], "color": t["color"], "is_local": p.is_local})
    index.sort(key=lambda x: -x["score"])

    reports = [r for r in session.exec(select(Report).order_by(Report.ts.desc())).all() if r.product_id in by_id]
    cats = Counter(r.category for r in reports)

    alerts = []
    cities = defaultdict(set)
    for s in session.exec(select(Scan).where(Scan.serial != None)).all():  # noqa: E711
        if s.gtin in by_gtin and s.city:
            cities[(s.serial, s.gtin)].add(s.city)
    for (serial, gtin), cs in cities.items():
        if len(cs) >= 2:
            alerts.append({"type": "clone", "severity": "danger", "product": by_gtin[gtin].trade_name, "serial": serial,
                           "detail": "Shaharlar: " + ", ".join(sorted(cs)),
                           "title": "Klon kod shubhasi"})
    for b in session.exec(select(Batch).where(Batch.recalled == True)).all():  # noqa: E712
        if b.product_id in by_id:
            alerts.append({"type": "recall", "severity": "danger", "product": by_id[b.product_id].trade_name,
                           "serial": None, "detail": f"Partiya {b.batch_no}", "title": "Qaytarib olingan partiya"})
    for b in session.exec(select(Batch)).all():
        if b.product_id in by_id and b.exp_date < date.today() and not b.recalled:
            alerts.append({"type": "expired", "severity": "warn", "product": by_id[b.product_id].trade_name,
                           "serial": None, "detail": f"Partiya {b.batch_no}, muddat {b.exp_date.isoformat()}",
                           "title": "Muddati o'tgan partiya muomalada"})
    avg = round(sum(i["score"] for i in index) / len(index)) if index else 0
    return {
        "manufacturer": manufacturer,
        "kpis": {"scans": len(scans), "avg_index": avg, "reports": len(reports), "alerts": len(alerts),
                 "products": len(products)},
        "scans_by_day": {"labels": [d.strftime("%d.%m") for d in days], "values": [per_day.get(d, 0) for d in days]},
        "index_per_product": index,
        "reports_by_category": [{"category": k, "count": v} for k, v in cats.most_common()],
        "alerts": alerts,
        "recent_reports": [{"id": r.id, "product": by_id[r.product_id].trade_name, "text": r.text, "category": r.category,
                            "severity": r.severity, "classified_by": r.classified_by,
                            "ts": r.ts.isoformat(timespec="minutes")} for r in reports[:8]],
        "is_mock": True,
    }


def pdf_text(data: bytes) -> str:
    import io

    import pdfplumber

    with pdfplumber.open(io.BytesIO(data)) as pdf:
        return "\n".join((pg.extract_text() or "") for pg in pdf.pages)


@router.post("/documents")
async def upload_document(product_id: int = Form(...), batch_no: str = Form(""), file: UploadFile = File(...),
                          session: Session = Depends(get_session), actor: Actor = Depends(maker_only)):
    p = get_product(session, product_id)
    data = await file.read()
    if not data:
        raise HTTPException(422, "Fayl bo'sh")
    if len(data) > 10 * 1024 * 1024:
        raise HTTPException(413, "Fayl hajmi 10 MB dan oshmasin")
    if not data.startswith(b"%PDF"):
        raise HTTPException(415, "Faqat PDF fayl qabul qilinadi")
    sha = hashlib.sha256(data).hexdigest()
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", file.filename or "coa.pdf")[-60:]
    config.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    path = config.UPLOAD_DIR / f"{sha[:12]}_{safe}"
    path.write_bytes(data)
    try:
        text = pdf_text(data)
    except Exception:
        text = ""
    extracted = llm.extract_coa(text) if text.strip() else {"data": {"batch_no": None, "results": []}, "source": "none", "model": None}
    doc = Document(product_id=p.id, batch_no=(batch_no or extracted["data"].get("batch_no") or None), type="CoA",
                   path=str(path.relative_to(config.ROOT)), sha256=sha, verified=False)
    session.add(doc)
    session.commit()
    session.refresh(doc)
    audit.log(session, actor, "document.upload", f"document:{doc.id}")
    return {"id": doc.id, "status": "pending", "message_uz": "Tekshiruvga yuborildi. Farmatsevt tasdiqlagach indeksga ta'sir qiladi.",
            "sha256": sha, "batch_no": doc.batch_no, "extracted": extracted["data"], "source": extracted["source"],
            "model": extracted.get("model")}
