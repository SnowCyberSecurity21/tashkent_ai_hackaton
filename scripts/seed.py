"""Seeds mezon.db from data/*.json.  Run:  python scripts/seed.py   (drops and recreates all tables)

Also called on app startup when the DB is empty (seed_if_empty).
# MOCK: all scans, ratings, reports and patients below are generated demo data.
"""
from __future__ import annotations

import hashlib
import random
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlmodel import Session, SQLModel, delete, func, select  # noqa: E402

from app import config  # noqa: E402
from app.db import engine, init_db, load_json  # noqa: E402
from app.models import (Approval, Batch, Code, Document, LabResult, Patient, Product, Rating, Regimen,  # noqa: E402
                        Report, SafetyRule, Scan)

CITIES = ["Toshkent", "Toshkent", "Toshkent", "Samarqand", "Buxoro", "Andijon", "Namangan", "Farg'ona", "Nukus", "Qarshi"]
SCAN_VOLUME = {  # approximate scans in the last 30 days (anonymous)
    "para_imp": 48, "para_loc": 61, "tylol": 37, "dentashan": 14, "ibu_imp": 29, "ibu_loc": 33, "dic_imp": 18,
    "dic_loc": 22, "ome_imp": 16, "ome_loc": 19, "set_imp": 12, "set_loc": 15, "bis_loc": 21, "bis_imp": 9,
    "aml_loc": 17, "aml_imp": 11, "met_loc": 13, "met_imp": 8, "tylol_loc": 9, "dent_loc": 7,
    "keto_imp": 2, "napr_imp": 1, "ena_imp": 3,
}
RATINGS = {
    "para_imp": [4, 5, 4, 4, 5], "para_loc": [5, 5, 4, 5, 4, 5], "ibu_loc": [5, 4, 4, 5], "ibu_imp": [4, 3, 4],
    "tylol": [4, 5, 4, 4], "aml_loc": [5, 4, 5], "bis_loc": [4, 5, 5], "dic_loc": [4, 4, 5], "ome_loc": [4, 5],
    "set_loc": [5, 4], "met_loc": [4, 4, 5], "tylol_loc": [4, 4],
}
REPORTS = [
    ("ibu_imp", "AN2410I", "Tabletka sekin eriydi, og'riq kech qoldi", "samarasizlik", "info", 6),
    ("ibu_imp", "AN2410I", "Ichgandan keyin oshqozonda og'riq bo'ldi", "nojo'ya ta'sir", "warn", 11),
    ("tylol", "NB2506T", "Ichgandan keyin kuchli uyquchanlik bo'ldi", "nojo'ya ta'sir", "warn", 4),
    ("tylol", "NB2506T", "Paket yirtilgan holda sotildi", "sifat shikoyati", "info", 9),
    ("dic_imp", "BP2402D", "Terimda toshma va lablar shishishi paydo bo'ldi, nafas qisdi", "allergik reaksiya", "danger", 21),
    ("ome_imp", "AN2505O", "Qadoq rangi avvalgisidan boshqacha, kod boshqa shaharda ham chiqdi", "qalbakilik shubhasi", "danger", 2),
    ("para_loc", "DF2508P", "Yaxshi yordam berdi, muammo bo'lmadi", "boshqa", "info", 13),
    ("set_imp", "EG2309S", "Muddati o'tgan qadoq sotildi", "sifat shikoyati", "warn", 5),
    ("aml_loc", "OV2501A", "Boshim biroz aylandi", "nojo'ya ta'sir", "info", 8),
]


def reset() -> None:
    SQLModel.metadata.drop_all(engine)
    init_db()


