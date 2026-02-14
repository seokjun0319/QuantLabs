"""
QuantLabs - 데이터 수집 모듈
API 호출 등 공통 로직. 에러 시 Slack 전송.
"""
import os
from typing import Optional

import pandas as pd
import requests
from dotenv import load_dotenv

from .slack_notifier import send_error_to_slack

load_dotenv()

COINGECKO_BASE = "https://api.coingecko.com/api/v3"


def _safe_request(url: str, params: Optional[dict] = None) -> Optional[dict]:
    """GET 요청 후 JSON 반환. 실패 시 Slack 전송."""
    try:
        r = requests.get(url, params=params or {}, timeout=15)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        send_error_to_slack(e, context=f"GET {url}")
        return None


def get_btc_price() -> Optional[float]:
    """비트코인 현재가 (USD). CoinGecko 무료 API."""
    data = _safe_request(
        f"{COINGECKO_BASE}/simple/price",
        params={"ids": "bitcoin", "vs_currencies": "usd"},
    )
    if data and "bitcoin" in data and "usd" in data["bitcoin"]:
        return float(data["bitcoin"]["usd"])
    return None


def get_btc_ohlc(days: int = 30) -> Optional[pd.DataFrame]:
    """비트코인 OHLC (일봉). days: 1~90."""
    days = max(1, min(90, days))
    data = _safe_request(
        f"{COINGECKO_BASE}/coins/bitcoin/market_chart",
        params={"vs_currency": "usd", "days": str(days)},
    )
    if not data or "prices" not in data:
        return None
    df = pd.DataFrame(data["prices"], columns=["timestamp", "price"])
    df["date"] = pd.to_datetime(df["timestamp"], unit="ms")
    df = df.set_index("date").drop(columns=["timestamp"]).sort_index()
    return df
