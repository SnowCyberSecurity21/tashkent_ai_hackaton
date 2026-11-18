"""GS1 Data Matrix / EAN-13 parser.

Accepted inputs:
  * raw scanner string with GS (\\x1d) separators, optional ']d2' symbology prefix
  * parenthesised human-readable string '(01)...(21)...(17)...(10)...'
  * plain EAN-13 (-> GTIN = '0' + ean) or plain 14-digit GTIN
Textual '<GS>', '{GS}', '\\x1d' or '|' typed by hand are treated as GS separators.

Real packs (Asl Belgisi):  ]d2 01<GTIN> 21<serial, 13> GS 17<YYMMDD> 10<batch> GS 91<key, 4> GS 92<crypto, 44>.
Decoders differ: some keep GS, some drop it, some emit the leading FNC1 as GS, some return the HRI form with
parentheses (a crypto value may itself contain parentheses). All of these are accepted.
"""
from __future__ import annotations

import calendar
import re
from datetime import date

GS = "\x1d"
FIXED = {"01": 14, "02": 14, "17": 6, "11": 6, "15": 6, "16": 6, "13": 6}
VARIABLE = {"21": 20, "10": 20, "91": 90, "92": 90, "93": 90, "240": 30, "241": 30, "30": 8, "710": 20, "714": 20}
CRYPTO = {"91", "92", "93"}

_PREFIXES = ("]d2", "]D2", "]C1", "]c1", "]Q3", "]q3", "]e0")


class GS1Error(ValueError):
    pass


def check_digit_ok(digits: str) -> bool:
    if not digits.isdigit() or len(digits) < 8:
        return False
    body, check = digits[:-1], int(digits[-1])
    total = sum(int(ch) * (3 if i % 2 == 0 else 1) for i, ch in enumerate(reversed(body)))
    return (10 - total % 10) % 10 == check


def parse_yymmdd(v: str) -> date:
    if not re.fullmatch(r"\d{6}", v):
        raise GS1Error("Sana formati noto'g'ri (YYMMDD kutilgan)")
    yy, mm, dd = int(v[:2]), int(v[2:4]), int(v[4:6])
    year = 2000 + yy
    if not 1 <= mm <= 12:
        raise GS1Error("Sanadagi oy noto'g'ri")
    if dd == 0:  # GS1: DD=00 means the last day of the month
        dd = calendar.monthrange(year, mm)[1]
    try:
        return date(year, mm, dd)
    except ValueError as exc:
        raise GS1Error("Sanadagi kun noto'g'ri") from exc


def _normalize(raw: str) -> str:
    s = raw.replace("\r", "").replace("\n", "").strip()
    for token in ("<GS>", "{GS}", "[GS]", "\\x1d", "\\u001d", "<FNC1>", "|"):
        s = s.replace(token, GS)
    s = s.replace("␝", GS)  # visible GS symbol
    for p in _PREFIXES:
        if s.startswith(p):
            s = s[len(p):]
            break
    return s.lstrip(GS).strip(" ")


_KNOWN_AI_RX = re.compile(r"\((" + "|".join(sorted(set(FIXED) | set(VARIABLE), key=len, reverse=True)) + r")\)")


def _parse_parenthesized(s: str) -> dict[str, str]:
    """'(01)…(21)…' — splits only on known AIs; a trailing crypto value like '(92)ab(c)d' stays intact."""
    s = s.replace(GS, "")
    out: dict[str, str] = {}
    i = 0
    while i < len(s):
        m = _KNOWN_AI_RX.match(s, i)
        if not m:
            raise GS1Error("Qavsli GS1 kod formati noto'g'ri")
        ai, start = m.group(1), m.end()
        if ai in FIXED:
            end = start + FIXED[ai]
        elif ai in ("92", "93"):  # crypto signature: always the last field, may contain '(' and ')'
            end = len(s)
        else:
            nxt = _KNOWN_AI_RX.search(s, start)
            end = nxt.start() if nxt else len(s)
        val = s[start:end]
        if not val or ai in out or (ai in FIXED and (len(val) != FIXED[ai] or not val.isdigit())):
            raise GS1Error(f"({ai}) maydoni noto'g'ri")
        out[ai] = val
        i = end
    if not out:
        raise GS1Error("Qavsli GS1 kod formati noto'g'ri")
    return out


# typical lengths in real Asl Belgisi / Chestny Znak codes; tried first when a decoder dropped the GS separators
_PREFERRED_LEN = {"21": (13,), "91": (4,), "92": (44, 88)}


def _ai_at(s: str, i: int):
    for ln in (2, 3, 4):
        cand = s[i:i + ln]
        if cand in FIXED or cand in VARIABLE:
            return cand
    return None


