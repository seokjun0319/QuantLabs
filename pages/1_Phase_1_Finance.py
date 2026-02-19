"""
QuantLabs - Phase 1: 금융 자산 (미장/ISA/비트코인)
비트코인 로직: 현재가, 지표, 슬랙 상태, 전략 선택, 백테스트.
Optimization History DB + Load Model (Rollback) 지원.
"""
import json
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# 프로젝트 루트를 path에 추가
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules.data_fetcher import get_btc_price, get_btc_ohlc
from modules.slack_notifier import get_slack_webhook_url, send_error_to_slack
from modules.upbit_fetcher import (
    load_btc_daily,
    update_btc_daily_csv,
    get_btc_krw_price,
)
from modules.vbs_backtest import get_best_k, get_today_target_and_remaining
from modules.nvda_fetcher import (
    get_nvda_history,
    get_nvda_current_price,
    get_nvda_current_price_and_datetime,
    get_nvda_ma_distance,
    get_nvda_rsi,
    get_nvda_support_resistance,
    compute_rsi,
)
from modules.nvda_engine import (
    build_indicator_df,
    load_golden_params,
    save_golden_params,
    run_backtest,
    optimize_golden_params,
    get_current_buy_score,
    get_current_buy_score_breakdown,
    get_current_sell_score,
    valuation_vs_volatility,
)
from modules.nvda_news import get_nvda_rss_news, add_korean_to_news
from modules.strategy_simulator import (
    fetch_ohlc,
    fetch_main_and_benchmark,
    STRATEGY_CLASSES,
    META_STRATEGY_CLASSES,
    ALL_STRATEGY_CLASSES,
    run_buy_and_hold,
    TrendFollowingStrategy,
    MeanReversionStrategy,
    MomentumStrategy,
    ValueStrategy,
    ArbitrageStrategy,
    VolTargetingStrategy,
    DualMomentumStrategy,
    ADXFilterStrategy,
)
from modules.hunter_screener import (
    US_ATTACKERS_BY_THEME,
    US_ETF_BY_THEME,
    KR_ATTACKERS_BY_THEME,
    KR_ETF_BY_THEME,
    KR_TICKER_NAMES,
    fetch_tickers_ohlc,
    compute_screener_metrics,
)

st.set_page_config(page_title="Phase 1 Finance | QuantLabs", page_icon="📈", layout="wide")

# 종목 발굴기 데이터 1시간 캐싱
@st.cache_data(ttl=3600)
def get_cached_hunter_data(tickers: list, days: int = 250):
    return fetch_tickers_ohlc(tickers, days)

# 차트 공통: 마우스 드래그로 이동(패닝), 스크롤로 줌
PLOTLY_CONFIG = {"scrollZoom": True, "displayModeBar": True}


def _render_screener_table(data: dict, ticker_names: dict | None = None, price_fmt: str = "${:,.2f}"):
    """공통: 스크리너 메트릭 테이블 + RSI/Vol 스타일."""
    rows = compute_screener_metrics(data, ticker_names=ticker_names)
    if not rows:
        st.caption("데이터 준비 중입니다.")
        return
    df = pd.DataFrame(rows)
    def _rsi_style(s):
        return [
            "background-color: #d4edda; color: #0a0; font-weight: bold" if v <= 30
            else ("background-color: #f8d7da; color: #c00; font-weight: bold" if v >= 70 else "")
            for v in s
        ]
    def _vol_style(s):
        return ["font-weight: bold" if v >= 1.5 else "" for v in s]
    styled = df.style.apply(_rsi_style, subset=["RSI (14)"])
    styled = styled.apply(_vol_style, subset=["Vol (전일대비)"])
    styled = styled.format({
        "Current Price": price_fmt,
        "RSI (14)": "{:.1f}",
        "Vol (전일대비)": "{:.0%}",
    })
    st.dataframe(styled, use_container_width=True, hide_index=True)


