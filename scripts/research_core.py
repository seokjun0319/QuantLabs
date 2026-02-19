# -*- coding: utf-8 -*-
"""
QuantLabs 리서치 코어: Train/Val/Test 분리, Walk-forward, OOS 폐기, 통계 검정, 채택 기준.
"""
from __future__ import annotations

import random
from typing import Any, Callable

import numpy as np

# IS/OOS 괴리 30% 초과 시 폐기 (Consistency)
OOS_IS_RATIO_MIN = 0.70
SHARPE_GAP_MAX = 0.30
# 채택 기준
GATE_SHARPE_MIN = 1.2
GATE_MDD_MAX = 0.20
GATE_PVALUE_MAX = 0.05
# 몬테카를로 시뮬레이션 횟수
MC_SIM = 500
TRADING_DAYS = 252


def train_val_test_split(
    n: int,
    train_ratio: float = 0.6,
    val_ratio: float = 0.2,
    test_ratio: float = 0.2,
) -> tuple[int, int, int, int]:
    """
    인덱스 구간: [0, t1) train, [t1, t2) val, [t2, n) test.
    Returns (t1, t2, n) so df.iloc[:t1], df.iloc[t1:t2], df.iloc[t2:].
    """
    t1 = int(n * train_ratio)
    t2 = int(n * (train_ratio + val_ratio))
    return t1, t2, n


def walk_forward_windows(
    n: int,
    train_size: int,
    test_size: int,
    step: int,
) -> list[tuple[int, int, int, int]]:
    """
    Walk-forward: (train_start, train_end, test_start, test_end) 리스트.
    train 구간이 지나면 다음 구간으로 밀려남.
    """
    out = []
    train_end = train_size
    while train_end + test_size <= n:
        train_start = train_end - train_size
        test_start = train_end
        test_end = test_start + test_size
        out.append((train_start, train_end, test_start, test_end))
        train_end += step
    return out


def oos_discard(is_metrics: dict, oos_metrics: dict, ratio: float = OOS_IS_RATIO_MIN) -> bool:
    """
    OOS가 IS 대비 ratio 이하로 떨어지면 True(폐기).
    """
    is_sharpe = is_metrics.get("sharpe_ratio") or 0
    oos_sharpe = oos_metrics.get("sharpe_ratio") or 0
    if is_sharpe <= 0:
        return oos_sharpe <= 0
    if oos_sharpe < ratio * is_sharpe:
        return True
    is_ret = abs(is_metrics.get("returns") or 0)
    oos_ret = abs(oos_metrics.get("returns") or 0)
    if is_ret >= 1e-6 and oos_ret < ratio * is_ret:
        return True
    return False


def sharpe_gap_ok(is_sharpe: float, oos_sharpe: float, max_gap: float = SHARPE_GAP_MAX) -> bool:
    """IS vs OOS Sharpe 괴리율이 max_gap 이내면 True."""
    if is_sharpe <= 0:
        return True
    gap = abs(is_sharpe - oos_sharpe) / abs(is_sharpe)
    return gap <= max_gap


def monte_carlo_pvalue(daily_returns: np.ndarray, observed_sharpe: float, n_sim: int = MC_SIM) -> float:
    """
    수익률 순서를 섞어서 Sharpe 분포를 만들고, observed_sharpe 이상인 비율을 p-value로.
    p-value 낮으면 통계적으로 유의(우연이 아님).
    """
    if daily_returns is None or len(daily_returns) < 2:
        return 1.0
    annualizer = (TRADING_DAYS ** 0.5)
    sharpes = []
    for _ in range(n_sim):
        shuffled = np.random.permutation(daily_returns)
        mu, sigma = shuffled.mean(), shuffled.std()
        if sigma and sigma > 1e-10:
            sharpes.append(mu / sigma * annualizer)
        else:
            sharpes.append(0.0)
    sharpes = np.array(sharpes)
    p = float(np.mean(sharpes >= observed_sharpe))
    return p


def gatekeeping(
    is_metrics: dict,
    oos_metrics: dict,
    mdd: float,
    p_value: float,
    daily_returns_for_mc=None,
) -> tuple[bool, list[str]]:
    """
    채택 기준: Sharpe>1.2, MDD<20%, IS/OOS 괴리 30% 이내, p-value(통계 유의).
    Returns (passed, list of failure reasons).
    """
    failures = []
    oos_sharpe = oos_metrics.get("sharpe_ratio") or 0
    is_sharpe = is_metrics.get("sharpe_ratio") or 0
    if oos_sharpe < GATE_SHARPE_MIN:
        failures.append(f"OOS Sharpe {oos_sharpe:.2f} < {GATE_SHARPE_MIN}")
    if mdd > GATE_MDD_MAX:
        failures.append(f"MDD {mdd:.2%} > {GATE_MDD_MAX:.0%}")
    if not sharpe_gap_ok(is_sharpe, oos_sharpe):
        failures.append(f"IS/OOS Sharpe 괴리 > {SHARPE_GAP_MAX:.0%}")
    if p_value > GATE_PVALUE_MAX:
        failures.append(f"p-value {p_value:.4f} > {GATE_PVALUE_MAX} (통계적 유의성 부족)")
    if daily_returns_for_mc is not None and len(daily_returns_for_mc) >= 10:
        p = monte_carlo_pvalue(np.asarray(daily_returns_for_mc), oos_sharpe, n_sim=MC_SIM)
        if p > GATE_PVALUE_MAX:
            failures.append(f"몬테카를로 p-value {p:.4f} > {GATE_PVALUE_MAX}")
    return (len(failures) == 0, failures)


def run_walk_forward(
    df,
    params: dict,
    backtest_fn: Callable,
    train_ratio: float = 0.6,
    test_ratio: float = 0.2,
) -> tuple[dict, dict, float, float, list]:
    """
    Train/Test 한 번 분할 후 IS·OOS 메트릭 반환.
    backtest_fn(df, **params) → dict with returns, mdd, sharpe_ratio, optional daily_returns.
    Returns (is_metrics, oos_metrics, mdd_used, p_value, daily_returns_for_mc).
    """
    n = len(df)
    t1 = int(n * train_ratio)
    t2 = n
    df_train = df.iloc[:t1]
    df_test = df.iloc[t1:t2]
    if len(df_train) < 30 or len(df_test) < 20:
        return (
            {"returns": 0, "sharpe_ratio": 0, "mdd": 1},
            {"returns": 0, "sharpe_ratio": 0, "mdd": 1},
            1.0,
            1.0,
            [],
        )
    is_m = backtest_fn(df_train, **params)
    oos_m = backtest_fn(df_test, **params)
    # 메트릭만 전달할 때 daily_returns 키 제거해 downstream 호환
    is_clean = {k: v for k, v in is_m.items() if k != "daily_returns"}
    oos_clean = {k: v for k, v in oos_m.items() if k != "daily_returns"}
    mdd_used = max(is_clean.get("mdd") or 0, oos_clean.get("mdd") or 0)
    daily_ret = oos_m.get("daily_returns") or []
    if isinstance(daily_ret, list) and len(daily_ret) >= 2:
        p_val = monte_carlo_pvalue(np.asarray(daily_ret), oos_clean.get("sharpe_ratio") or 0, n_sim=MC_SIM)
    else:
        p_val = GATE_PVALUE_MAX
    return (is_clean, oos_clean, mdd_used, p_val, daily_ret)