def _parse_no_gs(s: str):
    """GS-less string: backtracks over where each variable field ends; returns the first full parse or None.
    Memoised on (position, AIs already seen), so it stays fast on any input."""
    if len(s) > 300:
        return None
    memo: dict = {}

    def go(i: int, seen: frozenset):
        key = (i, seen)
        if key in memo:
            return memo[key]
        memo[key] = None
        if i == len(s):
            memo[key] = {}
            return memo[key]
        ai = _ai_at(s, i)
        if ai is None or ai in seen:
            return None
        start = i + len(ai)
        if ai in FIXED:
            val = s[start:start + FIXED[ai]]
            if len(val) == FIXED[ai] and val.isdigit():
                rest = go(start + len(val), seen | {ai})
                if rest is not None:
                    memo[key] = {ai: val, **rest}
            return memo[key]
        remaining = len(s) - start
        limit = min(VARIABLE[ai], remaining)
        lengths = [n for n in _PREFERRED_LEN.get(ai, ()) if n <= limit]
        lengths += [n for n in range(1, limit + 1) if n not in lengths]
        if ai in ("92", "93"):  # crypto signature is the last field: run to the end
            lengths = [remaining] if remaining <= VARIABLE[ai] else []
        for n in lengths:
            rest = go(start + n, seen | {ai})
            if rest is not None:
                memo[key] = {ai: s[start:start + n], **rest}
                break
        return memo[key]

    return go(0, frozenset())


def _parse_raw(s: str) -> dict[str, str]:
    if GS not in s:
        parsed = _parse_no_gs(s)
        if parsed is not None:
            return parsed
    out: dict[str, str] = {}
    i, n = 0, len(s)
    while i < n:
        if s[i] == GS:
            i += 1
            continue
        ai = None
        for ln in (2, 3, 4):
            cand = s[i:i + ln]
            if cand in FIXED or cand in VARIABLE:
                ai = cand
                break
        if ai is None:
            raise GS1Error(f"Noma'lum GS1 identifikatori: {s[i:i + 2]!r}")
        i += len(ai)
        if ai in FIXED:
            ln = FIXED[ai]
            val = s[i:i + ln]
            if len(val) != ln:
                raise GS1Error(f"({ai}) maydoni qisqa")
            i += ln
        else:
            j = s.find(GS, i)
            j = n if j == -1 else j
            val = s[i:j]
            i = j
            if GS not in s and ai == "21":
                # MOCK-friendly heuristic for GS-less strings: (21)serial(17)YYMMDD(10)batch
                m = re.fullmatch(r"(.{1,20}?)17(\d{6})10(.{1,20})", val)
                if m:
                    out["21"], out["17"], out["10"] = m.group(1), m.group(2), m.group(3)
                    continue
            if len(val) == 0 or len(val) > VARIABLE[ai]:
                raise GS1Error(f"({ai}) maydoni uzunligi noto'g'ri")
        out[ai] = val
    return out


def parse(raw: str) -> dict:
    if raw is None or not str(raw).strip():
        raise GS1Error("Kod bo'sh. Kodni skanerlang yoki qo'lda kiriting.")
    s = _normalize(str(raw))

    if re.fullmatch(r"\d{13}", s):
        if not check_digit_ok(s):
            raise GS1Error("EAN-13 nazorat raqami noto'g'ri")
        return {"gtin": "0" + s, "serial": None, "batch": None, "exp_date": None, "mfg_date": None,
                "kind": "ean13", "crypto": {}}
    if re.fullmatch(r"\d{14}", s) and not s.startswith("01"):
        if not check_digit_ok(s):
            raise GS1Error("GTIN nazorat raqami noto'g'ri")
        return {"gtin": s, "serial": None, "batch": None, "exp_date": None, "mfg_date": None,
                "kind": "ean13", "crypto": {}}

    fields = _parse_parenthesized(s) if s.startswith("(") else _parse_raw(s)
    gtin = fields.get("01")
    if not gtin:
        raise GS1Error("Kodda GTIN (01) topilmadi")
    if not re.fullmatch(r"\d{14}", gtin) or not check_digit_ok(gtin):
        raise GS1Error("GTIN nazorat raqami noto'g'ri")
    return {
        "gtin": gtin,
        "serial": fields.get("21"),
        "batch": fields.get("10"),
        "exp_date": parse_yymmdd(fields["17"]) if "17" in fields else None,
        "mfg_date": parse_yymmdd(fields["11"]) if "11" in fields else None,
        "kind": "datamatrix",
        "crypto": {ai: fields[ai] for ai in CRYPTO if ai in fields},
    }