def render_hunter_tab():
    """🔍 종목 발굴(Hunter): 미장(테마 탭 + ETF) / 국장(테마 탭 + ETF), 캐싱 적용."""
    st.subheader("🔍 종목 발굴 (Hunter)")
    st.caption("데이터는 1시간 캐시됩니다. 테마별 탭 전환 · 옆에 ETF 방어군.")

    # ----- 1행: 미장 공격수(테마 탭) | 미장 ETF 방어군 -----
    st.markdown("### 🇺🇸 미장")
    col_us_a, col_us_etf = st.columns(2)

    with col_us_a:
        st.markdown("#### 미장 공격수 (테마별)")
        theme_us = st.tabs(list(US_ATTACKERS_BY_THEME.keys()))
        for i, (theme_name, tickers) in enumerate(US_ATTACKERS_BY_THEME.items()):
            with theme_us[i]:
                data = get_cached_hunter_data(tuple(tickers))
                _render_screener_table(data, price_fmt="${:,.2f}")
        st.caption("🟢 RSI ≤ 30 과매도 | 🔴 RSI ≥ 70 과매수 | **Vol 150%+** 거래량 급증")

    with col_us_etf:
        st.markdown("#### 미장 ETF 방어군 (테마별)")
        etf_us_tabs = st.tabs(list(US_ETF_BY_THEME.keys()))
        for i, (theme_name, tickers) in enumerate(US_ETF_BY_THEME.items()):
            with etf_us_tabs[i]:
                data_etfs = get_cached_hunter_data(tuple(tickers))
                _render_screener_table(data_etfs, price_fmt="${:,.2f}")
        st.caption("지수·배당·채권·원자재·섹터 ETF")

    st.markdown("---")

    # ----- 2행: 국장 공격수(테마 탭) | 국장 ETF 방어군 -----
    st.markdown("### 🇰🇷 국장")
    col_kr_a, col_kr_etf = st.columns(2)

    with col_kr_a:
        st.markdown("#### 국장 공격수 (테마별)")
        theme_kr = st.tabs(list(KR_ATTACKERS_BY_THEME.keys()))
        for i, (theme_name, tickers) in enumerate(KR_ATTACKERS_BY_THEME.items()):
            with theme_kr[i]:
                data = get_cached_hunter_data(tuple(tickers))
                _render_screener_table(data, ticker_names=KR_TICKER_NAMES, price_fmt="{:,.0f}")
        st.caption("국장 종목: 원화 기준 가격")

    with col_kr_etf:
        st.markdown("#### 국장 ETF 방어군 (테마별)")
        etf_kr_tabs = st.tabs(list(KR_ETF_BY_THEME.keys()))
        for i, (theme_name, ticker_list) in enumerate(KR_ETF_BY_THEME.items()):
            with etf_kr_tabs[i]:
                kr_etf_tickers = [t[0] for t in ticker_list]
                kr_etf_names = {t[0]: t[1] for t in ticker_list}
                data_kr_etf = get_cached_hunter_data(tuple(kr_etf_tickers))
                _render_screener_table(data_kr_etf, ticker_names=kr_etf_names, price_fmt="{:,.0f}")
        st.caption("KODEX/TIGER 등 국내 ETF")

    with st.expander("📌 추천 신호 요약"):
        st.markdown("- **Buy the Dip (줍줍 기회)**: RSI < 35 이면서 가격 > 200일선")
        st.markdown("- **Overbought (과열 조심)**: RSI > 75")
        st.markdown("- **Hold / Wait**: 그 외")


