"""LLM tasks with strict JSON, cache and precomputed fallback.

Call chain for every task:
    cache  ->  primary model (20 s hard timeout)  ->  fallback model once (20 s)  ->  precomputed / rules
Timeout, HTTP 429, invalid JSON, schema violations and any other error all trigger the next step.
`pii.mask()` runs on every prompt before it leaves the server.

The LLM never creates, removes or changes a safety warning: `leaflet_to_rules` only *proposes* rules
(approved=False) that a pharmacist must approve; explanations are free text shown under "AI izohi".
"""
from __future__ import annotations

import difflib
import hashlib
import json
import logging
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeout
from typing import Any, Callable, Optional

from sqlmodel import Session

from . import config, pii
from .db import classes, conditions, engine, load_json
from .models import LlmCache

log = logging.getLogger("mezon.llm")

_executor = ThreadPoolExecutor(max_workers=8, thread_name_prefix="llm")
_client_lock = threading.Lock()
_gemini_client = None
_anthropic_client = None
_cooldown_until = 0.0  # after both models fail, skip live calls briefly so the UI stays fast
COOLDOWN_S = 30
_last_error: Optional[str] = None
_last_status: Optional[str] = None  # live | fallback | precomputed (cache hits don't change it)
_last_latency_ms: Optional[int] = None

KINDS = {"duplicate", "max_daily", "drug_drug", "drug_condition"}
SEVERITIES = {"info", "warn", "danger"}
REPORT_CATEGORIES = ["nojo'ya ta'sir", "allergik reaksiya", "sifat shikoyati", "samarasizlik", "qalbakilik shubhasi", "boshqa"]


class LLMError(RuntimeError):
    pass


# ---------------------------------------------------------------- provider plumbing
def _provider() -> str:
    return config.LLM_PROVIDER


def _models() -> list[str]:
    if _provider() == "anthropic":
        return [config.ANTHROPIC_MODEL, config.ANTHROPIC_FALLBACK_MODEL]
    return [config.GEMINI_MODEL, config.GEMINI_FALLBACK_MODEL]


def is_configured() -> bool:
    if config.LLM_OFFLINE:
        return False
    if _provider() == "anthropic":
        return bool(config.ANTHROPIC_API_KEY)
    return bool(config.GEMINI_API_KEY)


def status() -> dict:
    return {
        "provider": _provider(), "configured": is_configured(), "model": _models()[0], "fallback_model": _models()[1],
        "timeout_s": config.LLM_TIMEOUT_S, "offline": config.LLM_OFFLINE,
        "cooldown_s": max(0, round(_cooldown_until - time.time())), "last_error": _last_error,
        "primary": _models()[0], "fallback": _models()[1],
        "last_status": _last_status, "last_latency_ms": _last_latency_ms,
    }


def _gemini():
    global _gemini_client
    with _client_lock:
        if _gemini_client is None:
            from google import genai
            from google.genai import types

            _gemini_client = genai.Client(
                api_key=config.GEMINI_API_KEY,
                http_options=types.HttpOptions(
                    timeout=int(config.LLM_TIMEOUT_S * 1000),
                    retry_options=types.HttpRetryOptions(attempts=1),  # no SDK retries: we control fallback
                ),
            )
        return _gemini_client


def _anthropic():
    global _anthropic_client
    with _client_lock:
        if _anthropic_client is None:
            import anthropic

            _anthropic_client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY, timeout=config.LLM_TIMEOUT_S,
                                                    max_retries=0)
        return _anthropic_client


def _generate(model: str, system: str, prompt: str) -> str:
    if _provider() == "anthropic":
        msg = _anthropic().messages.create(
            model=model, max_tokens=2048, system=system + "\nFaqat JSON qaytar.",
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(getattr(b, "text", "") for b in msg.content)
    from google.genai import types

    resp = _gemini().models.generate_content(
        model=model, contents=prompt,
        config=types.GenerateContentConfig(system_instruction=system, response_mime_type="application/json",
                                           temperature=0.2, max_output_tokens=4096),
    )
    return resp.text or ""


def _describe(exc: BaseException) -> str:
    code = getattr(exc, "code", None) or getattr(exc, "status_code", None)
    if isinstance(exc, (FuturesTimeout, TimeoutError)) or "timeout" in type(exc).__name__.lower():
        return "timeout"
    if code == 429 or "429" in str(exc)[:200] or "RESOURCE_EXHAUSTED" in str(exc)[:300]:
        return "429"
    return f"{type(exc).__name__}: {str(exc)[:160]}"


def _parse_json(text: str) -> Any:
    t = (text or "").strip()
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t)
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        m = re.search(r"(\{.*\}|\[.*\])", t, re.S)
        if not m:
            raise
        return json.loads(m.group(1))


