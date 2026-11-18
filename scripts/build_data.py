"""Generates data/products.json, data/batches.json and data/codes.json.

Run once (already run; the JSON files are committed):  python scripts/build_data.py
GTIN check digits are computed here so every demo code is a valid GS1 element string.

# MOCK: every product below is demo data. Local manufacturers are fictional.
# Prices are approximate and marked is_mock.
"""
from __future__ import annotations

import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"


def gtin_check_digit(body: str) -> str:
    total = 0
    for i, ch in enumerate(reversed(body)):
        total += int(ch) * (3 if i % 2 == 0 else 1)
    return str((10 - total % 10) % 10)


def make_gtin14(prefix: str, item: int) -> str:
    body12 = (prefix + str(item).zfill(12 - len(prefix)))[:12]
    gtin13 = body12 + gtin_check_digit(body12)
    return "0" + gtin13


ORAL = "og'iz orqali"
TAB = "tabletka"
CAP = "kapsula"

LOCAL_MAKERS = {
    "demo": ("Demo Farm MChJ", "O'zbekiston"),
    "navroz": ("Navro'z Farm (demo)", "O'zbekiston"),
    "shifo": ("Shifo Lab (demo)", "O'zbekiston"),
    "vodiy": ("Oltin Vodiy Farm (demo)", "O'zbekiston"),
}
IMPORT_MAKERS = {
    "euro": ("EuroGenerics GmbH (demo)", "Germaniya", "400"),
    "anatoliya": ("Anatoliya Ilac A.S. (demo)", "Turkiya", "869"),
    "balkan": ("Balkan Pharma d.o.o. (demo)", "Sloveniya", "383"),
    "danube": ("Danube Pharma Zrt (demo)", "Vengriya", "599"),
    "indus": ("Indus Remedies Ltd (demo)", "Hindiston", "890"),
}