def render_nvda_section():
    """미장 직투: NVDA Alpha-V1 전문가용 대시보드 — 수익곡선 겹침, 매수점수 게이지, 최적화 Status."""
    st.subheader("📈 엔비디아 (NVDA) Alpha-V1 전문가용 대시보드")

    df_full = build_indicator_df(365)
    if df_full is None or len(df_full) < 60:
        st.warning("NVDA 1년 데이터를 불러올 수 없습니다.")
        return

    params, metrics = load_golden_params()
    if st.button("Golden Parameter 최적화 실행 (최대 50회 시뮬레이션)"):
        status_opt = st.empty()
        status_opt.warning("최적화 중... (50회 시뮬레이션)")
        best_p, best_ret, best_mdd, best_sharpe = optimize_golden_params(
            df_full, target_return=0.30, target_mdd=0.15, max_iter=50
        )
        save_golden_params(best_p, {"return": best_ret, "mdd": best_mdd, "sharpe": best_sharpe})
        params, metrics = load_golden_params()  # 저장 직후 재로드 → 이번 화면에서 바로 새 점수/수익률 반영
        if str(ROOT / "scripts") not in sys.path:
            sys.path.insert(0, str(ROOT / "scripts"))
        try:
            from optimization_logger import append_log
            append_log(
                source="golden_param",
                params=best_p,
                result={
                    "returns": best_ret,
                    "mdd": best_mdd,
                    "annualized_return": best_ret,
                    "sharpe_ratio": best_sharpe,
                },
                iteration_count=50,
                target_ann_ret=0.30,
                target_mdd=0.15,
                strategy_summary="NVDA Alpha-V1. MA 정배열·RSI 과매수 해소·ATR 돌파 가중치, 매수점수 기준선 이상 시 1일 보유.",
            )
        except Exception:
            pass
        status_opt.success("최적화 완료. Golden Parameter 저장됨. 아래 수치가 갱신되었습니다. 히스토리 DB에 기록됨.")

    opt_status = st.empty()
    if not metrics:
        opt_status.info("🔄 최적화 미실행. 아래 [Golden Parameter 최적화 실행] 버튼을 눌러 50회 시뮬레이션을 실행하세요.")
    else:
        opt_status.success(f"✅ 최적화 완료. 수익률 {metrics.get('return', 0):.1%} / MDD {metrics.get('mdd', 0):.1%} / Sharpe {metrics.get('sharpe', 0):.2f}")

    p = params
    ret, mdd, sharpe, equity, extras = run_backtest(
        df_full,
        score_threshold=p.get("score_threshold", 55),
        w_ma=p.get("w_ma", 0.35), w_rsi=p.get("w_rsi", 0.35), w_atr=p.get("w_atr", 0.30),
        rsi_ob=p.get("rsi_ob", 70), rsi_rel=p.get("rsi_rel", 65), atr_k=p.get("atr_k", 0.5),
    )
    thresh = p.get("score_threshold", 55)
    score = get_current_buy_score(
        df_full,
        w_ma=p.get("w_ma", 0.35), w_rsi=p.get("w_rsi", 0.35), w_atr=p.get("w_atr", 0.30),
        rsi_ob=p.get("rsi_ob", 70), rsi_rel=p.get("rsi_rel", 65), atr_k=p.get("atr_k", 0.5),
    )
    breakdown = get_current_buy_score_breakdown(
        df_full,
        w_ma=p.get("w_ma", 0.35), w_rsi=p.get("w_rsi", 0.35), w_atr=p.get("w_atr", 0.30),
        rsi_ob=p.get("rsi_ob", 70), rsi_rel=p.get("rsi_rel", 65), atr_k=p.get("atr_k", 0.5),
    )
    sell_score = get_current_sell_score(
        df_full,
        w_ma=p.get("w_ma", 0.35), w_rsi=p.get("w_rsi", 0.35), w_atr=p.get("w_atr", 0.30),
        rsi_ob=p.get("rsi_ob", 70), rsi_rel=p.get("rsi_rel", 65), atr_k=p.get("atr_k", 0.5),
    )
    price, price_datetime = get_nvda_current_price_and_datetime()

    col_ga, col_met = st.columns(2)
    with col_ga:
        fig_gauge = go.Figure(go.Indicator(
            mode="gauge+number",
            value=score,
            number={"suffix": " 점"},
            title={"text": "현재 매수 점수 (Buy Score)"},
            gauge={"axis": {"range": [0, 100]}, "bar": {"color": "#76b900"},
                   "threshold": {"line": {"color": "red", "width": 4}, "value": thresh}},
        ))
        fig_gauge.update_layout(height=260, margin=dict(l=20, r=20), dragmode="pan")
        st.plotly_chart(fig_gauge, use_container_width=True, config=PLOTLY_CONFIG)
        st.caption(
            f"**집계 사유** · "
            f"MA 정배열: {breakdown.get('ma_contrib', 0):.0f}점 / "
            f"RSI 과매수 해소: {breakdown.get('rsi_contrib', 0):.0f}점 / "
            f"ATR 돌파: {breakdown.get('atr_contrib', 0):.0f}점 → "
            f"합계 {breakdown.get('total', 0):.0f}점"
        )
        st.info(f"**추천 구간**: {int(thresh)}점 이상일 때 매수 신호 (현재 {'✅ 추천' if score >= thresh else '⏸ 대기'})")

        fig_sell = go.Figure(go.Indicator(
            mode="gauge+number",
            value=sell_score,
            number={"suffix": " 점"},
            title={"text": "현재 매도 점수 (Sell Score)"},
            gauge={"axis": {"range": [0, 100]}, "bar": {"color": "#e65100"},
                   "threshold": {"line": {"color": "darkred", "width": 4}, "value": 60}},
        ))
        fig_sell.update_layout(height=260, margin=dict(l=20, r=20), dragmode="pan")
        st.plotly_chart(fig_sell, use_container_width=True, config=PLOTLY_CONFIG)
        st.caption("매도 점수: 역배열·RSI 과매수·하락 돌파 가중. 높을수록 매도 신호에 가깝습니다.")

    with col_met:
        if price is not None:
            st.metric("NVDA 현재가", f"${price:,.2f}")
            if price_datetime:
                st.caption(f"📅 시세 기준일시: {price_datetime}")
        st.metric("백테스트 수익률(1년)", f"{ret:.1%}")
        if extras.get("first_buy_date") is not None and extras.get("first_buy_price") is not None:
            fd = extras["first_buy_date"]
            fp = extras["first_buy_price"]
            fd_str = fd.strftime("%Y-%m-%d") if hasattr(fd, "strftime") else str(fd)[:10]
            st.caption(f"첫 진입일: {fd_str} · 구매단가(종가): ${fp:,.2f}")
        st.metric("MDD", f"{mdd:.1%}")
        if extras.get("mdd_date") is not None:
            md = extras["mdd_date"]
            md_str = md.strftime("%Y-%m-%d") if hasattr(md, "strftime") else str(md)[:10]
            st.caption(f"최대 낙폭 구간: {md_str} 기준")
        st.metric("Sharpe", f"{sharpe:.2f}")
        st.caption("**Sharpe**: 위험 대비 초과 수익. 1 이상이면 변동성 대비 수익이 양호, 2 이상이면 우수.")

    # 현재가 차트 위에 백테스트 수익률 곡선 겹침 (보조 Y축)
    common_idx = equity.dropna().index.intersection(df_full.index)
    if len(common_idx) > 0:
        price_norm = df_full.loc[common_idx, "close"] / df_full.loc[common_idx, "close"].iloc[0]
        eq_norm = equity.reindex(common_idx).ffill().fillna(1)
        fig_overlay = go.Figure()
        fig_overlay.add_trace(go.Scatter(x=common_idx, y=df_full.loc[common_idx, "close"], mode="lines", name="주가", line=dict(color="#76b900")))
        fig_overlay.add_trace(go.Scatter(x=common_idx, y=eq_norm * df_full.loc[common_idx, "close"].iloc[0], mode="lines", name="전략 수익 곡선", line=dict(color="#2196F3", dash="dash")))
        fig_overlay.update_layout(title="주가 vs Alpha-V1 전략 수익 곡선", height=380, template="plotly_white", legend=dict(orientation="h"), dragmode="pan")
        st.plotly_chart(fig_overlay, use_container_width=True, config=PLOTLY_CONFIG)

    # 기존: 5일 거래량, RSI, 지지/저항
    st.markdown("---")
    st.markdown("**최근 5일 거래량 / RSI / 지지·저항**")
    vol = df_full.tail(5)[["volume"]].copy()
    vol.index = vol.index.strftime("%m/%d")
    fig_vol = go.Figure(go.Bar(x=vol.index, y=vol["volume"], name="거래량", marker_color="#76b900"))
    fig_vol.update_layout(height=220, template="plotly_white", margin=dict(t=10, b=30), dragmode="pan")
    st.plotly_chart(fig_vol, use_container_width=True, config=PLOTLY_CONFIG)

    rsi_last = get_nvda_rsi(14)
    if rsi_last is not None:
        st.metric("RSI(14)", f"{rsi_last:.1f}")
    support, resistance = get_nvda_support_resistance(20)
    fig_sr = go.Figure()
    fig_sr.add_trace(go.Scatter(x=df_full.index, y=df_full["close"], mode="lines", name="종가", line=dict(color="#76b900")))
    if support is not None:
        fig_sr.add_hline(y=support, line_dash="dash", line_color="green", annotation_text="지지")
    if resistance is not None:
        fig_sr.add_hline(y=resistance, line_dash="dash", line_color="red", annotation_text="저항")
    fig_sr.update_layout(title="가격 + 지지/저항선", height=320, template="plotly_white", dragmode="pan")
    st.plotly_chart(fig_sr, use_container_width=True, config=PLOTLY_CONFIG)


