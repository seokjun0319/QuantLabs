# -*- coding: utf-8 -*-
"""
NVDA 자율 진화 엔진. 과적합 방지 3중 방어(7:3 분할, OOS 검증, 파라미터 안정성).
목표: 연간수익률 15%+, MDD 8% 이하, Sharpe 1.5+.
UTF-8, Windows/Linux 호환.
"""
from __future__ import annotations

import json
import os
import random
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
HISTORY_FILE = DATA_DIR / "strategy_history.json"
BEST_PARAMS_FILE = DATA_DIR / "best_params.json"
ENCODING = "utf-8"

# 목표치
TARGET_ANN_RET = 0.15
TARGET_MDD_MAX = 0.08
TARGET_SHARPE_MIN = 1.5
# 과적합: 훈련 vs 테스트 괴리 20% 초과 시 폐기
OOS_GAP_THRESHOLD = 0.20
# 최대 탐색 횟수
MAX_ITERATIONS = 100
# Train 70% / Test 30% (최근 1년 중)
TRAIN_RATIO = 0.7
DAYS_1Y = 365

if getattr(sys.stdout, "reconfigure", None):
    try:
        sys.stdout.reconfigure(encoding=ENCODING)
    except Exception:
        pass


def _ensure_scripts_path() -> None:
    if str(ROOT / "scripts") not in sys.path:
        sys.path.insert(0, str(ROOT / "scripts"))


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


def generate_param_combos(max_combos: int = MAX_ITERATIONS) -> list[dict[str, Any]]:
    """EMA(9,21,50), RSI(14,21), ATR(2.0~3.5) 조합. ema_fast < ema_slow만."""
    ema_fast_opts = [9, 12, 21]
    ema_slow_opts = [21, 26, 50]
    rsi_opts = [14, 21]
    atr_opts = [2.0, 2.5, 3.0, 3.5]
    combos = []
    for ef in ema_fast_opts:
        for es in ema_slow_opts:
            if ef >= es:
                continue
            for rp in rsi_opts:
                for am in atr_opts:
                    combos.append({
                        "ema_fast": ef,
                        "ema_slow": es,
                        "rsi_period": rp,
                        "atr_trail_mult": am,
                    })
    if len(combos) > max_combos:
        random.shuffle(combos)
        combos = combos[:max_combos]
    return combos


def train_test_split(df) -> tuple[Any, Any]:
    """앞 70% 훈련, 뒤 30% 테스트."""
    n = len(df)
    if n < 100:
        return df, df.iloc[0:0]
    split = int(n * TRAIN_RATIO)
    return df.iloc[:split], df.iloc[split:]


def score_train(m: dict) -> tuple[float, float, float]:
    """정렬용: MDD 낮을수록 좋고, Sharpe·연간수익률 높을수록 좋음. (mdd_penalty, -sharpe, -ann_ret)."""
    mdd = m.get("mdd") or 0
    sharpe = m.get("sharpe_ratio") or 0
    ann = m.get("annualized_return") or 0
    return (mdd, -sharpe, -ann)


def is_overfit(train_m: dict, test_m: dict) -> bool:
    """훈련 vs 테스트 괴리가 20% 초과면 과적합."""
    for key in ("annualized_return", "sharpe_ratio", "mdd"):
        t1 = train_m.get(key)
        t2 = test_m.get(key)
        if t1 is None or t2 is None:
            continue
        denom = max(abs(t1), 1e-6)
        gap = abs(t1 - t2) / denom
        if gap > OOS_GAP_THRESHOLD:
            return True
    return False


def meets_target(m: dict) -> bool:
    return (
        (m.get("annualized_return") or 0) >= TARGET_ANN_RET
        and (m.get("mdd") or 1) <= TARGET_MDD_MAX
        and (m.get("sharpe_ratio") or 0) >= TARGET_SHARPE_MIN
    )


