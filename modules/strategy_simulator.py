# -*- coding: utf-8 -*-
"""
QuantLabs 전략 시뮬레이터 — Strategy Pattern.
BaseStrategy 상속 5종: TrendFollowing, MeanReversion, Momentum, Value, Arbitrage.
모든 전략은 run(df, **kwargs) → { equity_curve, returns, mdd, sharpe_ratio, cagr } 반환.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

import numpy as np
import pandas as pd

TRADING_DAYS = 252


def _metrics_from_equity(equity: pd.Series) -> dict:
    """equity curve(1부터 시작)에서 returns, mdd, sharpe, cagr 계산."""
    if equity is None or len(equity) < 2:
        return {"returns": 0.0, "mdd": 0.0, "sharpe_ratio": 0.0, "cagr": 0.0}
    total_return = float(equity.iloc[-1] / equity.iloc[0] - 1.0)
    n_days = len(equity)
    cagr = (1 + total_return) ** (TRADING_DAYS / n_days) - 1.0 if n_days else 0.0
    daily_ret = equity.pct_change().dropna()
    std = daily_ret.std()
    sharpe = (daily_ret.mean() / std * np.sqrt(TRADING_DAYS)) if std and std > 1e-10 else 0.0
    peak = equity.cummax()
    dd = (equity - peak) / peak.replace(0, 1e-10)
    mdd = float(abs(dd.min()))
    return {
        "returns": total_return,
        "mdd": mdd,
        "sharpe_ratio": float(sharpe),
        "cagr": cagr,
    }


class BaseStrategy(ABC):
    """전략 시뮬레이터 공통 베이스. display_name은 UI 표시용."""

    display_name: str = "Base"

    @abstractmethod
    def run(self, df: pd.DataFrame, **kwargs) -> dict:
        """
        df: OHLC (open, high, low, close). Arbitrage는 df_bench 별도 인자.
        Returns: equity_curve (Series, 1부터 시작), returns, mdd, sharpe_ratio, cagr
        """
        pass


class TrendFollowingStrategy(BaseStrategy):
    """이동평균(MA) 크로스 기반 추세추종."""

    display_name = "추세추종 (MA 크로스)"

    def run(
        self,
        df: pd.DataFrame,
        fast: int = 9,
        slow: int = 21,
        **kwargs,
    ) -> dict:
        if df is None or len(df) < slow + 5:
            return {"equity_curve": pd.Series(dtype=float), "returns": 0.0, "mdd": 0.0, "sharpe_ratio": 0.0, "cagr": 0.0}
        d = df[["close"]].copy()
        d["ma_fast"] = d["close"].ewm(span=fast, adjust=False).mean()
        d["ma_slow"] = d["close"].ewm(span=slow, adjust=False).mean()
        d["signal"] = (d["ma_fast"] > d["ma_slow"]).astype(int)
        d["ret"] = d["close"].pct_change()
        d["strategy_ret"] = d["signal"].shift(1).fillna(0) * d["ret"]
        d = d.dropna(subset=["strategy_ret"])
        equity = (1 + d["strategy_ret"]).cumprod()
        equity = equity.reindex(d.index).ffill().fillna(1.0)
        m = _metrics_from_equity(equity)
        return {"equity_curve": equity, **m}


class MeanReversionStrategy(BaseStrategy):
    """볼린저 밴드 & RSI 기반 평균회귀."""

    display_name = "평균회귀 (볼린저+RSI)"

    @staticmethod
    def _rsi(series: pd.Series, period: int = 14) -> pd.Series:
        delta = series.diff()
        gain = delta.clip(lower=0)
        loss = (-delta).clip(lower=0)
        avg_gain = gain.rolling(period).mean()
        avg_loss = loss.rolling(period).mean()
        rs = avg_gain / avg_loss.replace(0, 1e-10)
        return 100 - (100 / (1 + rs))

    def run(
        self,
        df: pd.DataFrame,
        bb_period: int = 20,
        bb_std: float = 2.0,
        rsi_period: int = 14,
        rsi_oversold: float = 30,
        rsi_overbought: float = 70,
        **kwargs,
    ) -> dict:
        if df is None or len(df) < max(bb_period, rsi_period) + 5:
            return {"equity_curve": pd.Series(dtype=float), "returns": 0.0, "mdd": 0.0, "sharpe_ratio": 0.0, "cagr": 0.0}
        d = df[["close"]].copy()
        d["ma"] = d["close"].rolling(bb_period).mean()
        d["std"] = d["close"].rolling(bb_period).std().replace(0, 1e-10)
        d["upper"] = d["ma"] + bb_std * d["std"]
        d["lower"] = d["ma"] - bb_std * d["std"]
        d["rsi"] = self._rsi(d["close"], rsi_period)
        d["ret"] = d["close"].pct_change()
        # Long when below lower band & RSI oversold; exit when above upper or RSI overbought
        position = 0
        positions = []
        for i in range(len(d)):
            row = d.iloc[i]
            if row["close"] <= row["lower"] and row["rsi"] <= rsi_oversold:
                position = 1
            elif row["close"] >= row["upper"] or row["rsi"] >= rsi_overbought:
                position = 0
            positions.append(position)
        d["position"] = positions
        d["strategy_ret"] = d["position"].shift(1).fillna(0) * d["ret"]
        d = d.dropna(subset=["strategy_ret"])
        if len(d) < 2:
            return {"equity_curve": pd.Series(dtype=float), "returns": 0.0, "mdd": 0.0, "sharpe_ratio": 0.0, "cagr": 0.0}
        equity = (1 + d["strategy_ret"]).cumprod()
        equity = equity.reindex(d.index).ffill().fillna(1.0)
        m = _metrics_from_equity(equity)
        return {"equity_curve": equity, **m}


class MomentumStrategy(BaseStrategy):
    """ROC(Rate of Change) 및 모멘텀 스코어 기반."""

    display_name = "모멘텀 (ROC)"

    def run(
        self,
        df: pd.DataFrame,
        roc_period: int = 10,
        **kwargs,
    ) -> dict:
        if df is None or len(df) < roc_period + 5:
            return {"equity_curve": pd.Series(dtype=float), "returns": 0.0, "mdd": 0.0, "sharpe_ratio": 0.0, "cagr": 0.0}
        d = df[["close"]].copy()
        d["roc"] = (d["close"] - d["close"].shift(roc_period)) / d["close"].shift(roc_period).replace(0, 1e-10)
        d["ret"] = d["close"].pct_change()
        d["signal"] = (d["roc"] > 0).astype(int)
        d["strategy_ret"] = d["signal"].shift(1).fillna(0) * d["ret"]
        d = d.dropna(subset=["strategy_ret"])
        equity = (1 + d["strategy_ret"]).cumprod()
        equity = equity.reindex(d.index).ffill().fillna(1.0)
        m = _metrics_from_equity(equity)
        return {"equity_curve": equity, **m}


class ValueStrategy(BaseStrategy):
    """P/E 없음 → 고점 대비 하락폭(Drawdown) 크고 변동성 낮은 구간에서 분할 매수."""

    display_name = "가치 (DD+저변동성)"

    def run(
        self,
        df: pd.DataFrame,
        dd_lookback: int = 60,
        vol_lookback: int = 20,
        dd_threshold: float = 0.10,
        vol_quantile: float = 0.25,
        **kwargs,
    ) -> dict:
        if df is None or len(df) < max(dd_lookback, vol_lookback) + 5:
            return {"equity_curve": pd.Series(dtype=float), "returns": 0.0, "mdd": 0.0, "sharpe_ratio": 0.0, "cagr": 0.0}
        d = df[["close"]].copy()
        d["high_roll"] = d["close"].rolling(dd_lookback).max()
        d["drawdown"] = (d["close"] - d["high_roll"]) / d["high_roll"].replace(0, 1e-10)
        d["ret"] = d["close"].pct_change()
        d["vol"] = d["ret"].rolling(vol_lookback).std()
        d["vol_rank"] = d["vol"].rank(pct=True)
        d["weight"] = 0.0
        mask = (d["drawdown"] < -dd_threshold) & (d["vol_rank"] <= vol_quantile)
        mask = mask.fillna(False)
        d.loc[mask, "weight"] = np.minimum(1.0, (-d.loc[mask, "drawdown"] * 2).values)
        d["strategy_ret"] = d["weight"].shift(1).fillna(0) * d["ret"]
        d = d.dropna(subset=["strategy_ret"])
        if len(d) < 2:
            return {"equity_curve": pd.Series(dtype=float), "returns": 0.0, "mdd": 0.0, "sharpe_ratio": 0.0, "cagr": 0.0}
        equity = (1 + d["strategy_ret"]).cumprod()
        equity = equity.reindex(d.index).ffill().fillna(1.0)
        m = _metrics_from_equity(equity)
        return {"equity_curve": equity, **m}


class ArbitrageStrategy(BaseStrategy):
    """메인 티커 vs 상관 보조 티커 스프레드 역매매. df_bench 필수."""

    display_name = "차익거래 (스프레드)"

    def run(
        self,
        df: pd.DataFrame,
        df_bench: Optional[pd.DataFrame] = None,
        spread_window: int = 20,
        z_entry: float = 2.0,
        **kwargs,
    ) -> dict:
        if df is None or df_bench is None or len(df) < spread_window + 5 or len(df_bench) < spread_window + 5:
            return {"equity_curve": pd.Series(dtype=float), "returns": 0.0, "mdd": 0.0, "sharpe_ratio": 0.0, "cagr": 0.0}
        # Align by index
        common = df.index.intersection(df_bench.index).sort_values()
        if len(common) < spread_window + 5:
            return {"equity_curve": pd.Series(dtype=float), "returns": 0.0, "mdd": 0.0, "sharpe_ratio": 0.0, "cagr": 0.0}
        c_main = df.loc[common, "close"]
        c_bench = df_bench.loc[common, "close"]
        r_main = c_main.pct_change()
        r_bench = c_bench.pct_change()
        # Rolling beta: beta = cov(main, bench) / var(bench)
        beta_roll = r_main.rolling(spread_window).cov(r_bench) / r_bench.rolling(spread_window).var().replace(0, 1e-10)
        beta_roll = beta_roll.ffill().fillna(1.0)
        spread = c_main - beta_roll * c_bench
        spread_mean = spread.rolling(spread_window).mean()
        spread_std = spread.rolling(spread_window).std().replace(0, 1e-10)
        z = (spread - spread_mean) / spread_std
        z_prev = z.shift(1)
        sig = np.where(z_prev > z_entry, -1, np.where(z_prev < -z_entry, 1, 0))
        sig = pd.Series(sig, index=common).replace(0, np.nan).ffill().fillna(0)
        strategy_ret = sig * (r_main - beta_roll * r_bench)
        strategy_ret = strategy_ret.fillna(0)
        equity = (1 + strategy_ret).cumprod()
        equity = equity.reindex(common).ffill().fillna(1.0)
        m = _metrics_from_equity(equity)
        return {"equity_curve": equity, **m}


def run_buy_and_hold(df: pd.DataFrame) -> dict:
    """단순 보유(B&H) 수익 곡선 및 메트릭."""
    if df is None or len(df) < 2:
        return {"equity_curve": pd.Series(dtype=float), "returns": 0.0, "mdd": 0.0, "sharpe_ratio": 0.0, "cagr": 0.0}
    eq = (1 + df["close"].pct_change().fillna(0)).cumprod()
    m = _metrics_from_equity(eq)
    return {"equity_curve": eq, **m}


# ----- 고급 메타 전략 (Advanced Meta-Strategies) -----

def _atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Average True Range."""
    high_low = df["high"] - df["low"]
    high_close = (df["high"] - df["close"].shift(1)).abs()
    low_close = (df["low"] - df["close"].shift(1)).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    return tr.rolling(period).mean()