def render_mijang_tab():
    """미장 직투 탭: NVDA 집중 분석."""
    render_nvda_section()


def render_isa_tab():
    """ISA 지수추종 탭 (플레이스홀더)."""
    st.info("ISA 지수추종 기능은 추후 연동됩니다. 여기에 ISA/지수추종 대시보드를 배치합니다.")


def render_btc_metrics(df: pd.DataFrame) -> None:
    """비트코인 주요 지표 시각화 (Plotly)."""
    if df is None or df.empty:
        st.warning("가격 데이터를 불러올 수 없습니다.")
        return
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df.index, y=df["price"], mode="lines", name="BTC/USD", line=dict(color="#F7931A")))
    fig.update_layout(
        title="BTC/USD 가격",
        xaxis_title="날짜",
        yaxis_title="USD",
        template="plotly_white",
        height=400,
        dragmode="pan",
    )
    st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)
    with st.expander("데이터 테이블"):
        st.dataframe(df.tail(30).round(2), use_container_width=True)


def run_backtest_trend_following(df: pd.DataFrame, window: int = 20) -> pd.DataFrame:
    """추세추종: 이동평균 골든크로스/데드크로스 기반 시그널."""
    if df is None or len(df) < window:
        return pd.DataFrame()
    d = df.copy()
    d["ma_short"] = d["price"].rolling(window=window // 2).mean()
    d["ma_long"] = d["price"].rolling(window=window).mean()
    d["signal"] = 0
    d.loc[d["ma_short"] > d["ma_long"], "signal"] = 1
    d.loc[d["ma_short"] < d["ma_long"], "signal"] = -1
    d["returns"] = d["price"].pct_change()
    d["strategy"] = d["signal"].shift(1) * d["returns"]
    d = d.dropna()
    return d


def run_backtest_mean_reversion(df: pd.DataFrame, window: int = 20, z_threshold: float = 2.0) -> pd.DataFrame:
    """평균회귀: Z-Score 기반 과매수/과매도 시그널."""
    if df is None or len(df) < window:
        return pd.DataFrame()
    d = df.copy()
    d["ma"] = d["price"].rolling(window=window).mean()
    d["std"] = d["price"].rolling(window=window).std()
    d["zscore"] = (d["price"] - d["ma"]) / d["std"].replace(0, 1e-8)
    d["signal"] = 0
    d.loc[d["zscore"] > z_threshold, "signal"] = -1
    d.loc[d["zscore"] < -z_threshold, "signal"] = 1
    d["returns"] = d["price"].pct_change()
    d["strategy"] = d["signal"].shift(1) * d["returns"]
    d = d.dropna()
    return d


def render_vbs_gauge(current_price: float, target_price: float) -> None:
    """현재가 vs 목표가 게이지 차트."""
    if target_price <= 0:
        return
    low = min(current_price, target_price) * 0.98
    high = max(current_price, target_price) * 1.05
    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=current_price,
            number={"suffix": " 원", "font": {"size": 24}},
            title={"text": "현재가 vs 목표가"},
            gauge={
                "axis": {"range": [low, high]},
                "bar": {"color": "#F7931A"},
                "steps": [{"range": [low, target_price], "color": "lightgray"}],
                "threshold": {
                    "line": {"color": "red", "width": 4},
                    "thickness": 0.8,
                    "value": target_price,
                },
            },
        )
    )
    fig.update_layout(height=280, margin=dict(l=20, r=20), dragmode="pan")
    st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)


