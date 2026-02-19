# -*- coding: utf-8 -*-
"""
Quantlab Strategic Operation Board — 미장/국장 공격수·방어군 종목 트래킹 대시보드.
Tab: US Attackers, US ETF Defenders, KR Attackers, KR ETF Defenders.
"""
import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules.tracking_dashboard import (
    US_ATTACKERS,
    US_ETF_DEFENDERS,
    KR_ATTACKERS,
    KR_ETF_DEFENDERS,
    fetch_ticker_ohlc,
    fetch_tickers_batch,
    get_quote_metrics,
    build_candlestick_trace,
    build_cumreturn_chart,
    build_allocation_bars,
    get_kr_ticker_list,
    get_kr_etf_ticker_list,
)

st.set_page_config(page_title="Strategic Board | Quantlab", page_icon="📊", layout="wide")

# ----- API 호출 최적화: 1시간 캐시 -----
@st.cache_data(ttl=3600)
def cached_fetch_tickers(tickers: tuple, days: int = 400):
    """티커 리스트를 튜플로 받아 캐시 키로 사용, 조회 결과 반환."""
    return fetch_tickers_batch(list(tickers), days)


@st.cache_data(ttl=3600)
def cached_fetch_single(ticker: str, days: int = 400):
    """단일 티커 캐시 조회."""
    return fetch_ticker_ohlc(ticker, days)


# ----- 상단 타이틀 -----
st.title("**Quantlab Strategic Operation Board**")
st.markdown("미장(US) 및 국장(KR) 공격수/방어군 종목 실시간 트래킹")
st.markdown("---")

tab1, tab2, tab3, tab4 = st.tabs([
    "🇺🇸 US Attackers (미장 공격수)",
    "🇺🇸 US ETF Defenders (미장 방어군)",
    "🇰🇷 KR Attackers (국장 공격수)",
    "🇰🇷 KR ETF Defenders (국장 방어군)",
])


def render_us_attackers():
    """Tab 1: AI&Semi, Space&Tech, Bio&Energy 카테고리별 현재가/등락률/52주위치/캔들차트."""
    category = st.selectbox(
        "카테고리 선택",
        list(US_ATTACKERS.keys()),
        key="us_attack_cat",
    )
    tickers = US_ATTACKERS[category]
    data = cached_fetch_tickers(tuple(tickers))
    if not data:
        st.info("데이터 준비 중입니다. 잠시 후 새로고침 해 주세요.")
        return
    # 각 종목별 메트릭 + 캔들
    cols = st.columns(len(tickers))
    for i, ticker in enumerate(tickers):
        with cols[i] if i < len(cols) else st.container():
            df = data.get(ticker)
            if df is None:
                st.caption(f"{ticker}: 데이터 준비 중")
                continue
            m = get_quote_metrics(df)
            st.subheader(ticker)
            st.metric("현재가", f"${m.get('current_price', 0):,.2f}", f"{m.get('change_pct', 0):+.2f}%")
            st.caption(f"52주 고가 대비 {m.get('pos_52w_pct', 0):.1f}%")
            trace = build_candlestick_trace(df, ticker)
            if trace:
                fig = go.Figure(trace)
                fig.update_layout(height=260, template="plotly_white", xaxis_rangeslider_visible=False)
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.caption("차트 데이터 준비 중")


def render_us_etf_defenders():
    """Tab 2: QQQ, SPY, SCHD, TLT, GLD — 비중 시뮬레이션 및 수익률 비교 차트."""
    tickers = US_ETF_DEFENDERS
    data = cached_fetch_tickers(tuple(tickers))
    if not data:
        st.info("데이터 준비 중입니다. 잠시 후 새로고침 해 주세요.")
        return
    # 자산군별 비중 시뮬레이션 (동일 비중 20% 가정)
    st.subheader("자산군별 비중 현황 시뮬레이션 (동일 비중)")
    weights = [1.0 / len(tickers)] * len(tickers)
    fig_alloc = build_allocation_bars(tickers, weights, "ETF 비중 (예: 동일 20%)")
    st.plotly_chart(fig_alloc, use_container_width=True)
    # 수익률 비교 차트
    st.subheader("누적 수익률 비교")
    fig_cum = build_cumreturn_chart(data, "ETF 누적 수익률")
    st.plotly_chart(fig_cum, use_container_width=True)
    # 요약 테이블
    rows = []
    for t in tickers:
        df = data.get(t)
        if df is None:
            rows.append({"ETF": t, "현재가": "—", "전일대비": "—", "52주대비": "—"})
            continue
        m = get_quote_metrics(df)
        rows.append({
            "ETF": t,
            "현재가": f"${m.get('current_price', 0):,.2f}",
            "전일대비": f"{m.get('change_pct', 0):+.2f}%",
            "52주대비": f"{m.get('pos_52w_pct', 0):.1f}%",
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def render_kr_attackers():
    """Tab 3: 국장 공격수 — 현재가, 등락률. 외인/기관 수급은 데이터 소스 한계로 생략."""
    ticker_tuples = KR_ATTACKERS
    tickers = [t[0] for t in ticker_tuples]
    data = cached_fetch_tickers(tuple(tickers))
    if not data:
        st.info("데이터 준비 중입니다. 잠시 후 새로고침 해 주세요.")
        return
    name_by_ticker = {t[0]: t[1] for t in ticker_tuples}
    rows = []
    for ticker, name in ticker_tuples:
        df = data.get(ticker)
        if df is None:
            rows.append({"종목": name, "티커": ticker, "현재가": "데이터 준비 중", "전일대비": "—"})
            continue
        m = get_quote_metrics(df)
        rows.append({
            "종목": name,
            "티커": ticker,
            "현재가": f"{m.get('current_price', 0):,.0f}",
            "전일대비": f"{m.get('change_pct', 0):+.2f}%",
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    st.caption("외인/기관 수급 동향은 별도 데이터 소스 연동 시 제공 예정입니다.")


def render_kr_etf_defenders():
    """Tab 4: 국장 방어군 ETF — 현재가, 등락률."""
    ticker_tuples = KR_ETF_DEFENDERS
    tickers = [t[0] for t in ticker_tuples]
    data = cached_fetch_tickers(tuple(tickers))
    if not data:
        st.info("데이터 준비 중입니다. 잠시 후 새로고침 해 주세요.")
        return
    rows = []
    for ticker, name in ticker_tuples:
        df = data.get(ticker)
        if df is None:
            rows.append({"ETF": name, "티커": ticker, "현재가": "데이터 준비 중", "전일대비": "—"})
            continue
        m = get_quote_metrics(df)
        rows.append({
            "ETF": name,
            "티커": ticker,
            "현재가": f"{m.get('current_price', 0):,.0f}",
            "전일대비": f"{m.get('change_pct', 0):+.2f}%",
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


with tab1:
    render_us_attackers()
with tab2:
    render_us_etf_defenders()
with tab3:
    render_kr_attackers()
with tab4:
    render_kr_etf_defenders()