# key, trade_name, inns, form, route, maker, rx, price, max_units, gmp, be, shelf_months, original
P = [
    # --- 9 import -> local pairs ---
    ("para_imp", "Paratsetamol 500 mg tabletka №20", [("paratsetamol", 500)], TAB, ORAL, "euro", False, 32000, 8, True, True, 48, False),
    ("para_loc", "Paratsetamol-Demo 500 mg tabletka №20", [("paratsetamol", 500)], TAB, ORAL, "demo", False, 14000, 8, True, True, 36, False),
    ("ibu_imp", "Ibuprofen 400 mg tabletka №20", [("ibuprofen", 400)], TAB, ORAL, "anatoliya", False, 38000, 3, True, True, 36, False),
    ("ibu_loc", "Ibuprofen-Navro'z 400 mg tabletka №20", [("ibuprofen", 400)], TAB, ORAL, "navroz", False, 21000, 3, True, True, 36, False),
    ("dic_imp", "Diklofenak 50 mg tabletka №20", [("diklofenak", 50)], TAB, ORAL, "balkan", False, 29000, 3, True, True, 36, False),
    ("dic_loc", "Diklofenak-Shifo 50 mg tabletka №20", [("diklofenak", 50)], TAB, ORAL, "shifo", False, 15500, 3, True, True, 24, False),
    ("met_imp", "Metformin 500 mg tabletka №60", [("metformin", 500)], TAB, ORAL, "danube", True, 54000, 4, True, True, 36, False),
    ("met_loc", "Metformin-Shifo 500 mg tabletka №60", [("metformin", 500)], TAB, ORAL, "shifo", True, 27000, 4, True, True, 36, False),
    ("aml_imp", "Amlodipin 5 mg tabletka №30", [("amlodipin", 5)], TAB, ORAL, "indus", True, 36000, 2, True, True, 36, False),
    ("aml_loc", "Amlodipin-Vodiy 5 mg tabletka №30", [("amlodipin", 5)], TAB, ORAL, "vodiy", True, 19000, 2, True, True, 24, False),
    ("ome_imp", "Omeprazol 20 mg kapsula №30", [("omeprazol", 20)], CAP, ORAL, "anatoliya", False, 42000, 2, True, True, 36, False),
    ("ome_loc", "Omeprazol-Demo 20 mg kapsula №30", [("omeprazol", 20)], CAP, ORAL, "demo", False, 23000, 2, True, True, 24, False),
    ("set_imp", "Setirizin 10 mg tabletka №10", [("setirizin", 10)], TAB, ORAL, "euro", False, 31000, 1, True, True, 36, False),
    ("set_loc", "Setirizin-Navro'z 10 mg tabletka №10", [("setirizin", 10)], TAB, ORAL, "navroz", False, 16000, 1, True, True, 36, False),
    ("bis_imp", "Bisoprolol 5 mg tabletka №30", [("bisoprolol", 5)], TAB, ORAL, "euro", True, 46000, 2, True, True, 36, False),
    ("bis_loc", "Bisoprolol-Shifo 5 mg tabletka №30", [("bisoprolol", 5)], TAB, ORAL, "shifo", True, 24000, 2, True, True, 36, False),
    ("var_imp", "Varfarin 5 mg tabletka №50", [("varfarin", 5)], TAB, ORAL, "danube", True, 61000, 2, True, True, 36, False),
    ("var_loc", "Varfarin-Vodiy 5 mg tabletka №50", [("varfarin", 5)], TAB, ORAL, "vodiy", True, 39000, 2, True, None, 24, False),
    # --- demo cases ---
    ("tylol", "Tylol Hot 500 mg+60 mg+4 mg kukun, 1 paket",
     [("paratsetamol", 500), ("psevdoefedrin", 60), ("xlorfeniramin", 4)], "kukun (paket)", ORAL, "nobel", False, 6500, 4, True, None, 24, True),
    ("tylol_loc", "Gripp-Demo Hot kukun, 1 paket",
     [("paratsetamol", 500), ("psevdoefedrin", 60), ("xlorfeniramin", 4)], "kukun (paket)", ORAL, "navroz", False, 3500, 4, True, True, 24, False),
    ("dentashan", "Dentashan milk uchun gel 25 g №1",
     [("metronidazol", 16), ("xlorgeksidin", 2.5)], "gel", "stomatologik", "lincoln", False, 48000, 3, True, None, 36, True),
    ("dent_loc", "Metroxil-Denta gel 25 g №1",
     [("metronidazol", 16), ("xlorgeksidin", 2.5)], "gel", "stomatologik", "demo", False, 26000, 3, True, True, 24, False),
    # --- singles ---
    ("asa_loc", "Atsetilsalitsil kislota 100 mg tabletka №30", [("atsetilsalitsil kislota", 100)], TAB, ORAL, "shifo", False, 9000, 1, True, True, 36, False),
    ("keto_imp", "Ketoprofen 100 mg tabletka №20", [("ketoprofen", 100)], TAB, ORAL, "balkan", True, 44000, 2, True, True, 36, False),
    ("napr_imp", "Naproksen 250 mg tabletka №20", [("naproksen", 250)], TAB, ORAL, "indus", False, 27000, 4, False, True, 36, False),
    ("lor_loc", "Loratadin-Demo 10 mg tabletka №10", [("loratadin", 10)], TAB, ORAL, "demo", False, 8500, 1, True, True, 36, False),
    ("dif_loc", "Difengidramin 50 mg tabletka №20", [("difengidramin", 50)], TAB, ORAL, "vodiy", True, 7000, 3, True, True, 36, False),
    ("meto_imp", "Metoprolol 50 mg tabletka №30", [("metoprolol", 50)], TAB, ORAL, "danube", True, 39000, 4, True, True, 36, False),
    ("aten_loc", "Atenolol-Shifo 50 mg tabletka №30", [("atenolol", 50)], TAB, ORAL, "shifo", True, 12000, 2, True, True, 36, False),
    ("liz_loc", "Lizinopril-Navro'z 10 mg tabletka №30", [("lizinopril", 10)], TAB, ORAL, "navroz", True, 18000, 4, True, True, 36, False),
    ("ena_imp", "Enalapril 10 mg tabletka №20", [("enalapril", 10)], TAB, ORAL, "balkan", True, 25000, 4, True, True, 36, False),
    ("ator_imp", "Atorvastatin 20 mg tabletka №30", [("atorvastatin", 20)], TAB, ORAL, "euro", True, 69000, 4, True, True, 36, False),
    ("azi_imp", "Azitromitsin 500 mg tabletka №3", [("azitromitsin", 500)], TAB, ORAL, "indus", True, 35000, 1, True, True, 24, False),
    ("amox_loc", "Amoksitsillin-Demo 500 mg kapsula №16", [("amoksitsillin", 500)], CAP, ORAL, "demo", True, 17000, 3, True, True, 24, False),
    ("pant_imp", "Pantoprazol 40 mg tabletka №28", [("pantoprazol", 40)], TAB, ORAL, "anatoliya", False, 58000, 2, True, True, 36, False),
]

