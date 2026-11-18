"""Local analog search: same INN set, same amounts, same dose form and route."""
from __future__ import annotations

from sqlmodel import Session, select

from .models import Product
from .trust import product_trust


def composition_key(p: Product) -> tuple:
    comps = sorted((c["inn"].lower(), float(c.get("amount_mg") or 0)) for c in (p.inn_list or []))
    return tuple(comps), p.dose_form.lower().strip(), p.route.lower().strip()


def composition_checklist(a: Product, b: Product) -> list[dict]:
    ka, kb = composition_key(a), composition_key(b)
    return [
        {"label": "Ta'sir qiluvchi moddalar bir xil", "ok": [x[0] for x in ka[0]] == [x[0] for x in kb[0]]},
        {"label": "Miqdori (mg) bir xil", "ok": ka[0] == kb[0]},
        {"label": "Dori shakli bir xil", "ok": ka[1] == kb[1]},
        {"label": "Qabul qilish usuli bir xil", "ok": ka[2] == kb[2]},
    ]


def find_analogs(session: Session, product: Product, summarize) -> list[dict]:
    key = composition_key(product)
    out = []
    for p in session.exec(select(Product).where(Product.id != product.id)).all():
        if composition_key(p) != key:
            continue
        trust = product_trust(session, p)
        saving = product.price_uzs - p.price_uzs
        pct = round(100 * saving / product.price_uzs) if product.price_uzs else 0
        out.append({
            **summarize(p), "trust": trust,
            "savings_uzs": saving, "savings_pct": pct,
            "checklist": composition_checklist(product, p),
        })
    out.sort(key=lambda a: (not a["is_local"], -a["trust"]["score"], a["price_uzs"]))
    return out
