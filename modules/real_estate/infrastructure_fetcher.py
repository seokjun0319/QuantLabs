# -*- coding: utf-8 -*-
"""공공데이터 인프라 (지하철, 학교, IC) - 확장 가능 모듈."""
from __future__ import annotations

import pandas as pd


def get_infrastructure_data(
    category: str,
    region: str | None = None,
    bounds: tuple[float, float, float, float] | None = None,
) -> pd.DataFrame:
    """category: subway | school | ic | env"""
    if category == "subway":
        return _get_subway_data()
    if category == "school":
        return _get_school_data()
    if category == "ic":
        return _get_ic_data()
    if category == "env":
        return _get_env_data()
    return pd.DataFrame()


def _get_subway_data() -> pd.DataFrame:
    demos = [
        {"name": "강남역", "line": "2호선", "lat": 37.4979, "lon": 127.0276},
        {"name": "역삼역", "line": "2호선", "lat": 37.5006, "lon": 127.0366},
        {"name": "선릉역", "line": "2호선", "lat": 37.5045, "lon": 127.0490},
        {"name": "삼성역", "line": "2호선", "lat": 37.5088, "lon": 127.0632},
    ]
    return pd.DataFrame(demos)


def _get_school_data() -> pd.DataFrame:
    demos = [
        {"name": "OO초등학교", "level": "초등", "lat": 37.5000, "lon": 127.0300},
        {"name": "OO중학교", "level": "중등", "lat": 37.5020, "lon": 127.0350},
    ]
    return pd.DataFrame(demos)


def _get_ic_data() -> pd.DataFrame:
    demos = [
        {"name": "강남IC", "highway": "경부고속", "lat": 37.4700, "lon": 127.0900},
    ]
    return pd.DataFrame(demos)


def _get_env_data() -> pd.DataFrame:
    demos = [
        {"name": "OO공원", "type": "공원", "lat": 37.5100, "lon": 127.0400},
    ]
    return pd.DataFrame(demos)


def get_supply_data(region: str) -> pd.DataFrame:
    """입주 예정 물량 (향후 2~3년)."""
    demos = [
        {"year": 2025, "month": 6, "complex_name": "예정단지A", "households": 500},
        {"year": 2025, "month": 12, "complex_name": "예정단지B", "households": 800},
        {"year": 2026, "month": 6, "complex_name": "예정단지C", "households": 1200},
    ]
    return pd.DataFrame(demos)