def _adx(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """ADX(period). +DI, -DI, DX의 14일 스무딩."""
    high, low, close = df["high"], df["low"], df["close"]
    plus_dm = high.diff()
    minus_dm = -low.diff()
    plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0.0)
    minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0.0)
    tr = pd.concat([high - low, (high - close.shift(1)).abs(), (low - close.shift(1)).abs()], axis=1).max(axis=1)
    atr = tr.rolling(period).mean().replace(0, 1e-10)
    plus_di = 100 * (plus_dm.rolling(period).mean() / atr)
    minus_di = 100 * (minus_dm.rolling(period).mean() / atr)
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, 1e-10)
    adx = dx.rolling(period).mean()
    return adx


class VolTargetingStrategy(BaseStrategy):
    """
    변동성 타겟팅: 추세추종 시그널 + 최근 20일 ATR이 높으면 포지션 사이즈 반비례 축소.
    Target Volatility = 연 20%.
    """

    display_name = "VolTargeting (변동성 타겟)"

    def run(
        self,
        df: pd.DataFrame,
        fast: int = 9,
        slow: int = 21,
        atr_period: int = 20,
        target_vol_annual: float = 0.20,
        **kwargs,
    ) -> dict:
        if df is None or len(df) < max(slow, atr_period) + 10:
            return {"equity_curve": pd.Series(dtype=float), "returns": 0.0, "mdd": 0.0, "sharpe_ratio": 0.0, "cagr": 0.0}
        d = df[["open", "high", "low", "close"]].copy()
        d["ma_fast"] = d["close"].ewm(span=fast, adjust=False).mean()
        d["ma_slow"] = d["close"].ewm(span=slow, adjust=False).mean()
        d["signal"] = (d["ma_fast"] > d["ma_slow"]).astype(int)
        d["ret"] = d["close"].pct_change()
        atr = _atr(d, atr_period)
        d["atr_pct"] = (atr / d["close"]).replace(0, 1e-10)
        target_daily_vol = target_vol_annual / np.sqrt(TRADING_DAYS)
        d["vol_annualized"] = d["atr_pct"] * np.sqrt(TRADING_DAYS)
        d["weight"] = (target_vol_annual / d["vol_annualized"]).clip(0, 1.0)
        d["strategy_ret"] = d["signal"].shift(1).fillna(0) * d["weight"].shift(1).fillna(0) * d["ret"]
        d = d.dropna(subset=["strategy_ret"])
        if len(d) < 2:
            return {"equity_curve": pd.Series(dtype=float), "returns": 0.0, "mdd": 0.0, "sharpe_ratio": 0.0, "cagr": 0.0}
        equity = (1 + d["strategy_ret"]).cumprod()
        equity = equity.reindex(d.index).ffill().fillna(1.0)
        m = _metrics_from_equity(equity)
        return {"equity_curve": equity, **m}


