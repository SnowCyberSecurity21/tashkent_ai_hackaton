"""Deterministic 4-level safety engine. Pure functions: no I/O, no LLM.

Levels: 1 duplicate INN · 2 daily total vs limit · 3 drug–drug · 4 drug–condition.
Only rules passed in (the caller passes `approved=True` rules only) can produce warnings.
"""
from __future__ import annotations

from typing import Iterable, Optional

CONSULT_UZ = "Shifokor yoki farmatsevt bilan maslahatlashing."
LEVEL = {"duplicate": 1, "max_daily": 2, "drug_drug": 3, "drug_condition": 4}
SEV_RANK = {"danger": 0, "warn": 1, "info": 2}
KIND_TITLE = {"duplicate": "Takroriy modda", "max_daily": "Kunlik miqdor", "drug_drug": "Dorilar o'zaro ta'siri",
              "drug_condition": "Kasallik bilan mos emas"}


def fmt_mg(x: float) -> str:
    x = round(x, 1)
    s = f"{int(x):,}".replace(",", " ") if float(x).is_integer() else f"{x:,.1f}".replace(",", " ").replace(".", ",")
    return s


def cap(s: str) -> str:
    return s[:1].upper() + s[1:] if s else s


def _consult(msg: str) -> str:
    msg = msg.strip()
    if not msg.endswith(CONSULT_UZ):
        if msg and msg[-1] not in ".!?":
            msg += "."
        msg = f"{msg} {CONSULT_UZ}"
    return msg


def _match(token: Optional[str], inn: str, classes: dict[str, list[str]]) -> bool:
    if not token:
        return False
    token = token.strip().lower()
    if token.startswith("class:"):
        return inn in [m.lower() for m in classes.get(token[6:], classes.get(token[6:].upper(), []))]
    return token == inn


def _class_label(token: str) -> str:
    names = {"class:nsaid": "NYaQV", "class:beta_blocker": "beta-blokator", "class:maoi": "MAO ingibitori",
             "class:sedating_antihistamine": "uyquchanlik chaqiruvchi antigistamin",
             "class:tricyclic_antidepressant": "trisiklik antidepressant"}
    return names.get(token.lower(), token)


def _norm_items(regimen: Iterable[dict], candidate: Optional[dict]) -> list[dict]:
    items = []
    for it in regimen:
        items.append({**it, "is_candidate": False})
    if candidate:
        # adding the same product again just raises its units/day
        for it in items:
            if it["product"]["id"] == candidate["product"]["id"]:
                it["units_per_day"] = it["units_per_day"] + candidate.get("units_per_day", 1)
                it["is_candidate"] = True
                break
        else:
            items.append({**candidate, "is_candidate": True})
    return items


