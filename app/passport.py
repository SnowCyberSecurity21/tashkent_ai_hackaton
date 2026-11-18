"""Builds the "Dori pasporti" payload shared by /api/scan and /api/products/{id}."""
from __future__ import annotations

import re
from datetime import date
from typing import Optional

from sqlmodel import Session, select

from . import llm
from .analogs import find_analogs
from .models import Batch, Document, LabResult, Product
from .trust import coa_for, product_trust

SEV_RANK = {"danger": 0, "warn": 1, "info": 2, "ok": 3}
ROUTE_LABEL = {"og'iz orqali": "Og'iz orqali (ichish uchun)", "stomatologik": "Stomatologik (og'iz bo'shlig'i uchun)"}
MONTHS_UZ = ["yanvar", "fevral", "mart", "aprel", "may", "iyun", "iyul", "avgust", "sentabr", "oktabr", "noyabr", "dekabr"]


def fmt_amount(mg: float) -> str:
    return (f"{mg:g}").replace(".", ",")


def fmt_date_uz(d: Optional[date]) -> Optional[str]:
    return f"{d.day}-{MONTHS_UZ[d.month - 1]}, {d.year}" if d else None


def inns_display(p: Product) -> str:
    return " + ".join(f"{c['inn']} {fmt_amount(c['amount_mg'])} mg" for c in p.inn_list or [])


def summarize(p: Product) -> dict:
    return {
        "id": p.id, "key": p.key, "gtin": p.gtin, "trade_name": p.trade_name, "inn_list": p.inn_list,
        "inns_display": inns_display(p), "dose_form": p.dose_form, "route": p.route,
        "route_label": ROUTE_LABEL.get(p.route, p.route), "manufacturer": p.manufacturer, "country": p.country,
        "is_local": p.is_local, "rx_only": p.rx_only, "price_uzs": p.price_uzs, "max_units_per_day": p.max_units_per_day,
        "shelf_life": f"{p.shelf_life_months} oy", "reg_status": p.reg_status, "conformity_expired": p.conformity_expired,
        "gmp": p.gmp, "bioequivalence": p.bioequivalence, "is_mock": p.is_mock,
    }


def alert(code: str, severity: str, title: str, detail: str = "", icon: str = "alert-triangle") -> dict:
    return {"code": code, "severity": severity, "title_uz": title, "detail_uz": detail, "icon": icon}


def build_alerts(product: Product, official: Optional[dict], batch: Optional[Batch], exp: Optional[date],
                 kind: Optional[str], clone_city: Optional[str], today: Optional[date] = None) -> list[dict]:
    today = today or date.today()
    out = []
    if product.conformity_expired:
        out.append(alert("conformity_expired", "danger", "Muvofiqlik hujjati muddati tugagan",
                         "Rasmiy bazada bu dori uchun muvofiqlik hujjati muddati tugagani belgilangan. "
                         "Sotib olishdan oldin farmatsevtdan hujjat holatini so'rang.", "file-warning"))
    if product.reg_status == "expired":
        out.append(alert("reg_expired", "danger", "Ro'yxatdan o'tish muddati tugagan", "", "file-x"))
    elif product.reg_status == "unknown":
        out.append(alert("reg_unknown", "warn", "Ro'yxatdan o'tish holati noma'lum", "", "help-circle"))
    if official is not None:
        if official.get("authentic") is False:
            out.append(alert("code_unknown", "danger", "Kod rasmiy bazada topilmadi",
                             "Bu seriya raqami Asl Belgisi bazasida yo'q. Kod noto'g'ri o'qilgan yoki qadoq haqiqiy bo'lmasligi mumkin.",
                             "shield-x"))
        elif official.get("authentic") is True and official.get("code_status") != "withdrawn":
            out.append(alert("code_ok", "ok", "Kod rasmiy bazada tasdiqlandi", "Seriya raqami Asl Belgisi bazasida bor.",
                             "shield-check"))
        if official.get("recalled"):
            out.append(alert("recalled", "danger", "Bu partiya qaytarib olingan",
                             "Rasmiy ma'lumotga ko'ra bu partiya muomaladan chiqarilgan. Dorini ishlatmang va dorixonaga qaytaring.",
                             "octagon-x"))
    elif batch is not None and batch.recalled:
        out.append(alert("recalled", "danger", "Bu partiya qaytarib olingan", "", "octagon-x"))
    if clone_city:
        out.append(alert("clone", "danger", "Klon kod: bu seriya boshqa shaharda ham skanerlangan",
                         f"Bu seriya avval {clone_city} shahrida skanerlangan. Bir qadoq kodi bir necha joyda uchrasa, "
                         "kod nusxalangan bo'lishi mumkin.", "copy"))
    exp = exp or (batch.exp_date if batch else None)
    if kind == "ean13":
        out.append(alert("ean13_only", "info", "Faqat shtrix-kod o'qildi",
                         "Aniq partiya, seriya va yaroqlilik muddati uchun qadoqdagi kvadrat Data Matrix kodini skanerlang.",
                         "scan-line"))
    elif exp:
        days = (exp - today).days
        if days < 0:
            out.append(alert("expired", "danger", "Yaroqlilik muddati o'tgan",
                             f"Muddat {fmt_date_uz(exp)} kuni tugagan. Bu dorini ishlatmang.", "calendar-x"))
        elif days <= 90:
            out.append(alert("near_expiry", "warn", f"Yaroqlilik muddati tugashiga {days} kun qoldi",
                             f"Muddat: {fmt_date_uz(exp)}.", "calendar-clock"))
        else:
            out.append(alert("exp_ok", "ok", f"Yaroqli: {fmt_date_uz(exp)} gacha", f"{days} kun qoldi.", "calendar-check"))
    if product.rx_only:
        out.append(alert("rx", "info", "Retsept bo'yicha beriladi", "Bu dori faqat shifokor retsepti bilan beriladi.", "file-text"))
    out.sort(key=lambda a: SEV_RANK[a["severity"]])
    return out


