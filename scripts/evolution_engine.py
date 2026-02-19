# -*- coding: utf-8 -*-
"""
QuantLabs 진화 엔진: 부모 선택 → 파라미터 Mutation → 고립 정점(민감도) 제외.
"""
from __future__ import annotations

import copy
import random
from typing import Any, Callable

# 부모 후보: OOS Sharpe >= 이 값
PARENT_SHARPE_MIN = 1.2
# Mutation 시 파라미터 변화 폭 (상대)
MUTATION_DELTA = 0.15
# 민감도: 파라미터 ±delta 시 Sharpe가 이 비율 이하로 떨어지면 고립 정점으로 제외
SENSITIVITY_DROP_MAX = 0.20


def mutate_params(parent_params: dict, delta: float = MUTATION_DELTA) -> dict:
    """
    부모 파라미터를 미세 조정. 정수 파라미터는 ±1~2, float는 ±delta 비율.
    """
    p = copy.deepcopy(parent_params)
    for key, val in list(p.items()):
        if isinstance(val, bool):
            continue
        if isinstance(val, int):
            step = max(1, int(round(val * delta)))
            p[key] = max(1, val + random.randint(-step, step))
        elif isinstance(val, (float,)):
            if key == "atr_trail_mult" or "mult" in key.lower():
                p[key] = round(val * (1 + random.uniform(-delta, delta)), 2)
                p[key] = max(0.5, min(5.0, p[key]))
            else:
                p[key] = round(val * (1 + random.uniform(-delta, delta)), 4)
    # EMA fast < slow 보장
    if "ema_fast" in p and "ema_slow" in p:
        if p["ema_fast"] >= p["ema_slow"]:
            p["ema_fast"] = max(5, p["ema_slow"] - random.randint(1, 5))
    return p


def param_sensitivity_check(
    df,
    params: dict,
    backtest_fn: Callable,
    delta: float = 0.1,
    drop_threshold: float = SENSITIVITY_DROP_MAX,
) -> bool:
    """
    파라미터를 조금만 바꿔도 Sharpe가 급락하면 True(고립 정점 → 제외).
    """
    base_m = backtest_fn(df, **params)
    base_sharpe = base_m.get("sharpe_ratio") or 0
    if base_sharpe <= 0:
        return True
    for key in list(params.keys()):
        if key not in params or params[key] is None:
            continue
        val = params[key]
        if isinstance(val, bool):
            continue
        for sign in (1, -1):
            p2 = copy.deepcopy(params)
            if isinstance(val, int):
                p2[key] = max(1, val + sign * max(1, int(val * delta)))
            else:
                p2[key] = val * (1 + sign * delta)
            if "ema_fast" in p2 and "ema_slow" in p2 and p2["ema_fast"] >= p2["ema_slow"]:
                continue
            try:
                m2 = backtest_fn(df, **p2)
                sh2 = m2.get("sharpe_ratio") or 0
                if base_sharpe > 1e-6 and sh2 < base_sharpe * (1 - drop_threshold):
                    return True
            except Exception:
                continue
    return False


def select_parents(experiments: list[dict], sharpe_min: float = PARENT_SHARPE_MIN, top_n: int = 5) -> list[dict]:
    """실험 로그에서 상위 전략만 필터 (부모 후보)."""
    out = [x for x in experiments if float(x.get("oos_sharpe") or x.get("is_sharpe") or 0) >= sharpe_min]
    out.sort(key=lambda x: float(x.get("oos_sharpe") or 0), reverse=True)
    return out[:top_n]
