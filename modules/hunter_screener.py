# -*- coding: utf-8 -*-
"""
QuantLabs 종목 발굴기 (Hunter Screener) — yfinance 기반.
Stocks / ETFs 리스트, OHLC 수집, RSI/MA200/Volume 비율/추천 신호 계산.
"""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

# ----- 미장: 테마별 공격수 (탭 전환용, 테마당 10종목) -----
US_ATTACKERS_BY_THEME = {
    "AI & Semi": [
        "NVDA", "AVGO", "MSFT", "AMD", "INTC", "QCOM", "AMAT", "ASML", "TSM", "MU",
    ],
    "Space & Tech": [
        "RKLB", "PLTR", "TSLA", "LMT", "RTX", "NOC", "BA", "HII", "LDOS", "SPCE",
    ],
    "Bio & Energy": [
        "LLY", "VRT", "CEG", "MRNA", "REGN", "BIIB", "XOM", "CVX", "OXY", "EOG",
    ],
    "Cloud & Software": [
        "AMZN", "GOOGL", "META", "CRM", "ORCL", "ADBE", "NOW", "SNOW", "WDAY", "DDOG",
    ],
    "Consumer & Media": [
        "AAPL", "NFLX", "COST", "DIS", "NKE", "SBUX", "HD", "MCD", "TJX", "LOW",
    ],
    "Fintech & Banks": [
        "V", "MA", "PYPL", "AXP", "JPM", "GS", "BAC", "COF", "SQ", "COIN",
    ],
}

# 미장 ETF 방어군 (테마별 10종목)
US_ETF_BY_THEME = {
    "지수·시장": [
        "SPY", "QQQ", "IWM", "DIA", "VTI", "VOO", "IVV", "VTV", "VUG", "SCHB",
    ],
    "배당·채권": [
        "SCHD", "JEPI", "TLT", "VYM", "BND", "HYG", "TIP", "LQD", "AGG", "IEF",
    ],
    "원자재·섹터": [
        "GLD", "SLV", "SOXX", "XLF", "XLK", "XLE", "XLV", "USO", "XLI", "XLY",
    ],
}

# 하위 호환용 플랫 리스트 (전체 미장 ETF)
TICKERS_ETFS = [t for tickers in US_ETF_BY_THEME.values() for t in tickers]

# ----- 국장: 테마별 공격수 (탭 전환용, 테마당 10종목), yfinance .KS 규칙 -----
KR_ATTACKERS_BY_THEME = {
    "반도체": [
        "005930.KS", "000660.KS", "009830.KS", "042700.KS", "051910.KS",
        "006400.KS", "247540.KS", "086520.KS", "068270.KS", "000990.KS",
    ],
    "2차전지·에너지": [
        "373220.KS", "006400.KS", "051910.KS", "247540.KS", "086520.KS",
        "009830.KS", "298020.KS", "010130.KS", "054540.KS", "017800.KS",
    ],
    "바이오": [
        "207940.KS", "068270.KS", "326030.KS", "207760.KS", "006280.KS",
        "293490.KS", "214450.KS", "086960.KS", "950210.KS", "068760.KS",
    ],
    "항공우주": [
        "012450.KS", "047810.KS", "042660.KS", "001040.KS", "008260.KS",
        "009540.KS", "010140.KS", "012630.KS", "017390.KS", "034020.KS",
    ],
    "IT·플랫폼": [
        "035420.KS", "035720.KS", "036570.KS", "263750.KS", "251270.KS",
        "377300.KS", "035900.KS", "068270.KS", "055990.KS", "247540.KS",
    ],
    "자동차·부품": [
        "005380.KS", "000270.KS", "012330.KS", "018880.KS", "009830.KS",
        "006400.KS", "051910.KS", "373220.KS", "247540.KS", "086520.KS",
    ],
    "금융·인프라": [
        "055550.KS", "086790.KS", "105560.KS", "316140.KS", "003550.KS",
        "000810.KS", "032830.KS", "009540.KS", "010140.KS", "017670.KS",
    ],
}