def evaluate(patient: dict, regimen: Iterable[dict], rules: Iterable[dict], classes: dict[str, list[str]],
             candidate: Optional[dict] = None, condition_labels: Optional[dict[str, str]] = None) -> dict:
    """patient: {conditions: [...], alcohol: bool}
    regimen / candidate items: {product: {id, trade_name, inn_list:[{inn, amount_mg}]}, units_per_day}
    rules: dicts with kind, a, b, threshold_mg, severity, message_uz, source (approved only)."""
    labels = condition_labels or {}
    rules = [r for r in rules if r.get("approved", True)]
    items = _norm_items(regimen, candidate)
    conds = set(c.lower() for c in patient.get("conditions") or [])
    if patient.get("alcohol"):
        conds.add("alcohol")

    found: dict[str, dict] = {}

    def add(key: str, w: dict) -> None:
        prev = found.get(key)
        if prev is None:
            found[key] = w
            return
        if SEV_RANK[w["severity"]] < SEV_RANK[prev["severity"]]:
            w["source"] = "; ".join(dict.fromkeys([w["source"], prev["source"]]))
            found[key] = w
        elif w["source"] not in prev["source"]:
            prev["source"] = f"{prev['source']}; {w['source']}"

    # index: inn -> list of (item, amount_mg)
    by_inn: dict[str, list[tuple[dict, float]]] = {}
    for it in items:
        for comp in it["product"].get("inn_list") or []:
            by_inn.setdefault(comp["inn"].lower(), []).append((it, float(comp.get("amount_mg") or 0)))

    # 1 — duplicate active ingredient
    for r in (r for r in rules if r["kind"] == "duplicate"):
        for inn, entries in by_inn.items():
            if r["a"] not in ("*", None, "") and not _match(r["a"], inn, classes):
                continue
            prods = {e[0]["product"]["id"]: e[0] for e in entries}
            if len(prods) < 2:
                continue
            names = [p["product"]["trade_name"] for p in prods.values()]
            add(f"duplicate:{inn}", {
                "level": 1, "kind": "duplicate", "severity": r["severity"],
                "title_uz": f"Takroriy modda: {cap(inn)}",
                "message_uz": _consult(f"Ikkala dorida ham {inn} bor: {' va '.join(names)}. {r['message_uz']}"),
                "source": r["source"], "products": names, "inns": [inn],
                "involves_candidate": any(p["is_candidate"] for p in prods.values()),
            })

    # 2 — daily totals
    totals = []
    for inn, entries in by_inn.items():
        total = sum(mg * e["units_per_day"] for e, mg in entries)
        applicable = [r for r in rules if r["kind"] == "max_daily" and _match(r["a"], inn, classes)
                      and r.get("threshold_mg") and (not r.get("b") or r["b"].lower() in conds)]
        limit_rule = min(applicable, key=lambda r: r["threshold_mg"]) if applicable else None
        limit = float(limit_rule["threshold_mg"]) if limit_rule else None
        pct = round(100 * total / limit) if limit else None
        totals.append({
            "inn": inn, "total_mg": total, "limit_mg": limit, "pct": pct,
            "contributors": [{"product": e["product"]["trade_name"], "mg": mg * e["units_per_day"],
                              "units_per_day": e["units_per_day"], "is_candidate": e["is_candidate"]}
                             for e, mg in entries],
            "limit_source": limit_rule["source"] if limit_rule else None,
            "limit_note": ("spirtli ichimlik sababli pasaytirilgan chegara" if limit_rule and limit_rule.get("b") == "alcohol" else None),
        })
        if limit and pct is not None and pct >= 80:
            sev = "danger" if total > limit else "warn"
            add(f"max_daily:{inn}", {
                "level": 2, "kind": "max_daily", "severity": sev,
                "title_uz": f"Kunlik miqdor: {cap(inn)} {fmt_mg(total)} / {fmt_mg(limit)} mg",
                "message_uz": _consult(f"Bugun jami {inn}: {fmt_mg(total)} mg / {fmt_mg(limit)} mg ({pct}%). {limit_rule['message_uz']}"),
                "source": limit_rule["source"], "products": [e["product"]["trade_name"] for e, _ in entries], "inns": [inn],
                "involves_candidate": any(e["is_candidate"] for e, _ in entries),
            })

    # 3 — drug–drug
    for r in (r for r in rules if r["kind"] == "drug_drug"):
        for i, it_a in enumerate(items):
            for it_b in items[i + 1:]:
                for ca in it_a["product"].get("inn_list") or []:
                    for cb in it_b["product"].get("inn_list") or []:
                        x, y = ca["inn"].lower(), cb["inn"].lower()
                        hit = (_match(r["a"], x, classes) and _match(r["b"], y, classes)) or \
                              (_match(r["a"], y, classes) and _match(r["b"], x, classes))
                        if not hit:
                            continue
                        pa, pb = it_a["product"], it_b["product"]
                        if not _match(r["a"], x, classes) or not _match(r["b"], y, classes):
                            x, y, pa, pb = y, x, pb, pa  # keep the rule's (a, b) order in the title
                        key = "drug_drug:" + "|".join(sorted([f"{pa['id']}:{x}", f"{pb['id']}:{y}"]))
                        add(key, {
                            "level": 3, "kind": "drug_drug", "severity": r["severity"],
                            "title_uz": f"{cap(x)} + {cap(y)}",
                            "message_uz": _consult(f"{r['message_uz']} ({pa['trade_name']} + {pb['trade_name']})"),
                            "source": r["source"], "products": [pa["trade_name"], pb["trade_name"]], "inns": [x, y],
                            "involves_candidate": it_a["is_candidate"] or it_b["is_candidate"],
                        })

    # 4 — drug–condition
    for r in (r for r in rules if r["kind"] == "drug_condition"):
        cond = (r.get("b") or "").lower()
        if cond not in conds:
            continue
        for inn, entries in by_inn.items():
            if not _match(r["a"], inn, classes):
                continue
            names = list(dict.fromkeys(e["product"]["trade_name"] for e, _ in entries))
            label = "spirtli ichimlik" if cond == "alcohol" else labels.get(cond, cond).lower()
            add(f"drug_condition:{inn}:{cond}", {
                "level": 4, "kind": "drug_condition", "severity": r["severity"],
                "title_uz": f"{cap(inn)} va {label}",
                "message_uz": _consult(f"{r['message_uz']} ({', '.join(names)})"),
                "source": r["source"], "products": names, "inns": [inn], "condition": cond,
                "involves_candidate": any(e["is_candidate"] for e, _ in entries),
            })

    warnings = []
    for key, w in found.items():
        w["id"] = key
        warnings.append(w)
    warnings.sort(key=lambda w: (SEV_RANK[w["severity"]], w["level"], w["title_uz"]))
    totals.sort(key=lambda t: (t["limit_mg"] is None, -(t["pct"] or 0), t["inn"]))
    counts = {s: sum(1 for w in warnings if w["severity"] == s) for s in SEV_RANK}
    max_sev = next((s for s in ("danger", "warn", "info") if counts[s]), None)
    return {"warnings": warnings, "daily_totals": totals, "counts": counts, "max_severity": max_sev}


def what_if(patient: dict, regimen: list[dict], rules: list[dict], classes: dict[str, list[str]],
            candidate: dict, condition_labels: Optional[dict[str, str]] = None) -> dict:
    before = evaluate(patient, regimen, rules, classes, None, condition_labels)
    after = evaluate(patient, [dict(it) for it in regimen], rules, classes, candidate, condition_labels)
    before_sev = {w["id"]: w["severity"] for w in before["warnings"]}
    new = [w for w in after["warnings"]
           if w["id"] not in before_sev or SEV_RANK[w["severity"]] < SEV_RANK[before_sev[w["id"]]]]
    before_tot = {t["inn"]: t["total_mg"] for t in before["daily_totals"]}
    meters = []
    for t in after["daily_totals"]:
        meters.append({**t, "before_mg": before_tot.get(t["inn"], 0.0)})
    return {"before": before, "after": after, "new_warnings": new, "meters": meters}
