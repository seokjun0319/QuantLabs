# -*- coding: utf-8 -*-
"""
Quant-based Coupang Item Scouter — 쿠팡 파트너스 수익 극대화용 급상승 아이템 발굴.
"""
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules.item_scouter import (
    fetch_rising_keywords,
    search_coupang_products,
    score_products,
    generate_hooking_point,
    create_partner_link,
)

st.set_page_config(page_title="아이템 스카우터 | QuantLabs", page_icon="🔍", layout="wide")

st.title("🔍 아이템 스카우터")
st.caption("쿠팡 파트너스 급상승 아이템 발굴 · 생활/건강 카테고리 · 스코어 기반 추천")

# ---- 설정 ----
with st.expander("⚙️ 설정", expanded=False):
    col1, col2 = st.columns(2)
    with col1:
        keyword_limit = st.number_input("급상승 키워드 수", min_value=5, max_value=30, value=20)
    with col2:
        max_products_per_keyword = st.number_input("키워드당 상품 수", min_value=5, max_value=36, value=10)

# ---- 실행 ----
if st.button("🚀 급상승 아이템 스캔 실행"):
    progress = st.progress(0)
    status = st.empty()

    status.info("네이버 쇼핑 인사이트 API로 급상승 키워드 수집 중...")
    keywords = fetch_rising_keywords(limit=keyword_limit)
    progress.progress(0.2)

    all_products = []
    total_kw = len(keywords)
    for i, kw in enumerate(keywords[:10]):
        status.info(f"쿠팡 검색 중: {kw} ({i+1}/{min(10, total_kw)})")
        products = search_coupang_products(kw)
        all_products.extend(products[:max_products_per_keyword])
        progress.progress(0.2 + 0.6 * (i + 1) / min(10, total_kw))

    status.info("스코어링 적용 중...")
    scored = score_products(all_products)
    scored = scored[:100]
    progress.progress(1.0)
    status.empty()
    progress.empty()

    if scored:
        st.session_state["scored_products"] = scored
        st.success(f"총 {len(scored)}개 상품 스코어링 완료 (가격 2~7만원 필터)")
    else:
        st.warning("수집된 상품이 없습니다. 네이버 API 키·쿠팡 접근 상태를 확인하세요.")

# ---- 결과 테이블 ----
if "scored_products" in st.session_state:
    products = st.session_state["scored_products"]
    rows = []
    for p in products:
        hook = generate_hooking_point(p)
        rows.append({
            "상품명": p.get("name", ""),
            "가격": p.get("price", 0),
            "리뷰수": p.get("review_count", 0),
            "리뷰가속도": p.get("review_acceleration", 0),
            "스코어": p.get("score", 0),
            "쇼츠 후킹포인트": hook,
            "URL": p.get("url", ""),
        })

    df = pd.DataFrame(rows)
    st.subheader("📊 스코어 Top 상품 (가격 2~7만원)")
    st.dataframe(
        df.style.format({"가격": "{:,.0f}원", "리뷰수": "{:,}", "스코어": "{:.1f}"}),
        use_container_width=True,
        hide_index=True,
    )

    st.subheader("🔗 파트너스 링크 & 쇼츠 후킹")
    for i, p in enumerate(products[:20]):
        with st.expander(f"{p.get('name', '')[:50]}... | {p.get('price', 0):,}원 | 스코어 {p.get('score', 0):.1f}"):
            hook = generate_hooking_point(p)
            st.text_area("쇼츠 후킹 포인트", value=hook, key=f"hook_{i}", height=60, disabled=False)
            col1, col2 = st.columns(2)
            with col1:
                if st.button("파트너스 링크 생성 (API)", key=f"btn_{i}"):
                    partner_url = create_partner_link(p.get("url", ""))
                    st.session_state[f"plink_{i}"] = partner_url
                if f"plink_{i}" in st.session_state:
                    st.code(st.session_state[f"plink_{i}"], language=None)
            with col2:
                manual_url = st.text_input("또는 수동 입력", key=f"manual_{i}", placeholder="https://link.coupang.com/...")
else:
    st.info("위 [급상승 아이템 스캔 실행] 버튼을 눌러 분석을 시작하세요.")

st.caption("네이버 쇼핑인사이트 API · 쿠팡 검색 · 리뷰 가속도 시뮬레이션 · 100점 스코어")