def render_btc_tab():
    """비트코인 탭: 현재가, 지표 차트, 슬랙 상태, VBS, 전략 선택, 백테스트."""
    st.subheader("비트코인 자산배분")

    # 현재가 및 슬랙 상태
    col_price, col_slack = st.columns(2)
    with col_price:
        try:
            price = get_btc_price()
            if price is not None:
                st.metric("BTC 현재가 (USD)", f"${price:,.0f}")
            else:
                st.metric("BTC 현재가 (USD)", "—")
        except Exception as e:
            send_error_to_slack(e, context="get_btc_price in Phase1")
            st.error("현재가 조회 실패. 슬랙으로 에러 전송됨.")

    with col_slack:
        slack_ok = bool(get_slack_webhook_url())
        st.metric("슬랙 연동", "✅ 설정됨" if slack_ok else "❌ 미설정")
        if not slack_ok:
            st.caption("Streamlit Cloud: 앱 설정 → Secrets에 SLACK_WEBHOOK_URL 추가. 로컬: .env에 설정.")

    # ----- VBS 변동성 돌파 -----
    st.markdown("---")
    st.subheader("📊 VBS 변동성 돌파 (Upbit BTC/KRW)")
    df_krw = load_btc_daily()
    if df_krw is None or len(df_krw) < 5:
        if st.button("Upbit 30일 일봉 불러오기"):
            update_btc_daily_csv()
            st.rerun()
        st.caption("데이터 없음. 위 버튼으로 data/btc_daily.csv를 생성하세요.")
    else:
        best_k, k_df = get_best_k(df_krw, k_min=0.3, k_max=0.7, step=0.05)
        st.metric("추천 K값 (최근 30일 백테스트)", f"{best_k:.2f}")
        with st.expander("K별 수익률"):
            st.dataframe(k_df.round(4), use_container_width=True)

        current_krw = get_btc_krw_price()
        target, remaining_pct = get_today_target_and_remaining(df_krw, current_krw or 0, best_k)
        col_gauge, col_pct = st.columns(2)
        with col_gauge:
            if target is not None and current_krw:
                render_vbs_gauge(current_krw, target)
        with col_pct:
            if target is not None:
                st.metric("오늘 목표가 (돌파가)", f"{target:,.0f} 원")
                if remaining_pct is not None:
                    label = "변동성 돌파까지 남은 퍼센트"
                    if remaining_pct <= 0:
                        st.success(f"{label}: **돌파 완료** (현재가 ≥ 목표가)")
                    else:
                        st.metric(label, f"{remaining_pct:.2f}%")
        if st.button("일봉 데이터 새로고침"):
            update_btc_daily_csv()
            st.rerun()

    # 가격 데이터 로드 및 시각화
    st.markdown("---")
    days = st.slider("기간 (일)", 7, 90, 30)
    try:
        df_ohlc = get_btc_ohlc(days=days)
    except Exception as e:
        send_error_to_slack(e, context="get_btc_ohlc in Phase1")
        df_ohlc = None

    render_btc_metrics(df_ohlc)

    # 전략 선택 및 백테스트
    st.subheader("전략 선택 및 백테스트")
    strategy = st.radio("전략", ["추세추종", "평균회귀"], horizontal=True)

    if df_ohlc is not None and len(df_ohlc) >= 20:
        if strategy == "추세추종":
            window = st.slider("이동평균 기간", 5, 60, 20, key="tf_window")
            result = run_backtest_trend_following(df_ohlc, window=window)
        else:
            window = st.slider("Z-Score 기간", 5, 60, 20, key="mr_window")
            z = st.slider("Z-Score 임계값", 1.0, 3.0, 2.0, 0.1, key="mr_z")
            result = run_backtest_mean_reversion(df_ohlc, window=window, z_threshold=z)

        if not result.empty:
            cum = (1 + result["strategy"]).cumprod()
            fig_bt = go.Figure()
            fig_bt.add_trace(go.Scatter(x=cum.index, y=cum, mode="lines", name="전략 수익률"))
            fig_bt.update_layout(
                title=f"백테스트 누적 수익률 ({strategy})",
                xaxis_title="날짜",
                yaxis_title="누적 수익률",
                template="plotly_white",
                height=350,
                dragmode="pan",
            )
            st.plotly_chart(fig_bt, use_container_width=True, config=PLOTLY_CONFIG)
            total_ret = cum.iloc[-1] - 1 if len(cum) else 0
            st.metric("백테스트 누적 수익률", f"{total_ret:.2%}")
            with st.expander("백테스트 결과 테이블"):
                st.dataframe(result.tail(20).round(4), use_container_width=True)
        else:
            st.warning("데이터 부족으로 백테스트를 수행할 수 없습니다.")
    else:
        st.warning("가격 데이터를 먼저 불러온 후 백테스트를 실행할 수 있습니다.")