# batch spec per product key: list of (batch_no, mfg, exp, recalled)
BATCHES = {
    "para_imp": [("EG2504P", "2025-04-10", "2029-04-30", False)],
    "para_loc": [("DF2508P", "2025-08-02", "2028-08-31", False)],
    "ibu_imp": [("AN2410I", "2024-10-15", "2027-10-31", False), ("AN2506I", "2025-06-01", "2028-06-30", False)],
    "ibu_loc": [("NV2507I", "2025-07-20", "2028-07-31", False)],
    "dic_imp": [("BP2402D", "2024-02-11", "2027-02-28", True), ("BP2509D", "2025-09-05", "2028-09-30", False)],
    "dic_loc": [("SH2506D", "2025-06-18", "2027-06-30", False)],
    "met_imp": [("DP2503M", "2025-03-03", "2028-03-31", False)],
    "met_loc": [("SH2505M", "2025-05-12", "2028-05-31", False)],
    "aml_imp": [("IR2501A", "2025-01-21", "2028-01-31", False)],
    "aml_loc": [("OV2501A", "2025-01-15", "2027-01-31", False), ("OV2509A", "2025-09-10", "2027-09-30", False)],
    "ome_imp": [("AN2505O", "2025-05-05", "2028-05-31", False)],
    "ome_loc": [("DF2507O", "2025-07-01", "2027-07-31", False)],
    "set_imp": [("EG2309S", "2023-09-01", "2026-09-30", False), ("EG2507S", "2025-07-07", "2028-07-31", False)],
    "set_loc": [("NV2504S", "2025-04-14", "2028-04-30", False)],
    "bis_imp": [("EG2502B", "2025-02-02", "2028-02-29", False)],
    "bis_loc": [("SH2506B", "2025-06-06", "2028-06-30", False)],
    "var_imp": [("DP2410V", "2024-10-10", "2027-10-31", False)],
    "var_loc": [("OV2505V", "2025-05-25", "2027-05-31", False)],
    "tylol": [("NB2506T", "2025-06-12", "2027-06-30", False)],
    "tylol_loc": [("NV2508T", "2025-08-08", "2027-08-31", False)],
    "dentashan": [("LP2407G", "2024-07-19", "2027-07-31", False)],
    "dent_loc": [("DF2509G", "2025-09-09", "2027-09-30", False)],
}
DEFAULT_BATCH = lambda key, i: (f"{key[:3].upper()}25{i:02d}X", "2025-03-01", "2028-02-29", False)

# The team's real Dentashan box (scannable on stage). Its GTIN replaces the generated one; the batch and serial are
# added after the random loop so every other generated serial stays exactly the same.
REAL_GTIN = {"dentashan": "08906045340359"}
REAL_PACKS = [  # (product key, batch, mfg, exp, serial)
    ("dentashan", "EU601", "2026-01-01", "2028-12-31", "7D126A0001245"),
]