# 국장 ETF 방어군 (테마별 10종목, (티커, 표시명))
KR_ETF_BY_THEME = {
    "지수·시장": [
        ("069500.KS", "KODEX 200"),
        ("360750.KS", "TIGER 미국S&P500"),
        ("379810.KS", "KODEX 미국나스닥100"),
        ("360740.KS", "KODEX 미국S&P500TR"),
        ("379800.KS", "KODEX 미국나스닥100TR"),
        ("360760.KS", "TIGER 미국나스닥100"),
        ("133690.KS", "KODEX 200선물"),
        ("251340.KS", "KODEX 200초단기선물"),
        ("305720.KS", "KODEX 200미니선물"),
        ("278420.KS", "KODEX 200동시가격"),
    ],
    "배당·채권": [
        ("252650.KS", "KODEX 배당성장"),
        ("123310.KS", "TIGER 200고배당"),
        ("148070.KS", "KODEX 10년국채"),
        ("136340.KS", "TIGER 10년국채"),
        ("329260.KS", "KODEX 미국배당다우존스"),
        ("360720.KS", "TIGER 미국배당다우존스"),
        ("261240.KS", "KODEX 미국배당프리미엄액티브"),
        ("360770.KS", "TIGER 미국배당프리미엄"),
        ("114260.KS", "KODEX 골드선물"),
        ("132030.KS", "KODEX 미국달러선물"),
    ],
    "원자재": [
        ("114260.KS", "KODEX 골드선물"),
        ("253280.KS", "KODEX 골드선물(H)"),
        ("130680.KS", "KODEX WTI원유선물"),
        ("138910.KS", "KODEX 구리선물(H)"),
        ("144600.KS", "KODEX 은선물(H)"),
        ("116480.KS", "KODEX 골드선물인버스"),
        ("261420.KS", "KODEX WTI원유선물인버스"),
        ("307520.KS", "KODEX 골드선물2X"),
        ("319640.KS", "TIGER 골드선물(H)"),
        ("411060.KS", "ACE KRX금현물"),
    ],
    "인버스·헤지": [
        ("252670.KS", "KODEX 200선물인버스2X"),
        ("233740.KS", "KODEX 인버스"),
        ("114800.KS", "KODEX 인버스2X"),
        ("441680.KS", "KODEX 미국나스닥100헤지"),
        ("245340.KS", "KODEX 미국S&P500헤지"),
        ("117460.KS", "KODEX 중국심천ChiNext"),
        ("102960.KS", "KODEX 일본니케이225"),
        ("266420.KS", "KODEX 미국나스닥100레버리지"),
        ("251340.KS", "KODEX 200초단기선물"),
        ("305720.KS", "KODEX 200미니선물"),
    ],
}

# 하위 호환용 플랫 리스트 (국장 ETF 전체)
KR_ETF_DEFENDERS = [
    item for tickers in KR_ETF_BY_THEME.values() for item in tickers
]

# 국장 티커 표시명 (공격수, 주요 종목)
KR_TICKER_NAMES = {
    "005930.KS": "삼성전자",
    "000660.KS": "SK하이닉스",
    "012450.KS": "한화에어로스페이스",
    "373220.KS": "LG에너지솔루션",
    "207940.KS": "삼성바이오로직스",
    "009830.KS": "한화솔루션",
    "042700.KS": "한솔케미칼",
    "051910.KS": "LG화학",
    "006400.KS": "삼성SDI",
    "247540.KS": "에코프로비엠",
    "086520.KS": "에코프로",
    "068270.KS": "셀트리온",
    "000990.KS": "DB하이텍",
    "035420.KS": "NAVER",
    "035720.KS": "카카오",
    "036570.KS": "엔씨소프트",
    "263750.KS": "펄어비스",
    "251270.KS": "넷마블",
    "377300.KS": "카카오페이",
    "035900.KS": "JYP",
    "055990.KS": "신한지주",
    "005380.KS": "현대차",
    "000270.KS": "기아",
    "012330.KS": "현대모비스",
    "018880.KS": "한온시스템",
    "055550.KS": "신한지주",
    "086790.KS": "하나금융",
    "105560.KS": "KB금융",
    "316140.KS": "우리금융",
    "003550.KS": "LG",
    "000810.KS": "삼성화재",
    "032830.KS": "삼성생명",
    "009540.KS": "HD한국조선",
    "010140.KS": "삼성중공업",
    "017670.KS": "SK텔레콤",
    "047810.KS": "한국항공우주",
    "042660.KS": "한화시스템",
    "001040.KS": "CJ",
    "008260.KS": "SK스틸",
    "012630.KS": "HDC",
    "017390.KS": "삼성전기",
    "034020.KS": "두산에너빌리티",
    "298020.KS": "효성첨단소재",
    "010130.KS": "고려아연",
    "054540.KS": "삼성엔지니어링",
    "017800.KS": "현대엘리베이터",
    "326030.KS": "SK바이오팜",
    "207760.KS": "롯데케미칼",
    "006280.KS": "녹십자",
    "293490.KS": "카카오게임즈",
    "214450.KS": "파마리서치",
    "086960.KS": "엔에프씨",
    "950210.KS": "셀트리온헬스케어",
    "068760.KS": "셀트리온제약",
}

# 하위 호환: 기존 플랫 리스트 (전체 미장 공격수)
TICKERS_STOCKS = [
    t for tickers in US_ATTACKERS_BY_THEME.values() for t in tickers
]

