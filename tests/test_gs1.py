from datetime import date

import pytest

from app import gs1

GTIN = "04007000011209"


def test_gs_separated():
    r = gs1.parse(f"01{GTIN}21SER123\x1d17290430" + "10EG2504P")
    assert r["gtin"] == GTIN and r["serial"] == "SER123" and r["batch"] == "EG2504P"
    assert r["exp_date"] == date(2029, 4, 30) and r["kind"] == "datamatrix"


def test_parenthesized():
    r = gs1.parse(f"(01){GTIN}(21)4VZUMTHBR24SW(17)290430(10)EG2504P")
    assert (r["serial"], r["batch"], r["exp_date"]) == ("4VZUMTHBR24SW", "EG2504P", date(2029, 4, 30))


def test_d2_prefix_with_leading_fnc1_and_crypto():
    raw = f"]d2\x1d01{GTIN}21ABC\x1d91EE10\x1d92dGVzdA=="
    r = gs1.parse(raw)
    assert r["gtin"] == GTIN and r["serial"] == "ABC" and r["crypto"] == {"91": "EE10", "92": "dGVzdA=="}


def test_ean13():
    r = gs1.parse("4007000011209")
    assert r["gtin"] == "0" + "4007000011209" and r["kind"] == "ean13" and r["serial"] is None


@pytest.mark.parametrize("raw", ["", "hello", "4007000011208", f"(01){GTIN[:-1]}0(21)X", "01123", f"01{GTIN}17291340"])
def test_invalid(raw):
    with pytest.raises(ValueError):
        gs1.parse(raw)


def test_dd00_is_last_day_of_month():
    r = gs1.parse(f"(01){GTIN}(17)280200(10)B1")
    assert r["exp_date"] == date(2028, 2, 29)  # leap year
    assert gs1.parse(f"(01){GTIN}(17)270400")["exp_date"] == date(2027, 4, 30)


def test_fixed_order_without_gs():
    r = gs1.parse(f"01{GTIN}17290430" + "10EG2504P")
    assert r["exp_date"] == date(2029, 4, 30) and r["batch"] == "EG2504P"


def test_typed_gs_token():
    r = gs1.parse(f"01{GTIN}21SER<GS>10LOT1")
    assert r["serial"] == "SER" and r["batch"] == "LOT1"


# ---- the team's real Dentashan box (Asl Belgisi layout), as different decoders return it
REAL_GTIN, REAL_SERIAL = "08906045340359", "7D126A0001245"
CRYPTO92 = "q8Lk3sZr/AbcDEf+gh1xyZ1234567890123456789Ab="


@pytest.mark.parametrize("raw", [
    # BarcodeDetector / ML Kit style: symbology prefix, GS separators, crypto tail
    f"]d2010{REAL_GTIN[1:]}21{REAL_SERIAL}\x1d17281231" + "10EU601\x1d91EE11\x1d92" + CRYPTO92,
    # ZXing-js: leading FNC1 emitted as GS
    f"\x1d01{REAL_GTIN}21{REAL_SERIAL}\x1d17281231" + "10EU601\x1d91EE11\x1d92" + CRYPTO92,
    # zxing-cpp Plain text: no leading FNC1
    f"01{REAL_GTIN}21{REAL_SERIAL}\x1d17281231" + "10EU601\x1d91EE11\x1d92" + CRYPTO92,
    # a decoder that drops every GS
    f"01{REAL_GTIN}21{REAL_SERIAL}17281231" + "10EU601" + "91EE11" + "92" + CRYPTO92,
    # HRI text where the crypto value itself contains parentheses
    f"(01){REAL_GTIN}(21){REAL_SERIAL}(17)281231(10)EU601(91)EE11(92)ab(c)d",
])
def test_real_dentashan_pack(raw):
    r = gs1.parse(raw)
    assert (r["gtin"], r["serial"], r["batch"], r["exp_date"]) == (REAL_GTIN, REAL_SERIAL, "EU601", date(2028, 12, 31))
    assert r["kind"] == "datamatrix"


def test_real_pack_crypto_kept_separately():
    r = gs1.parse(f"]d201{REAL_GTIN}21{REAL_SERIAL}\x1d17281231" + "10EU601\x1d91EE11\x1d92" + CRYPTO92)
    assert r["crypto"] == {"91": "EE11", "92": CRYPTO92}


def test_gsless_parser_is_fast_on_hostile_input():
    import time
    t = time.time()
    for raw in ["21" + "10" * 140, "10" + "9" * 280, f"01{GTIN}21" + "17" * 100]:
        with pytest.raises(ValueError):
            gs1.parse(raw)
    assert time.time() - t < 1.0