def _live(system: str, prompt: str, validate: Callable[[Any], Any]) -> tuple[Any, str]:
    """Primary model, then the fallback model exactly once. Each attempt has a hard timeout."""
    global _cooldown_until, _last_error
    errors = []
    for model in _models():
        fut = _executor.submit(_generate, model, system, prompt)
        try:
            text = fut.result(timeout=config.LLM_TIMEOUT_S)
            data = validate(_parse_json(text))
            _last_error = None
            return data, model
        except FuturesTimeout as exc:
            fut.cancel()
            errors.append(f"{model}: {_describe(exc)}")
        except Exception as exc:  # 429, network, invalid JSON, schema violation …
            errors.append(f"{model}: {_describe(exc)}")
        log.warning("LLM attempt failed: %s", errors[-1])
    _cooldown_until = time.time() + COOLDOWN_S
    _last_error = "; ".join(errors)
    raise LLMError(_last_error)


def _cache_get(key: str):
    with Session(engine) as s:
        row = s.get(LlmCache, key)
        return (row.response_json, row.model) if row else (None, None)


def _cache_put(key: str, task: str, model: str, data: Any) -> None:
    with Session(engine) as s:
        row = s.get(LlmCache, key) or LlmCache(key=key)
        row.task, row.model, row.response_json = task, model, {"data": data}
        s.add(row)
        s.commit()


def run_task(task: str, system: str, prompt: str, validate: Callable[[Any], Any], fallback: Callable[[], Any],
             live: bool = True, use_cache: bool = True, force: bool = False) -> dict:
    """Returns {data, source: cache|live|precomputed, model, error}."""
    global _last_status, _last_latency_ms
    masked = pii.mask(prompt)
    key = hashlib.sha256(f"{task}\n{masked}".encode("utf-8")).hexdigest()
    if use_cache:
        cached, model = _cache_get(key)
        if cached is not None:
            return {"data": cached["data"], "source": "cache", "model": model, "error": None}
    error = None
    can_live = live and is_configured() and (force or time.time() >= _cooldown_until)
    if can_live:
        t0 = time.time()
        try:
            data, model = _live(system, masked, validate)
            _last_latency_ms = round((time.time() - t0) * 1000)
            _last_status = "live" if model == _models()[0] else "fallback"
            _cache_put(key, task, model, data)
            return {"data": data, "source": "live", "model": model, "error": None}
        except LLMError as exc:
            error = str(exc)
            _last_latency_ms = round((time.time() - t0) * 1000)
            _last_status = "precomputed"
    elif live and is_configured():
        error = "cooldown"
        _last_status, _last_latency_ms = "precomputed", 0
    return {"data": fallback(), "source": "precomputed", "model": None, "error": error}


def _pre() -> dict:
    return load_json("precomputed_llm.json")


# ---------------------------------------------------------------- 1. explain_uz
# composition ("paratsetamol 500 mg") is fine; dosing instructions ("kuniga 2 tabletka", "3 marta") are not
_DOSE_RX = re.compile(
    r"\b(kuniga|sutkasiga|sutkada|har\s+\d+\s+soatda)\b|\b\d+\s*(tabletka|tabletkadan|kapsula|paket|paketdan|marta|dona|qoshiq)\b",
    re.I)

EXPLAIN_SYSTEM = (
    "Sen Mezon ilovasining yordamchisisan: bemorga dorixonada dori haqidagi rasmiy ma'lumotni tushuntirasan. "
    "Faqat o'zbek tilida, lotin yozuvida yoz. 2–3 ta qisqa, xotirjam va hurmatli gap. "
    "QAT'IY: tashxis qo'yma, dori tayinlama, doza, miqdor yoki qabul tartibini aytma, raqamli dozalarni yozma. "
    "Faqat berilgan faktlarga tayan, hech narsa o'ylab topma. Ogohlantirish qo'shma va mavjud ogohlantirishlarni inkor qilma. "
    'Javob JSON: {"text": "..."}'
)


