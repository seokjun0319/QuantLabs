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
BEST_PARAMS_FILE = DATA_DIR / "best_params.json"
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
    """Gemini API에 이력 전달 후 ema_fast, ema_slow 제안 받기. 마지막 3개 성과 반영."""
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        return 9, 21
    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-1.5-flash")
        last_three = history[-3:] if len(history) >= 3 else history
        prompt = (
            "You are a quant strategy tuner for NVDA (6 months daily). Strategy uses EMA crossover + RSI<70 entry and 2*ATR trailing stop. "
            "Analyze the LAST 3 backtest results and suggest the next ema_fast and ema_slow (integers, 5-50; e.g. 9 and 21). "
            "CRITICAL: If any previous experiment had MDD over 20%, suggest parameters that target MDD 10% or lower. "
            "Reply with only two integers separated by a space, e.g. '9 21'.\n"
            "Last 3 results:\n" + json.dumps(last_three, ensure_ascii=False)
        )
        response = model.generate_content(prompt)
        text = (response.text or "").strip()
        parts = text.split()
        fast = int(parts[0]) if len(parts) >= 1 else 9
        slow = int(parts[1]) if len(parts) >= 2 else 21
        fast = max(5, min(50, fast))
        slow = max(5, min(50, slow))
        if fast >= slow:
            fast, slow = 9, 21
        return fast, slow
    except Exception:
        return 9, 21


def load_best_params() -> dict | None:
    """자율 진화로 저장된 best_params.json이 있으면 사용."""
    if not BEST_PARAMS_FILE.exists():
        return None
    try:
        with open(BEST_PARAMS_FILE, "r", encoding=ENCODING) as f:
            data = json.load(f)
        return data
    except Exception:
        return None


def run_pipeline() -> None:
    history = load_history()
    best = load_best_params()
    if best and "ema_fast" in best and "ema_slow" in best:
        ema_fast = int(best["ema_fast"])
        ema_slow = int(best["ema_slow"])
        rsi_period = int(best.get("rsi_period", 14))
        atr_trail_mult = float(best.get("atr_trail_mult", 2.0))
        param_source = "best_params(진화)"
    else:
        ema_fast, ema_slow = ask_gemini_for_params(history)
        rsi_period, atr_trail_mult = 14, 2.0
        param_source = "Gemini"

    sys.path.insert(0, str(ROOT / "scripts"))
    from strategy_engine import run as engine_run
    from report_slack import send_result_to_slack

    result = engine_run(
        ema_fast=ema_fast,
        ema_slow=ema_slow,
        rsi_period=rsi_period,
        atr_trail_mult=atr_trail_mult,
        with_metrics=True,
    )
    ts = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    params_entry = {"ema_fast": ema_fast, "ema_slow": ema_slow, "rsi_period": rsi_period, "atr_trail_mult": atr_trail_mult}
    entry = {
        "timestamp": ts,
        "params": params_entry,
        "result": {"returns": result["returns"], "mdd": result["mdd"]},
    }
    history.append(entry)
    save_history(history)

    try:
        from optimization_logger import append_log
        append_log(
            source="main",
            params=params_entry,
            result=result,
            iteration_count=1,
            strategy_summary="NVDA 6개월 일봉. EMA(빠름/느림) 골든크로스 + RSI<70 진입, 2×ATR 트레일 스탑.",
        )
    except Exception:
        pass

    msg = (
        f"📊 NVDA 자율 최적화 1회 완료 (최근 6개월)\n"
        f"파라미터 출처: {param_source} | EMA {ema_fast}/{ema_slow} | RSI period {rsi_period} | ATR mult {atr_trail_mult}\n"
        f"수익률: {result['returns']:.2%} / MDD: {result['mdd']:.2%}"
    )
    send_result_to_slack(msg, "QuantLabs NVDA 자율 최적화")


if __name__ == "__main__":
    run_pipeline()
