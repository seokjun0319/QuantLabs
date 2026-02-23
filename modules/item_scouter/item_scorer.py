# -*- coding: utf-8 -*-
"""
아이템 스코어링 — 리뷰 가속도 시뮬레이션 + 가격대(2~7만원) 100점 만점.
"""
from __future__ import annotations

import random
from typing import Any

# 가격대 필터 (원)
PRICE_MIN = 20_000
PRICE_MAX = 70_000


def _simulate_review_acceleration(review_count: int) -> float:
    """
    현재 리뷰 수 기준 리뷰 가속도 시뮬레이션.
    리뷰가 많고 비슷한 가격대 상품 대비 상대적 '유입 속도' 추정.
    """
    if review_count <= 0:
        return 0.0
    import math
    base = math.log1p(review_count)
    noise = random.uniform(0.9, 1.1)
    return base * noise


def _price_score(price: int) -> float:
    """가격대 2~7만원일수록 높은 점수. 5만원 전후가 최적."""
    if price < PRICE_MIN or price > PRICE_MAX:
        return 0.0
    mid = (PRICE_MIN + PRICE_MAX) / 2
    distance = abs(price - mid)
    max_dist = (PRICE_MAX - PRICE_MIN) / 2
    return max(0, 1.0 - distance / max_dist * 0.5)


def score_products(products: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    상품 리스트에 스코어(0~100) 및 리뷰 가속도 시뮬레이션 적용.
    가격대 2~7만원 필터, 리뷰 가속도 50점 + 가격 적합도 50점.
    """
    if not products:
        return []

    review_accels = [_simulate_review_acceleration(p.get("review_count", 0)) for p in products]
    max_accel = max(review_accels) if review_accels else 1.0

    scored = []
    for i, p in enumerate(products):
        price = p.get("price", 0) or 0
        if price < PRICE_MIN or price > PRICE_MAX:
            continue
        accel = review_accels[i] if i < len(review_accels) else 0
        accel_norm = (accel / max_accel) * 50 if max_accel > 0 else 0
        price_pts = _price_score(price) * 50
        total = min(100, round(accel_norm + price_pts, 1))
        p2 = dict(p)
        p2["review_acceleration"] = round(accel, 2)
        p2["score"] = total
        scored.append(p2)

    return sorted(scored, key=lambda x: x["score"], reverse=True)


def generate_hooking_point(product: dict[str, Any]) -> str:
    """쇼츠 제작용 후킹 포인트 문구 생성."""
    name = (product.get("name") or "")[:50]
    price = product.get("price", 0)
    reviews = product.get("review_count", 0)
    keyword = product.get("keyword", "")
    price_str = f"{price:,}원" if price else ""
    hook = f"[{keyword}] {name}"
    if price_str:
        hook += f" | {price_str}"
    if reviews > 0:
        hook += f" | 리뷰 {reviews:,}개"
    return hook[:120]