def banner(trust: dict, alerts: list[dict]) -> dict:
    sev = {a["severity"] for a in alerts}
    color = trust["color"]
    first_danger = next((a["title_uz"] for a in alerts if a["severity"] == "danger"), None)
    first_warn = next((a["title_uz"] for a in alerts if a["severity"] == "warn"), None)
    if "danger" in sev:
        color = "red"
    elif "warn" in sev and color == "green":
        color = "amber"
    titles = {"green": "Ishonchli: rasmiy ma'lumotlar mos", "amber": "Diqqat: ayrim ma'lumotlar to'liq emas",
              "red": "Ehtiyot bo'ling: muhim ogohlantirish bor", "gray": "Ma'lumot yetarli emas"}
    words = {"green": "Yashil", "amber": "Sariq", "red": "Qizil", "gray": "Kulrang"}
    icons = {"green": "shield-check", "amber": "alert-triangle", "red": "shield-alert", "gray": "help-circle"}
    return {"color": color, "word": words[color], "title_uz": titles[color], "icon": icons[color],
            "reason_uz": first_danger or first_warn or (
                "Laboratoriya hujjati yo'q va skanlar kam" if trust["color"] == "gray" else f"Ishonch indeksi {trust['score']} / 100")}


def scenario_of(alerts: list[dict]) -> Optional[str]:
    codes = {a["code"] for a in alerts}
    for c, s in (("clone", "clone"), ("recalled", "recalled"), ("expired", "expired"), ("code_unknown", "unknown"),
                 ("coa_out", "coa_out"), ("near_expiry", "near_expiry")):
        if c in codes:
            return s
    return None


def coa_payload(session: Session, product: Product, batch_no: Optional[str]) -> Optional[dict]:
    doc, results, other = coa_for(session, product, batch_no)
    if not doc:
        return None
    return {
        "document_id": doc.id, "batch_no": doc.batch_no, "other_batch": other, "verified": doc.verified,
        "date": doc.ts.date().isoformat(), "sha256": doc.sha256[:16] if doc.sha256 else None,
        "results": [{"parameter": r.parameter, "value": r.value, "spec_min": r.spec_min, "spec_max": r.spec_max,
                     "unit": r.unit, "status": r.status} for r in results],
        "all_ok": all(r.status == "ok" for r in results),
    }


def explanation_context(product: Product, official, alerts, trust, scenario) -> dict:
    return {"key": product.key, "scenario": scenario, "name": product.trade_name, "inns": inns_display(product),
            "is_local": product.is_local, "country": product.country,
            "official": {k: official.get(k) for k in ("authentic", "reg_status", "conformity_expired", "recalled")} if official else None,
            "alerts": alerts, "trust": trust}


