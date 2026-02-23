# -*- coding: utf-8 -*-
"""
네이버 쇼핑인사이트 API — 생활/건강 카테고리 급상승 키워드 추출.
API 키: st.secrets 또는 환경변수 NAVER_CLIENT_ID, NAVER_CLIENT_SECRET
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

import requests

# 생활/건강 카테고리 코드
CATEGORY_LIFESTYLE_HEALTH = "50000804"

# 급상승 키워드 후보 (생활/건강 관련, API는 미리 알려진 키워드만 조회 가능)
KEYWORD_CANDIDATES = [
    "비타민", "오메가3", "유산균", "마그네슘", "콜라겐", "프로바이오틱스",
    "홍삼", "수면유도제", "눈건강", "관절영양제", "멀티비타민", "비오틴",
    "밀크씨슬", "녹차엑기스", "루테인", "아르기닌", "브로멜라인",
    "오메가369", "흑염소진액", "철분", "칼슘", "아연", "비타민D",
    "코엔자임Q10", "밀크시슬", "프로폴리스", "쏘팔메토", "마카",
    "레시틴", "글루코사민", "히알루론산", "폴리코사놀", "케르세틴",
]

NAVER_INSIGHT_URL = "https://openapi.naver.com/v1/datalab/shopping/category/keywords"


def _get_api_credentials() -> tuple[str, str]:
    """st.secrets 또는 환경변수에서 API 키 조회."""
    try:
        import streamlit as st
        cid = st.secrets.get("NAVER_CLIENT_ID", "")
        csec = st.secrets.get("NAVER_CLIENT_SECRET", "")
        if cid and csec:
            return cid, csec
    except Exception:
        pass
    import os
    return os.getenv("NAVER_CLIENT_ID", ""), os.getenv("NAVER_CLIENT_SECRET", "")


def fetch_rising_keywords(
    category: str = CATEGORY_LIFESTYLE_HEALTH,
    limit: int = 20,
    candidates: list[str] | None = None,
) -> list[str]:
    """
    생활/건강 카테고리에서 급상승 키워드 limit개 추출.
    최근 2주 vs 그 전 2주 비율로 상승률 계산 후 정렬.
    API 미설정 시 후보 리스트 상위 limit개 반환.
    """
    candidates = candidates or KEYWORD_CANDIDATES
    cid, csec = _get_api_credentials()
    if not cid or not csec:
        return candidates[:limit]

    end_date = datetime.now()
    start_date = end_date - timedelta(days=28)
    start_str = start_date.strftime("%Y-%m-%d")
    end_str = end_date.strftime("%Y-%m-%d")

    keyword_scores: dict[str, float] = {}

    for i in range(0, min(len(candidates), 25), 5):
        batch = candidates[i : i + 5]
        keyword_payload = [
            {"name": kw, "param": [kw]} for kw in batch
        ]
        payload = {
            "startDate": start_str,
            "endDate": end_str,
            "timeUnit": "week",
            "category": category,
            "keyword": keyword_payload,
        }
        try:
            r = requests.post(
                NAVER_INSIGHT_URL,
                json=payload,
                headers={
                    "X-Naver-Client-Id": cid,
                    "X-Naver-Client-Secret": csec,
                    "Content-Type": "application/json",
                },
                timeout=10,
            )
            if r.status_code != 200:
                continue
            data = r.json()
            for res in data.get("results", []):
                kw = res.get("title", "")
                points = res.get("data", [])
                if len(points) >= 2:
                    recent = points[-1].get("ratio", 0) or 1
                    older = points[-2].get("ratio", 0) or 0.1
                    rise = recent / older if older > 0 else 1.0
                    keyword_scores[kw] = rise
                else:
                    keyword_scores[kw] = 1.0
        except Exception:
            continue

    if keyword_scores:
        sorted_kw = sorted(
            keyword_scores.keys(),
            key=lambda k: keyword_scores.get(k, 0),
            reverse=True,
        )
        return sorted_kw[:limit]
    return candidates[:limit]