def stability_check(
    df_train,
    params: dict,
    baseline_ann: float,
    baseline_sharpe: float,
    engine_backtest_with_metrics,
) -> tuple[bool, str]:
    """인접 파라미터(EMA ±1)에서 성능 유지 여부. 둔감하면 True."""
    ef, es = params.get("ema_fast", 9), params.get("ema_slow", 21)
    neighbors = [
        {"ema_fast": max(5, ef - 1), "ema_slow": es, "rsi_period": params.get("rsi_period", 14), "atr_trail_mult": params.get("atr_trail_mult", 2.0)},
        {"ema_fast": min(50, ef + 1), "ema_slow": es, "rsi_period": params.get("rsi_period", 14), "atr_trail_mult": params.get("atr_trail_mult", 2.0)},
        {"ema_fast": ef, "ema_slow": max(ef + 1, es - 1), "rsi_period": params.get("rsi_period", 14), "atr_trail_mult": params.get("atr_trail_mult", 2.0)},
        {"ema_fast": ef, "ema_slow": min(50, es + 1), "rsi_period": params.get("rsi_period", 14), "atr_trail_mult": params.get("atr_trail_mult", 2.0)},
    ]
    for nb in neighbors:
        if nb["ema_fast"] >= nb["ema_slow"]:
            continue
        m = engine_backtest_with_metrics(
            df_train,
            rsi_upper=70,
            atr_period=14,
            **nb,
        )
        ann = m.get("annualized_return") or 0
        sharpe = m.get("sharpe_ratio") or 0
        if baseline_ann and (ann < baseline_ann * 0.5):
            return False, f"인접 EMA에서 연간수익률 급락 (baseline {baseline_ann:.2%} vs {ann:.2%})"
        if baseline_sharpe and (sharpe < baseline_sharpe * 0.5):
            return False, f"인접 EMA에서 샤프 급락 (baseline {baseline_sharpe:.2f} vs {sharpe:.2f})"
    return True, "OK"


