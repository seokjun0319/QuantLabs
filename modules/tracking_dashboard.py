# -*- coding: utf-8 -*-
"""
Quantlab 종목 트래킹 대시보드 — 미장/국장 공격수·방어군 실시간 모니터링.
yfinance 기반, plotly 시각화. 캐싱은 호출측(st.cache_data)에서 수행.
"""
from __future__ import annotations

from typing import Any, Optional

import pandas as pd

# ----- 티커 정의 (지시서 기준) -----

# Tab 1: 미장 공격수 — 카테고리별
US_ATTACKERS = {
    "AI & Semi": ["NVDA", "AVGO", "MSFT"],
    "Space & Tech": ["RKLB", "PLTR", "TSLA"],
    "Bio & Energy": ["LLY", "VRT", "CEG"],
}

# Tab 2: 미장 방어군 ETF
US_ETF_DEFENDERS = ["QQQ", "SPY", "SCHD", "TLT", "GLD"]

# Tab 3: 국장 공격수 (yfinance: .KS)
KR_ATTACKERS = [
    ("005930.KS", "삼성전자"),
    ("000660.KS", "SK하이닉스"),
    ("012450.KS", "한화에어로스페이스"),
    ("373220.KS", "LG에너지솔루션"),
    ("207940.KS", "삼성바이오로직스"),
]

# Tab 4: 국장 방어군 ETF
KR_ETF_DEFENDERS = [
    ("069500.KS", "KODEX 200"),
    ("360750.KS", "TIGER 미국S&P500"),
    ("252650.KS", "KODEX 배당성장"),
    ("252670.KS", "KODEX 200선물인버스2X"),
]


def fetch_ticker_ohlc(ticker: str, days: int = 400) -> Optional[pd.DataFrame]:
    """
    단일 티커 OHLCV 조회. 실패 시 None.
    52주 고가 계산을 위해 약 400일 수집.
    """
    try:
        import yfinance as yf
        df = yf.download(
            ticker, period=f"{days}d", interval="1d",
            progress=False, auto_adjust=True, threads=False,
        )
        if df is None or df.empty or len(df) < 2:
            return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [c[0].lower() if isinstance(c, tuple) else str(c).lower() for c in df.columns]
        else:
            df.columns = [str(c).lower() for c in df.columns]
        for c in ["open", "high", "low", "close"]:
            if c not in df.columns:
                return None
        return df[["open", "high", "low", "close"]].sort_index()
    except Exception:
        return None


def fetch_tickers_batch(tickers: list[str], days: int = 400) -> dict[str, pd.DataFrame]:
    """여러 티커 일괄 조회. 반환: { ticker: DataFrame }."""
    out: dict[str, pd.DataFrame] = {}
    for t in tickers:
        df = fetch_ticker_ohlc(t, days)
        if df is not None:
            out[t] = df
    return out


def get_quote_metrics(df: pd.DataFrame) -> dict[str, Any]:
    """
    현재가, 전일대비 등락률, 52주 신고가 대비 위치(0~1) 계산.
    """
    if df is None or len(df) < 2:
        return {}
    close = df["close"]
    current = float(close.iloc[-1])
    prev = float(close.iloc[-2])
    chg_pct = (current - prev) / prev * 100.0 if prev else 0.0
    high_52 = close.rolling(min(252, len(close))).max()
    high52 = float(high_52.iloc[-1]) if len(high_52.dropna()) else current
    if high52 and high52 > 0:
        pos_52 = (current / high52) * 100.0  # 52주 고가 대비 % (100 = 고가)
    else:
        pos_52 = 100.0
    return {
        "current_price": current,
        "change_pct": chg_pct,
        "pos_52w_pct": pos_52,
        "high_52w": high52,
    }


def get_kr_ticker_list() -> list[str]:
    """국장 공격수 티커만 리스트 (튜플에서)."""
    return [t[0] for t in KR_ATTACKERS]


def get_kr_etf_ticker_list() -> list[str]:
    """국장 방어군 ETF 티커 리스트."""
    return [t[0] for t in KR_ETF_DEFENDERS]


def build_candlestick_trace(df: pd.DataFrame, name: str):
    """Plotly 캔들 trace 생성. 인덱스는 날짜."""
    if df is None or len(df) < 2:
        return None
    try:
        import plotly.graph_objects as go
        last_60 = df.tail(60)
        return go.Candlestick(
            x=last_60.index,
            open=last_60["open"],
            high=last_60["high"],
            low=last_60["low"],
            close=last_60["close"],
            name=name,
        )
    except Exception:
        return None


def build_cumreturn_chart(data: dict[str, pd.DataFrame], title: str):
    """
    티커별 누적 수익률(1부터 시작) 시계열. plotly Figure 반환.
    """
    import plotly.graph_objects as go
    try:
        fig = go.Figure()
        for ticker, df in data.items():
            if df is None or len(df) < 2:
                continue
            close = df["close"]
            cum = (close / close.iloc[0])
            fig.add_trace(go.Scatter(x=cum.index, y=cum.values, mode="lines", name=ticker))
        fig.update_layout(
            title=title,
            template="plotly_white",
            height=360,
            legend=dict(orientation="h"),
            xaxis_title="날짜",
            yaxis_title="누적 수익률",
        )
        return fig
    except Exception:
        return go.Figure()


def build_allocation_bars(labels: list[str], values: list[float], title: str):
    """자산군별 비중 막대 차트. values는 비중(0~1 합 1)."""
    import plotly.graph_objects as go
    try:
        fig = go.Figure(go.Bar(x=labels, y=[v * 100 for v in values], text=[f"{v*100:.1f}%" for v in values], textposition="auto"))
        fig.update_layout(title=title, template="plotly_white", height=280, yaxis_title="비중(%)")
        return fig
    except Exception:
        return go.Figure()
