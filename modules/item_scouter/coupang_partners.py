# -*- coding: utf-8 -*-
"""
쿠팡 파트너스 링크 생성.
API: HMAC 인증 필요. st.secrets에 COUPANG_ACCESS_KEY, COUPANG_SECRET_KEY.
API 미설정 시 수동 입력 URL 반환.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
from datetime import datetime
from typing import Any
from urllib.parse import quote

import requests


def _get_partner_credentials() -> tuple[str, str]:
    """st.secrets 또는 환경변수에서 쿠팡 파트너스 키 조회."""
    try:
        import streamlit as st
        ak = st.secrets.get("COUPANG_ACCESS_KEY", "")
        sk = st.secrets.get("COUPANG_SECRET_KEY", "")
        if ak and sk:
            return ak, sk
    except Exception:
        pass
    import os
    return os.getenv("COUPANG_ACCESS_KEY", ""), os.getenv("COUPANG_SECRET_KEY", "")


def create_partner_link(product_url: str, sub_id: str = "") -> str:
    """
    쿠팡 상품 URL을 파트너스 추적 링크로 변환.
    API 미설정 시 원본 URL 반환. API 호출 실패 시 수동 입력 권장.
    """
    if not product_url or "coupang.com" not in product_url:
        return product_url

    access_key, secret_key = _get_partner_credentials()
    if not access_key or not secret_key:
        return product_url

    method = "POST"
    path = "/v2/providers/affiliate_open_api/apis/openapi/v1/deeplink"
    domain = "https://api-gateway.coupang.com"
    url = domain + path

    timestamp = datetime.utcnow().strftime("%y%m%d") + "T" + datetime.utcnow().strftime("%H%M%S") + "Z"
    message = timestamp + method + path
    signature = base64.b64encode(
        hmac.new(
            secret_key.encode(),
            message.encode(),
            hashlib.sha256,
        ).digest()
    ).decode()

    headers = {
        "Authorization": f"CEA algorithm=HmacSHA256, access-key={access_key}, signed-date={timestamp}, signature={signature}",
        "Content-Type": "application/json",
    }
    payload = {"coupangUrls": [product_url]}
    if sub_id:
        payload["subId"] = sub_id

    try:
        r = requests.post(url, json=payload, headers=headers, timeout=10)
        if r.status_code == 200:
            data = r.json()
            if data.get("data") and len(data["data"]) > 0:
                return data["data"][0].get("shortenUrl", product_url)
    except Exception:
        pass
    return product_url