def render_nvda_news_clipping():
    """엔비디아 관련 뉴스 RSS 클리핑 5건 — 작고 심플, 제목 한글 해석·내용 한글 요약."""
    st.caption("📰 엔비디아 뉴스 클리핑")
    try:
        news = get_nvda_rss_news(limit=5)
        add_korean_to_news(news)
    except Exception:
        news = []
    if not news:
        st.caption("RSS 뉴스를 불러오지 못했습니다.")
        return
    for i, n in enumerate(news, 1):
        title = n.get("title", "") or ""
        link = n.get("link", "")
        title_kr = n.get("title_kr", "")
        summary_kr = n.get("summary_kr", "")
        snippet = n.get("snippet", "")
        date_str = n.get("date", "")[:10] if n.get("date") else ""
        with st.container():
            if link:
                st.markdown(f"<small>{i}. <a href=\"{link}\" target=\"_blank\">{title[:60]}{'…' if len(title) > 60 else ''}</a></small>", unsafe_allow_html=True)
            else:
                st.markdown(f"<small>{i}. {title[:60]}{'…' if len(title) > 60 else ''}</small>", unsafe_allow_html=True)
            if title_kr:
                st.caption(f"→ {title_kr}")
            if summary_kr and summary_kr != "-":
                st.caption(f"  {summary_kr}")
            elif not summary_kr and snippet:
                st.caption(f"  {snippet[:80]}{'…' if len(snippet) > 80 else ''}")
            if date_str:
                st.caption(f"  _{date_str}_")


