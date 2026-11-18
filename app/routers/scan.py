from __future__ import annotations

import io
import logging
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlmodel import Session, select

from .. import config, gs1, llm, passport
from ..auth import Actor, get_actor
from ..db import get_session
from ..integrations.asl_belgisi_mock import AslBelgisiClient
from ..models import Product, Scan
from .common import get_product

router = APIRouter(prefix="/api", tags=["scan"])
log = logging.getLogger("mezon.scan")

MAX_IMAGE_BYTES = 15 * 1024 * 1024
NOT_FOUND_UZ = "Kod topilmadi. Kodga yaqinroq va to'g'ri burchakda rasmga oling yoki kodni qo'lda kiriting."


def _zxing_variants(img):
    """Full image first (zxing-cpp rotates/downscales itself), then contrast-boosted and centre-crop variants."""
    from PIL import ImageOps

    gray = ImageOps.exif_transpose(img).convert("L")
    yield gray
    yield ImageOps.autocontrast(gray, cutoff=1)
    w, h = gray.size
    for frac in (0.6, 0.35):  # a small code in a big photo: give it more pixels
        side = int(min(w, h) * frac)
        box = ((w - side) // 2, (h - side) // 2, (w + side) // 2, (h + side) // 2)
        crop = gray.crop(box)
        if side < 1200:
            crop = crop.resize((side * 2, side * 2))
        yield crop


@router.post("/decode-image")
async def decode_image(file: UploadFile = File(...)):
    """Server-side fallback for "Rasmdan o'qish": zxing-cpp (same family as phone scanners) on the uploaded photo.
    Returns the raw text with GS (\\x1d) separators preserved, ready for POST /api/scan."""
    data = await file.read(MAX_IMAGE_BYTES + 1)
    if not data:
        raise HTTPException(422, "Rasm bo'sh.")
    if len(data) > MAX_IMAGE_BYTES:
        raise HTTPException(413, "Rasm juda katta (15 MB dan oshmasin).")
    try:
        import zxingcpp
        from PIL import Image
    except ImportError:
        raise HTTPException(503, "Serverda rasm dekoderi o'rnatilmagan (pip install zxing-cpp). Kodni qo'lda kiriting.")
    try:
        img = Image.open(io.BytesIO(data))
        img.load()
    except Exception:
        raise HTTPException(422, "Rasmni o'qib bo'lmadi. JPG yoki PNG yuklang.")
    fmts = zxingcpp.BarcodeFormat.DataMatrix | zxingcpp.BarcodeFormat.EAN13 | zxingcpp.BarcodeFormat.QRCode
    for i, variant in enumerate(_zxing_variants(img)):
        found = zxingcpp.read_barcodes(variant, formats=fmts, try_rotate=True, try_downscale=True,
                                       text_mode=zxingcpp.TextMode.Plain)
        found = [b for b in found if b.valid and b.text]
        if found:
            b = max(found, key=lambda x: (x.format == zxingcpp.BarcodeFormat.DataMatrix, len(x.text)))
            log.info("decode-image ok variant=%d format=%s symbology=%s raw=%r", i, b.format.name,
                     b.symbology_identifier, b.text[:400])
            return {"text": b.text, "format": b.format.name, "symbology": b.symbology_identifier}
    log.info("decode-image: no code found (%dx%d, %d bytes)", img.size[0], img.size[1], len(data))
    raise HTTPException(404, NOT_FOUND_UZ)


class ScanIn(BaseModel):
    raw: str
    city: Optional[str] = None


@router.post("/scan")
def scan(body: ScanIn, session: Session = Depends(get_session), actor: Actor = Depends(get_actor)):
    # exact decoded text (GS shows as \x1d) so a failing real pack can be diagnosed from the server console
    log.info("scan raw=%r city=%r", (body.raw or "")[:400], body.city)
    try:
        parsed = gs1.parse(body.raw)
    except gs1.GS1Error as exc:
        log.warning("scan parse failed: %s raw=%r", exc, (body.raw or "")[:400])
        raise HTTPException(422, str(exc))
    product = session.exec(select(Product).where(Product.gtin == parsed["gtin"])).first()
    if not product:
        raise HTTPException(404, "Bu kod bo'yicha dori bazada topilmadi. Kodni qayta skanerlang yoki qo'lda tekshiring.")
    city = (body.city or config.DEFAULT_CITY).strip() or config.DEFAULT_CITY
    official = AslBelgisiClient(session).check(parsed["gtin"], parsed["serial"], parsed["batch"])

    clone_city = None
    if parsed["serial"]:
        prev = session.exec(select(Scan).where(Scan.serial == parsed["serial"], Scan.city != None)).all()  # noqa: E711
        other = [s.city for s in prev if s.city and s.city.lower() != city.lower()]
        clone_city = other[0] if other else None

    row = Scan(serial=parsed["serial"], gtin=parsed["gtin"], city=city)
    session.add(row)
    session.commit()
    session.refresh(row)

    result = passport.build(session, product, parsed=parsed, official=official, clone_city=clone_city)
    result["scan_id"] = row.id
    result["city"] = city
    result["ts"] = row.ts.isoformat(timespec="seconds")
    row.result_json = result
    session.add(row)
    session.commit()
    return result


@router.get("/scans/{scan_id}")
def get_scan(scan_id: int, session: Session = Depends(get_session)):
    row = session.get(Scan, scan_id)
    if not row or not row.result_json:
        raise HTTPException(404, "Skan natijasi topilmadi")
    return row.result_json


class ExplainIn(BaseModel):
    scan_id: Optional[int] = None
    product_id: Optional[int] = None


@router.post("/explain")
def explain(body: ExplainIn, session: Session = Depends(get_session)):
    """Upgrades the instant (cached/precomputed) explanation with a live LLM answer when available."""
    if body.scan_id:
        row = session.get(Scan, body.scan_id)
        if not row or not row.result_json:
            raise HTTPException(404, "Skan natijasi topilmadi")
        res = row.result_json
        product = get_product(session, res["product"]["id"])
        ctx = passport.explanation_context(product, res.get("official"), res["alerts"], res["trust"], res.get("scenario"))
    elif body.product_id:
        product = get_product(session, body.product_id)
        res = passport.build(session, product)
        ctx = passport.explanation_context(product, None, res["alerts"], res["trust"], res.get("scenario"))
        row = None
    else:
        raise HTTPException(422, "scan_id yoki product_id kerak")
    out = llm.explain_uz(ctx, live=True)
    if row is not None and out["source"] in ("live", "cache"):
        data = dict(row.result_json)
        data.update(explanation_uz=out["data"], explanation_source=out["source"], explanation_model=out["model"])
        row.result_json = data
        session.add(row)
        session.commit()
    return {"text": out["data"], "source": out["source"], "model": out["model"], "error": out["error"]}
