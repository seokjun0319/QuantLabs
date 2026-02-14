# -*- coding: utf-8 -*-
"""
QuantLabs 자율 최적화 파이프라인.
strategy_history.json 이력 → Gemini API로 개선 파라미터 제안 → 백테스트 → 저장 → 슬랙 보고.
UTF-8, Windows/Linux 호환.
"""
import json
import os
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
HISTORY_FILE = DATA_DIR / "strategy_history.json"
ENCODING = "utf-8"

if getattr(sys.stdout, "reconfigure", None):
    try:
        sys.stdout.reconfigure(encoding=ENCODING)
    except Exception:
        pass


def load_history() -> list:
    if not HISTORY_FILE.exists():
        return []
    try:
        with open(HISTORY_FILE, "r", encoding=ENCODING) as f:
            return json.load(f)
    except Exception:
        return []


def save_history(history: list) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(HISTORY_FILE, "w", encoding=ENCODING) as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


def ask_gemini_for_params(history: list) -> tuple[int, int]:
    """Gemini API에 이력 전달 후 ema_fast, ema_slow 제안 받기."""
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        return 12, 26
    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-1.5-flash")
        prompt = (
            "You are a quant strategy tuner. Given the following backtest history in JSON, "
            "suggest the next ema_fast and ema_slow (integers, 5-50) to try for BTC-USD. "
            "Reply with only two integers separated by a space, e.g. '10 30'.\n"
            "History:\n" + json.dumps(history[-10:], ensure_ascii=False)
        )
        response = model.generate_content(prompt)
        text = (response.text or "").strip()
        parts = text.split()
        fast = int(parts[0]) if len(parts) >= 1 else 12
        slow = int(parts[1]) if len(parts) >= 2 else 26
        fast = max(5, min(50, fast))
        slow = max(5, min(50, slow))
        if fast >= slow:
            fast, slow = 12, 26
        return fast, slow
    except Exception:
        return 12, 26


def run_pipeline() -> None:
    history = load_history()
    ema_fast, ema_slow = ask_gemini_for_params(history)

    sys.path.insert(0, str(ROOT / "scripts"))
    from strategy_engine import run as engine_run
    from report_slack import send_result_to_slack

    result = engine_run(ema_fast=ema_fast, ema_slow=ema_slow)
    ts = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    entry = {
        "timestamp": ts,
        "params": {"ema_fast": ema_fast, "ema_slow": ema_slow},
        "result": {"returns": result["returns"], "mdd": result["mdd"]},
    }
    history.append(entry)
    save_history(history)

    msg = (
        f"📊 자율 최적화 1회 완료\n"
        f"EMA fast/slow: {ema_fast}/{ema_slow}\n"
        f"수익률: {result['returns']:.2%} / MDD: {result['mdd']:.2%}"
    )
    send_result_to_slack(msg, "QuantLabs 자율 최적화")


if __name__ == "__main__":
    run_pipeline()