# a live explanation must not drop a danger alert: each one needs a matching keyword in the text
_ALERT_KEYWORDS = {
    "conformity_expired": r"muvofiqlik",
    "recalled": r"qaytarib|muomaladan",
    "clone": r"klon|nusxa",
    "expired": r"muddat",
    "code_unknown": r"topilmadi|bazada yo'q|ro'yxatda yo'q|markirovka",
    "reg_expired": r"ro'yxat",
}


def _validate_explain(d: Any, required: Optional[list[str]] = None) -> str:
    text = (d or {}).get("text") if isinstance(d, dict) else None
    if not isinstance(text, str):
        raise ValueError("no text")
    text = text.strip()
    if not 30 <= len(text) <= 700:
        raise ValueError("bad length")
    if _DOSE_RX.search(text):
        raise ValueError("dosing content rejected")
    if re.search(r"[А-Яа-яЁё]", text):
        raise ValueError("cyrillic")
    for code in required or []:
        rx = _ALERT_KEYWORDS.get(code)
        if rx and not re.search(rx, text, re.I):
            raise ValueError(f"explanation omits danger alert {code}")
    return text


def template_explanation(ctx: dict) -> str:
    """Deterministic fallback when no precomputed text exists for this product/scenario."""
    name = ctx["name"]
    origin = "mahalliy" if ctx.get("is_local") else "import"
    dangers = [a["title_uz"] for a in ctx.get("alerts", []) if a["severity"] == "danger"]
    warns = [a["title_uz"] for a in ctx.get("alerts", []) if a["severity"] == "warn"]
    t = ctx.get("trust") or {}
    s1 = f"{name} — {origin} dori."
    if dangers:
        s2 = f"Rasmiy tekshiruvda muhim ogohlantirish bor: {dangers[0][:1].lower() + dangers[0][1:]}."
    elif warns:
        s2 = f"E'tibor bering: {warns[0][:1].lower() + warns[0][1:]}."
    else:
        s2 = "Rasmiy ma'lumotlarda jiddiy muammo topilmadi."
    if t.get("color") == "gray":
        s3 = "Ishonch indeksi uchun hozircha ma'lumot yetarli emas, savollar bo'lsa farmatsevtdan so'rang."
    else:
        s3 = f"Ishonch indeksi {t.get('score')} ({t.get('color_word', '').lower()}); savollar bo'lsa farmatsevtdan so'rang."
    return f"{s1} {s2} {s3}"


def explain_uz(ctx: dict, live: bool = True) -> dict:
    """ctx: {key, scenario, name, inns, is_local, country, official, alerts, trust}."""
    facts = {
        "dori": ctx["name"], "tarkib": ctx.get("inns"), "mahalliy": ctx.get("is_local"), "mamlakat": ctx.get("country"),
        "rasmiy": ctx.get("official"),
        "ogohlantirishlar": [a["title_uz"] for a in ctx.get("alerts", []) if a["severity"] in ("danger", "warn")],
        "ishonch_indeksi": {"ball": (ctx.get("trust") or {}).get("score"), "rang": (ctx.get("trust") or {}).get("color_word"),
                            "izohlar": [c["label"] + ": " + c["reason"] for c in (ctx.get("trust") or {}).get("components", [])]},
    }
    prompt = ("Quyidagi faktlar asosida bemorga 2–3 gapli izoh yoz. Agar ogohlantirishlar bo'lsa, eng muhimini birinchi gapda "
              "aniq ayt (masalan, muvofiqlik hujjati muddati tugagani, partiya qaytarib olingani, klon kod).\n"
              + json.dumps(facts, ensure_ascii=False))
    required = [a["code"] for a in ctx.get("alerts", []) if a["severity"] == "danger"]
    pre = _pre()["explain_uz"]

    def fb():
        scen = ctx.get("scenario")
        return pre.get(f"{ctx.get('key')}:{scen}") or (pre.get(ctx.get("key")) if not scen else None) or template_explanation(ctx)

    return run_task("explain_uz", EXPLAIN_SYSTEM, prompt, lambda d: _validate_explain(d, required), fb, live=live)


