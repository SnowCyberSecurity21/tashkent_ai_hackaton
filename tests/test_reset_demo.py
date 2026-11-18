"""POST /api/admin/reset-demo restores the seeded demo state between mentor demos."""
from fastapi.testclient import TestClient
from sqlmodel import Session, func, select

from app.db import engine
from app.main import app
from app.models import Approval, LlmCache, Rating, Report, SafetyRule, Scan
from scripts.seed import _seeded_counts

PAT = {"X-Demo-Role": "patient"}
PH = {"X-Demo-Role": "pharmacist"}


def count(model, *where):
    with Session(engine) as s:
        q = select(func.count()).select_from(model)
        for w in where:
            q = q.where(w)
        return s.exec(q).one()


def test_reset_demo_restores_seed_state():
    with TestClient(app) as c:  # startup seeds the empty temp DB
        c.post("/api/admin/reset-demo", headers=PH)  # start from the seeded state whatever earlier tests did
        seed_scans = count(Scan)
        seed_rules = count(SafetyRule, SafetyRule.approved == True)  # noqa: E712
        assert seed_scans == _seeded_counts()["scans"]
        with Session(engine) as s:
            s.add(LlmCache(key="keep-me", task="test", model="m", response_json={"data": 1}))
            s.commit()

        featured = {f["scenario"]: f for f in c.get("/api/codes").json()["featured"]}
        # --- a full demo run ---------------------------------------------------------------
        para = c.post("/api/scan", json={"raw": featured["import_paracetamol"]["element_string"]}, headers=PAT).json()
        c.post("/api/scan", json={"raw": featured["clone"]["element_string"], "city": "Toshkent"}, headers=PAT)
        local = next(a for a in c.get(f"/api/products/{para['product']['id']}/analogs").json()["analogs"] if a["is_local"])
        appr = c.post("/api/approvals", json={"from_product_id": para["product"]["id"], "to_product_id": local["id"]},
                      headers=PAT).json()
        c.post(f"/api/approvals/{appr['id']}/decide", json={"decision": "approved"}, headers=PH)
        seeded_pending = [a for a in c.get("/api/approvals?status=pending", headers=PH).json()]
        for a in seeded_pending:  # the pharmacist also decides the seeded request
            c.post(f"/api/approvals/{a['id']}/decide", json={"decision": "rejected"}, headers=PH)
        c.post("/api/regimen", json={"product_id": para["product"]["id"], "units_per_day": 3}, headers=PAT)
        c.put("/api/patient", json={"conditions": ["astma"], "alcohol": True}, headers=PAT)
        c.post("/api/reports", json={"product_id": para["product"]["id"], "text": "Terimda toshma chiqdi"}, headers=PAT)
        c.post("/api/ratings", json={"product_id": para["product"]["id"], "stars": 2}, headers=PAT)
        rules = c.post("/api/admin/llm/leaflet-rules", headers=PH).json()["rules"]
        c.post(f"/api/rules/{rules[0]['id']}/approve", headers=PH)
        assert count(Scan) > seed_scans and count(SafetyRule, SafetyRule.origin == "llm") > 0

        # --- reset ---------------------------------------------------------------------------
        assert c.post("/api/admin/reset-demo", headers=PAT).status_code == 403
        r = c.post("/api/admin/reset-demo", headers=PH)
        assert r.status_code == 200 and r.json()["ok"]

        pat = c.get("/api/patient", headers=PAT).json()
        assert pat["conditions"] == ["gipertoniya"] and pat["alcohol"] is False
        reg = c.get("/api/regimen", headers=PAT).json()
        assert len(reg) == 1 and "bisoprolol" in reg[0]["product"]["inns_display"] and reg[0]["units_per_day"] == 1

        pending = c.get("/api/approvals?status=pending", headers=PH).json()
        assert count(Approval) == 1 and len(pending) == 1 and pending[0]["status"] == "pending"
        assert count(Report) == _seeded_counts()["reports"] and count(Rating) == _seeded_counts()["ratings"]
        assert count(Scan) == seed_scans
        clone = featured["clone"]
        assert count(Scan, Scan.serial == clone["serial"]) == 1  # the pre-seeded Samarqand scan stays

        assert count(SafetyRule, SafetyRule.origin == "llm") == 0
        assert count(SafetyRule, SafetyRule.approved == True) == seed_rules  # noqa: E712
        assert count(LlmCache, LlmCache.key == "keep-me") == 1

        # the clone demo still works after a reset
        again = c.post("/api/scan", json={"raw": clone["element_string"], "city": "Toshkent"}, headers=PAT).json()
        assert any(a["code"] == "clone" for a in again["alerts"])
        c.post("/api/admin/reset-demo", headers=PH)
