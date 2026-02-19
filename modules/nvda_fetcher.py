# -*- coding: utf-8 -*-
"""
QuantLabs - 엔비디아(NVDA) 시세 및 지표
yfinance로 실시간 시세, 20/50일 이격도, RSI, 지지/저항.
"""
from typing import Optional, Tuple

import pandas as pd

from .slack_notifier import send_error_to_slack

TICKER = "NVDA"


def get_nvda_history(days: int = 60) -> Optional[pd.DataFrame]:
    """NVDA 일봉 (Open, High, Low, Close, Volume)."""
    try:
        import yfinance as yf
        t = yf.Ticker(TICKER)
        df = t.history(period=f"{days}d", interval="1d")
        if df is None or df.empty:
            return None
        df = df.rename(columns={"Open": "open", "High": "high", "Low": "low", "Close": "close", "Volume": "volume"})
        return df[["open", "high", "low", "close", "volume"]].sort_index()
    except Exception as e:
        send_error_to_slack(e, context="get_nvda_history")
        return None


def get_nvda_current_price() -> Optional[float]:
    """NVDA 현재가 (USD)."""
    try:
        import yfinance as yf
        t = yf.Ticker(TICKER)
        h = t.history(period="5d")
        if h is not None and not h.empty:
            return float(h["Close"].iloc[-1])
        return None
    except Exception as e:
        send_error_to_slack(e, context="get_nvda_current_price")
        return None


def get_nvda_current_price_and_datetime() -> Tuple[Optional[float], Optional[str]]:
    """NVDA 현재가(USD)와 해당 시세의 날짜·시간(문자열)."""
    try:
        import yfinance as yf
        t = yf.Ticker(TICKER)
        h = t.history(period="5d")
        if h is not None and not h.empty:
            price = float(h["Close"].iloc[-1])
            last_ts = h.index[-1]
            if hasattr(last_ts, "strftime"):
                dt_str = last_ts.strftime("%Y-%m-%d %H:%M")
            else:
                dt_str = str(last_ts)[:16]
            return price, dt_str
        return None, None
    except Exception as e:
        send_error_to_slack(e, context="get_nvda_current_price_and_datetime")
        return None, None


def compute_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """RSI 계산."""
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)
    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()
    rs = avg_gain / avg_loss.replace(0, 1e-10)
    return 100 - (100 / (1 + rs))


def get_nvda_ma_distance() -> Tuple[Optional[float], Optional[float], Optional[float], Optional[float], Optional[float]]:
    """
    NVDA 현재가, MA20, MA50, 20일 이격도(%), 50일 이격도(%).
    이격도 = (현재가 - MA) / MA * 100
    """
    df = get_nvda_history(60)
    if df is None or len(df) < 50:
        return None, None, None, None, None
    df["ma20"] = df["close"].rolling(20).mean()
    df["ma50"] = df["close"].rolling(50).mean()
    row = df.iloc[-1]
    close = float(row["close"])
    ma20 = float(row["ma20"])
    ma50 = float(row["ma50"])
    dist20 = (close - ma20) / ma20 * 100 if ma20 else None
    dist50 = (close - ma50) / ma50 * 100 if ma50 else None
    return close, ma20, ma50, dist20, dist50


def get_nvda_rsi(period: int = 14) -> Optional[float]:
    """NVDA 최근 RSI."""
    df = get_nvda_history(60)
    if df is None or len(df) < period + 1:
        return None
    rsi = compute_rsi(df["close"], period)
    return float(rsi.iloc[-1]) if pd.notna(rsi.iloc[-1]) else None


def get_nvda_support_resistance(days: int = 20) -> Tuple[Optional[float], Optional[float]]:
    """최근 days일 고가/저가 중 주요 지지(저가 상위), 저항(고가 하위). 단순화: 최근 고점/저점."""
    df = get_nvda_history(max(days + 5, 30))
    if df is None or len(df) < days:
        return None, None
    recent = df.tail(days)
    return float(recent["low"].min()), float(recent["high"].max())