# ---------------------------------------------------------------- 2. normalize_inn
def _vocabulary() -> list[str]:
    vocab = set()
    for p in load_json("products.json"):
        for c in p["inn_list"]:
            vocab.add(c["inn"])
    for members in classes().values():
        vocab.update(members)
    return sorted(vocab)


def _fuzzy_inn(raw: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z'ʻ’\s-]", " ", raw).strip().lower()
    cleaned = re.sub(r"\s+(hcl|maleat|natriy|gidroxlorid)$", "", cleaned)
    vocab = _vocabulary()
    match = difflib.get_close_matches(cleaned, vocab, n=1, cutoff=0.6)
    if not match:  # phonetic variants (h/x, e/i) common in raw registry data
        alt = cleaned.replace("hl", "xl").replace("edin", "idin")
        match = difflib.get_close_matches(alt, vocab, n=1, cutoff=0.6)
    return match[0] if match else cleaned


NORMALIZE_SYSTEM = (
    "Dori moddasi nomini (INN) o'zbek lotin imlosida normallashtir. Kichik harflarda yoz, tuz qismini (HCl, maleat) olib tashla. "
    "Ma'lum ro'yxatdan tanlashga harakat qil. Javob JSON: {\"inn\": \"...\"}"
)


def normalize_inn(raw: str, live: bool = True) -> dict:
    raw = (raw or "").strip()
    pre = _pre()["normalize_inn"]
    if raw in pre:  # deterministic dictionary hit — instant
        return {"data": pre[raw], "source": "precomputed", "model": None, "error": None}

    def validate(d):
        inn = (d or {}).get("inn") if isinstance(d, dict) else None
        if not isinstance(inn, str) or not re.fullmatch(r"[a-zʻ'’ \-]{3,40}", inn.strip().lower()):
            raise ValueError("bad inn")
        return inn.strip().lower()

    prompt = f"Ma'lum INN ro'yxati: {', '.join(_vocabulary())}\nXom nom: {raw}"
    return run_task("normalize_inn", NORMALIZE_SYSTEM, prompt, validate, lambda: _fuzzy_inn(raw), live=live)


# ---------------------------------------------------------------- 3. extract_coa
COA_SYSTEM = (
    "Sen laboratoriya tahlil sertifikati (CoA) matnidan ma'lumot ajratuvchi yordamchisan. Faqat matnda bor qiymatlarni ol. "
    "Natijani solishtirma va xulosa chiqarma — faqat qiymatlar. "
    'JSON: {"batch_no": str|null, "results": [{"parameter": str, "value": number, "spec_min": number|null, '
    '"spec_max": number|null, "unit": str}]}'
)


def _validate_coa(d: Any) -> dict:
    if not isinstance(d, dict) or not isinstance(d.get("results"), list) or not d["results"]:
        raise ValueError("no results")
    out = []
    for r in d["results"]:
        out.append({
            "parameter": str(r["parameter"])[:80], "value": float(r["value"]),
            "spec_min": None if r.get("spec_min") is None else float(r["spec_min"]),
            "spec_max": None if r.get("spec_max") is None else float(r["spec_max"]),
            "unit": str(r.get("unit") or "")[:12],
        })
    return {"batch_no": d.get("batch_no"), "results": out}


_ROW_RX = re.compile(
    r"^(?P<param>[A-Za-z'ʻ’() ]+?)\s+(?P<val>\d+(?:[.,]\d+)?)\s+"
    r"(?:(?P<lo>\d+(?:[.,]\d+)?)\s*-\s*(?P<hi>\d+(?:[.,]\d+)?)|>=\s*(?P<min>\d+(?:[.,]\d+)?)|<=\s*(?P<max>\d+(?:[.,]\d+)?))"
    r"\s+(?P<unit>\S+)", re.M)


def parse_coa_text(text: str) -> dict:
    """Deterministic parser for the Mezon CoA layout (fallback without LLM)."""
    num = lambda v: None if v is None else float(v.replace(",", "."))
    results = []
    for m in _ROW_RX.finditer(text or ""):
        lo, hi = num(m.group("lo")), num(m.group("hi"))
        results.append({"parameter": m.group("param").strip(), "value": num(m.group("val")),
                        "spec_min": lo if lo is not None else num(m.group("min")),
                        "spec_max": hi if hi is not None else num(m.group("max")), "unit": m.group("unit")})
    bm = re.search(r"Partiya raqami\s+(\S+)", text or "")
    batch = bm.group(1) if bm else None
    if not results and batch and batch in _pre()["extract_coa"]:
        return _pre()["extract_coa"][batch]
    return {"batch_no": batch, "results": results}


def in_spec(r: dict) -> bool:
    if r.get("spec_min") is not None and r["value"] < r["spec_min"]:
        return False
    if r.get("spec_max") is not None and r["value"] > r["spec_max"]:
        return False
    return True


def extract_coa(pdf_text: str, live: bool = True, force: bool = False) -> dict:
    res = run_task("extract_coa", COA_SYSTEM, "CoA matni:\n" + (pdf_text or "")[:12000], _validate_coa,
                   lambda: parse_coa_text(pdf_text), live=live, force=force)
    data = res["data"]
    for r in data.get("results", []):
        r["status"] = "ok" if in_spec(r) else "out"  # comparison is done in Python, never by the LLM
    return res


# ---------------------------------------------------------------- 4. leaflet_to_rules
def leaflet_sections(text: str) -> str:
    m = re.search(r"4\.2\.\s.*?(?=4\.7\.\s)", text or "", re.S)
    return (m.group(0) if m else (text or ""))[:16000]


def _rule_vocab() -> dict:
    return {"inn": _vocabulary(), "class": [f"class:{k}" for k in classes()],
            "condition": [c["key"] for c in conditions()] + ["alcohol"]}


def _in_product(token: Optional[str], product_inns: set[str]) -> bool:
    if not token:
        return False
    if token.startswith("class:"):
        return bool(set(classes().get(token[6:], [])) & product_inns)
    return token in product_inns


def _validate_rules(d: Any, product_inns: Optional[set[str]] = None) -> list[dict]:
    rules = d.get("rules") if isinstance(d, dict) else d
    if not isinstance(rules, list):
        raise ValueError("no rules")
    v = _rule_vocab()
    drugs = set(v["inn"]) | set(v["class"])
    conds = set(v["condition"])
    out = []
    for r in rules:
        try:
            kind, sev = str(r["kind"]), str(r["severity"])
            a = str(r["a"]).strip().lower().replace("class:nsaid", "class:NSAID").replace("class:maoi", "class:MAOI")
            b = r.get("b")
            b = None if b in (None, "", "null") else str(b).strip()
            b = b if b is None or not b.lower().startswith("class:") else "class:" + {k.lower(): k for k in classes()}.get(b[6:].lower(), b[6:])
            a = a if not a.startswith("class:") else "class:" + {k.lower(): k for k in classes()}.get(a[6:].lower(), a[6:])
            msg, src = str(r["message_uz"]).strip(), str(r["source"]).strip()
        except (KeyError, TypeError):
            continue
        thr = r.get("threshold_mg")
        if kind not in KINDS or sev not in SEVERITIES or not msg or not src:
            continue
        if kind == "drug_condition" and (a not in drugs or (b or "").lower() not in conds):
            continue
        if kind == "drug_drug" and (a not in drugs or b not in drugs):
            continue
        if kind == "max_daily" and (a not in drugs or not isinstance(thr, (int, float)) or thr <= 0):
            continue
        if kind == "duplicate":
            continue  # global duplicate rule already exists
        if product_inns:
            # rules from a leaflet must involve one of that product's own active ingredients
            if kind == "drug_drug" and not _in_product(a, product_inns) and _in_product(b, product_inns):
                a, b = b, a
            if not _in_product(a, product_inns):
                continue
            if kind == "drug_drug" and (b == a or (not b.startswith("class:") and b in product_inns)):
                continue
        if re.search(r"[çğışöüÇĞİŞÖÜ]", msg):
            continue  # untranslated Turkish leaked into the patient message
        if not re.search(r"4\.\d", src):
            continue  # must cite the leaflet section
        out.append({"kind": kind, "a": a, "b": b.lower() if kind == "drug_condition" and b else b,
                    "threshold_mg": float(thr) if kind == "max_daily" else None, "severity": sev,
                    "message_uz": msg[:400], "source": src[:160]})
    if not out:
        raise ValueError("no valid rules")
    return out


TYLOL_INNS = ["paratsetamol", "psevdoefedrin", "xlorfeniramin"]


def _leaflet_system(product_inns: list[str]) -> str:
    v = _rule_vocab()
    return (
        f"Yo'riqnoma egasi bo'lgan dorining ta'sir qiluvchi moddalari: {product_inns}. Har bir qoidada a — shu moddalardan "
        "biri, b — u bilan o'zaro ta'sir qiluvchi BOSHQA dori yoki sinf (drug_drug) yoki bemor holati (drug_condition). "
        "Sen klinik farmakolog yordamchisisan. Turkcha dori yo'riqnomasi (KÜB) bo'limlaridan (4.2–4.6) xavfsizlik QOIDALARINI "
        "taklif qil. Bu qoidalar farmatsevt tasdiqlamaguncha ishlamaydi. Faqat matnda aniq yozilgan narsalarni ol. "
        "kind: max_daily | drug_drug | drug_condition. severity: info | warn | danger (qarshi ko'rsatma = danger, ehtiyotkorlik = warn). "
        f"a va b faqat shu tokenlardan: INN {v['inn']}; sinflar {v['class']}; holatlar {v['condition']}. "
        "drug_condition uchun a = INN yoki sinf, b = holat. max_daily uchun threshold_mg (mg), b = null yoki 'alcohol'. "
        "message_uz — faqat o'zbek lotin tilida (turkcha so'z ishlatma), 1–2 gap, bemorga tushunarli; source — 'Tylol Hot qisqa mahsulot ma'lumoti, 4.x' ko'rinishida. "
        'JSON: {"rules": [{"kind","a","b","threshold_mg","severity","message_uz","source"}]}. 5–10 ta qoida.'
    )


def leaflet_to_rules(pdf_text: str, live: bool = True, force: bool = False, use_cache: bool = True,
                     product_inns: Optional[list[str]] = None) -> dict:
    inns = product_inns or TYLOL_INNS
    prompt = "Yo'riqnoma bo'limlari:\n" + leaflet_sections(pdf_text)
    return run_task("leaflet_to_rules", _leaflet_system(inns), prompt, lambda d: _validate_rules(d, set(inns)),
                    lambda: _pre()["leaflet_to_rules"]["tylol-hot"], live=live, force=force, use_cache=use_cache)


# ---------------------------------------------------------------- 5. classify_report
_KEYWORDS = [
    (r"nafas|bo'g'il|hush|shish(?!a)|anafilak|qon ket|tutqanoq|yurak", "allergik reaksiya", "danger"),
    (r"toshma|qichi|allergi|qizar|eshak yem", "allergik reaksiya", "warn"),
    (r"qalbaki|soxta|klon|kod.*(mos|noto)", "qalbakilik shubhasi", "danger"),
    (r"rang|hid|ta'm|qadoq|siniq|ezil|cho'kma|loyqa", "sifat shikoyati", "warn"),
    (r"ta'sir qilmadi|foyda bermadi|samara|yordam bermadi", "samarasizlik", "info"),
    (r"ko'ngil|qus|bosh og'ri|bosh aylan|uyqu|ich ket|qabziyat|og'ri", "nojo'ya ta'sir", "warn"),
]

REPORT_SYSTEM = (
    "Bemor xabarini tasnifla. category: " + " | ".join(REPORT_CATEGORIES) + ". "
    "severity: info (yengil) | warn (o'rtacha) | danger (jiddiy: nafas qisishi, hushdan ketish, qon ketish, qalbakilik). "
    'Faqat JSON: {"category": "...", "severity": "..."}'
)


def keyword_classify(text: str) -> dict:
    t = (text or "").lower()
    for rx, cat, sev in _KEYWORDS:
        if re.search(rx, t):
            return {"category": cat, "severity": sev}
    return {"category": "boshqa", "severity": "info"}


def classify_report(text: str, live: bool = True) -> dict:
    def validate(d):
        if not isinstance(d, dict) or d.get("category") not in REPORT_CATEGORIES or d.get("severity") not in SEVERITIES:
            raise ValueError("bad classification")
        return {"category": d["category"], "severity": d["severity"]}

    return run_task("classify_report", REPORT_SYSTEM, "Xabar: " + (text or "")[:2000], validate,
                    lambda: keyword_classify(text), live=live)
