# -*- coding: utf-8 -*-
"""
QuantLabs Phase 2 - Real Estate Intelligence
호갱노노 스타일 UI · 퀀트 관점 입지·가격 분석
"""
import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules.real_estate import (
    fetch_apt_trades,
    fetch_apt_rents,
    get_infrastructure_data,
    get_supply_data,
    render_naver_map,
    find_undervalued_complexes,
)
from modules.real_estate import aggregate_by_complex

st.set_page_config(page_title="Phase 2 RealEstate | QuantLabs", page_icon="🏠", layout="wide")

st.title("🏠 Phase 2: Real Estate Intelligence")
st.caption("호갱노노 스타일 · 퀀트 관점 입지·가격 분석")

# ---- 지역·필터 설정 ----
LAWD_OPTIONS = {
    "11110": "서울 종로구",
    "11140": "서울 중구",
    "11215": "서울 광진구",
    "11680": "서울 강남구",
    "41135": "경기 성남시",
    "41190": "경기 용인시",
}

with st.expander("⚙️ 지역·필터", expanded=True):
    col1, col2, col3 = st.columns(3)
    with col1:
        lawd_key = st.selectbox(
            "지역",
            options=list(LAWD_OPTIONS.keys()),
            format_func=lambda x: LAWD_OPTIONS[x],
        )
    with col2:
        deal_ymd = st.text_input("계약년월 (YYYYMM)", value="", placeholder="비워두면 최근월")
    with col3:
        price_min = st.number_input("최저가 (만원)", min_value=0, value=0, step=100)
        price_max = st.number_input("최고가 (만원)", min_value=0, value=0, step=100, key="pmax")

tab1, tab2 = st.tabs(["📍 입지 분석 (Location)", "📊 가격 분석 (Price)"])