class DualMomentumStrategy(BaseStrategy):
    """
    듀얼 모멘텀: (메인 3개월 수익률 > 0) AND (메인 3개월 수익률 > 벤치마크 3개월 수익률) 일 때만 매수, 아니면 전량 현금.
    벤치마크 기본 SPY.
    """

    display_name = "DualMomentum (듀얼 모멘텀)"

    def run(
        self,
        df: pd.DataFrame,
        df_bench: Optional[pd.DataFrame] = None,
        lookback_days: int = 63,
        **kwargs,
    ) -> dict:
        if df is None or len(df) < lookback_days + 5:
            return {"equity_curve": pd.Series(dtype=float), "returns": 0.0, "mdd": 0.0, "sharpe_ratio": 0.0, "cagr": 0.0}
        if df_bench is None or len(df_bench) < lookback_days + 5:
            return {"equity_curve": pd.Series(dtype=float), "returns": 0.0, "mdd": 0.0, "sharpe_ratio": 0.0, "cagr": 0.0}
        common = df.index.intersection(df_bench.index).sort_values()
        if len(common) < lookback_days + 5:
            return {"equity_curve": pd.Series(dtype=float), "returns": 0.0, "mdd": 0.0, "sharpe_ratio": 0.0, "cagr": 0.0}
        c_main = df.loc[common, "close"]
        c_bench = df_bench.loc[common, "close"]
        ret_main = c_main.pct_change()
        main_3m = (c_main / c_main.shift(lookback_days) - 1.0)
        bench_3m = (c_bench / c_bench.shift(lookback_days) - 1.0)
        position = ((main_3m > 0) & (main_3m > bench_3m)).astype(int)
        position = position.shift(1).fillna(0)
        strategy_ret = position * ret_main
        strategy_ret = strategy_ret.fillna(0)
        equity = (1 + strategy_ret).cumprod()
        equity = equity.reindex(common).ffill().fillna(1.0)
        m = _metrics_from_equity(equity)
        return {"equity_curve": equity, **m}


