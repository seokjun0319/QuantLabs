"""
QuantLabs - 대문 (Entry Point)
Data-Driven Wealth: 목적과 전략을 한눈에.
"""
import streamlit as st

st.set_page_config(
    page_title="QuantLabs",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---- Header ----
st.title("🚀 QuantLabs: Data-Driven Wealth")
st.markdown("---")

# ---- Mission Statement (3단계) ----
st.subheader("📌 Mission")
col1, col2, col3 = st.columns(3)

with col1:
    with st.container():
        st.markdown("#### Level 1: 금융 자산 최적화")
        st.markdown("""
        - 미장 직투
        - ISA 지수추종
        - 비트코인 자산배분
        """)
        st.caption("현재 집중 구간")

with col2:
    with st.container():
        st.markdown("#### Level 2: 부동산 가치 분석")
        st.markdown("""
        - 전국 입지 분석
        - 데이터 기반 가격 타이밍
        """)
        st.caption("Phase 2 예정")

with col3:
    with st.container():
        st.markdown("#### Level 3: 완전 자동화")
        st.markdown("""
        - 실시간 종목 추천
        - 로보어드바이저 매매
        """)
        st.caption("Phase 3 예정")

st.markdown("---")
st.subheader("📊 Core Strategy (퀀트 전략)")

# ---- 전략 카드 (Expander) ----
strategies = [
    ("추세추종", "Trend Following", "가격 추세가 지속된다고 보며, 상승 추세에서는 Long, 하락 추세에서는 Short 또는 현금 보유."),
    ("평균회귀", "Mean Reversion", "가격이 일정 구간 평균으로 돌아온다고 보고, 극단적 이탈 시 반대 방향 포지션."),
    ("모멘텀", "Momentum", "최근 수익률이 좋은 자산이 계속 좋을 것이라는 관점. 강한 모멘텀 구간에 동행."),
    ("가치투자", "Value Investing", "실적·재무 지표 기반 저평가 종목 발굴. PER, PBR, 배당률 등으로 밸류에이션."),
    ("차익거래", "Arbitrage", "동일 자산의 가격 차이(시장/거래소 간)를 이용한 무위험(또는 저위험) 수익 추구."),
]

for name_ko, name_en, desc in strategies:
    with st.expander(f"**{name_ko}** ({name_en})"):
        st.write(desc)

st.markdown("---")
st.info("왼쪽 사이드바에서 **Phase 1 Finance**, **Phase 2 RealEstate**, **Phase 3 AutoTrade** 페이지로 이동할 수 있습니다.")
