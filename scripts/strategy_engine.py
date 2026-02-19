# -*- coding: utf-8 -*-
"""
NVDA 전용 퀀트 엔진. yfinance 일봉.
EMA(9/21) + RSI(14) + ATR(14). 진입: EMA9>EMA21 & RSI<70. 익절: 2*ATR Trailing Stop.
자율 진화: 연간수익률/샤프/구간 백테스트 지원.
UTF-8, Windows/Linux 호환.
"""
from __future__ import annotations

import json
import sys
import warnings
from pathlib import Path
from typing import Tuple

import pandas as pd

warnings.filterwarnings("ignore", message="Downcasting object dtype", category=FutureWarning)

ROOT = Path(__file__).resolve().parents[1]
TICKER = "NVDA"
MONTHS = 6
TRADING_DAYS_PER_YEAR = 252


def fetch_nvda(days: int | None = None) -> pd.DataFrame:
    """NVDA 일봉 (OHLC). days 미지정 시 6개월(약 132일). 1년은 365."""
    n = days or (MONTHS * 22)
    try:
        import yfinance as yf
        df = yf.download(TICKER, period=f"{n}d", interval="1d", progress=False, auto_adjust=True)
        if df is None or df.empty:
            return pd.DataFrame()
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [c.lower() for c in df.columns.get_level_values(0)]
        for c in ["open", "high", "low", "close"]:
            if c not in df.columns:
                return pd.DataFrame()
        return df[["open", "high", "low", "close"]].sort_index()
    except Exception:
        return pd.DataFrame()


def add_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)
    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()
    rs = avg_gain / avg_loss.replace(0, 1e-10)
    return 100 - (100 / (1 + rs))


def add_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high_low = df["high"] - df["low"]
    high_close = (df["high"] - df["close"].shift(1)).abs()
    low_close = (df["low"] - df["close"].shift(1)).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    return tr.rolling(period).mean()


def backtest_nvda(
    df: pd.DataFrame,
    ema_fast: int = 9,
    ema_slow: int = 21,
    rsi_period: int = 14,
    rsi_upper: float = 70,
    atr_period: int = 14,
    atr_trail_mult: float = 2.0,
    return_equity_curve: bool = False,
) -> Tuple[float, float] | Tuple[float, float, pd.Series]:
    """
    진입: EMA(9) > EMA(21) 이면서 RSI(14) < 70.
    익절: 2*ATR(14) Trailing Stop (고점 대비 2*ATR 하락 시 청산).
    Returns: (수익률, MDD) 또는 return_equity_curve=True 시 (수익률, MDD, equity_curve).
    """
    if df is None or len(df) < max(ema_slow, rsi_period, atr_period) + 10:
        if return_equity_curve:
            return 0.0, 0.0, pd.Series(dtype=float)
        return 0.0, 0.0
    d = df.copy()
    d["ema_fast"] = d["close"].ewm(span=ema_fast, adjust=False).mean()
    d["ema_slow"] = d["close"].ewm(span=ema_slow, adjust=False).mean()
    d["rsi"] = add_rsi(d["close"], rsi_period)
    d["atr"] = add_atr(d, atr_period)
    d = d.dropna(subset=["ema_slow", "rsi", "atr"])
    if len(d) < 5:
        if return_equity_curve:
            return 0.0, 0.0, pd.Series(dtype=float)
        return 0.0, 0.0

    # 진입 신호: EMA9 > EMA21 & RSI < 70 (전일 기준으로 다음 봉 진입)
    d["entry_signal"] = ((d["ema_fast"] > d["ema_slow"]) & (d["rsi"] < rsi_upper)).shift(1).fillna(False).astype(bool)

    # Trailing Stop: 진입 후 고점 대비 2*ATR 하락 시 청산
    position = 0
    entry_price = 0.0
    high_water = 0.0
    prev_close = float(d["close"].iloc[0])
    equity = 1.0
    equity_curve = []
    for i in range(len(d)):
        row = d.iloc[i]
        close = row["close"]
        atr = row["atr"]
        trail_dist = atr_trail_mult * atr if atr > 0 else 0

        if position == 0:
            if row["entry_signal"]:
                position = 1
                entry_price = close
                high_water = close
            equity_curve.append(equity)
            prev_close = close
            continue

        if position == 1:
            high_water = max(high_water, row["high"], close)
            if trail_dist > 0 and close <= high_water - trail_dist:
                ret = (close - entry_price) / entry_price if entry_price else 0
                equity *= 1 + ret
                position = 0
            else:
                ret = (close - prev_close) / prev_close if prev_close else 0
                equity *= 1 + ret
            equity_curve.append(equity)
            prev_close = close
            continue

        equity_curve.append(equity)
        prev_close = close

    if not equity_curve:
        if return_equity_curve:
            return 0.0, 0.0, pd.Series(dtype=float)
        return 0.0, 0.0
    eq = pd.Series(equity_curve)
    total_return = float(eq.iloc[-1] - 1.0)
    peak = eq.cummax()
    dd = (eq - peak) / peak.replace(0, 1e-10)
    mdd = float(abs(dd.min()))
    if return_equity_curve:
        return total_return, mdd, eq
    return total_return, mdd