# ---- Tab 1: 입지 분석 ----
with tab1:
    st.subheader("지도 기반 아파트 실거래가")
    if st.button("📍 데이터 로드 & 지도 갱신"):
        with st.spinner("실거래가 조회 중..."):
            df_trade = fetch_apt_trades(lawd_key, deal_ymd or None)
            agg = aggregate_by_complex(df_trade)

            # 가격 필터
            if price_min > 0:
                agg = agg[agg["평균가격"] >= price_min * 10000]
            if price_max > 0:
                agg = agg[agg["평균가격"] <= price_max * 10000]

            st.session_state["re_agg"] = agg
            st.session_state["re_trades"] = df_trade
        st.success(f"총 {len(agg)}개 단지 로드됨")

    if "re_agg" in st.session_state:
        agg = st.session_state["re_agg"]
        infra_col1, infra_col2, infra_col3, _ = st.columns(4)
        with infra_col1:
            show_subway = st.checkbox("🚇 지하철", value=True, key="s1")
        with infra_col2:
            show_school = st.checkbox("🏫 학교", value=False, key="s2")
        with infra_col3:
            show_ic = st.checkbox("🛣️ IC", value=False, key="s3")

        markers = []
        for _, row in agg.iterrows():
            price_str = f"{row['평균가격']/10000:.0f}만원" if row.get("평균가격") else ""
            specs = f"건축 {int(row.get('건축년도',0))}년 · 거래 {int(row.get('거래건수',0))}건"
            markers.append({
                "lat": row["lat"],
                "lon": row["lon"],
                "name": row["아파트명"],
                "price": price_str,
                "specs": specs,
            })

        center_lat = agg["lat"].mean() if "lat" in agg.columns else 37.5
        center_lon = agg["lon"].mean() if "lon" in agg.columns else 127.0
        render_naver_map(
            markers,
            center_lat=center_lat,
            center_lon=center_lon,
            height=480,
            show_infra={"subway": show_subway, "school": show_school, "ic": show_ic},
        )

        st.subheader("단지별 요약")
        st.dataframe(
            agg[["아파트명", "평균가격", "거래건수", "건축년도"]].style.format({
                "평균가격": "{:,.0f}원",
                "거래건수": "{:,.0f}",
            }),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("위 [데이터 로드 & 지도 갱신] 버튼을 눌러 시작하세요.")

# ---- Tab 2: 가격 분석 ----
with tab2:
    st.subheader("퀀트 차트: 가격 시계열 & 거래량")
    if "re_trades" not in st.session_state:
        st.info("입지 분석 탭에서 먼저 데이터를 로드해 주세요.")
    else:
        df = st.session_state["re_trades"]
        if "가격" not in df.columns:
            df["가격"] = df.get("거래금액", pd.Series([0] * len(df)))
            if hasattr(df["가격"].iloc[0], "replace"):
                df["가격"] = df["가격"].astype(str).str.replace(",", "").str.replace(" ", "").apply(
                    lambda x: int(x) if str(x).isdigit() else 0
                )

        # 월별 집계 (시계열)
        if "년" in df.columns and "월" in df.columns:
            df["ym"] = df["년"].astype(str) + "-" + df["월"].astype(str).str.zfill(2)
        else:
            df["ym"] = "조회월"
        monthly = df.groupby("ym").agg({
            "가격": ["mean", "min", "max", "count"],
        }).reset_index()
        monthly.columns = ["ym", "평균가", "최저가", "최고가", "거래량"]

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=monthly["ym"],
            y=monthly["평균가"],
            mode="lines+markers",
            name="평균 매매가",
            line=dict(color="#3498db", width=2),
        ))
        fig.add_trace(go.Bar(
            x=monthly["ym"],
            y=monthly["거래량"],
            name="거래량",
            yaxis="y2",
            marker_color="rgba(149,165,166,0.5)",
        ))
        avg_vol = monthly["거래량"].mean()
        fig.add_hline(y=avg_vol, yref="y2", line_dash="dash", opacity=0.5)
        fig.update_layout(
            title="매매가 추이 & 거래량 (평균선 대비)",
            xaxis_title="계약월",
            yaxis=dict(title="가격(원)"),
            yaxis2=dict(title="거래량", overlaying="y", side="right"),
            height=400,
            legend=dict(orientation="h", y=1.1),
        )
        st.plotly_chart(fig, use_container_width=True)

        st.subheader("수급 지표: 입주 예정 물량 (향후 2~3년)")
        region_name = LAWD_OPTIONS.get(lawd_key, lawd_key)
        supply_df = get_supply_data(region_name)
        st.dataframe(supply_df, use_container_width=True, hide_index=True)

        st.subheader("대장 아파트 대비 상대 가치")
        if "re_agg" in st.session_state:
            agg2 = st.session_state["re_agg"].copy()
            top3 = agg2.nlargest(3, "거래건수")
            champ_avg = top3["평균가격"].mean() if len(top3) > 0 else 0
            agg2["대장대비"] = ((agg2["평균가격"] - champ_avg) / champ_avg * 100).round(1) if champ_avg else 0
            st.caption("대장 = 거래건수 상위 3개 단지 평균. 음수 = 대장보다 저렴")
            st.dataframe(
                agg2[["아파트명", "평균가격", "거래건수", "대장대비"]].head(15).style.format({
                    "평균가격": "{:,.0f}원",
                    "대장대비": "{:+.1f}%",
                }),
                use_container_width=True,
                hide_index=True,
            )

        st.subheader("저평가 단지 (입지↑ 가격↓)")
        if "re_agg" in st.session_state:
            agg = st.session_state["re_agg"]
            infra_df = pd.DataFrame()
            undervalued = find_undervalued_complexes(agg, infra_df)
            st.dataframe(
                undervalued[["아파트명", "평균가격", "거래건수", "입지점수", "저평가점수"]].head(10).style.format({
                    "평균가격": "{:,.0f}원",
                    "입지점수": "{:.1f}",
                    "저평가점수": "{:.1f}",
                }),
                use_container_width=True,
                hide_index=True,
            )

st.caption("QuantLabs — Real Estate Intelligence · MOLIT API · 네이버 지도")
