"""Mask personal data before any text leaves the server for an LLM."""
from __future__ import annotations

import re

_JSHSHIR = re.compile(r"(?<!\d)\d{14}(?!\d)")
_PHONE = re.compile(r"(?:\+?998)[\s\-()]*\d{2}[\s\-()]*\d{3}[\s\-]*\d{2}[\s\-]*\d{2}")
_UP = "A-ZÀ-ÖØ-ÞĞİŞÇÖÜ"
_LOW = "a-zà-öø-ÿğışçöüʻ’'`"
_WORD = rf"[{_UP}][{_LOW}]+"
# Full names: 2–3 capitalised words where at least one carries a typical surname / patronymic ending.
_SURNAME = re.compile(rf"[{_UP}][{_LOW}]*(?:ova|ov|eva|ev|yeva|yev|vich|vna|skiy|skaya|qizi|o['ʻ’`]g['ʻ’`]li)\b")
_NAME_SEQ = re.compile(rf"\b{_WORD}(?:\s+{_WORD}){{1,2}}\b")
_LABELLED = re.compile(r"(?i)\b(FISh|F\.I\.Sh\.|Bemor|Ism|Familiya|Name)\s*[:\-]\s*([^\n,;]+)")


def _mask_names(text: str) -> str:
    def repl(m: re.Match) -> str:
        words = m.group(0).split()
        if any(_SURNAME.fullmatch(w) for w in words):
            return "[FISh]"
        return m.group(0)

    return _NAME_SEQ.sub(repl, text)


def mask(text: str) -> str:
    if not text:
        return text
    text = _LABELLED.sub(lambda m: f"{m.group(1)}: [FISh]", text)
    text = _PHONE.sub("[TELEFON]", text)
    text = _JSHSHIR.sub("[JShShIR]", text)
    text = _mask_names(text)
    return text
