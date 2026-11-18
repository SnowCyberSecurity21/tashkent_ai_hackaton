from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from .. import passport
from ..analogs import find_analogs
from ..db import conditions, load_json
from ..db import get_session
from ..models import Product
from ..trust import product_trust
from .common import get_product

router = APIRouter(prefix="/api", tags=["products"])


@router.get("/products")
def list_products(q: Optional[str] = None, limit: int = 50, session: Session = Depends(get_session)):
    rows = session.exec(select(Product).order_by(Product.trade_name)).all()
    if q:
        ql = q.strip().lower()
        rows = [p for p in rows if ql in p.trade_name.lower() or any(ql in c["inn"] for c in p.inn_list or [])
                or ql in p.manufacturer.lower() or ql == p.gtin]
    out = []
    for p in rows[:limit]:
        t = product_trust(session, p)
        out.append({**passport.summarize(p), "trust": {"score": t["score"], "color": t["color"], "color_word": t["color_word"]}})
    return out


@router.get("/products/{product_id}")
def product_detail(product_id: int, session: Session = Depends(get_session)):
    p = get_product(session, product_id)
    return passport.build(session, p)


@router.get("/products/{product_id}/analogs")
def product_analogs(product_id: int, session: Session = Depends(get_session)):
    p = get_product(session, product_id)
    base = {**passport.summarize(p), "trust": product_trust(session, p)}
    analogs = find_analogs(session, p, passport.summarize)
    return {"product": base, "analogs": analogs, "local_count": sum(1 for a in analogs if a["is_local"])}


@router.get("/products/{product_id}/compare")
def product_compare(product_id: int, session: Session = Depends(get_session)):
    return passport.comparison(get_product(session, product_id))


@router.get("/codes")
def demo_codes(session: Session = Depends(get_session)):
    data = load_json("codes.json")
    names = {p.key: (p.id, p.trade_name) for p in session.exec(select(Product)).all()}
    featured = [{**f, "product_id": names.get(f["product_key"], (None, ""))[0],
                 "trade_name": names.get(f["product_key"], (None, ""))[1]} for f in data["featured"]]
    return {"featured": featured, "clone_first_city": data["clone_first_city"], "is_mock": True}


@router.get("/conditions")
def list_conditions():
    return conditions()