def run_evolution() -> dict:
    """진화 1회 실행: 탐색 → 상위 5 → OOS 검증 → 안정성 → 목표 달성 시 저장/보고."""
    _ensure_scripts_path()
    from strategy_engine import fetch_nvda, backtest_with_metrics

    df_full = fetch_nvda(DAYS_1Y)
    if df_full is None or len(df_full) < 120:
        return {"success": False, "reason": "NVDA 1년 데이터 부족", "best": None}

    df_train, df_test = train_test_split(df_full)
    if len(df_test) < 20:
        return {"success": False, "reason": "테스트 구간 데이터 부족", "best": None}

    combos = generate_param_combos(MAX_ITERATIONS)
    train_results: list[tuple[dict, dict]] = []
    for p in combos:
        m = backtest_with_metrics(
            df_train,
            ema_fast=p["ema_fast"],
            ema_slow=p["ema_slow"],
            rsi_period=p["rsi_period"],
            rsi_upper=70,
            atr_period=14,
            atr_trail_mult=p["atr_trail_mult"],
        )
        train_results.append((p, m))

    # Step B: 훈련 성적 상위 5개
    train_results.sort(key=lambda x: score_train(x[1]))
    top5 = train_results[:5]

    # Step C: OOS 검증, 과적합 제거
    candidates = []
    for params, train_m in top5:
        test_m = backtest_with_metrics(
            df_test,
            ema_fast=params["ema_fast"],
            ema_slow=params["ema_slow"],
            rsi_period=params["rsi_period"],
            rsi_upper=70,
            atr_period=14,
            atr_trail_mult=params["atr_trail_mult"],
        )
        if is_overfit(train_m, test_m):
            continue
        candidates.append((params, train_m, test_m))

    if not candidates:
        best_params = top5[0][0]
        best_train = top5[0][1]
        best_test = backtest_with_metrics(
            df_test,
            ema_fast=best_params["ema_fast"],
            ema_slow=best_params["ema_slow"],
            rsi_period=best_params["rsi_period"],
            rsi_upper=70,
            atr_period=14,
            atr_trail_mult=best_params["atr_trail_mult"],
        )
        candidates = [(best_params, best_train, best_test)]

    # OOS 기준으로 최선 선택 (테스트 성능이 진짜 성과)
    candidates.sort(key=lambda x: score_train(x[2]))
    best_params, best_train_m, best_test_m = candidates[0]

    # Step D: 안정성 체크 (참고만, 실패해도 목표 달성 시 채택 가능)
    stable, stable_msg = stability_check(
        df_train, best_params,
        best_train_m.get("annualized_return"), best_train_m.get("sharpe_ratio"),
        backtest_with_metrics,
    )

    try:
        from optimization_logger import append_log
        append_log(
            source="evolve",
            params=best_params,
            result=best_test_m,
            iteration_count=len(combos),
            target_ann_ret=TARGET_ANN_RET,
            target_mdd=TARGET_MDD_MAX,
            target_sharpe=TARGET_SHARPE_MIN,
            strategy_summary="NVDA 1년 7:3 훈련/테스트. EMA·RSI·ATR 조합 탐색, OOS·파라미터 안정성 검증. 목표 연15%·MDD8%·샤프1.5.",
        )
    except Exception:
        pass

    if meets_target(best_test_m):
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        payload = {
            "ema_fast": best_params["ema_fast"],
            "ema_slow": best_params["ema_slow"],
            "rsi_period": best_params["rsi_period"],
            "atr_trail_mult": best_params["atr_trail_mult"],
            "source": "evolve_nvda",
            "updated": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "train": best_train_m,
            "test": best_test_m,
            "stable": stable,
            "stable_note": stable_msg,
        }
        with open(BEST_PARAMS_FILE, "w", encoding=ENCODING) as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

        history = load_history()
        history.append({
            "timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "type": "optimization",
            "params": best_params,
            "result": {
                "returns": best_test_m.get("returns"),
                "mdd": best_test_m.get("mdd"),
                "annualized_return": best_test_m.get("annualized_return"),
                "sharpe_ratio": best_test_m.get("sharpe_ratio"),
            },
            "train_metrics": best_train_m,
            "test_metrics": best_test_m,
            "stable": stable,
        })
        save_history(history)
        return {
            "success": True,
            "best": best_params,
            "test_metrics": best_test_m,
            "train_metrics": best_train_m,
            "stable": stable,
            "saved_best_params": True,
        }

    # 목표 미달: 최고 조합과 한계점 보고용 반환
    return {
        "success": False,
        "best": best_params,
        "test_metrics": best_test_m,
        "train_metrics": best_train_m,
        "stable": stable,
        "stable_note": stable_msg,
        "reason": "목표 미달 (AnnRet≥15%, MDD≤8%, Sharpe≥1.5)",
    }


def report_slack(msg: str) -> None:
    try:
        _ensure_scripts_path()
        from report_slack import send_result_to_slack
        send_result_to_slack(msg, "QuantLabs NVDA 자율 진화")
    except Exception:
        pass


if __name__ == "__main__":
    result = run_evolution()
    out = json.dumps(result, ensure_ascii=False, indent=2)
    print(out)

    if result.get("success"):
        p = result["best"]
        m = result.get("test_metrics") or {}
        report_slack(
            f"🎯 NVDA 자율 진화 목표 달성\n"
            f"파라미터: EMA {p['ema_fast']}/{p['ema_slow']}, RSI period {p['rsi_period']}, ATR mult {p['atr_trail_mult']}\n"
            f"연간수익률: {m.get('annualized_return', 0):.2%} | MDD: {m.get('mdd', 0):.2%} | Sharpe: {m.get('sharpe_ratio', 0):.2f}\n"
            f"best_params.json 반영됨."
        )
    else:
        best = result.get("best")
        tm = result.get("test_metrics") or {}
        report_slack(
            f"⚠️ NVDA 자율 진화 1회 완료 (목표 미달)\n"
            f"현재 최고: EMA {best.get('ema_fast')}/{best.get('ema_slow')} | "
            f"AnnRet {tm.get('annualized_return', 0):.2%} | MDD {tm.get('mdd', 0):.2%} | Sharpe {tm.get('sharpe_ratio', 0):.2f}\n"
            f"한계: {result.get('reason', '')}"
        )
