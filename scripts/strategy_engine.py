# -*- coding: utf-8 -*-
"""
yfinance로 BTC-USD 데이터 수집 후 ema_fast, ema_slow 백테스트.
수익률(returns), MDD 반환. UTF-8, Windows/Linux 호환.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Tuple

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def fetch_btc_usd(days: int = 365) -> pd.DataFrame:
    """BTC-USD 일봉 (yfinance)."""
    try:
        import yfinance as yf
        df = yf.download("BTC-USD", period=f"{days}d", interval="1d", progress=False, auto_adjust=True)
        if df is None or df.empty:
            return pd.DataFrame()
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [c.lower() for c in df.columns.get_level_values(0)]
        return df[["close"]].rename(columns={"close": "close"}).sort_index()
    except Exception:
        return pd.DataFrame()


def backtest_ema(df: pd.DataFrame, ema_fast: int, ema_slow: int) -> Tuple[float, float]:
    """
    EMA 골든/데드 크로스 백테스트.
    Returns: (수익률, MDD)
    """
    if df is None or len(df) < ema_slow + 5:
        return 0.0, 0.0
    d = df.copy()
    d["ema_fast"] = d["close"].ewm(span=ema_fast, adjust=False).mean()
    d["ema_slow"] = d["close"].ewm(span=ema_slow, adjust=False).mean()
    d["signal"] = (d["ema_fast"] > d["ema_slow"]).astype(int)
    d["ret"] = d["close"].pct_change()
    d["strategy_ret"] = d["signal"].shift(1) * d["ret"]
    d = d.dropna(subset=["strategy_ret"])
    if d.empty:
        return 0.0, 0.0
    equity = (1 + d["strategy_ret"]).cumprod()
    total_return = float(equity.iloc[-1] - 1.0)
    peak = equity.cummax()
    dd = (equity - peak) / peak.replace(0, 1e-10)
    mdd = float(abs(dd.min()))
    return total_return, mdd


def run(ema_fast: int = 12, ema_slow: int = 26, days: int = 365) -> dict:
    """BTC-USD 수집 후 백테스트. returns, mdd 반환."""
    df = fetch_btc_usd(days)
    ret, mdd = backtest_ema(df, ema_fast, ema_slow)
    return {"returns": ret, "mdd": mdd}


if __name__ == "__main__":
    encoding = "utf-8"
    fast = int(sys.argv[1]) if len(sys.argv) > 1 else 12
    slow = int(sys.argv[2]) if len(sys.argv) > 2 else 26
    res = run(ema_fast=fast, ema_slow=slow)
    sys.stdout.reconfigure(encoding=encoding) if getattr(sys.stdout, "reconfigure", None) else None
    print(json.dumps(res, ensure_ascii=False))