class HybridStrategy(BaseStrategy):
    """
    국면 전환 (Regime Switching): 200일선 위면 추세추종, 아래면 평균회귀.
    상승장엔 올라타고 하락장엔 줍줍.
    """

    display_name = "Hybrid (하평상추)"

    def run(
        self,
        df: pd.DataFrame,
        fast: int = 9,
        slow: int = 21,
        bb_period: int = 20,
        bb_std: float = 2.0,
        rsi_period: int = 14,
        rsi_oversold: float = 30,
        rsi_overbought: float = 70,
        **kwargs,
    ) -> dict:
        if df is None or len(df) < 220:
            return {"equity_curve": pd.Series(dtype=float), "returns": 0.0, "mdd": 0.0, "sharpe_ratio": 0.0, "cagr": 0.0}
        d = df[["close"]].copy()
        d["ma200"] = d["close"].rolling(200).mean()
        d["regime"] = (d["close"] > d["ma200"]).fillna(False)
        d["ma_fast"] = d["close"].ewm(span=fast, adjust=False).mean()
        d["ma_slow"] = d["close"].ewm(span=slow, adjust=False).mean()
        d["signal_tf"] = (d["ma_fast"] > d["ma_slow"]).astype(int)
        d["ma"] = d["close"].rolling(bb_period).mean()
        d["std"] = d["close"].rolling(bb_period).std().replace(0, 1e-10)
        d["upper"] = d["ma"] + bb_std * d["std"]
        d["lower"] = d["ma"] - bb_std * d["std"]
        d["rsi"] = MeanReversionStrategy._rsi(d["close"], rsi_period)
        d["ret"] = d["close"].pct_change()
        position_mr = 0
        positions_mr = []
        for i in range(len(d)):
            row = d.iloc[i]
            if row["close"] <= row["lower"] and row["rsi"] <= rsi_oversold:
                position_mr = 1
            elif row["close"] >= row["upper"] or row["rsi"] >= rsi_overbought:
                position_mr = 0
            positions_mr.append(position_mr)
        d["signal_mr"] = positions_mr
        d["signal"] = np.where(d["regime"], d["signal_tf"], d["signal_mr"])
        d["strategy_ret"] = d["signal"].shift(1).fillna(0) * d["ret"]
        d = d.dropna(subset=["strategy_ret"])
        if len(d) < 2:
            return {"equity_curve": pd.Series(dtype=float), "returns": 0.0, "mdd": 0.0, "sharpe_ratio": 0.0, "cagr": 0.0}
        equity = (1 + d["strategy_ret"]).cumprod()
        equity = equity.reindex(d.index).ffill().fillna(1.0)
        m = _metrics_from_equity(equity)
        return {"equity_curve": equity, **m}