DAYS_LOOKBACK = 250  # MA200 및 RSI용

# Entry Signal Safe Guard 설정 (대장님 조정 가능)
PER_THRESHOLD = 30  # 개별주: PER < 이 값일 때만 Buy the Dip
NAV_PREMIUM_THRESHOLD_PCT = 0.2  # ETF: 괴리율 < 이 %일 때만 Buy the Dip

# ETF 티커 집합 (Safe Guard 및 필드 표시용)
ALL_ETF_TICKERS: set[str] = (
    set(t for ticks in US_ETF_BY_THEME.values() for t in ticks)
    | set(t for ticks in KR_ETF_BY_THEME.values() for t, _ in ticks)
)


def fetch_ticker_fundamentals(tickers: list[str]) -> dict[str, dict[str, Any]]:
    """
    티커별 PER(개별주) / NAV 괴리율%(ETF) 수집.
    Returns: {ticker: {per, nav_premium_pct, is_etf, value_check}}
    """
    result: dict[str, dict[str, Any]] = {}
    try:
        import yfinance as yf
        for t in tickers:
            out: dict[str, Any] = {"per": None, "nav_premium_pct": None, "is_etf": False, "value_check": ""}
            try:
                obj = yf.Ticker(t)
                info = obj.info or {}
                quote_type = (info.get("quoteType") or "").upper()
                out["is_etf"] = quote_type == "ETF" or t in ALL_ETF_TICKERS

                if out["is_etf"]:
                    nav = info.get("navPrice")  # ETF 전용, 없으면 N/A
                    price = info.get("regularMarketPrice") or info.get("previousClose") or 0
                    if nav and float(nav) > 0 and price:
                        price_f = float(price)
                        nav_f = float(nav)
                        out["nav_premium_pct"] = round((price_f - nav_f) / nav_f * 100, 2)
                else:
                    pe = info.get("trailingPE") or info.get("forwardPE")
                    if pe is not None:
                        out["per"] = round(float(pe), 1)
            except Exception:
                pass
            result[t] = out
    except Exception:
        pass
    return result


def fetch_treemap_data(
    theme_map: dict[str, list],
    ticker_names: dict[str, str] | None = None,
    kr_etf_format: bool = False,
) -> list[dict[str, Any]]:
    """
    트리맵용 데이터: theme, label, market_cap, pct_change, price, per, rsi
    kr_etf_format: theme_map 값이 [(ticker, name), ...] 형태일 때 True
    """
    rows: list[dict[str, Any]] = []
    try:
        import yfinance as yf
        for theme, tickers in theme_map.items():
            for item in tickers:
                ticker = item[0] if kr_etf_format else item
                display = item[1] if kr_etf_format else (ticker_names.get(ticker, ticker) if ticker_names else ticker)
                try:
                    t = yf.Ticker(ticker)
                    info = t.info or {}
                    cap = info.get("marketCap") or info.get("enterpriseValue")
                    price = info.get("regularMarketPrice") or info.get("previousClose") or info.get("currentPrice")
                    prev = info.get("regularMarketPreviousClose") or info.get("previousClose")
                    pct = None
                    if price and prev and float(prev) > 0:
                        pct = round((float(price) - float(prev)) / float(prev) * 100, 2)
                    per = info.get("trailingPE") or info.get("forwardPE")
                    per_val = round(float(per), 1) if per is not None else None
                    cap_val = float(cap) if cap is not None else 1e9  # 기본값으로 정렬
                    price_val = float(price) if price else None
                    rows.append({
                        "theme": theme,
                        "label": str(display),
                        "market_cap": max(cap_val, 1e6),
                        "pct_change": pct if pct is not None else 0.0,
                        "price": price_val,
                        "per": per_val,
                        "rsi": None,  # RSI는 OHLC 필요, 선택적 보강
                    })
                except Exception:
                    continue
    except Exception:
        pass
    return rows


def _rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)
    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()
    rs = avg_gain / avg_loss.replace(0, 1e-10)
    return 100 - (100 / (1 + rs))


def fetch_tickers_ohlc(tickers: list[str], days: int = DAYS_LOOKBACK) -> dict[str, pd.DataFrame]:
    """yfinance로 티커별 OHLC + Volume 수집. 캐싱은 호출측(st.cache_data)에서 수행."""
    result: dict[str, pd.DataFrame] = {}
    try:
        import yfinance as yf
        for t in tickers:
            try:
                df = yf.download(
                    t, period=f"{days}d", interval="1d",
                    progress=False, auto_adjust=True, threads=False,
                )
                if df is None or df.empty or len(df) < 2:
                    continue
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = [c[0].lower() if isinstance(c, tuple) else str(c).lower() for c in df.columns]
                else:
                    df.columns = [str(c).lower() for c in df.columns]
                need = ["open", "high", "low", "close"]
                if "volume" in df.columns:
                    need = need + ["volume"]
                if not all(c in df.columns for c in ["open", "high", "low", "close"]):
                    continue
                result[t] = df[need].sort_index() if "volume" in df.columns else df[["open", "high", "low", "close"]].sort_index()
            except Exception:
                continue
    except Exception:
        pass
    return result


