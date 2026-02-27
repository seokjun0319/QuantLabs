# -*- coding: utf-8 -*-
"""
국토교통부 아파트 실거래가 API (MOLIT)
- 매매: getRTMSDataSvcAptTrade
- 전월세: getRTMSDataSvcAptRent
API 키: 공공데이터포털 serviceKey (MOLIT_SERVICE_KEY)
"""
from __future__ import annotations

from datetime import datetime
from typing import Any
from urllib.parse import urlencode

import pandas as pd
import requests

# 공공데이터포털/MOLIT API 엔드포인트
MOLIT_APT_TRADE_URL = (
    "http://openapi.molit.go.kr:8081/OpenAPI_ToolInstallPackage/service/rest"
    "/RTMSOBJSvc/getRTMSDataSvcAptTrade"
)
MOLIT_APT_RENT_URL = (
    "http://openapi.molit.go.kr:8081/OpenAPI_ToolInstallPackage/service/rest"
    "/RTMSOBJSvc/getRTMSDataSvcAptRent"
)

# 법정동코드 예시 (시도+구)
LAWD_CODES = {
    "11110": "서울 종로구",
    "11140": "서울 중구",
    "11215": "서울 광진구",
    "11680": "서울 강남구",
    "26260": "부산 수영구",
    "27110": "대구 수성구",
    "28177": "인천 서구",
    "41135": "경기 성남시",
    "41190": "경기 용인시",
}


def _get_service_key() -> str:
    """st.secrets 또는 환경변수에서 MOLIT API 키 조회."""
    try:
        import streamlit as st
        key = st.secrets.get("MOLIT_SERVICE_KEY", "")
        if key:
            return key
    except Exception:
        pass
    import os
    return os.getenv("MOLIT_SERVICE_KEY", "")


def _parse_apt_trade_xml(xml_text: str) -> list[dict[str, Any]]:
    """매매 XML 응답 파싱."""
    import xml.etree.ElementTree as ET

    items = []
    try:
        root = ET.fromstring(xml_text)
        for item in root.findall(".//item"):
            d = {}
            for child in item:
                d[child.tag] = child.text or ""
            if d.get("거래금액"):
                items.append(d)
    except Exception:
        pass
    return items


def _parse_apt_rent_xml(xml_text: str) -> list[dict[str, Any]]:
    """전월세 XML 응답 파싱."""
    return _parse_apt_trade_xml(xml_text)


def fetch_apt_trades(
    lawd_cd: str,
    deal_ymd: str | None = None,
    service_key: str | None = None,
) -> pd.DataFrame:
    """
    아파트 매매 실거래가 조회.
    lawd_cd: 법정동코드 5자리 (예: 11110)
    deal_ymd: 계약년월 YYYYMM (미입력 시 최근 1개월)
    """
    key = service_key or _get_service_key()
    if not key:
        return _get_demo_trades(lawd_cd, deal_ymd)

    deal_ymd = deal_ymd or datetime.now().strftime("%Y%m")
    params = {
        "serviceKey": key,
        "LAWD_CD": lawd_cd,
        "DEAL_YMD": deal_ymd,
    }
    url = f"{MOLIT_APT_TRADE_URL}?{urlencode(params)}"
    try:
        r = requests.get(url, timeout=15)
        if r.status_code != 200:
            return _get_demo_trades(lawd_cd, deal_ymd)
        items = _parse_apt_trade_xml(r.text)
        if not items:
            return _get_demo_trades(lawd_cd, deal_ymd)
        df = pd.DataFrame(items)
        df = _normalize_trade_df(df)
        return df
    except Exception:
        return _get_demo_trades(lawd_cd, deal_ymd)


def fetch_apt_rents(
    lawd_cd: str,
    deal_ymd: str | None = None,
    service_key: str | None = None,
) -> pd.DataFrame:
    """아파트 전월세 실거래가 조회."""
    key = service_key or _get_service_key()
    if not key:
        return _get_demo_rents(lawd_cd, deal_ymd)

    deal_ymd = deal_ymd or datetime.now().strftime("%Y%m")
    params = {
        "serviceKey": key,
        "LAWD_CD": lawd_cd,
        "DEAL_YMD": deal_ymd,
    }
    url = f"{MOLIT_APT_RENT_URL}?{urlencode(params)}"
    try:
        r = requests.get(url, timeout=15)
        if r.status_code != 200:
            return _get_demo_rents(lawd_cd, deal_ymd)
        items = _parse_apt_rent_xml(r.text)
        if not items:
            return _get_demo_rents(lawd_cd, deal_ymd)
        df = pd.DataFrame(items)
        df = _normalize_rent_df(df)
        return df
    except Exception:
        return _get_demo_rents(lawd_cd, deal_ymd)


