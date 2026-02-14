# -*- coding: utf-8 -*-
"""
QuantLabs - VBS(변동성 돌파) 백테스트 엔진
목표가 = 전일 종가 + (전일 고가 - 전일 저가) * K
K 0.3~0.7 범위 시뮬레이션, 최적 K 추출.
"""
from typing import Optional, Tuple

import pandas as pd


def backtest_vbs(df: pd.DataFrame, k: float) -> Tuple[float, pd.DataFrame]:
    """
    VBS 백테스트: K값 하나에 대해 수익률 계산.
    매일 목표가 = 전일 close + (전일 high - 전일 low) * K
    당일 고가가 목표가를 돌파하면 목표가에 매수, 당일 종가에 매도 가정.
    Returns: (누적 수익률, 일별 결과 DataFrame)
    """
    if df is None or len(df) < 3:
        return 0.0, pd.DataFrame()
    d = df.copy()
    if "high" not in d.columns:
        return 0.0, pd.DataFrame()
    d["prev_high"] = d["high"].shift(1)
    d["prev_low"] = d["low"].shift(1)
    d["prev_close"] = d["close"].shift(1)
    d["target"] = d["prev_close"] + (d["prev_high"] - d["prev_low"]) * k
    d["breakout"] = d["high"] >= d["target"]
    d["entry"] = d["target"]
    d["exit"] = d["close"]
    d["daily_return"] = 0.0
    d.loc[d["breakout"], "daily_return"] = (d.loc[d["breakout"], "exit"] - d.loc[d["breakout"], "entry"]) / d.loc[d["breakout"], "entry"]
    d = d.dropna(subset=["target"])
    if d["daily_return"].empty:
        return 0.0, d
    cum = (1 + d["daily_return"]).cumprod()
    total_return = cum.iloc[-1] - 1 if len(cum) else 0.0
    return total_return, d


def get_best_k(df: pd.DataFrame, k_min: float = 0.3, k_max: float = 0.7, step: float = 0.05) -> Tuple[float, pd.DataFrame]:
    """
    K를 k_min ~ k_max 범위(step 간격)로 돌려 최고 수익률인 K 반환.
    Returns: (최적 K, K별 수익률 DataFrame)
    """
    if df is None or len(df) < 3:
        return 0.5, pd.DataFrame()
    k_vals = []
    ret_vals = []
    k = k_min
    while k <= k_max:
        ret, _ = backtest_vbs(df, k)
        k_vals.append(round(k, 2))
        ret_vals.append(ret)
        k += step
    result = pd.DataFrame({"K": k_vals, "수익률": ret_vals})
    best_idx = result["수익률"].idxmax()
    best_k = result.loc[best_idx, "K"]
    return float(best_k), result


def get_today_target_and_remaining(
    df: pd.DataFrame, current_price: float, k: float
) -> Tuple[Optional[float], Optional[float]]:
    """
    오늘 목표가와 현재가 기준 '돌파까지 남은 퍼센트'.
    df 마지막 행이 전일 데이터라고 가정.
    Returns: (목표가, 남은 %). 이미 돌파했으면 (목표가, 0 또는 음수).
    """
    if df is None or len(df) < 1:
        return None, None
    row = df.iloc[-1]
    prev_high = row["high"]
    prev_low = row["low"]
    prev_close = row["close"]
    target = prev_close + (prev_high - prev_low) * k
    if target <= 0:
        return None, None
    remaining_pct = (target - current_price) / target * 100
    return float(target), float(remaining_pct)