FEATURED = [
    # (product key, batch_no or None, scenario, label)
    ("dentashan", "LP2407G", "conformity_expired", "Dentashan gel"),
    ("para_imp", "EG2504P", "import_paracetamol", "Paratsetamol (import)"),
    ("para_loc", "DF2508P", "local_paracetamol", "Paratsetamol (mahalliy)"),
    ("tylol", "NB2506T", "tylol_hot", "Tylol Hot"),
    ("ome_imp", "AN2505O", "clone", "Omeprazol — klon kod"),
    ("dic_imp", "BP2402D", "recalled", "Diklofenak — qaytarib olingan"),
    ("set_imp", "EG2309S", "expired", "Setirizin — muddati o'tgan"),
    ("ibu_imp", "AN2410I", "coa_out_of_spec", "Ibuprofen (import)"),
    ("aml_loc", "OV2501A", "near_expiry", "Amlodipin — muddati yaqin"),
]
CLONE_SERIAL = "OMEK7Q2X9ZB41"  # pre-seeded as scanned in Samarqand
UNKNOWN_SERIAL = "ZZFAKE0000001"  # never stored in the Code table


def yymmdd(iso: str) -> str:
    y, m, d = iso.split("-")
    return y[2:] + m + d


def element_string(gtin: str, serial: str, exp_iso: str, batch: str) -> str:
    return f"(01){gtin}(21){serial}(17){yymmdd(exp_iso)}(10){batch}"


def raw_inn_string(inns):
    # mimic the messy official formatting: capitalised, odd dashes, dot decimals
    parts = []
    for inn, mg in inns:
        mg_s = str(mg).replace(",", ".")
        parts.append(f"{inn.capitalize()}-{mg_s} mg")
    return ", ".join(parts)