def seed(session: Session) -> dict:
    rng = random.Random(42)
    today = date.today()
    products = {}
    for p in load_json("products.json"):
        row = Product(**{k: v for k, v in p.items()})
        session.add(row)
        products[p["key"]] = row
    session.commit()
    for row in products.values():
        session.refresh(row)

    batches = {}
    for b in load_json("batches.json"):
        row = Batch(product_id=products[b["product_key"]].id, batch_no=b["batch_no"], mfg_date=date.fromisoformat(b["mfg_date"]),
                    exp_date=date.fromisoformat(b["exp_date"]), recalled=b["recalled"])
        session.add(row)
        batches[b["batch_no"]] = row
    codes = load_json("codes.json")
    for c in codes["codes"]:
        session.add(Code(serial=c["serial"], gtin=c["gtin"], batch_no=c["batch_no"], status=c["status"]))
    session.commit()

    # CoA documents + pre-parsed lab results (LLM not needed at runtime)
    for cert in load_json("coa_results.json")["certificates"]:
        pdf = config.DATA_DIR / "coa" / f"coa_{cert['batch_no']}.pdf"
        sha = hashlib.sha256(pdf.read_bytes()).hexdigest() if pdf.exists() else ""
        doc = Document(product_id=products[cert["product_key"]].id, batch_no=cert["batch_no"], type="CoA",
                       path=str(pdf.relative_to(config.ROOT)) if pdf.exists() else "", sha256=sha, verified=True,
                       ts=datetime.fromisoformat(cert["date"]))
        session.add(doc)
        session.commit()
        session.refresh(doc)
        for r in cert["results"]:
            ok = not ((r["spec_min"] is not None and r["value"] < r["spec_min"]) or
                      (r["spec_max"] is not None and r["value"] > r["spec_max"]))
            session.add(LabResult(document_id=doc.id, parameter=r["parameter"], value=r["value"], spec_min=r["spec_min"],
                                  spec_max=r["spec_max"], unit=r["unit"], status="ok" if ok else "out"))
    session.commit()

    for r in load_json("rules.json")["rules"]:
        session.add(SafetyRule(kind=r["kind"], a=r["a"], b=r["b"], threshold_mg=r["threshold_mg"], severity=r["severity"],
                               message_uz=r["message_uz"], source=r["source"], approved=True, origin="seed"))

    aziza = Patient(name="Aziza (demo)", conditions=["gipertoniya"], alcohol=False)
    bobur = Patient(name="Bobur (demo)", conditions=[], alcohol=False)
    session.add(aziza)
    session.add(bobur)
    session.commit()
    session.refresh(aziza)
    session.refresh(bobur)
    session.add(Regimen(patient_id=aziza.id, product_id=products["bis_loc"].id, units_per_day=1))
    # an existing pending request from another demo patient so the pharmacist queue is not empty
    session.add(Approval(patient_id=bobur.id, from_product_id=products["ibu_imp"].id, to_product_id=products["ibu_loc"].id,
                         status="pending", ts=datetime.now() - timedelta(minutes=18)))

    # anonymous background scans for the maker dashboard and Trust Index (F/gray rule)
    n_scans = 0
    for key, n in SCAN_VOLUME.items():
        p = products[key]
        for _ in range(n):
            day = today - timedelta(days=rng.randint(0, 29))
            ts = datetime.combine(day, datetime.min.time()) + timedelta(minutes=rng.randint(8 * 60, 21 * 60))
            serial = "BG" + "".join(rng.choice("ABCDEFGHJKLMNPQRSTUVWXYZ23456789") for _ in range(11))
            session.add(Scan(serial=serial, gtin=p.gtin, city=rng.choice(CITIES), ts=ts))
            n_scans += 1
    # clone-code scenario: the demo serial was already scanned in Samarqand
    session.add(Scan(serial=codes["clone_serial"], gtin=products["ome_imp"].gtin, city=codes["clone_first_city"],
                     ts=datetime.now() - timedelta(days=3, hours=2)))

    for key, stars in RATINGS.items():
        for i, s in enumerate(stars):
            session.add(Rating(product_id=products[key].id, role="pharmacist" if i % 2 == 0 else "patient", stars=s))
    for key, bno, text, cat, sev, days_ago in REPORTS:
        session.add(Report(product_id=products[key].id, batch_no=bno, text=text, category=cat, severity=sev,
                           classified_by="rules", ts=datetime.now() - timedelta(days=days_ago)))
    session.commit()
    return {"products": len(products), "batches": len(batches), "codes": len(codes["codes"]), "scans": n_scans + 1}


def _seeded_counts() -> dict:
    """How many rows seed() inserts per table; seeded rows are always the lowest ids."""
    return {
        "scans": sum(SCAN_VOLUME.values()) + 1,  # + the pre-seeded clone-code scan
        "ratings": sum(len(v) for v in RATINGS.values()),
        "reports": len(REPORTS),
        "documents": len(load_json("coa_results.json")["certificates"]),
        "patients": 2,
    }


def _last_seeded_id(session: Session, model, n: int) -> int:
    ids = session.exec(select(model.id).order_by(model.id).offset(max(n - 1, 0)).limit(1)).all()
    return ids[0] if ids else 0


