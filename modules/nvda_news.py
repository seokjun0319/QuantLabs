# -*- coding: utf-8 -*-
"""
엔비디아(NVIDIA) 관련 뉴스 RSS 클리핑.
Google News RSS 검색으로 최신 5건 수집 + Gemini 한글 번역/요약(선택).
"""
from __future__ import annotations

import os
import re
import xml.etree.ElementTree as ET
from typing import Optional

import requests

# Google News RSS: NVIDIA / NVDA 관련 검색 (영문)
NVDA_RSS_URL = (
    "https://news.google.com/rss/search?"
    "q=NVIDIA+OR+NVDA+stock&hl=en-US&gl=US&ceid=US:en"
)
TIMEOUT = 10
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; rv:91.0) Gecko/20100101"


def _text(el: Optional[ET.Element]) -> str:
    if el is None:
        return ""
    return (el.text or "").strip() + "".join((t or "") for t in el.itertext() if t and t != (el.text or "")).strip()


def _find_any(parent: ET.Element, *tags: str) -> Optional[ET.Element]:
    for t in tags:
        el = parent.find(t)
        if el is not None:
            return el
        # namespace
        for child in parent:
            if child.tag.endswith("}" + t) or child.tag == t:
                return child
    return None


def get_nvda_rss_news(limit: int = 5) -> list[dict]:
    """
    RSS에서 엔비디아 관련 뉴스 limit건 수집.
    Returns: [{"title": str, "link": str, "date": str, "snippet": str}, ...]
    """
    out: list[dict] = []
    try:
        r = requests.get(
            NVDA_RSS_URL,
            timeout=TIMEOUT,
            headers={"User-Agent": USER_AGENT},
        )
        r.raise_for_status()
        root = ET.fromstring(r.content)
    except Exception:
        return out

    # RSS: channel > item  또는  Atom: entry (네임스페이스 무시)
    def local_tag(e: ET.Element) -> str:
        return e.tag.split("}")[-1] if "}" in str(e.tag) else e.tag

    items: list[ET.Element] = []
    for node in [root] + list(root):
        for child in node:
            if local_tag(child) == "item" or local_tag(child) == "entry":
                items.append(child)
    items = items[:limit]

    for item in items:
        title_el = _find_any(item, "title")
        link_el = _find_any(item, "link")
        pub_el = _find_any(item, "pubDate") or _find_any(item, "updated")
        desc_el = _find_any(item, "description") or _find_any(item, "summary")
        title = _text(title_el) if title_el is not None else ""
        if not title:
            continue
        link = ""
        if link_el is not None:
            link = link_el.get("href", "") or _text(link_el)
        date_str = _text(pub_el)[:16] if pub_el is not None else ""
        snippet = _text(desc_el) if desc_el is not None else ""
        if len(snippet) > 120:
            snippet = snippet[:120] + "..."
        out.append({"title": title, "link": link, "date": date_str, "snippet": snippet})
    return out


def _get_gemini_api_key() -> str:
    """Streamlit Cloud: st.secrets['GEMINI_API_KEY'] 우선, 로컬: .env."""
    try:
        import streamlit as _st
        k = _st.secrets.get("GEMINI_API_KEY", "")
        if k:
            return (k or "").strip()
    except Exception:
        pass
    return (os.environ.get("GEMINI_API_KEY", "") or "").strip()


def _add_korean_via_gemini(news: list[dict]) -> None:
    """news 리스트 각 항목에 title_kr, summary_kr 필드 추가. 실패 시 무시."""
    if not news:
        return
    api_key = _get_gemini_api_key()
    if not api_key:
        return
    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-1.5-flash")
        lines = []
        for i, n in enumerate(news, 1):
            t = (n.get("title") or "")[:200]
            s = (n.get("snippet") or "")[:300]
            lines.append(f"[{i}] TITLE: {t}")
            lines.append(f"[{i}] SNIPPET: {s}")
        prompt = (
            "Below are 5 news items. For each [N] TITLE and [N] SNIPPET, reply with exactly two lines per item:\n"
            "N제목: (Korean translation of title only)\n"
            "N요약: (One short Korean summary sentence of the snippet, or '-' if empty)\n"
            "No other text. Use N=1,2,3,4,5.\n\n" + "\n".join(lines)
        )
        response = model.generate_content(prompt)
        text = (response.text or "").strip()
        for n in news:
            n["title_kr"] = ""
            n["summary_kr"] = ""
        for i in range(1, min(6, len(news) + 1)):
            m1 = re.search(rf"{i}\s*제목\s*[:\s]+(.+?)(?=\n\d\s*제목|\n\d요약|$)", text, re.DOTALL)
            m2 = re.search(rf"{i}\s*요약\s*[:\s]+(.+?)(?=\n\d\s*제목|\n\d\s*요약|$)", text, re.DOTALL)
            title_kr = (m1.group(1).strip().split("\n")[0][:80]) if m1 else ""
            summary_kr = (m2.group(1).strip().split("\n")[0][:120]) if m2 else ""
            news[i - 1]["title_kr"] = title_kr or ""
            news[i - 1]["summary_kr"] = summary_kr or ""
    except Exception:
        pass


def add_korean_to_news(news: list[dict]) -> None:
    """뉴스 리스트에 title_kr, summary_kr 추가 (Gemini 사용, API 키 있을 때만)."""
    _add_korean_via_gemini(news)