def main():
    rng = random.Random(17)
    products, batches, codes = [], [], []
    counters = {}
    for idx, row in enumerate(P, start=1):
        key, name, inns, form, route, maker, rx, price, max_u, gmp, be, shelf, original = row
        if maker in LOCAL_MAKERS:
            mname, country = LOCAL_MAKERS[maker]
            prefix, is_local = "478", True
        elif maker in IMPORT_MAKERS:
            mname, country, prefix = IMPORT_MAKERS[maker]
            is_local = False
        elif maker == "nobel":
            mname, country, prefix, is_local = "NOBEL İLAÇ SANAYİİ VE TİCARET A.Ş.", "Turkiya", "869", False
        else:  # lincoln
            mname, country, prefix, is_local = "LINCOLN PHARMACEUTICALS LIMITED", "Hindiston", "890", False
        counters[prefix] = counters.get(prefix, 100) + 7
        gtin = make_gtin14(prefix + "7", 1000 + idx * 13 + counters[prefix])
        gtin = REAL_GTIN.get(key, gtin)
        conformity_expired = key == "dentashan"
        raw = {
            "Savdo nomi": name,
            "Ishlab chiqaruvchi": mname,
            "Ishlab chiqaruvchi mamlakat": country,
            "Ta'sir qiluvchi moddalar": raw_inn_string(inns),
            "Dori shakli": form,
            "Boshqaruv usuli": "Og'iz orqali" if route == ORAL else "Stomatologiya",
            "Yaroqlilik muddati": str(shelf),
            "Retsept bo'yicha": "Ha" if rx else "Yo'q",
            "Ro'yxatdan o'tganlik holati": "Ro'yxatdan o'tgan",
            "Muvofiqlik hujjatining tugaganligining belgisi": "Ha" if conformity_expired else "Yo'q",
        }
        if key == "dentashan":
            # exact messy source fields from the official app
            raw["Ta'sir qiluvchi moddalar"] = "Metrodonidazol -16 mg, hlorgeksedin-2.5 mg"
            raw["Yaroqlilik muddati"] = "36"
            raw["Boshqaruv usuli"] = "Stomatologiya"
            raw["Muvofiqlik hujjatining tugaganligining belgisi"] = "Ha"
        products.append({
            "key": key, "gtin": gtin, "trade_name": name,
            "inn_list": [{"inn": i, "amount_mg": mg} for i, mg in inns],
            "dose_form": form, "route": route, "manufacturer": mname, "country": country,
            "is_local": is_local, "rx_only": rx, "reg_status": "registered",
            "conformity_expired": conformity_expired, "gmp": gmp, "bioequivalence": be,
            "price_uzs": price, "max_units_per_day": max_u, "shelf_life_months": shelf,
            "is_original": original, "raw_official": raw, "is_mock": True,
        })
        specs = BATCHES.get(key) or [DEFAULT_BATCH(key, 1 + idx % 9)]
        for b in specs:
            bno, mfg, exp, recalled = b
            batches.append({"product_key": key, "batch_no": bno, "mfg_date": mfg, "exp_date": exp, "recalled": recalled})
            n_codes = 3
            for c in range(n_codes):
                serial = "".join(rng.choice("ABCDEFGHJKLMNPQRSTUVWXYZ23456789") for _ in range(13))
                if key == "ome_imp" and c == 0:
                    serial = CLONE_SERIAL
                status = "withdrawn" if recalled else "valid"
                codes.append({
                    "product_key": key, "gtin": gtin, "serial": serial, "batch_no": bno, "exp_date": exp,
                    "status": status, "element_string": element_string(gtin, serial, exp, bno),
                })

    for key, bno, mfg, exp, serial in REAL_PACKS:
        gtin = next(p["gtin"] for p in products if p["key"] == key)
        batches.append({"product_key": key, "batch_no": bno, "mfg_date": mfg, "exp_date": exp, "recalled": False})
        codes.append({"product_key": key, "gtin": gtin, "serial": serial, "batch_no": bno, "exp_date": exp,
                      "status": "valid", "element_string": element_string(gtin, serial, exp, bno)})

    featured = []
    for key, bno, scenario, label in FEATURED:
        code = next(c for c in codes if c["product_key"] == key and c["batch_no"] == bno)
        if scenario == "clone":
            code = next(c for c in codes if c["serial"] == CLONE_SERIAL)
        featured.append({"scenario": scenario, "label": label, "product_key": key, "element_string": code["element_string"],
                         "serial": code["serial"], "batch_no": bno})
    # unknown code: valid GTIN of the local paracetamol, serial that does not exist officially
    pl = next(p for p in products if p["key"] == "para_loc")
    featured.append({"scenario": "unknown", "label": "Noma'lum seriya", "product_key": "para_loc",
                     "element_string": element_string(pl["gtin"], UNKNOWN_SERIAL, "2028-08-31", "DF2508P"),
                     "serial": UNKNOWN_SERIAL, "batch_no": "DF2508P"})
    # EAN-13 only
    featured.append({"scenario": "ean13", "label": "Faqat shtrix-kod (EAN-13)", "product_key": "para_imp",
                     "element_string": next(p for p in products if p["key"] == "para_imp")["gtin"][1:],
                     "serial": None, "batch_no": None})

    (DATA / "products.json").write_text(json.dumps(products, ensure_ascii=False, indent=1), encoding="utf-8")
    (DATA / "batches.json").write_text(json.dumps(batches, ensure_ascii=False, indent=1), encoding="utf-8")
    (DATA / "codes.json").write_text(json.dumps({"clone_serial": CLONE_SERIAL, "clone_first_city": "Samarqand",
                                                 "featured": featured, "codes": codes}, ensure_ascii=False, indent=1),
                                     encoding="utf-8")
    print(f"products={len(products)} batches={len(batches)} codes={len(codes)} featured={len(featured)}")


if __name__ == "__main__":
    main()
