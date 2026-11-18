"""Walks the demo script (MVP section 13) against a RUNNING server and prints PASS/FAIL per step.

Usage:  python scripts/smoke_test.py [--base http://127.0.0.1:8000]   (127.0.0.1: on Windows "localhost" adds ~2 s per request)
It starts nothing itself. It cleans up the regimen items it adds, so it can be re-run.
"""
from __future__ import annotations

import argparse
import sys

import requests

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

results: list[tuple[str, bool, str]] = []


def check(name: str, cond: bool, detail: str = "") -> bool:
    results.append((name, bool(cond), detail))
    print(f"{'PASS' if cond else 'FAIL'}  {name}" + (f"  — {detail}" if detail and not cond else ""))
    return bool(cond)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8000")
    base = ap.parse_args().base.rstrip("/")
    s = requests.Session()

    def call(method, path, role="patient", **kw):
        r = s.request(method, base + path, headers={"X-Demo-Role": role}, timeout=90, **kw)
        try:
            data = r.json()
        except ValueError:
            data = None
        return r.status_code, data

    try:
        code, h = call("GET", "/api/health")
    except requests.RequestException as exc:
        print(f"FAIL  server not reachable at {base}: {exc}")
        return 1
    check("0. health", code == 200 and h["ok"], str(h))
    code, page = s.get(base + "/").status_code, None
    check("0. patient app served at /", code == 200)
    check("0. staff console served at /staff.html", s.get(base + "/staff.html").status_code == 200)

    _, codes = call("GET", "/api/codes")
    by = {f["scenario"]: f for f in codes["featured"]}

    # 1. Dentashan
    code, d = call("POST", "/api/scan", json={"raw": by["conformity_expired"]["element_string"], "city": "Toshkent"})
    ok = code == 200
    check("1. Dentashan scan", ok, str(d)[:200])
    if ok:
        check("1. red banner", d["banner"]["color"] == "red", d["banner"]["color"])
        check("1. alert 'Muvofiqlik hujjati muddati tugagan'", any(a["title_uz"] == "Muvofiqlik hujjati muddati tugagan" for a in d["alerts"]))
        check("1. composition cleaned", d["product"]["inns_display"] == "metronidazol 16 mg + xlorgeksidin 2,5 mg", d["product"]["inns_display"])
        check("1. shelf life '36 oy'", d["product"]["shelf_life"] == "36 oy")
        _, cmp_ = call("GET", f"/api/products/{d['product']['id']}/compare")
        row = next(r for r in cmp_["rows"] if r["label"] == "Ta'sir qiluvchi moddalar")
        check("1. Asl Belgisi raw vs clean", row["raw"] == "Metrodonidazol -16 mg, hlorgeksedin-2.5 mg" and "metronidazol" in row["clean"])
        check("1. explanation present", bool(d["explanation_uz"]))

    # 2. import paracetamol -> local analog -> approval
    code, p = call("POST", "/api/scan", json={"raw": by["import_paracetamol"]["element_string"]})
    check("2. import paracetamol scan + Trust Card", code == 200 and len(p["trust"]["components"]) == 5, str(p)[:200])
    para_id = p["product"]["id"]
    _, an = call("GET", f"/api/products/{para_id}/analogs")
    local = next((a for a in an["analogs"] if a["is_local"]), None)
    check("2. local analog green with savings", bool(local) and local["trust"]["color"] == "green" and local["savings_uzs"] > 0,
          str(local and (local["trust"]["color"], local["savings_uzs"])))
    code, appr = call("POST", "/api/approvals", json={"from_product_id": para_id, "to_product_id": local["id"]})
    check("2. approval requested", code == 200 and appr["status"] == "pending", str(appr)[:200])
    _, pend = call("GET", "/api/approvals?status=pending", role="pharmacist")
    check("2. pharmacist sees the request", any(a["id"] == appr["id"] for a in pend))
    code, dec = call("POST", f"/api/approvals/{appr['id']}/decide", role="pharmacist", json={"decision": "approved", "note": "Smoke test"})
    check("2. pharmacist approves", code == 200 and dec["status"] == "approved")
    _, mine = call("GET", f"/api/approvals/{appr['id']}")
    check("2. patient timeline shows 'Tasdiqlandi'", mine["status"] == "approved")
    code, _ = call("POST", f"/api/approvals/{appr['id']}/decide", role="patient", json={"decision": "approved"})
    check("2. patient cannot decide (403)", code == 403)

    # 3. Dorilarim: gipertoniya + bisoprolol, add paracetamol x3, what-if Tylol Hot x1
    _, pat = call("GET", "/api/patient")
    check("3. patient has gipertoniya", "gipertoniya" in pat["conditions"])
    _, reg = call("GET", "/api/regimen")
    check("3. bisoprolol in regimen", any("bisoprolol" in r["product"]["inns_display"] for r in reg))
    for r in reg:  # clean slate: keep only the beta-blocker
        if "bisoprolol" not in r["product"]["inns_display"]:
            call("DELETE", f"/api/regimen/{r['id']}")
    code, reg = call("POST", "/api/regimen", json={"product_id": para_id, "units_per_day": 3})
    check("3. paracetamol 500 mg x3/day added", code == 200 and any(r["product"]["id"] == para_id and r["units_per_day"] == 3 for r in reg))
    tylol_id = by["tylol_hot"]["product_id"]
    code, wi = call("POST", "/api/safety/check", json={"product_id": tylol_id, "units_per_day": 1})
    ids = {w["id"] for w in wi["new_warnings"]}
    check("3. what-if: duplicate paracetamol", "duplicate:paratsetamol" in ids, str(ids))
    m = next(x for x in wi["meters"] if x["inn"] == "paratsetamol")
    check("3. what-if meter 1 500 -> 2 000 / 4 000 mg", (m["before_mg"], m["total_mg"], m["limit_mg"]) == (1500, 2000, 4000), str(m))
    danger = [w for w in wi["new_warnings"] if w["severity"] == "danger"]
    check("3. red: psevdoefedrin + gipertoniya", any(w["id"] == "drug_condition:psevdoefedrin:gipertoniya" for w in danger))
    check("3. red: psevdoefedrin + beta-blocker", any(w["kind"] == "drug_drug" and "bisoprolol" in w["inns"] for w in danger))
    check("3. every warning ends with consult sentence",
          all(w["message_uz"].endswith("Shifokor yoki farmatsevt bilan maslahatlashing.") for w in wi["after"]["warnings"]))

    # 4. AI rules from Tylol Hot leaflet -> approve one
    code, lr = call("POST", "/api/admin/llm/leaflet-rules", role="pharmacist")
    check("4. leaflet -> proposed rules", code == 200 and len(lr["rules"]) > 0 and all(r["approved"] is False for r in lr["rules"]),
          f"source={lr and lr.get('source')} error={lr and lr.get('error')}")
    print(f"      (rules source: {lr.get('source')}, model: {lr.get('model')})")
    rid = lr["rules"][0]["id"]
    code, ar = call("POST", f"/api/rules/{rid}/approve", role="pharmacist")
    check("4. pharmacist approves one rule", code == 200 and ar["approved"] is True)
    code, _ = call("POST", "/api/admin/llm/leaflet-rules", role="patient")
    check("4. patient cannot run admin LLM (403)", code == 403)

    # 5. clone code
    code, c = call("POST", "/api/scan", json={"raw": by["clone"]["element_string"], "city": "Toshkent"})
    ok = code == 200
    check("5. clone scan", ok)
    if ok:
        check("5. 'Klon kod' alert", any(a["code"] == "clone" for a in c["alerts"]))
        mcomp = next(x for x in c["trust"]["components"] if x["key"] == "M")
        check("5. M component lowered", mcomp["score"] <= 40, str(mcomp["score"]))

    # extras
    code, e = call("POST", "/api/scan", json={"raw": "not a code"})
    check("x. invalid code -> 422 with Uzbek message", code == 422 and isinstance(e.get("detail"), str))
    code, rep = call("POST", "/api/reports", json={"product_id": tylol_id, "text": "Ichgandan keyin terimda toshma chiqdi"})
    check("x. report classified", code == 200 and rep["category"] in ("allergik reaksiya", "nojo'ya ta'sir"), str(rep)[:150])
    code, ms = call("GET", "/api/maker/stats", role="maker")
    check("x. maker stats", code == 200 and ms["kpis"]["scans"] > 0 and len(ms["scans_by_day"]["values"]) == 30)

    # cleanup: remove what step 3 added
    _, reg = call("GET", "/api/regimen")
    for r in reg:
        if r["product"]["id"] == para_id:
            call("DELETE", f"/api/regimen/{r['id']}")

    failed = [n for n, ok, _ in results if not ok]
    print(f"\n{len(results) - len(failed)}/{len(results)} passed" + (f"; FAILED: {failed}" if failed else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
