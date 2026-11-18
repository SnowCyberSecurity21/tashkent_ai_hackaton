from app.trust import TrustInputs, compute


def comp(res, key):
    return next(c for c in res["components"] if c["key"] == key)


def test_green_import_paracetamol_like():
    r = compute(TrustInputs(has_coa=True, coa_batch="EG2504P", bioequivalence=True, ratings=[4, 5, 4, 4, 5], scan_count=48))
    assert r["color"] == "green" and r["score"] >= 80
    assert comp(r, "R")["score"] == 100 and comp(r, "L")["score"] == 100 and comp(r, "M")["score"] == 100
    assert comp(r, "F")["score"] == 70 and comp(r, "U")["score"] == 88
    assert all(c["reason"] and c["source"] for c in r["components"])


def test_red_conformity_expired_no_coa():
    r = compute(TrustInputs(conformity_expired=True, has_coa=False, scan_count=14))
    assert comp(r, "R")["score"] == 70 and comp(r, "L")["score"] == 0
    assert r["score"] == 57 and r["color"] == "red"


def test_gray_when_no_coa_and_few_scans():
    r = compute(TrustInputs(has_coa=False, scan_count=2))
    assert r["color"] == "gray" and r["label"] == "Ma'lumot yetarli emas"


def test_clone_penalty_and_recall():
    base = compute(TrustInputs(has_coa=False, scan_count=20))
    clone = compute(TrustInputs(has_coa=False, scan_count=20, clone=True))
    assert comp(clone, "M")["score"] == 40
    assert base["score"] - clone["score"] == 12  # 0.20 × 60
    recalled = compute(TrustInputs(has_coa=False, scan_count=20, recalled=True))
    assert comp(recalled, "M")["score"] == 0


def test_coa_out_of_spec_and_serious_reports():
    r = compute(TrustInputs(has_coa=True, coa_out_count=1, bioequivalence=True, serious_reports=2, total_reports=3, scan_count=30))
    assert comp(r, "L")["score"] == 60 and comp(r, "F")["score"] == 80
