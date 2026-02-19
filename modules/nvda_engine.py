# -*- coding: utf-8 -*-
"""
QuantLabs - NVDA 심층 데이터 파이프라인 & Alpha-V1 엔진
보조지표 5종(RSI, MACD, Bollinger Bands, ATR, OBV) + 세력 매집 지표.
"""
import json
from pathlib import Path
from typing import Optional, Tuple

import numpy as np
import pandas as pd

from .nvda_fetcher import get_nvda_history
from .slack_notifier import send_error_to_slack

ROOT = Path(__file__).resolve().parents[1]
GOLDEN_PARAMS_PATH = ROOT / "data" / "nvda_golden_params.json"


def load_ohlc(days: int = 365) -> Optional[pd.DataFrame]:
    """NVDA OHLCV 로드."""
    return get_nvda_history(days)


def add_rsi(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    df = df.copy()
    delta = df["close"].diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)
    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()
    rs = avg_gain / avg_loss.replace(0, 1e-10)
    df["rsi"] = 100 - (100 / (1 + rs))
    return df


def add_macd(df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    df = df.copy()
    ema_fast = df["close"].ewm(span=fast, adjust=False).mean()
    ema_slow = df["close"].ewm(span=slow, adjust=False).mean()
    df["macd"] = ema_fast - ema_slow
    df["macd_signal"] = df["macd"].ewm(span=signal, adjust=False).mean()
    df["macd_hist"] = df["macd"] - df["macd_signal"]
    return df


def add_bollinger(df: pd.DataFrame, period: int = 20, std: float = 2.0) -> pd.DataFrame:
    df = df.copy()
    df["bb_mid"] = df["close"].rolling(period).mean()
    df["bb_std"] = df["close"].rolling(period).std()
    df["bb_upper"] = df["bb_mid"] + std * df["bb_std"]
    df["bb_lower"] = df["bb_mid"] - std * df["bb_std"]
    return df


def add_atr(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    df = df.copy()
    high_low = df["high"] - df["low"]
    high_close = (df["high"] - df["close"].shift(1)).abs()
    low_close = (df["low"] - df["close"].shift(1)).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df["atr"] = tr.rolling(period).mean()
    return df


def add_obv(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["obv"] = (np.sign(df["close"].diff()) * df["volume"]).fillna(0).cumsum()
    return df


def add_accumulation_indicator(df: pd.DataFrame, window: int = 10) -> pd.DataFrame:
    """
    세력 매집 지표 초안: 가격 상승일 거래량 가중합 - 하락일 거래량 가중합.
    상관: 가격 변화율과 거래량의 롤링 상관계수.
    """
    df = df.copy()
    ret = df["close"].pct_change()
    df["accum_raw"] = np.sign(ret) * df["volume"]
    df["accum_ma"] = df["accum_raw"].rolling(window).mean()
    df["price_vol_corr"] = df["close"].pct_change().rolling(window).corr(df["volume"])
    df["accum_signal"] = df["accum_ma"].rolling(5).mean()  # 스무딩
    return df


def build_indicator_df(days: int = 365) -> Optional[pd.DataFrame]:
    """5종 지표 + 세력 매집 지표가 붙은 DataFrame."""
    df = load_ohlc(days)
    if df is None or len(df) < 50:
        return None
    df = add_rsi(df, 14)
    df = add_macd(df, 12, 26, 9)
    df = add_bollinger(df, 20, 2.0)
    df = add_atr(df, 14)
    df = add_obv(df)
    df = add_accumulation_indicator(df, 10)
    return df.dropna(how="all")


# ----- Alpha-V1: 이동평균 정배열 + RSI 과매수 해소 + ATR 변동성 돌파 -----
def ma_alignment_signal(df: pd.DataFrame, short: int = 5, long: int = 20) -> pd.Series:
    """정배열: short MA > long MA → 1, else 0."""
    ma_s = df["close"].rolling(short).mean()
    ma_l = df["close"].rolling(long).mean()
    return (ma_s > ma_l).astype(float)


def rsi_relief_signal(df: pd.DataFrame, overbought: float = 70, relief: float = 65) -> pd.Series:
    """RSI 과매수 해소: RSI < relief 또는 (이전에 과매수였다가 해소) → 1에 가깝게."""
    rsi = df["rsi"]
    was_ob = rsi.shift(1) >= overbought
    now_relief = rsi < relief
    score = 1.0 - (rsi / 100)  # RSI 낮을수록 점수 높음 (과매수 해소)
    score = score.clip(0, 1)
    return score


def atr_breakout_signal(df: pd.DataFrame, k: float = 0.5) -> pd.Series:
    """ATR 변동성 돌파: close > prev_close + k*ATR → 1, else 0."""
    prev = df["close"].shift(1)
    target = prev + k * df["atr"]
    return (df["close"] > target).astype(float)


def compute_buy_score(
    df: pd.DataFrame,
    w_ma: float = 0.35,
    w_rsi: float = 0.35,
    w_atr: float = 0.30,
    rsi_overbought: float = 70,
    rsi_relief: float = 65,
    atr_k: float = 0.5,
) -> pd.DataFrame:
    """매수 점수(Buy Score) 0~100. 가중치 적용."""
    d = df.copy()
    d["sig_ma"] = ma_alignment_signal(d, 5, 20)
    d["sig_rsi"] = rsi_relief_signal(d, rsi_overbought, rsi_relief)
    d["sig_atr"] = atr_breakout_signal(d, atr_k)
    d["buy_score"] = (w_ma * d["sig_ma"] + w_rsi * d["sig_rsi"] + w_atr * d["sig_atr"]) * 100
    d["buy_score"] = d["buy_score"].clip(0, 100)
    return d


def run_backtest(
    df: pd.DataFrame,
    score_threshold: float = 55,
    w_ma: float = 0.35,
    w_rsi: float = 0.35,
    w_atr: float = 0.30,
    rsi_ob: float = 70,
    rsi_rel: float = 65,
    atr_k: float = 0.5,
) -> Tuple[float, float, float, pd.Series, dict]:
    """
    백테스트: Buy Score > threshold 인 날 다음 시가 매수, 1일 보유 후 다음 시가 매도.
    Returns: (연간 수익률, MDD, Sharpe, equity curve Series, extras)
    extras: first_buy_date, first_buy_price, mdd_date (날짜/가격/최대낙폭일)
    """
    d = compute_buy_score(df, w_ma, w_rsi, w_atr, rsi_ob, rsi_rel, atr_k)
    d = d.dropna(subset=["buy_score"])
    extras = {"first_buy_date": None, "first_buy_price": None, "mdd_date": None}
    if len(d) < 20:
        return 0.0, 1.0, 0.0, pd.Series(dtype=float), extras
    entries = d["buy_score"] >= score_threshold
    ret = df["close"].pct_change()
    strategy_ret = ret.copy()
    strategy_ret[:] = 0.0
    mask = entries.shift(1).fillna(False).reindex(df.index).fillna(False).astype(bool)
    strategy_ret.loc[mask] = ret.loc[mask]
    if mask.any():
        first_idx = mask.idxmax() if hasattr(mask, "idxmax") else d.index[mask].min()
        extras["first_buy_date"] = first_idx
        extras["first_buy_price"] = float(df.loc[first_idx, "close"]) if first_idx in df.index else None
    equity = (1 + strategy_ret).cumprod()
    total_ret = equity.iloc[-1] - 1 if len(equity) > 0 else 0.0
    peak = equity.cummax()
    dd = (equity - peak) / peak.replace(0, 1e-10)
    mdd = dd.min()
    if not dd.empty:
        extras["mdd_date"] = dd.idxmin()
    excess = strategy_ret - 0.0  # risk-free 0 가정
    sharpe = (excess.mean() / excess.std() * np.sqrt(252)) if excess.std() > 1e-10 else 0.0
    return total_ret, abs(mdd), sharpe, equity, extras


def optimize_golden_params(
    df: pd.DataFrame,
    target_return: float = 0.30,
    target_mdd: float = 0.15,
    max_iter: int = 50,
) -> Tuple[dict, float, float, float]:
    """
    목표: 연간 30%+, MDD 15% 이하. 가중치/파라미터 0.1 단위 조정, 최대 50회.
    Returns: (best_params, best_return, best_mdd, best_sharpe)
    """
    best_ret, best_mdd, best_sharpe = 0.0, 1.0, 0.0
    best_params = dict(
        w_ma=0.35, w_rsi=0.35, w_atr=0.30,
        rsi_ob=70, rsi_rel=65, atr_k=0.5, score_threshold=55,
    )
    rng = np.random.default_rng(42)
    for i in range(max_iter):
        w_ma = float(np.clip(0.2 + rng.uniform(0, 0.5), 0.1, 0.8))
        w_rsi = float(np.clip(0.2 + rng.uniform(0, 0.5), 0.1, 0.8))
        w_atr = 1.0 - w_ma - w_rsi
        if w_atr < 0.1:
            w_atr = 0.2
            w_ma, w_rsi = 0.4, 0.4
        thresh = 50 + int(rng.uniform(0, 20))
        rsi_ob_v = 65 + int(rng.integers(0, 10))
        rsi_rel_v = 60 + int(rng.integers(0, 10))
        atr_k_v = 0.3 + float(rng.uniform(0, 0.4))
        ret, mdd, sharpe, _, _ = run_backtest(
            df,
            score_threshold=thresh,
            w_ma=w_ma, w_rsi=w_rsi, w_atr=w_atr,
            rsi_ob=rsi_ob_v, rsi_rel=rsi_rel_v, atr_k=atr_k_v,
        )
        if ret >= best_ret and mdd <= max(best_mdd, target_mdd):
            best_ret, best_mdd, best_sharpe = ret, mdd, sharpe
            best_params = dict(
                w_ma=round(w_ma, 2), w_rsi=round(w_rsi, 2), w_atr=round(w_atr, 2),
                rsi_ob=rsi_ob_v, rsi_rel=rsi_rel_v, atr_k=round(atr_k_v, 2),
                score_threshold=thresh,
            )
        if ret >= target_return and mdd <= target_mdd:
            break
    return best_params, best_ret, best_mdd, best_sharpe


def optimize_golden_params_with_slack(
    df: pd.DataFrame,
    target_return: float = 0.30,
    target_mdd: float = 0.15,
    max_iter: int = 50,
    report_interval: int = 10,
) -> Tuple[dict, float, float, float]:
    """
    최적화 루프 + 10회마다 슬랙 중간 보고, 완료 시 종합 리포트 전송.
    Returns: (best_params, best_return, best_mdd, best_sharpe)
    """
    from .slack_notifier import send_slack_message
    best_ret, best_mdd, best_sharpe = 0.0, 1.0, 0.0
    best_params = dict(
        w_ma=0.35, w_rsi=0.35, w_atr=0.30,
        rsi_ob=70, rsi_rel=65, atr_k=0.5, score_threshold=55,
    )
    rng = np.random.default_rng(42)
    for i in range(max_iter):
        w_ma = float(np.clip(0.2 + rng.uniform(0, 0.5), 0.1, 0.8))
        w_rsi = float(np.clip(0.2 + rng.uniform(0, 0.5), 0.1, 0.8))
        w_atr = 1.0 - w_ma - w_rsi
        if w_atr < 0.1:
            w_atr = 0.2
            w_ma, w_rsi = 0.4, 0.4
        thresh = 50 + int(rng.uniform(0, 20))
        rsi_ob_v = 65 + int(rng.integers(0, 10))
        rsi_rel_v = 60 + int(rng.integers(0, 10))
        atr_k_v = 0.3 + float(rng.uniform(0, 0.4))
        ret, mdd, sharpe, _, _ = run_backtest(
            df,
            score_threshold=thresh,
            w_ma=w_ma, w_rsi=w_rsi, w_atr=w_atr,
            rsi_ob=rsi_ob_v, rsi_rel=rsi_rel_v, atr_k=atr_k_v,
        )
        if ret >= best_ret and mdd <= max(best_mdd, target_mdd):
            best_ret, best_mdd, best_sharpe = ret, mdd, sharpe
            best_params = dict(
                w_ma=round(w_ma, 2), w_rsi=round(w_rsi, 2), w_atr=round(w_atr, 2),
                rsi_ob=rsi_ob_v, rsi_rel=rsi_rel_v, atr_k=round(atr_k_v, 2),
                score_threshold=thresh,
            )
        # 10회마다 슬랙 보고
        if (i + 1) % report_interval == 0:
            msg = (
                f"🚨 [NVDA 연구 {i+1}회차] 현재 최고 수익률 {best_ret:.0%} 달성, 파라미터 조정 중...\n"
                f"MDD {best_mdd:.1%} / RSI기준 {best_params.get('rsi_ob', 70)}·{best_params.get('rsi_rel', 65)} / K(ATR) {best_params.get('atr_k', 0.5)}"
            )
            send_slack_message(msg, title="QuantLabs NVDA 연구", color="#2196F3")
        if ret >= target_return and mdd <= target_mdd:
            break
    # 최종 종합 리포트
    valuation = valuation_vs_volatility(df)
    score_now = get_current_buy_score(df, **{k: best_params[k] for k in ["w_ma", "w_rsi", "w_atr", "rsi_ob", "rsi_rel", "atr_k"] if k in best_params})
    if score_now >= best_params.get("score_threshold", 55):
        pm_line = f"현재 매수점수 {score_now:.0f}점으로 진입 조건 충족. {valuation}"
    else:
        pm_line = f"현재 매수점수 {score_now:.0f}점. 대기 권장. {valuation}"
    final_msg = (
        "✅ 최종 전략: NVDA Alpha-V1 최적화 완료\n\n"
        f"📈 예상 수익률 / MDD: {best_ret:.1%} / {best_mdd:.1%}\n\n"
        f"🛠️ 최적 파라미터\n"
        f"  · RSI 과매수/해소: {best_params.get('rsi_ob', 70)} / {best_params.get('rsi_rel', 65)}\n"
        f"  · ATR K값: {best_params.get('atr_k', 0.5)}\n"
        f"  · 매수점수 기준선: {best_params.get('score_threshold', 55)}점\n\n"
        f"💡 PM 한줄평: {pm_line}"
    )
    send_slack_message(final_msg, title="QuantLabs NVDA 최종 리포트", color="#76b900")
    save_golden_params(best_params, {"return": best_ret, "mdd": best_mdd, "sharpe": best_sharpe})
    return best_params, best_ret, best_mdd, best_sharpe


def get_current_buy_score(
    df: pd.DataFrame,
    w_ma: float = 0.35,
    w_rsi: float = 0.35,
    w_atr: float = 0.30,
    rsi_ob: float = 70,
    rsi_rel: float = 65,
    atr_k: float = 0.5,
) -> float:
    """현재 봉 기준 매수 점수 0~100."""
    d = compute_buy_score(df, w_ma, w_rsi, w_atr, rsi_ob, rsi_rel, atr_k)
    if d.empty or pd.isna(d["buy_score"].iloc[-1]):
        return 50.0
    return float(d["buy_score"].iloc[-1])


def get_current_buy_score_breakdown(
    df: pd.DataFrame,
    w_ma: float = 0.35,
    w_rsi: float = 0.35,
    w_atr: float = 0.30,
    rsi_ob: float = 70,
    rsi_rel: float = 65,
    atr_k: float = 0.5,
) -> dict:
    """매수 점수 집계 사유: MA·RSI·ATR 기여도(점) 및 총점."""
    d = compute_buy_score(df, w_ma, w_rsi, w_atr, rsi_ob, rsi_rel, atr_k)
    if d.empty or d["buy_score"].iloc[-1] is None or pd.isna(d["buy_score"].iloc[-1]):
        return {"total": 50.0, "ma_contrib": 0, "rsi_contrib": 0, "atr_contrib": 0}
    row = d.iloc[-1]
    ma_contrib = round(w_ma * row["sig_ma"] * 100, 1)
    rsi_contrib = round(w_rsi * row["sig_rsi"] * 100, 1)
    atr_contrib = round(w_atr * row["sig_atr"] * 100, 1)
    return {
        "total": round(float(row["buy_score"]), 1),
        "ma_contrib": ma_contrib,
        "rsi_contrib": rsi_contrib,
        "atr_contrib": atr_contrib,
    }


def compute_sell_score(
    df: pd.DataFrame,
    w_ma: float = 0.35,
    w_rsi: float = 0.35,
    w_atr: float = 0.30,
    rsi_overbought: float = 70,
    rsi_relief: float = 65,
    atr_k: float = 0.5,
) -> pd.DataFrame:
    """매도 점수(Sell Score) 0~100. MA 역배열·RSI 과매수·ATR 하락 돌파 가중."""
    d = df.copy()
    d["sig_ma"] = ma_alignment_signal(d, 5, 20)
    d["sig_rsi"] = rsi_relief_signal(d, rsi_overbought, rsi_relief)
    d["sig_atr"] = atr_breakout_signal(d, atr_k)
    # 매도: 역배열(1-ma), RSI 높을수록(과매수), ATR 하락(1-atr)
    d["sell_score"] = (w_ma * (1 - d["sig_ma"]) + w_rsi * (d["rsi"] / 100) + w_atr * (1 - d["sig_atr"])) * 100
    d["sell_score"] = d["sell_score"].clip(0, 100)
    return d


def get_current_sell_score(
    df: pd.DataFrame,
    w_ma: float = 0.35,
    w_rsi: float = 0.35,
    w_atr: float = 0.30,
    rsi_ob: float = 70,
    rsi_rel: float = 65,
    atr_k: float = 0.5,
) -> float:
    """현재 봉 기준 매도 점수 0~100."""
    d = compute_sell_score(df, w_ma, w_rsi, w_atr, rsi_ob, rsi_rel, atr_k)
    if d.empty or pd.isna(d["sell_score"].iloc[-1]):
        return 50.0
    return float(d["sell_score"].iloc[-1])


def save_golden_params(params: dict, metrics: Optional[dict] = None) -> None:
    """최적화된 파라미터 저장."""
    ROOT.joinpath("data").mkdir(parents=True, exist_ok=True)
    payload = {"params": params, "metrics": metrics or {}}
    GOLDEN_PARAMS_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def load_golden_params() -> Tuple[dict, dict]:
    """저장된 파라미터 로드. 없으면 기본값."""
    default_p = dict(w_ma=0.35, w_rsi=0.35, w_atr=0.30, rsi_ob=70, rsi_rel=65, atr_k=0.5, score_threshold=55)
    if not GOLDEN_PARAMS_PATH.exists():
        return default_p, {}
    try:
        data = json.loads(GOLDEN_PARAMS_PATH.read_text(encoding="utf-8"))
        return data.get("params", default_p), data.get("metrics", {})
    except Exception:
        return default_p, {}


def valuation_vs_volatility(df: pd.DataFrame) -> str:
    """역사적 변동성 대비 현재 가격 국면. 저평가/고평가/중립."""
    if df is None or len(df) < 30:
        return "중립"
    ret = df["close"].pct_change().dropna()
    vol_30 = ret.tail(30).std() * (252 ** 0.5) * 100  # 연환산 변동성 %
    current = df["close"].iloc[-1]
    ma20 = df["close"].tail(20).mean()
    z = (current - ma20) / (df["close"].tail(20).std() or 1e-10)
    if z < -0.5:
        return "역사적 변동성 대비 현재 가격은 저평가 국면입니다"
    if z > 0.5:
        return "역사적 변동성 대비 현재 가격은 고평가 국면입니다"
    return "역사적 변동성 대비 현재 가격은 중립 수준입니다"
