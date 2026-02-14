"""
QuantLabs - Phase 1: 금융 자산 (미장/ISA/비트코인)
비트코인 로직: 현재가, 지표, 슬랙 상태, 전략 선택, 백테스트.
"""
import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# 프로젝트 루트를 path에 추가
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules.data_fetcher import get_btc_price, get_btc_ohlc
from modules.slack_notifier import SLACK_WEBHOOK_URL, send_error_to_slack
from modules.upbit_fetcher import (
    load_btc_daily,
    update_btc_daily_csv,
    get_btc_krw_price,
)
from modules.vbs_backtest import get_best_k, get_today_target_and_remaining
from modules.nvda_fetcher import (
    get_nvda_history,
    get_nvda_current_price,
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
    valuation_vs_volatility,
)

st.set_page_config(page_title="Phase 1 Finance | QuantLabs", page_icon="📈", layout="wide")


def render_nvda_section():
    """미장 직투: NVDA Alpha-V1 전문가용 대시보드 — 수익곡선 겹침, 매수점수 게이지, 최적화 Status."""
    st.subheader("📈 엔비디아 (NVDA) Alpha-V1 전문가용 대시보드")

    df_full = build_indicator_df(365)
    if df_full is None or len(df_full) < 60:
        st.warning("NVDA 1년 데이터를 불러올 수 없습니다.")
        return

    params, metrics = load_golden_params()
    opt_status = st.empty()
    if not metrics:
        opt_status.info("🔄 최적화 미실행. 아래 [Golden Parameter 최적화 실행] 버튼을 눌러 50회 시뮬레이션을 실행하세요.")
    else:
        opt_status.success(f"✅ 최적화 완료. 수익률 {metrics.get('return', 0):.1%} / MDD {metrics.get('mdd', 0):.1%} / Sharpe {metrics.get('sharpe', 0):.2f}")

    if st.button("Golden Parameter 최적화 실행 (최대 50회 시뮬레이션)"):
        status_opt = st.empty()
        status_opt.warning("최적화 중... (50회 시뮬레이션)")
        best_p, best_ret, best_mdd, best_sharpe = optimize_golden_params(
            df_full, target_return=0.30, target_mdd=0.15, max_iter=50
        )
        save_golden_params(best_p, {"return": best_ret, "mdd": best_mdd, "sharpe": best_sharpe})
        status_opt.success("최적화 완료. Golden Parameter 저장됨.")
        st.rerun()

    p = params
    ret, mdd, sharpe, equity = run_backtest(
        df_full,
        score_threshold=p.get("score_threshold", 55),
        w_ma=p.get("w_ma", 0.35), w_rsi=p.get("w_rsi", 0.35), w_atr=p.get("w_atr", 0.30),
        rsi_ob=p.get("rsi_ob", 70), rsi_rel=p.get("rsi_rel", 65), atr_k=p.get("atr_k", 0.5),
    )

    # 현재 매수 점수 게이지
    score = get_current_buy_score(
        df_full,
        w_ma=p.get("w_ma", 0.35), w_rsi=p.get("w_rsi", 0.35), w_atr=p.get("w_atr", 0.30),
        rsi_ob=p.get("rsi_ob", 70), rsi_rel=p.get("rsi_rel", 65), atr_k=p.get("atr_k", 0.5),
    )
    col_ga, col_met = st.columns(2)
    with col_ga:
        fig_gauge = go.Figure(go.Indicator(
            mode="gauge+number",
            value=score,
            number={"suffix": " 점"},
            title={"text": "현재 매수 점수 (Buy Score)"},
            gauge={"axis": {"range": [0, 100]}, "bar": {"color": "#76b900"},
                   "threshold": {"line": {"color": "red", "width": 4}, "value": p.get("score_threshold", 55)}},
        ))
        fig_gauge.update_layout(height=260, margin=dict(l=20, r=20))
        st.plotly_chart(fig_gauge, use_container_width=True)
    with col_met:
        price = get_nvda_current_price()
        if price is not None:
            st.metric("NVDA 현재가", f"${price:,.2f}")
        st.metric("백테스트 수익률(1년)", f"{ret:.1%}")
        st.metric("MDD", f"{mdd:.1%}")
        st.metric("Sharpe", f"{sharpe:.2f}")

    # 현재가 차트 위에 백테스트 수익률 곡선 겹침 (보조 Y축)
    common_idx = equity.dropna().index.intersection(df_full.index)
    if len(common_idx) > 0:
        price_norm = df_full.loc[common_idx, "close"] / df_full.loc[common_idx, "close"].iloc[0]
        eq_norm = equity.reindex(common_idx).ffill().fillna(1)
        fig_overlay = go.Figure()
        fig_overlay.add_trace(go.Scatter(x=common_idx, y=df_full.loc[common_idx, "close"], mode="lines", name="주가", line=dict(color="#76b900")))
        fig_overlay.add_trace(go.Scatter(x=common_idx, y=eq_norm * df_full.loc[common_idx, "close"].iloc[0], mode="lines", name="전략 수익 곡선", line=dict(color="#2196F3", dash="dash")))
        fig_overlay.update_layout(title="주가 vs Alpha-V1 전략 수익 곡선", height=380, template="plotly_white", legend=dict(orientation="h"))
        st.plotly_chart(fig_overlay, use_container_width=True)

    # 기존: 5일 거래량, RSI, 지지/저항
    st.markdown("---")
    st.markdown("**최근 5일 거래량 / RSI / 지지·저항**")
    vol = df_full.tail(5)[["volume"]].copy()
    vol.index = vol.index.strftime("%m/%d")
    fig_vol = go.Figure(go.Bar(x=vol.index, y=vol["volume"], name="거래량", marker_color="#76b900"))
    fig_vol.update_layout(height=220, template="plotly_white", margin=dict(t=10, b=30))
    st.plotly_chart(fig_vol, use_container_width=True)

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
    fig_sr.update_layout(title="가격 + 지지/저항선", height=320, template="plotly_white")
    st.plotly_chart(fig_sr, use_container_width=True)


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
    )
    st.plotly_chart(fig, use_container_width=True)
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
    fig.update_layout(height=280, margin=dict(l=20, r=20))
    st.plotly_chart(fig, use_container_width=True)


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
        slack_ok = bool(SLACK_WEBHOOK_URL)
        st.metric("슬랙 연동", "✅ 설정됨" if slack_ok else "❌ 미설정")
        if not slack_ok:
            st.caption(".env에 SLACK_WEBHOOK_URL을 설정하세요.")

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
            )
            st.plotly_chart(fig_bt, use_container_width=True)
            total_ret = cum.iloc[-1] - 1 if len(cum) else 0
            st.metric("백테스트 누적 수익률", f"{total_ret:.2%}")
            with st.expander("백테스트 결과 테이블"):
                st.dataframe(result.tail(20).round(4), use_container_width=True)
        else:
            st.warning("데이터 부족으로 백테스트를 수행할 수 없습니다.")
    else:
        st.warning("가격 데이터를 먼저 불러온 후 백테스트를 실행할 수 있습니다.")


def main():
    st.title("📈 Phase 1: 금융 자산")
    tab1, tab2, tab3 = st.tabs(["미장 직투", "ISA 지수추종", "비트코인"])

    with tab1:
        render_mijang_tab()
    with tab2:
        render_isa_tab()
    with tab3:
        render_btc_tab()


if __name__ == "__main__":
    main()
