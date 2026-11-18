import json
from pathlib import Path

from app import safety

DATA = Path(__file__).resolve().parent.parent / "data"
RULES = [dict(r, approved=True) for r in json.loads((DATA / "rules.json").read_text(encoding="utf-8"))["rules"]]
CLASSES = json.loads((DATA / "classes.json").read_text(encoding="utf-8"))

PARA = {"id": 1, "trade_name": "Paratsetamol 500 mg", "inn_list": [{"inn": "paratsetamol", "amount_mg": 500}]}
TYLOL = {"id": 2, "trade_name": "Tylol Hot", "inn_list": [{"inn": "paratsetamol", "amount_mg": 500},
                                                         {"inn": "psevdoefedrin", "amount_mg": 60},
                                                         {"inn": "xlorfeniramin", "amount_mg": 4}]}
IBU = {"id": 3, "trade_name": "Ibuprofen 400 mg", "inn_list": [{"inn": "ibuprofen", "amount_mg": 400}]}
DIC = {"id": 4, "trade_name": "Diklofenak 50 mg", "inn_list": [{"inn": "diklofenak", "amount_mg": 50}]}
BIS = {"id": 5, "trade_name": "Bisoprolol 5 mg", "inn_list": [{"inn": "bisoprolol", "amount_mg": 5}]}
HEALTHY = {"conditions": [], "alcohol": False}


def item(p, n):
    return {"product": p, "units_per_day": n}


def kinds(res):
    return {(w["kind"], w["severity"]) for w in res["warnings"]}


def total(res, inn):
    return next(t for t in res["daily_totals"] if t["inn"] == inn)


def test_tylol_plus_paracetamol_duplicate_and_daily_total():
    res = safety.evaluate(HEALTHY, [item(PARA, 6), item(TYLOL, 1)], RULES, CLASSES)
    assert ("duplicate", "warn") in kinds(res)
    t = total(res, "paratsetamol")
    assert t["total_mg"] == 3500 and t["limit_mg"] == 4000 and t["pct"] == 88
    w = next(w for w in res["warnings"] if w["kind"] == "max_daily")
    assert w["severity"] == "warn" and "3 500 mg / 4 000 mg" in w["message_uz"]
    over = safety.evaluate(HEALTHY, [item(PARA, 8), item(TYLOL, 1)], RULES, CLASSES)
    assert next(w for w in over["warnings"] if w["kind"] == "max_daily")["severity"] == "danger"
    assert all(w["message_uz"].endswith(safety.CONSULT_UZ) for w in res["warnings"])


def test_ibuprofen_plus_diclofenac_nsaid_pair():
    res = safety.evaluate(HEALTHY, [item(IBU, 1), item(DIC, 1)], RULES, CLASSES)
    w = [w for w in res["warnings"] if w["kind"] == "drug_drug"]
    assert len(w) == 1 and w[0]["severity"] == "danger" and w[0]["level"] == 3


def test_hypertension_plus_tylol_and_beta_blocker():
    pat = {"conditions": ["gipertoniya"], "alcohol": False}
    res = safety.evaluate(pat, [item(BIS, 1), item(TYLOL, 1)], RULES, CLASSES)
    ids = {w["id"] for w in res["warnings"]}
    assert "drug_condition:psevdoefedrin:gipertoniya" in ids
    assert any(w["kind"] == "drug_drug" and "psevdoefedrin" in w["inns"] and "bisoprolol" in w["inns"] for w in res["warnings"])
    assert res["warnings"][0]["severity"] == "danger"  # sorted by severity first
    assert res["max_severity"] == "danger"


def test_alcohol_lowers_paracetamol_limit():
    pat = {"conditions": [], "alcohol": True}
    res = safety.evaluate(pat, [item(PARA, 4)], RULES, CLASSES)
    t = total(res, "paratsetamol")
    assert t["limit_mg"] == 2000 and t["total_mg"] == 2000
    assert next(w for w in res["warnings"] if w["kind"] == "max_daily")["severity"] == "warn"


def test_what_if_before_adding():
    pat = {"conditions": ["gipertoniya"], "alcohol": False}
    res = safety.what_if(pat, [item(BIS, 1), item(PARA, 3)], RULES, CLASSES, item(TYLOL, 1))
    meter = next(m for m in res["meters"] if m["inn"] == "paratsetamol")
    assert meter["before_mg"] == 1500 and meter["total_mg"] == 2000 and meter["limit_mg"] == 4000
    new_ids = {w["id"] for w in res["new_warnings"]}
    assert "duplicate:paratsetamol" in new_ids
    assert "drug_condition:psevdoefedrin:gipertoniya" in new_ids
    assert any(i.startswith("drug_drug:") for i in new_ids)
    assert res["before"]["warnings"] == []


def test_unapproved_rules_are_ignored():
    rules = [dict(r, approved=False) for r in RULES]
    res = safety.evaluate({"conditions": ["gipertoniya"]}, [item(IBU, 1), item(DIC, 1), item(TYLOL, 1)], rules, CLASSES)
    assert res["warnings"] == []