def reset_demo(session: Session) -> dict:
    """Puts the demo back to the just-seeded state without touching LlmCache, products or seed rules.

    - demo patient Aziza: conditions [gipertoniya], alcohol off, regimen = bisoprolol only
    - approvals: only the seeded one (Bobur, pending); everything created later is deleted
    - reports, ratings, scans, uploaded documents created after seed are deleted
      (the pre-seeded clone-code scan in Samarqand stays, so the clone demo still works)
    - AI-proposed rules (origin=llm) are deleted; seed rules stay approved
    """
    n = _seeded_counts()
    products = {p.key: p for p in session.exec(select(Product)).all()}
    patients = session.exec(select(Patient).order_by(Patient.id)).all()
    if len(patients) < 2 or "bis_loc" not in products:
        raise RuntimeError("Baza demo seed'iga mos emas: python scripts/seed.py ni ishga tushiring")
    aziza, bobur = patients[0], patients[1]
    extra_ids = [p.id for p in patients[2:]]
    out = {}

    def rm(name, stmt):
        out[name] = out.get(name, 0) + (session.exec(stmt).rowcount or 0)

    # patient + regimen
    aziza.name, aziza.conditions, aziza.alcohol = "Aziza (demo)", ["gipertoniya"], False
    bobur.name, bobur.conditions, bobur.alcohol = "Bobur (demo)", [], False
    session.add(aziza)
    session.add(bobur)
    rm("regimen", delete(Regimen))
    session.add(Regimen(patient_id=aziza.id, product_id=products["bis_loc"].id, units_per_day=1))

    # approvals: keep only the seeded pending request from Bobur
    seeded = session.exec(select(Approval).where(Approval.patient_id == bobur.id,
                                                 Approval.from_product_id == products["ibu_imp"].id,
                                                 Approval.to_product_id == products["ibu_loc"].id)
                          .order_by(Approval.id)).first()
    keep = seeded.id if seeded else -1
    rm("approvals", delete(Approval).where(Approval.id != keep))
    if seeded:
        seeded.status, seeded.note, seeded.decided_at, seeded.seen_at = "pending", None, None, None
        seeded.ts = datetime.now() - timedelta(minutes=18)
        session.add(seeded)
    else:
        session.add(Approval(patient_id=bobur.id, from_product_id=products["ibu_imp"].id,
                             to_product_id=products["ibu_loc"].id, status="pending",
                             ts=datetime.now() - timedelta(minutes=18)))
    if extra_ids:
        rm("patients", delete(Patient).where(Patient.id.in_(extra_ids)))

    # post-seed activity
    rm("scans", delete(Scan).where(Scan.id > _last_seeded_id(session, Scan, n["scans"])))
    rm("ratings", delete(Rating).where(Rating.id > _last_seeded_id(session, Rating, n["ratings"])))
    rm("reports", delete(Report).where(Report.id > _last_seeded_id(session, Report, n["reports"])))
    last_doc = _last_seeded_id(session, Document, n["documents"])
    new_docs = session.exec(select(Document).where(Document.id > last_doc)).all()
    uploads = config.UPLOAD_DIR.resolve()
    for d in new_docs:
        f = (config.ROOT / d.path).resolve() if d.path else None
        if f and uploads in f.parents and f.exists():
            f.unlink()
    if new_docs:
        rm("lab_results", delete(LabResult).where(LabResult.document_id.in_([d.id for d in new_docs])))
        rm("documents", delete(Document).where(Document.id > last_doc))

    # rules: drop AI proposals (approved or not); seed rules stay approved
    rm("ai_rules", delete(SafetyRule).where(SafetyRule.origin != "seed"))
    for r in session.exec(select(SafetyRule).where(SafetyRule.origin == "seed", SafetyRule.approved == False)).all():  # noqa: E712
        r.approved = True
        session.add(r)
    session.commit()
    out["scans_left"] = session.exec(select(func.count()).select_from(Scan)).one()
    out["rules_approved"] = session.exec(select(func.count()).select_from(SafetyRule).where(SafetyRule.approved == True)).one()  # noqa: E712
    return out


def seed_if_empty() -> bool:
    init_db()
    with Session(engine) as s:
        if s.exec(select(Product)).first() is not None:
            return False
        seed(s)
        return True


def main() -> None:
    reset()
    with Session(engine) as s:
        stats = seed(s)
    print("Seed tayyor:", stats, "->", config.DB_PATH)


if __name__ == "__main__":
    main()