class ADXFilterStrategy(BaseStrategy):
    """
    ADX 스나이퍼: ADX(14) >= 25 일 때만 추세추종 진입 허용, 25 미만이면 강제 Hold Cash.
    """

    display_name = "ADXFilter (스나이퍼)"

    def run(
        self,
        df: pd.DataFrame,
        fast: int = 9,
        slow: int = 21,
        adx_period: int = 14,
        adx_threshold: float = 25.0,
        **kwargs,
    ) -> dict:
        if df is None or len(df) < max(slow, adx_period) + 10:
            return {"equity_curve": pd.Series(dtype=float), "returns": 0.0, "mdd": 0.0, "sharpe_ratio": 0.0, "cagr": 0.0}
        d = df[["open", "high", "low", "close"]].copy()
        d["ma_fast"] = d["close"].ewm(span=fast, adjust=False).mean()
        d["ma_slow"] = d["close"].ewm(span=slow, adjust=False).mean()
        d["signal_tf"] = (d["ma_fast"] > d["ma_slow"]).astype(int)
        d["adx"] = _adx(d, adx_period)
        d["signal"] = (d["signal_tf"] == 1) & (d["adx"] >= adx_threshold)
        d["signal"] = d["signal"].astype(int)
        d["ret"] = d["close"].pct_change()
        d["strategy_ret"] = d["signal"].shift(1).fillna(0) * d["ret"]
        d = d.dropna(subset=["strategy_ret"])
        if len(d) < 2:
            return {"equity_curve": pd.Series(dtype=float), "returns": 0.0, "mdd": 0.0, "sharpe_ratio": 0.0, "cagr": 0.0}
        equity = (1 + d["strategy_ret"]).cumprod()
        equity = equity.reindex(d.index).ffill().fillna(1.0)
        m = _metrics_from_equity(equity)
        return {"equity_curve": equity, **m}