def build(session: Session, product: Product, *, parsed: Optional[dict] = None, official: Optional[dict] = None,
          clone_city: Optional[str] = None, live_explain: bool = False) -> dict:
    batches = session.exec(select(Batch).where(Batch.product_id == product.id).order_by(Batch.exp_date.desc())).all()
    batch_no = (official or {}).get("batch_no") or (parsed or {}).get("batch")
    batch = next((b for b in batches if b.batch_no == batch_no), None)
    if batch is None and not parsed:
        batch = next((b for b in batches if not b.recalled), batches[0] if batches else None)
    exp = (parsed or {}).get("exp_date") or (batch.exp_date if batch else None)
    kind = (parsed or {}).get("kind")
    alerts = build_alerts(product, official, batch, exp, kind, clone_city)
    coa = coa_payload(session, product, batch.batch_no if batch else None)
    if coa and not coa["all_ok"]:
        n_out = sum(1 for r in coa["results"] if r["status"] == "out")
        alerts.append(alert("coa_out", "warn", f"Laboratoriya: {n_out} ta ko'rsatkich me'yordan tashqarida",
                            f"Partiya {coa['batch_no']} tahlil sertifikatiga ko'ra.", "flask-conical"))
        alerts.sort(key=lambda a: SEV_RANK[a["severity"]])
    recalled = bool((official or {}).get("recalled")) or bool(batch and batch.recalled)
    trust = product_trust(session, product, batch=batch, clone=bool(clone_city),
                          code_unknown=(official or {}).get("authentic") is False, recalled=recalled)
    scen = scenario_of(alerts)
    exp_ctx = explanation_context(product, official, alerts, trust, scen)
    expl = llm.explain_uz(exp_ctx, live=live_explain)
    analogs = find_analogs(session, product, summarize) if not product.is_local else []
    local_analogs = [a for a in analogs if a["is_local"]]
    days_left = (exp - date.today()).days if exp else None
    return {
        "product": summarize(product),
        "official": official,
        "parsed": {**parsed, "exp_date": parsed["exp_date"].isoformat() if parsed.get("exp_date") else None,
                   "mfg_date": parsed["mfg_date"].isoformat() if parsed.get("mfg_date") else None} if parsed else None,
        "alerts": alerts,
        "banner": banner(trust, alerts),
        "trust": trust,
        "batch": {"batch_no": batch.batch_no if batch else batch_no, "mfg_date": batch.mfg_date.isoformat() if batch else None,
                  "exp_date": exp.isoformat() if exp else None, "exp_label": fmt_date_uz(exp), "days_left": days_left,
                  "recalled": recalled} if (batch or exp) else None,
        "batches": [{"batch_no": b.batch_no, "exp_date": b.exp_date.isoformat(), "recalled": b.recalled} for b in batches],
        "coa": coa,
        "analogs": local_analogs if not product.is_local else [],
        "analogs_count": len(local_analogs),
        "explanation_uz": expl["data"],
        "explanation_source": expl["source"],
        "explanation_model": expl["model"],
        "scenario": scen,
    }


# ------------------------------------------------------------ Asl Belgisi comparison (raw vs clean)
_COMP_RX = re.compile(r"^\s*(?P<name>[^\d]+?)\s*[-–—]?\s*(?P<amt>\d+(?:[.,]\d+)?)\s*mg\s*$", re.I)


def comparison(product: Product, live: bool = True) -> dict:
    raw = product.raw_official or {}
    rows, ai_notes = [], []
    for label, value in raw.items():
        clean, changed, note = value, False, None
        if label == "Ta'sir qiluvchi moddalar":
            parts = []
            for piece in str(value).split(","):
                m = _COMP_RX.match(piece.strip().strip("-").strip())
                if not m:
                    parts.append(piece.strip())
                    continue
                name = m.group("name").strip().strip("-").strip()
                res = llm.normalize_inn(name, live=live)
                inn = res["data"]
                amt = m.group("amt").replace(".", ",")
                parts.append(f"{inn} {amt} mg")
                if inn.lower() != name.lower():
                    ai_notes.append({"raw": name, "inn": inn, "source": res["source"], "model": res["model"]})
            clean = " + ".join(parts)
            # The clean product record is authoritative; show it if normalisation disagreed
            if clean.lower() != inns_display(product).lower():
                clean = inns_display(product)
            changed = True
            note = "INN nomlari tozalandi" if ai_notes else "Format tozalandi"
        elif label == "Yaroqlilik muddati":
            clean, changed, note = f"{product.shelf_life_months} oy", True, "Birlik qo'shildi"
        elif label == "Boshqaruv usuli":
            clean = ROUTE_LABEL.get(product.route, product.route)
            changed = clean != value
            note = "Tushunarli tilga o'girildi" if changed else None
        elif label == "Muvofiqlik hujjatining tugaganligining belgisi":
            clean = "⚠ Muvofiqlik hujjati muddati tugagan" if product.conformity_expired else "Muvofiqlik hujjati amal qiladi"
            changed, note = True, "\"Ha/Yo'q\" belgisi ma'noga aylantirildi"
        elif label == "Retsept bo'yicha":
            clean = "Faqat retsept bilan" if product.rx_only else "Retseptsiz beriladi"
            changed = True
        rows.append({"label": label, "raw": value, "clean": clean, "changed": changed, "note": note,
                     "danger": label.startswith("Muvofiqlik") and product.conformity_expired})
    return {"product_id": product.id, "rows": rows, "ai_notes": ai_notes,
            "source_label": "Asl Belgisi ilovasidagi xom maydonlar (demo nusxa)"}
