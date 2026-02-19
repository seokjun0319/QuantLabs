# -*- coding: utf-8 -*-
"""
QuantLabs 리서치 파이프라인: Walk-forward, Gatekeeping, 진화 Mutation, 전 시도 DB 기록, 검증 통과만 대시보드 반영.
"""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
BEST_PARAMS_FILE = DATA_DIR / "best_params.json"
DASHBOARD_CANDIDATES_FILE = DATA_DIR / "dashboard_candidates.json"
ENCODING = "utf-8"

# 스크립트 경로
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from experiments_logger import append_experiment, load_experiments, load_top_strategies
from evolution_engine import mutate_params, param_sensitivity_check, select_parents
from research_core import (
    gatekeeping,
    oos_discard,
    run_walk_forward,
)
from strategy_engine import backtest_with_metrics, fetch_nvda

# strategy_engine.backtest_with_metrics 인자만 허용
BACKTEST_KEYS = ("ema_fast", "ema_slow", "rsi_period", "rsi_upper", "atr_period", "atr_trail_mult")

# 기본 파라미터 (부모 없을 때)
DEFAULT_PARAMS = {
    "ema_fast": 9,
    "ema_slow": 21,
    "rsi_period": 14,
    "rsi_upper": 70,
    "atr_period": 14,
    "atr_trail_mult": 2.0,
}


def _filter_params(params: dict) -> dict:
    return {k: v for k, v in params.items() if k in BACKTEST_KEYS}


def _backtest_with_daily_returns(df, **kwargs):
    """Walk-forward/몬테카를로용: 메트릭 + 일별 수익률 반환."""
    return backtest_with_metrics(df, return_daily_returns=True, **_filter_params(kwargs))


def _backtest_metrics_only(df, **kwargs):
    """민감도 검사용: 메트릭만 (daily_returns 불필요)."""
    return backtest_with_metrics(df, return_daily_returns=False, **_filter_params(kwargs))


def run_one_candidate(
    df,
    params: dict,
    parent_id: str = "",
    factors: str = "ema_rsi_atr",
    train_ratio: float = 0.6,
    test_ratio: float = 0.2,
    skip_sensitivity: bool = False,
) -> tuple[str | None, bool]:
    """
    단일 파라미터 후보에 대해 Walk-forward → OOS 폐기 → Gatekeeping → DB 기록.
    Returns (strategy_id, passed_gate).
    """
    is_metrics, oos_metrics, mdd_used, p_value, daily_returns = run_walk_forward(
        df,
        params,
        _backtest_with_daily_returns,
        train_ratio=train_ratio,
        test_ratio=test_ratio,
    )
    if oos_discard(is_metrics, oos_metrics):
        passed = False
        # 폐기되어도 DB에는 기록
    else:
        passed, failures = gatekeeping(
            is_metrics,
            oos_metrics,
            mdd_used,
            p_value,
            daily_returns_for_mc=daily_returns,
        )
    sid = append_experiment(
        params=params,
        is_return=float(is_metrics.get("returns") or 0),
        is_sharpe=float(is_metrics.get("sharpe_ratio") or 0),
        oos_return=float(oos_metrics.get("returns") or 0),
        oos_sharpe=float(oos_metrics.get("sharpe_ratio") or 0),
        mdd=mdd_used,
        p_value=p_value,
        passed_gate=passed,
        parent_id=parent_id,
        factors=factors,
    )
    return sid, passed


def run_research_loop(
    days: int = 365,
    train_ratio: float = 0.6,
    test_ratio: float = 0.2,
    num_mutations: int = 10,
    parent_sharpe_min: float = 1.2,
    top_parents: int = 5,
    run_sensitivity: bool = True,
) -> dict:
    """
    실행 루프: 상위 전략 로드 → 변이 생성 → Walk-forward → 전부 DB 기록 → 검증 통과만 대시보드 반영.
    """
    df = fetch_nvda(days=days)
    if df is None or len(df) < 100:
        return {"error": "데이터 부족", "passed": [], "best_params": None}

    parents = load_top_strategies(sharpe_min=parent_sharpe_min, passed_only=True, limit=top_parents)
    candidates = []

    # 부모 기반 변이 (부모가 있으면 랜덤 선택)
    for _ in range(num_mutations):
        if parents:
            p = random.choice(parents)
            parent_params = p.get("_params") or json.loads(p.get("params_json") or "{}")
            parent_id = p.get("strategy_id", "")
            params = mutate_params(parent_params)
        else:
            parent_params = DEFAULT_PARAMS.copy()
            parent_id = ""
            params = mutate_params(parent_params)

        if run_sensitivity and param_sensitivity_check(df, params, _backtest_metrics_only):
            continue
        candidates.append((params, parent_id))

    # 부모가 없을 때 기본 1회 추가
    if not candidates:
        params = DEFAULT_PARAMS.copy()
        if not (run_sensitivity and param_sensitivity_check(df, params, _backtest_metrics_only)):
            candidates.append((params, ""))

    passed_list = []
    for params, parent_id in candidates:
        sid, passed = run_one_candidate(
            df,
            params,
            parent_id=parent_id,
            train_ratio=train_ratio,
            test_ratio=test_ratio,
        )
        if passed:
            passed_list.append({"strategy_id": sid, "params": params})

    # 검증 통과한 모델만 대시보드 반영
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if passed_list:
        # OOS Sharpe 기준 정렬 후 1등을 best_params.json에
        all_exp = load_experiments()
        by_id = {r["strategy_id"]: r for r in all_exp}
        passed_list.sort(
            key=lambda x: float(by_id.get(x["strategy_id"], {}).get("oos_sharpe") or 0),
            reverse=True,
        )
        best = passed_list[0]["params"]
        payload = {
            **best,
            "source": "research_pipeline",
            "updated": __import__("datetime").datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        with open(BEST_PARAMS_FILE, "w", encoding=ENCODING) as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        with open(DASHBOARD_CANDIDATES_FILE, "w", encoding=ENCODING) as f:
            json.dump(passed_list, f, ensure_ascii=False, indent=2)
    else:
        # 통과한 게 없으면 best_params는 기존 유지, 후보만 비움
        with open(DASHBOARD_CANDIDATES_FILE, "w", encoding=ENCODING) as f:
            json.dump([], f, ensure_ascii=False, indent=2)

    return {
        "candidates_run": len(candidates),
        "passed": passed_list,
        "best_params": passed_list[0]["params"] if passed_list else None,
    }


if __name__ == "__main__":
    if getattr(sys.stdout, "reconfigure", None):
        try:
            sys.stdout.reconfigure(encoding=ENCODING)
        except Exception:
            pass
    out = run_research_loop(num_mutations=8, run_sensitivity=True)
    print(json.dumps(out, ensure_ascii=False, indent=2))