def compute_screener_metrics(
    data: dict[str, pd.DataFrame],
    ticker_names: dict[str, str] | None = None,
    ticker_info: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """
    티커별 지표 계산.
    ticker_names: 티커→표시명 (국장 등). 있으면 표에 표시명 사용.
    ticker_info: fetch_ticker_fundamentals() 결과. PER/NAV Safe Guard 및 Value Check용.
    Returns list of dicts: ticker, current_price, rsi, ..., per, nav_premium_pct, entry_signal, value_check, risk_status.
    """
    ticker_info = ticker_info or {}
    rows = []
    for ticker, df in data.items():
        if df is None or len(df) < 30:
            continue
        close = df["close"]
        current_price = float(close.iloc[-1])
        rsi_series = _rsi(close, 14)
        rsi = float(rsi_series.iloc[-1]) if not pd.isna(rsi_series.iloc[-1]) else None
        ma200 = close.rolling(200).mean()
        ma200_last = float(ma200.iloc[-1]) if len(ma200.dropna()) else None
        if ma200_last is not None:
            trend = "상승세(🔥)" if current_price > ma200_last else "하락세(❄️)"
        else:
            trend = "—"

        vol_ratio = None
        if "volume" in df.columns and len(df) >= 2:
            v = df["volume"]
            try:
                prev = float(v.iloc[-2])
                if prev and prev > 0:
                    vol_ratio = float(v.iloc[-1]) / prev
            except (TypeError, ValueError, IndexError):
                pass

        if rsi is None:
            rsi = 0.0
        if ma200_last is None:
            ma200_last = 0.0
        if vol_ratio is None:
            vol_ratio = 0.0

        info = ticker_info.get(ticker, {})
        is_etf = info.get("is_etf", ticker in ALL_ETF_TICKERS)
        per = info.get("per")
        nav_premium_pct = info.get("nav_premium_pct")

        # PER / NAV 괴리율 표시값
        per_display = f"{per:.1f}" if per is not None else "N/A"
        nav_display = f"{nav_premium_pct:+.2f}%" if nav_premium_pct is not None else "N/A"

        # Value Check: 정상(Green), 주의(Yellow), 위험(Red)
        if is_etf:
            if nav_premium_pct is None:
                value_check = "N/A"
            elif nav_premium_pct < 0.2:
                value_check = "정상"
            elif nav_premium_pct < 1.0:
                value_check = "주의"
            else:
                value_check = "위험"
        else:
            if per is None:
                value_check = "N/A"
            elif per < PER_THRESHOLD:
                value_check = "정상"
            elif per < 50:
                value_check = "주의"
            else:
                value_check = "위험"

        # Entry Signal (진입 신호) + Safe Guard 필터
        if rsi < 35 and ma200_last and current_price > ma200_last:
            # Safe Guard: 개별주 PER < 30, ETF 괴리율 < 0.2%
            if is_etf:
                guard_ok = nav_premium_pct is not None and nav_premium_pct < NAV_PREMIUM_THRESHOLD_PCT
            else:
                guard_ok = per is not None and per < PER_THRESHOLD
            entry_signal = "Buy the Dip (줍줍 기회)" if guard_ok else "Value Trap (진입 보류)"
        elif ma200_last and current_price > ma200_last:
            entry_signal = "Watch (상승추세 관망)"
        else:
            entry_signal = "No Entry (하락추세 진입금지)"

        # Risk Status (리스크 관리): 보유종목 매도 시점·위험도
        if ma200_last and current_price < ma200_last:
            risk_status = "Trend Broken (무조건 탈출)"
        elif rsi > 80:
            risk_status = "Strong Sell (적극 익절)"
        elif rsi > 70:
            risk_status = "Caution (과열 주의)"
        else:
            risk_status = "Stable (평온)"

        display_ticker = (ticker_names.get(ticker, ticker) if ticker_names else ticker)
        rows.append({
            "Ticker": display_ticker,
            "Current Price": current_price,
            "RSI (14)": rsi,
            "Trend (MA200)": trend,
            "Vol (전일대비)": vol_ratio,
            "PER": per_display if not is_etf else "—",
            "NAV 괴리율(%)": nav_display if is_etf else "—",
            "Entry Signal": entry_signal,
            "Value Check": value_check,
            "Risk Status": risk_status,
        })
    return rows
