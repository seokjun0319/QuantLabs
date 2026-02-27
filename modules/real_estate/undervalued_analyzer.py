# -*- coding: utf-8 -*-
"""
"입지는 최고인데 가격은 싼" 저평가 단지 추출 로직.
입지 점수(인프라 접근성) vs 가격 상대 비교로 스코어 산출.
"""
from __future__ import annotations

from typing import Any

import pandas as pd


def find_undervalued_complexes(
    complex_df: pd.DataFrame,
    infra_df: pd.DataFrame,
    location_scores: dict[str, float] | None = None,
) -> pd.DataFrame:
    """
    저평가 단지 추출.
    complex_df: 단지별 평균가격, 거래건수 등
    infra_df: 인근 인프라 (지하철 거리 등)
    location_scores: 단지별 입지 점수 (미입력 시 거래건수로 추정)
    """
    if complex_df.empty:
        return complex_df

    df = complex_df.copy()
    # 입지 점수 (0~100): 거래건수 기반 추정 또는 location_scores 사용
    if location_scores:
        df["입지점수"] = df["아파트명"].map(location_scores).fillna(50)
    else:
        max_cnt = df["거래건수"].max() or 1
        df["입지점수"] = (df["거래건수"] / max_cnt * 70 + 30).clip(0, 100)

    # 가격 백분위 (낮을수록 저렴)
    df["가격백분위"] = df["평균가격"].rank(pct=True) * 100
    # 저평가 점수: 입지 높고 가격 낮을수록 높음
    df["저평가점수"] = df["입지점수"] * (100 - df["가격백분위"]) / 100
    df = df.sort_values("저평가점수", ascending=False).reset_index(drop=True)
    return df