def _normalize_trade_df(df: pd.DataFrame) -> pd.DataFrame:
    """매매 데이터 정규화."""
    cols = ["지역코드", "법정동", "아파트명", "거래금액", "전용면적", "건축년도", "년", "월", "일"]
    for c in cols:
        if c not in df.columns:
            df[c] = ""
    df["가격"] = df["거래금액"].astype(str).str.replace(",", "").str.replace(" ", "").apply(
        lambda x: int(x) if x.isdigit() else 0
    )
    df["건축년도"] = pd.to_numeric(df["건축년도"], errors="coerce").fillna(0).astype(int)
    return df


def _normalize_rent_df(df: pd.DataFrame) -> pd.DataFrame:
    """전월세 데이터 정규화."""
    cols = ["지역코드", "법정동", "아파트명", "보증금액", "월세금액", "전용면적", "건축년도", "년", "월", "일"]
    for c in cols:
        if c not in df.columns:
            df[c] = ""
    df["보증금"] = df["보증금액"].astype(str).str.replace(",", "").str.replace(" ", "").apply(
        lambda x: int(x) if x.isdigit() else 0
    )
    df["월세"] = pd.to_numeric(df["월세금액"], errors="coerce").fillna(0).astype(int)
    df["건축년도"] = pd.to_numeric(df["건축년도"], errors="coerce").fillna(0).astype(int)
    return df


def _get_demo_trades(lawd_cd: str, deal_ymd: str | None) -> pd.DataFrame:
    """API 미설정/실패 시 데모 데이터."""
    import random
    names = ["래미안", "자이", "푸르지오", "e편한세상", "힐스테이트"]
    area = lawd_cd
    ym = deal_ymd or datetime.now().strftime("%Y%m")
    rows = []
    for i in range(30):
        rows.append({
            "지역코드": area,
            "법정동": "테스트동",
            "아파트명": f"{random.choice(names)}아파트 {i+1}동",
            "거래금액": f"{random.randint(300, 800) * 1000:,}",
            "가격": random.randint(300, 800) * 1000,
            "전용면적": random.randint(80, 120),
            "건축년도": random.randint(2010, 2023),
            "년": ym[:4],
            "월": ym[4:6],
            "일": str(random.randint(1, 28)),
        })
    return pd.DataFrame(rows)


def _get_demo_rents(lawd_cd: str, deal_ymd: str | None) -> pd.DataFrame:
    """전월세 데모 데이터."""
    import random
    names = ["래미안", "자이", "푸르지오"]
    ym = deal_ymd or datetime.now().strftime("%Y%m")
    rows = []
    for i in range(15):
        rows.append({
            "지역코드": lawd_cd,
            "법정동": "테스트동",
            "아파트명": f"{random.choice(names)}아파트 {i+1}동",
            "보증금액": f"{random.randint(100, 300) * 1000:,}",
            "보증금": random.randint(100, 300) * 1000,
            "월세금액": str(random.randint(0, 100)),
            "월세": random.randint(0, 100),
            "전용면적": random.randint(80, 120),
            "건축년도": random.randint(2015, 2023),
            "년": ym[:4],
            "월": ym[4:6],
            "일": str(random.randint(1, 28)),
        })
    return pd.DataFrame(rows)


def _complex_to_coords(name: str, center_lat: float = 37.5, center_lon: float = 127.0) -> tuple[float, float]:
    """단지명 기반 안정적 좌표 생성 (해시 사용). 실제 연동 시 Geocoding/단지코드DB 사용."""
    h = hash(name) % 10000
    lat = center_lat + (h % 100) * 0.002 - 0.1
    lon = center_lon + (h // 100) * 0.002 - 0.1
    return round(lat, 4), round(lon, 4)


def aggregate_by_complex(df: pd.DataFrame) -> pd.DataFrame:
    """단지별 집계 (평균가격, 거래건수, 최근거래)."""
    if df.empty:
        return df
    agg = df.groupby("아파트명").agg({
        "가격": ["mean", "count", "min", "max"],
        "건축년도": "first",
        "전용면적": "mean",
    }).reset_index()
    agg.columns = ["아파트명", "평균가격", "거래건수", "최저가", "최고가", "건축년도", "평균면적"]
    agg["평균가격"] = agg["평균가격"].astype(int)
    agg["lat"], agg["lon"] = zip(
        *agg["아파트명"].apply(lambda n: _complex_to_coords(str(n)))
    )
    return agg.sort_values("거래건수", ascending=False)