def render_strategy_simulator():
    """전략 시뮬레이터: 기본 5종 + 메타 3종(VolTargeting, DualMomentum, ADXFilter) 선택 및 비교."""
    st.subheader("🎮 전략 시뮬레이터")
    col_ticker, col_days = st.columns([2, 1])
    with col_ticker:
        main_ticker = st.text_input("메인 티커", value="NVDA", key="sim_main_ticker")
        benchmark_ticker = st.text_input("벤치마크 티커 (차익거래/듀얼모멘텀용)", value="AMD", key="sim_bench_ticker")
    with col_days:
        days = st.slider("기간(일)", 60, 730, 365, key="sim_days")

    df_main, df_bench = fetch_main_and_benchmark(main_ticker, benchmark_ticker, days)
    if df_main is None or df_main.empty or len(df_main) < 30:
        st.warning(f"{main_ticker} 데이터를 불러올 수 없거나 기간이 짧습니다. 기간을 늘려 보세요.")
        return

    # DualMomentum은 벤치마크로 SPY 사용 (요구사항)
    df_spy = fetch_ohlc("SPY", days) if days >= 70 else pd.DataFrame()

    strategy_names = [s.display_name for s in ALL_STRATEGY_CLASSES]
    try:
        sel_idx = st.pills("전략 선택", strategy_names, key="sim_pills")
        selected_name = strategy_names[sel_idx] if isinstance(sel_idx, int) else sel_idx
    except Exception:
        selected_name = st.radio("전략 선택", strategy_names, horizontal=True, key="sim_radio")

    selected_cls = next((c for c in ALL_STRATEGY_CLASSES if c.display_name == selected_name), ALL_STRATEGY_CLASSES[0])
    selected_strategy = selected_cls()

    tab_detail, tab_compare = st.tabs(["선택 전략 상세", "모든 전략 비교"])

    with tab_detail:
        if selected_name == "차익거래 (스프레드)":
            res = selected_strategy.run(df_main, df_bench=df_bench)
        elif selected_name == "DualMomentum (듀얼 모멘텀)":
            res = selected_strategy.run(df_main, df_bench=df_spy) if df_spy is not None and len(df_spy) >= 70 else selected_strategy.run(df_main, df_bench=df_bench)
        else:
            res = selected_strategy.run(df_main)
        eq = res.get("equity_curve")
        if eq is not None and len(eq) > 0:
            common_idx = eq.dropna().index.intersection(df_main.index)
            if len(common_idx) > 0:
                price_norm = df_main.loc[common_idx, "close"] / df_main.loc[common_idx, "close"].iloc[0]
                eq_norm = eq.reindex(common_idx).ffill().fillna(1.0)
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=common_idx, y=df_main.loc[common_idx, "close"], mode="lines", name="주가", line=dict(color="#76b900")))
                fig.add_trace(go.Scatter(x=common_idx, y=(eq_norm * df_main.loc[common_idx, "close"].iloc[0]).values, mode="lines", name=f"{selected_name} 수익곡선", line=dict(color="#2196F3", dash="dash")))
                fig.update_layout(title=f"{selected_name} — 주가 vs 수익 곡선", height=400, template="plotly_white", legend=dict(orientation="h"), dragmode="pan")
                st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)
        st.metric("CAGR", f"{res.get('cagr', 0):.2%}")
        st.metric("MDD", f"{res.get('mdd', 0):.2%}")
        st.metric("Sharpe", f"{res.get('sharpe_ratio', 0):.2f}")

    with tab_compare:
        all_results = []
        colors = ["#2196F3", "#4CAF50", "#FF9800", "#9C27B0", "#F44336", "#607D8B", "#00BCD4", "#8BC34A"]
        fig_comp = go.Figure()
        bh = run_buy_and_hold(df_main)
        all_results.append({"전략": "B&H (단순보유)", "CAGR": bh.get("cagr", 0), "MDD": bh.get("mdd", 0), "Sharpe": bh.get("sharpe_ratio", 0)})
        eq_bh = bh.get("equity_curve")
        if eq_bh is not None and len(eq_bh) > 0:
            fig_comp.add_trace(go.Scatter(x=eq_bh.index, y=eq_bh.values, mode="lines", name="B&H (단순보유)", line=dict(color=colors[0])))
        for i, StrategyCls in enumerate(ALL_STRATEGY_CLASSES):
            s = StrategyCls()
            if s.display_name == "차익거래 (스프레드)":
                res = s.run(df_main, df_bench=df_bench)
            elif s.display_name == "DualMomentum (듀얼 모멘텀)":
                res = s.run(df_main, df_bench=df_spy) if df_spy is not None and len(df_spy) >= 70 else s.run(df_main, df_bench=df_bench)
            else:
                res = s.run(df_main)
            all_results.append({
                "전략": s.display_name,
                "CAGR": res.get("cagr", 0),
                "MDD": res.get("mdd", 0),
                "Sharpe": res.get("sharpe_ratio", 0),
            })
            eq = res.get("equity_curve")
            if eq is not None and len(eq) > 0:
                c = colors[(i + 1) % len(colors)]
                fig_comp.add_trace(go.Scatter(x=eq.index, y=eq.values, mode="lines", name=s.display_name, line=dict(color=c)))
        fig_comp.update_layout(title="모든 전략 수익률 비교", height=450, template="plotly_white", legend=dict(orientation="h"), dragmode="pan")
        st.plotly_chart(fig_comp, use_container_width=True, config=PLOTLY_CONFIG)
        df_comp = pd.DataFrame(all_results)
        df_comp["CAGR"] = df_comp["CAGR"].apply(lambda x: f"{x:.2%}")
        df_comp["MDD"] = df_comp["MDD"].apply(lambda x: f"{x:.2%}")
        df_comp["Sharpe"] = df_comp["Sharpe"].apply(lambda x: f"{x:.2f}")
        st.dataframe(df_comp, use_container_width=True, hide_index=True)


