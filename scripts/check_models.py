"""Checks which Gemini models answer reliably and fast with the key from .env.

Usage:  python scripts/check_models.py [--runs 3]
Calls each candidate (primary, fallback from .env + gemini-3.1-flash-lite, gemini-3.5-flash-lite) N times with a
short Uzbek prompt and a 20 s hard timeout. Prints successes, median latency and error kinds (503/429/404/timeout).
The key is read from .env and never printed.
"""
from __future__ import annotations

import argparse
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from app import config  # noqa: E402

PROMPT = "Bir qisqa gapda o'zbekcha javob ber: paratsetamol nima uchun ishlatiladi?"
TIMEOUT_S = 20.0


def kind(exc: BaseException) -> str:
    code = getattr(exc, "code", None) or getattr(exc, "status_code", None)
    if isinstance(code, int):
        return str(code)
    s = str(exc)[:400]
    for code in ("503", "429", "404", "400", "403", "500"):
        if code in s:
            return code
    if isinstance(exc, (FuturesTimeout, TimeoutError)) or "timeout" in type(exc).__name__.lower():
        return "timeout"
    return type(exc).__name__


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=3)
    runs = ap.parse_args().runs
    if not config.GEMINI_API_KEY:
        print("GEMINI_API_KEY .env faylida yo'q — tekshirib bo'lmaydi.")
        return 1
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=config.GEMINI_API_KEY, http_options=types.HttpOptions(
        timeout=int(TIMEOUT_S * 1000), retry_options=types.HttpRetryOptions(attempts=1)))
    candidates = []
    for m in (config.GEMINI_MODEL, config.GEMINI_FALLBACK_MODEL, "gemini-3.1-flash-lite", "gemini-3.5-flash-lite"):
        if m and m not in candidates:
            candidates.append(m)
    pool = ThreadPoolExecutor(max_workers=2)
    summary = []
    for model in candidates:
        role = "primary" if model == config.GEMINI_MODEL else "fallback" if model == config.GEMINI_FALLBACK_MODEL else "candidate"
        lat, errs = [], []
        for _ in range(runs):
            t0 = time.time()
            fut = pool.submit(client.models.generate_content, model=model, contents=PROMPT,
                              config=types.GenerateContentConfig(temperature=0.2, max_output_tokens=200))
            try:
                r = fut.result(timeout=TIMEOUT_S)
                if not (r.text or "").strip():
                    raise ValueError("empty")
                lat.append(time.time() - t0)
            except Exception as exc:  # noqa: BLE001
                errs.append(kind(exc))
        med = statistics.median(lat) if lat else None
        summary.append((model, role, len(lat), med, errs))
        print(f"{model:28s} {role:9s} ok {len(lat)}/{runs}  median "
              f"{(f'{med:.2f} s' if med is not None else '  —   '):>7s}  errors: {', '.join(errs) or '-'}", flush=True)
    pool.shutdown(wait=False, cancel_futures=True)
    ok = [s for s in summary if s[2] == runs]
    if ok:
        best = min(ok, key=lambda s: s[3])
        print(f"\nEng ishonchli va tez: {best[0]} (median {best[3]:.2f} s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
