"""Warms LlmCache so every demo screen opens instantly.

Usage:  python scripts/warm_cache.py            (server may be running; only LlmCache rows are written)

Runs each LLM task the demo touches once, through the same code path and the same cache keys as the API:
  - explanations for every featured demo code (as scanned in the default city) and every demo product page;
  - INN normalisation behind "Asl Belgisi bilan solishtirish";
  - CoA extraction for the demo batches' certificates;
  - Tylol Hot leaflet -> proposed rules (the staff "Qayta tahlil qilish" button still calls the model live);
  - classification of the sample patient reports.
A task that fails live (no key, timeout, 429) is reported and left uncached, so the app keeps using precomputed data.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from sqlmodel import Session, select  # noqa: E402

from app import config, gs1, llm, passport  # noqa: E402
from app.db import engine, init_db, load_json  # noqa: E402
from app.integrations.asl_belgisi_mock import AslBelgisiClient  # noqa: E402
from app.models import Document, Product, Report, Scan  # noqa: E402
from app.routers.admin import bundled_leaflet_text  # noqa: E402
from app.routers.maker import pdf_text  # noqa: E402

stats = {"cache": 0, "live": 0, "precomputed": 0}


def run(label: str, fn, *args, **kw) -> dict:
    t0 = time.time()
    res = fn(*args, **kw)
    stats[res["source"]] = stats.get(res["source"], 0) + 1
    tail = f"  ({res['error'][:90]})" if res.get("error") else ""
    print(f"  {res['source']:11s} {time.time() - t0:5.1f} s  {label}{tail}", flush=True)
    return res


def scan_context(session: Session, raw: str, city: str = config.DEFAULT_CITY) -> dict:
    """Same context as POST /api/scan + POST /api/explain, but read-only (no Scan row is written)."""
    parsed = gs1.parse(raw)
    product = session.exec(select(Product).where(Product.gtin == parsed["gtin"])).one()
    official = AslBelgisiClient(session).check(parsed["gtin"], parsed["serial"], parsed["batch"])
    clone_city = None
    if parsed["serial"]:
        prev = session.exec(select(Scan).where(Scan.serial == parsed["serial"], Scan.city != None)).all()  # noqa: E711
        other = [s.city for s in prev if s.city and s.city.lower() != city.lower()]
        clone_city = other[0] if other else None
    res = passport.build(session, product, parsed=parsed, official=official, clone_city=clone_city)
    return passport.explanation_context(product, res.get("official"), res["alerts"], res["trust"], res.get("scenario"))


def main() -> int:
    init_db()
    llm.COOLDOWN_S = 0  # the app pauses live calls 30 s after a double failure; the warm-up should keep trying
    print(f"LLM: {llm.status()['provider']} · {config.GEMINI_MODEL} → {config.GEMINI_FALLBACK_MODEL}"
          f"{' · OFFLINE' if not llm.is_configured() else ''}")
    codes = load_json("codes.json")
    with Session(engine) as session:
        print("1. Skan izohlari (demo kodlar)")
        for f in codes["featured"]:
            ctx = scan_context(session, f["element_string"])
            run(f["label"], llm.explain_uz, ctx, live=True)

        print("2. Mahsulot sahifasi izohlari va Asl Belgisi solishtiruvi")
        seen = set()
        for f in codes["featured"]:
            product = session.exec(select(Product).where(Product.key == f["product_key"])).first()
            if not product or product.id in seen:
                continue
            seen.add(product.id)
            res = passport.build(session, product)
            ctx = passport.explanation_context(product, None, res["alerts"], res["trust"], res.get("scenario"))
            run(f"{product.trade_name} (sahifa)", llm.explain_uz, ctx, live=True)
            passport.comparison(product, live=True)  # normalize_inn: dictionary first, LLM only for unknown names

        print("3. CoA tahlili (demo partiyalar)")
        for doc in session.exec(select(Document).where(Document.type == "CoA")).all():
            path = ROOT / doc.path
            if path.exists():
                run(f"CoA {doc.batch_no}", llm.extract_coa, pdf_text(path.read_bytes()), force=True)

        print("4. Tylol Hot yo'riqnomasi → qoidalar")
        text = bundled_leaflet_text()
        if text:
            run("tylol-hot.pdf", llm.leaflet_to_rules, text, live=True, force=True)
        else:
            print("  yo'riqnoma topilmadi: data/leaflets/tylol-hot.pdf")

        print("5. Xabarlar tasnifi")
        texts = {r.text for r in session.exec(select(Report)).all()}
        texts |= set(load_json("precomputed_llm.json").get("classify_report", {}))
        texts |= {"Ichgandan keyin terimda toshma chiqdi", "Ichgandan keyin terimda toshma paydo bo'ldi"}
        for t in sorted(texts):
            run(t[:60], llm.classify_report, t)

    print(f"\nKeshdan: {stats.get('cache', 0)} · jonli (keshga yozildi): {stats.get('live', 0)} · "
          f"tayyor natija (keshlanmadi): {stats.get('precomputed', 0)}")
    if stats.get("precomputed"):
        print("Ba'zi vazifalar jonli ishlamadi — skriptni keyinroq qayta ishga tushiring (keshdagilar takrorlanmaydi).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
