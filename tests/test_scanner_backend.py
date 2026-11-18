"""Real Dentashan box: seed data, POST /api/scan with a realistic raw string, POST /api/decode-image."""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app

FIX = Path(__file__).parent / "fixtures" / "dentashan_real_dm.png"
RAW = "]d2" + "0108906045340359" + "217D126A0001245" + "\x1d" + "17281231" + "10EU601" + "\x1d" + "91EE11" + "\x1d92" + "q8Lk3sZr/AbcDEf+gh1xyZ1234567890123456789Ab="
H = {"X-Demo-Role": "patient"}


def test_real_box_scans_as_dentashan():
    with TestClient(app) as c:
        r = c.post("/api/scan", json={"raw": RAW, "city": "Toshkent"}, headers=H)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["product"]["gtin"] == "08906045340359" and "Dentashan" in d["product"]["trade_name"]
        assert d["official"]["authentic"] is True and d["batch"]["batch_no"] == "EU601"
        assert d["batch"]["exp_date"] == "2028-12-31"
        assert d["banner"]["color"] == "red"
        assert any(a["title_uz"] == "Muvofiqlik hujjati muddati tugagan" for a in d["alerts"])
        assert d["parsed"]["crypto"]["91"] == "EE11"


def test_decode_image_endpoint():
    pytest.importorskip("zxingcpp")
    with TestClient(app) as c:
        r = c.post("/api/decode-image", files={"file": ("box.png", FIX.read_bytes(), "image/png")})
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["format"] == "DataMatrix" and "\x1d" in d["text"] and d["text"].startswith("010890604534035")
        assert c.post("/api/scan", json={"raw": d["text"]}, headers=H).json()["batch"]["batch_no"] == "EU601"


def test_decode_image_not_found_message():
    pytest.importorskip("zxingcpp")
    from io import BytesIO

    from PIL import Image

    buf = BytesIO()
    Image.new("RGB", (400, 300), (190, 190, 190)).save(buf, "PNG")
    with TestClient(app) as c:
        r = c.post("/api/decode-image", files={"file": ("x.png", buf.getvalue(), "image/png")})
        assert r.status_code == 404 and r.json()["detail"].startswith("Kod topilmadi.")


def test_exact_string_scanned_from_the_real_box_on_a_phone():
    """Captured from the server log (scan raw=...): real Asl Belgisi packs carry only 01+21+91+92, no (17)/(10).
    Batch and expiry come from the registered code, as in the real registry."""
    raw = "\x1d0108906045340359217D126A0001245\x1d91Bf6T\x1d92S0keiDJuQXNKa3pmcDZyTHFBcHVCVStkZ0R5YbYZbco="
    with TestClient(app) as c:
        d = c.post("/api/scan", json={"raw": raw, "city": "Toshkent"}, headers=H).json()
        assert d["official"]["authentic"] is True and d["banner"]["color"] == "red"
        assert d["batch"]["batch_no"] == "EU601" and d["batch"]["exp_date"] == "2028-12-31"
        assert set(d["parsed"]["crypto"]) == {"91", "92"}
