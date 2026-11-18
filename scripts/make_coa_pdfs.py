"""Renders demo Certificate of Analysis PDFs from data/coa_results.json into data/coa/.

# MOCK: these certificates are generated demo documents, not real laboratory results.
Run:  python scripts/make_coa_pdfs.py
"""
from __future__ import annotations

import json
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUT = DATA / "coa"

TEAL = colors.HexColor("#0F766E")
INK = colors.HexColor("#1E2326")
MUTED = colors.HexColor("#6A7075")
LINE = colors.HexColor("#E7E0D2")
RED = colors.HexColor("#B4232A")


def spec_text(r) -> str:
    lo, hi = r.get("spec_min"), r.get("spec_max")
    if lo is not None and hi is not None:
        return f"{lo:g} - {hi:g}"
    if lo is not None:
        return f">= {lo:g}"
    if hi is not None:
        return f"<= {hi:g}"
    return "-"


def in_spec(r) -> bool:
    v = r["value"]
    if r.get("spec_min") is not None and v < r["spec_min"]:
        return False
    if r.get("spec_max") is not None and v > r["spec_max"]:
        return False
    return True


def render(cert: dict, product: dict, path: Path) -> None:
    c = canvas.Canvas(str(path), pagesize=A4)
    w, h = A4
    c.setTitle(f"CoA {cert['batch_no']}")
    # header band
    c.setFillColor(TEAL)
    c.rect(0, h - 28 * mm, w, 28 * mm, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(18 * mm, h - 15 * mm, "TAHLIL SERTIFIKATI (Certificate of Analysis)")
    c.setFont("Helvetica", 9)
    c.drawString(18 * mm, h - 22 * mm, "DEMO HUJJAT - haqiqiy laboratoriya natijasi emas (MOCK)")

    y = h - 42 * mm
    c.setFillColor(INK)
    rows = [
        ("Mahsulot", product["trade_name"].replace("№", "No.")),
        ("Ishlab chiqaruvchi", product["manufacturer"]),
        ("GTIN", product["gtin"]),
        ("Partiya raqami", cert["batch_no"]),
        ("Laboratoriya", cert["lab"]),
        ("Tahlil sanasi", cert["date"]),
    ]
    for label, value in rows:
        c.setFont("Helvetica", 9)
        c.setFillColor(MUTED)
        c.drawString(18 * mm, y, label)
        c.setFont("Helvetica-Bold", 10)
        c.setFillColor(INK)
        c.drawString(60 * mm, y, str(value))
        y -= 6.5 * mm

    y -= 4 * mm
    cols = [18 * mm, 92 * mm, 118 * mm, 146 * mm, 164 * mm]
    heads = ["Ko'rsatkich", "Natija", "Me'yor", "Birlik", "Xulosa"]
    c.setFillColor(colors.HexColor("#F3EEE3"))
    c.rect(15 * mm, y - 2.5 * mm, w - 30 * mm, 8 * mm, fill=1, stroke=0)
    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 9)
    for x, t in zip(cols, heads):
        c.drawString(x, y, t)
    y -= 9 * mm
    for r in cert["results"]:
        ok = in_spec(r)
        c.setFont("Helvetica", 10)
        c.setFillColor(INK)
        c.drawString(cols[0], y, r["parameter"])
        c.drawString(cols[1], y, f"{r['value']:g}")
        c.drawString(cols[2], y, spec_text(r))
        c.drawString(cols[3], y, r["unit"])
        c.setFillColor(TEAL if ok else RED)
        c.setFont("Helvetica-Bold", 10)
        c.drawString(cols[4], y, "Mos" if ok else "Mos emas")
        c.setStrokeColor(LINE)
        c.line(15 * mm, y - 3 * mm, w - 15 * mm, y - 3 * mm)
        y -= 9 * mm

    y -= 6 * mm
    overall = all(in_spec(r) for r in cert["results"])
    c.setFont("Helvetica-Bold", 11)
    c.setFillColor(TEAL if overall else RED)
    c.drawString(18 * mm, y, "Umumiy xulosa: " + ("partiya me'yorlarga mos" if overall else "bir ko'rsatkich me'yordan tashqarida"))
    c.setFont("Helvetica", 8)
    c.setFillColor(MUTED)
    c.drawString(18 * mm, 18 * mm, "Mezon demo loyihasi uchun yaratilgan. Imzo: QC bo'limi boshlig'i (demo).")
    c.showPage()
    c.save()


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    products = {p["key"]: p for p in json.loads((DATA / "products.json").read_text(encoding="utf-8"))}
    certs = json.loads((DATA / "coa_results.json").read_text(encoding="utf-8"))["certificates"]
    for cert in certs:
        path = OUT / f"coa_{cert['batch_no']}.pdf"
        render(cert, products[cert["product_key"]], path)
        print("wrote", path.relative_to(ROOT))


if __name__ == "__main__":
    main()