def backtest_with_metrics(
    df: pd.DataFrame,
    ema_fast: int = 9,
    ema_slow: int = 21,
    rsi_period: int = 14,
    rsi_upper: float = 70,
    atr_period: int = 14,
    atr_trail_mult: float = 2.0,
    return_daily_returns: bool = False,
) -> dict:
    """
    백테스트 후 연간수익률·샤프 포함 메트릭 반환.
    return_daily_returns=True 시 몬테카를로용 일별 수익률 포함.
    Returns: returns, mdd, annualized_return, sharpe_ratio, n_days [, daily_returns]
    """
    ret, mdd, eq = backtest_nvda(
        df,
        ema_fast=ema_fast,
        ema_slow=ema_slow,
        rsi_period=rsi_period,
        rsi_upper=rsi_upper,
        atr_period=atr_period,
        atr_trail_mult=atr_trail_mult,
        return_equity_curve=True,
    )
    n_days = len(eq)
    out = {
        "returns": ret,
        "mdd": mdd,
        "annualized_return": 0.0,
        "sharpe_ratio": 0.0,
        "n_days": n_days,
    }
    if n_days < 2:
        if return_daily_returns:
            out["daily_returns"] = []
        return out
    daily_ret = eq.pct_change().dropna()
    ann_ret = (1 + ret) ** (TRADING_DAYS_PER_YEAR / n_days) - 1.0 if n_days else 0.0
    std = daily_ret.std()
    sharpe = (daily_ret.mean() / std * (TRADING_DAYS_PER_YEAR ** 0.5)) if std and std > 0 else 0.0
    out["annualized_return"] = ann_ret
    out["sharpe_ratio"] = float(sharpe)
    if return_daily_returns:
        out["daily_returns"] = daily_ret.tolist()
    return out


def run(
    ema_fast: int = 9,
    ema_slow: int = 21,
    days: int | None = None,
    rsi_period: int = 14,
    rsi_upper: float = 70,
    atr_trail_mult: float = 2.0,
    with_metrics: bool = False,
) -> dict:
    """NVDA 일봉 백테스트. with_metrics=True 시 annualized_return, sharpe_ratio 포함."""
    df = fetch_nvda(days)
    if with_metrics:
        return backtest_with_metrics(
            df,
            ema_fast=ema_fast,
            ema_slow=ema_slow,
            rsi_period=rsi_period,
            rsi_upper=rsi_upper,
            atr_period=14,
            atr_trail_mult=atr_trail_mult,
        )
    ret, mdd = backtest_nvda(
        df,
        ema_fast=ema_fast,
        ema_slow=ema_slow,
        rsi_period=rsi_period,
        rsi_upper=rsi_upper,
        atr_period=14,
        atr_trail_mult=atr_trail_mult,
    )
    return {"returns": ret, "mdd": mdd}


if __name__ == "__main__":
    encoding = "utf-8"
    fast = int(sys.argv[1]) if len(sys.argv) > 1 else 9
    slow = int(sys.argv[2]) if len(sys.argv) > 2 else 21
    res = run(ema_fast=fast, ema_slow=slow)
    if getattr(sys.stdout, "reconfigure", None):
        try:
            sys.stdout.reconfigure(encoding=encoding)
        except Exception:
            pass
    print(json.dumps(res, ensure_ascii=False))