# 전략 목록 (UI 선택용)
STRATEGY_CLASSES = [
    TrendFollowingStrategy,
    MeanReversionStrategy,
    MomentumStrategy,
    ValueStrategy,
    ArbitrageStrategy,
]

# 고급 메타 전략 (비교 탭에 포함) — 듀얼모멘텀 옆, ADX 위에 Hybrid 배치
META_STRATEGY_CLASSES = [
    VolTargetingStrategy,
    DualMomentumStrategy,
    HybridStrategy,
    ADXFilterStrategy,
]

# 전체 전략 (기본 5종 + 메타 3종) — UI 토글/비교용
ALL_STRATEGY_CLASSES = STRATEGY_CLASSES + META_STRATEGY_CLASSES


# ----- 데이터: yfinance 메인 + 벤치마크(비교군) 다운로드 -----

def fetch_ohlc(ticker: str, days: int = 365) -> pd.DataFrame:
    """yfinance로 단일 티커 OHLC (open, high, low, close) 다운로드."""
    try:
        import yfinance as yf
        df = yf.download(ticker, period=f"{days}d", interval="1d", progress=False, auto_adjust=True, threads=False)
        if df is None or df.empty:
            return pd.DataFrame()
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [c[0].lower() if isinstance(c, tuple) else str(c).lower() for c in df.columns]
        else:
            df.columns = [str(c).lower() for c in df.columns]
        required = ["open", "high", "low", "close"]
        if not all(c in df.columns for c in required):
            return pd.DataFrame()
        return df[required].sort_index()
    except Exception:
        return pd.DataFrame()


def fetch_main_and_benchmark(
    main_ticker: str = "NVDA",
    benchmark_ticker: str = "AMD",
    days: int = 365,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    메인 티커 + 비교군(벤치마크) OHLC 다운로드. Arbitrage용.
    Returns (df_main, df_bench) — 인덱스 정렬만 하고 공통 구간 자르지는 않음(호출측에서 align).
    """
    df_main = fetch_ohlc(main_ticker, days)
    df_bench = fetch_ohlc(benchmark_ticker, days)
    return df_main, df_bench
