from app import llm, pii


def test_pii_mask():
    t = pii.mask("Bemor: Karimova Aziza, JShShIR 31203987654321, tel +998 90 123-45-67. Tylol Hot ichdim.")
    assert "Karimova" not in t and "31203987654321" not in t and "123-45-67" not in t
    assert "Tylol Hot" in t and "[TELEFON]" in t and "[JShShIR]" in t
    assert "[FISh]" in pii.mask("Men Aliyev Bobur Akmalovich, toshma chiqdi")


def test_explain_validator_rejects_dosing_and_missing_alert():
    import pytest

    with pytest.raises(ValueError):
        llm._validate_explain({"text": "Bu dori yaxshi. Kuniga 3 tabletkadan iching, hammasi joyida bo'ladi."})
    with pytest.raises(ValueError):
        llm._validate_explain({"text": "Bu dori ro'yxatdan o'tgan va ishonchli mahsulot hisoblanadi."}, ["conformity_expired"])
    ok = llm._validate_explain({"text": "Paratsetamol 500 mg saqlaydi. Muvofiqlik hujjati muddati tugagan, farmatsevtdan so'rang."},
                               ["conformity_expired"])
    assert ok.startswith("Paratsetamol")


def test_offline_fallbacks():
    assert llm.normalize_inn("Metrodonidazol")["data"] == "metronidazol"
    assert llm.normalize_inn("hlorgeksedin")["data"] == "xlorgeksidin"
    assert llm.keyword_classify("terimda toshma va qichish")["category"] == "allergik reaksiya"


def test_leaflet_rule_validation_requires_product_ingredient():
    rules = [
        {"kind": "drug_drug", "a": "fenelzin", "b": "furazolidon", "severity": "danger", "message_uz": "x", "source": "4.3"},
        {"kind": "drug_drug", "a": "varfarin", "b": "paratsetamol", "severity": "warn", "message_uz": "Qon ketish xavfi", "source": "KÜB 4.5"},
        {"kind": "drug_condition", "a": "psevdoefedrin", "b": "gipertoniya", "severity": "danger", "message_uz": "Bosim", "source": "4.3"},
    ]
    out = llm._validate_rules({"rules": rules}, set(llm.TYLOL_INNS))
    assert len(out) == 2
    assert out[0]["a"] == "paratsetamol" and out[0]["b"] == "varfarin"  # swapped to the product's own INN


def test_fallback_chain_timeout_then_429_then_precomputed(monkeypatch):
    """primary times out -> fallback model tried exactly once (429) -> precomputed result."""
    import time

    from app import config

    calls = []

    def fake_generate(model, system, prompt):
        calls.append(model)
        if len(calls) == 1:
            time.sleep(1.5)  # longer than the (patched) timeout
            return '{"category": "boshqa", "severity": "info"}'
        raise RuntimeError("429 RESOURCE_EXHAUSTED")

    monkeypatch.setattr(config, "LLM_TIMEOUT_S", 0.5)
    monkeypatch.setattr(config, "LLM_OFFLINE", False)
    monkeypatch.setattr(config, "GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(config, "LLM_PROVIDER", "gemini")
    monkeypatch.setattr(llm, "_generate", fake_generate)
    monkeypatch.setattr(llm, "_cooldown_until", 0.0)
    monkeypatch.setattr(llm, "_cache_get", lambda key: (None, None))
    t0 = time.time()
    res = llm.classify_report("terimda toshma chiqdi")
    assert time.time() - t0 < 1.4  # did not wait for the slow primary
    assert calls == [config.GEMINI_MODEL, config.GEMINI_FALLBACK_MODEL]
    assert res["source"] == "precomputed" and res["data"]["category"] == "allergik reaksiya"
    assert "timeout" in res["error"] and "429" in res["error"]


def test_fallback_model_used_when_primary_fails(monkeypatch):
    from app import config

    calls = []

    def fake_generate(model, system, prompt):
        calls.append(model)
        if model == config.GEMINI_MODEL and len(calls) == 1:
            raise RuntimeError("503 UNAVAILABLE")
        return '{"category": "sifat shikoyati", "severity": "warn"}'

    monkeypatch.setattr(config, "LLM_OFFLINE", False)
    monkeypatch.setattr(config, "GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(llm, "_generate", fake_generate)
    monkeypatch.setattr(llm, "_cooldown_until", 0.0)
    monkeypatch.setattr(llm, "_cache_get", lambda key: (None, None))
    monkeypatch.setattr(llm, "_cache_put", lambda *a: None)
    res = llm.classify_report("qadoq rangi boshqacha")
    assert res["source"] == "live" and res["model"] == config.GEMINI_FALLBACK_MODEL and len(calls) == 2
