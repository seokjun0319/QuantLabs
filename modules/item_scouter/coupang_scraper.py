# -*- coding: utf-8 -*-
"""
쿠팡 검색 스크래퍼 — 검색 1페이지 상품 수집.
BeautifulSoup 우선, 차단 시 Selenium 폴백. 쿠팡 HTML 구조 변경 시 selectors 수정 필요.
"""
from __future__ import annotations

import re
from typing import Any
from urllib.parse import quote_plus, urljoin

import requests
from bs4 import BeautifulSoup

# 쿠팡 검색 URL
COUPANG_SEARCH_BASE = "https://www.coupang.com/np/search"

# 실제 브라우저처럼 보이도록 (쿠팡 봇 차단 완화)
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer": "https://www.coupang.com/",
    "Upgrade-Insecure-Requests": "1",
}

# 상품 리스트 선택자 (우선순위: 위가 공식 구조에 가까움)
PRODUCT_LIST_SELECTORS = [
    "ul#productList li.search-product",
    "ul.search-product-list li.search-product",
    "li.baby-product",
]

# 광고 제외용 (광고 상품은 skip)
AD_BADGE_CLASS = "search-product__ad-badge"


def _parse_product_item(li: Any, base_url: str, keyword: str) -> dict[str, Any] | None:
    """단일 li 요소에서 상품 정보 추출."""
    # 광고 상품 제외
    if li.find(class_=re.compile(r"ad-badge|ad_badge")):
        return None

    # 상품명
    name_el = li.select_one(".name, .product-name")
    name = (name_el.get_text(strip=True) if name_el else "").strip()
    if not name:
        return None

    # 가격
    price_el = li.select_one(".price-value, strong.price-value, em.sale")
    price = 0
    if price_el:
        text = price_el.get_text(strip=True)
        nums = re.sub(r"[^\d]", "", text)
        if nums:
            price = int(nums)

    # 리뷰 수
    review_el = li.select_one(".rating-total-count, span.rating-total-count")
    review_count = 0
    if review_el:
        text = review_el.get_text(strip=True)
        nums = re.sub(r"[^\d]", "", text)
        if nums:
            review_count = int(nums)

    # 링크
    link_el = li.select_one("a.search-product-link, a.baby-product-link, a[href*='/products/']")
    href = ""
    product_id = ""
    if link_el and link_el.get("href"):
        href = link_el["href"]
        if not href.startswith("http"):
            href = urljoin(base_url, href)
        # product_id 추출 (예: /np/products/12345 -> 12345)
        m = re.search(r"/products/(\d+)", href)
        if m:
            product_id = m.group(1)

    return {
        "name": name,
        "price": price,
        "review_count": review_count,
        "url": href or "",
        "product_id": product_id,
        "keyword": keyword,
    }


def _fetch_with_requests(keyword: str, timeout: int = 15) -> str | None:
    """requests로 HTML fetch. 실패 시 None."""
    url = f"{COUPANG_SEARCH_BASE}?q={quote_plus(keyword)}"
    try:
        r = requests.get(url, headers=DEFAULT_HEADERS, timeout=timeout)
        if r.status_code == 200 and "접근" not in r.text and "permission" not in r.text.lower():
            return r.text
    except Exception:
        pass
    return None


def _fetch_with_selenium(keyword: str, timeout: int = 15) -> str | None:
    """Selenium으로 HTML fetch (JS 렌더링 대응). selenium 미설치 시 None."""
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
    except ImportError:
        return None

    url = f"{COUPANG_SEARCH_BASE}?q={quote_plus(keyword)}"
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument(f"user-agent={DEFAULT_HEADERS['User-Agent']}")

    driver = None
    try:
        driver = webdriver.Chrome(options=options)
        driver.get(url)
        # 상품 리스트 로딩 대기 (선택자 중 하나라도 나올 때까지)
        try:
            WebDriverWait(driver, min(timeout, 12)).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "ul#productList, li.search-product, li.baby-product, ul.search-product-list"))
            )
        except Exception:
            import time
            time.sleep(3)
        return driver.page_source
    except Exception:
        return None
    finally:
        if driver:
            driver.quit()


def _parse_html(html: str, keyword: str) -> list[dict[str, Any]]:
    """HTML에서 상품 목록 파싱."""
    soup = BeautifulSoup(html, "html.parser")
    items = []

    li_list = []
    for sel in PRODUCT_LIST_SELECTORS:
        li_list = soup.select(sel)
        if li_list:
            break

    for li in li_list:
        row = _parse_product_item(li, "https://www.coupang.com", keyword)
        if row:
            items.append(row)

    return items


def _get_demo_products(keyword: str) -> list[dict[str, Any]]:
    """스크래핑 실패 시 개발/테스트용 더미 데이터 반환."""
    import random
    demos = [
        {"name": f"[{keyword}] 샘플 상품 A", "price": 35000, "review_count": 120},
        {"name": f"[{keyword}] 샘플 상품 B", "price": 52000, "review_count": 340},
        {"name": f"[{keyword}] 샘플 상품 C", "price": 45000, "review_count": 89},
        {"name": f"[{keyword}] 샘플 상품 D", "price": 28000, "review_count": 210},
        {"name": f"[{keyword}] 샘플 상품 E", "price": 65000, "review_count": 56},
    ]
    for d in demos:
        d["price"] = int(d["price"] * random.uniform(0.95, 1.05))
        d["review_count"] = int(d["review_count"] * random.uniform(0.8, 1.2))
    return [
        {
            "name": p["name"],
            "price": p["price"],
            "review_count": max(0, p["review_count"]),
            "url": f"https://www.coupang.com/np/products/{random.randint(10000, 99999)}",
            "product_id": str(random.randint(10000, 99999)),
            "keyword": keyword,
        }
        for p in demos
    ]


def search_coupang_products(
    keyword: str,
    use_selenium: bool = True,
    use_demo_fallback: bool = True,
    timeout: int = 15,
) -> list[dict[str, Any]]:
    """
    키워드로 쿠팡 검색 1페이지 상품 수집.
    - use_selenium: True이면 requests 실패 시 Selenium 시도
    - use_demo_fallback: 둘 다 실패 시 더미 데이터 반환 (개발용)
    """
    html = _fetch_with_requests(keyword, timeout=timeout)
    if not html and use_selenium:
        html = _fetch_with_selenium(keyword, timeout=timeout)

    if html:
        items = _parse_html(html, keyword)
        if items:
            return items

    if use_demo_fallback:
        return _get_demo_products(keyword)
    return []