def render_optimization_history():
    """맨 하단: Optimization History Database + Load Model (Rollback) 초석."""
    st.subheader("📊 Optimization History Database")
    if str(ROOT / "scripts") not in sys.path:
        sys.path.insert(0, str(ROOT / "scripts"))
    try:
        from optimization_logger import read_log, COLUMNS_KR
        log_rows = read_log()
    except Exception:
        log_rows = []
        COLUMNS_KR = {}
    if not log_rows:
        st.info("최적화 로그가 없습니다. scripts/main.py 또는 scripts/evolve_nvda.py 실행 시 자동 기록됩니다.")
        return
    # 최신순, 한글 컬럼명, 수치 소수점 이하 2자리
    ordered = list(reversed(log_rows))
    df = pd.DataFrame(ordered)
    display_cols = [c for c in ["timestamp", "source", "strategy_summary", "returns", "mdd", "annualized_return", "sharpe_ratio", "iteration_count", "params_json"] if c in df.columns]
    df_display = df[display_cols].copy()
    for col in ["returns", "mdd", "annualized_return", "sharpe_ratio"]:
        if col not in df_display.columns:
            continue
        try:
            df_display[col] = pd.to_numeric(df_display[col], errors="coerce").apply(lambda x: f"{x:.2f}" if pd.notna(x) else "")
        except Exception:
            pass
    if COLUMNS_KR:
        df_display = df_display.rename(columns=COLUMNS_KR)
    st.dataframe(df_display, use_container_width=True, height=min(400, 80 * len(ordered) + 38))

    st.markdown("**모델 복구 (Rollback)** — 선택한 행의 파라미터를 현재 활성 전략(best_params.json)에 적용합니다.")
    options = [
        f"{r.get('timestamp','')} | {r.get('source','')} | {(r.get('strategy_summary') or '')[:50]}"
        for r in ordered
    ]
    sel = st.selectbox("복구할 행 선택", range(len(ordered)), format_func=lambda i: options[i], key="opt_hist_sel")
    if st.button("Load Model (선택 행을 현재 활성 전략으로 적용)", key="opt_hist_load"):
        row = ordered[sel]
        try:
            params = json.loads(row["params_json"])
            best_path = ROOT / "data" / "best_params.json"
            best_path.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                **params,
                "source": "rollback",
                "updated": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            }
            with open(best_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            st.success("현재 활성 전략에 적용되었습니다. main.py 다음 실행 시 이 파라미터가 사용됩니다.")
        except Exception as e:
            st.error(f"적용 실패: {e}")


def main():
    st.title("📈 Phase 1: 금융 자산")
    tab0, tab1, tab2, tab3, tab4 = st.tabs([
        "🔍 종목 발굴(Hunter)",
        "미장 직투",
        "ISA 지수추종",
        "비트코인",
        "전략 시뮬레이터",
    ])

    with tab0:
        render_hunter_tab()
    with tab1:
        render_mijang_tab()
    with tab2:
        render_isa_tab()
    with tab3:
        render_btc_tab()
    with tab4:
        render_strategy_simulator()

    st.markdown("---")
    render_nvda_news_clipping()
    st.markdown("---")
    render_optimization_history()


if __name__ == "__main__":
    main()
