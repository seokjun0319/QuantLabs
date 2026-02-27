# -*- coding: utf-8 -*-
"""
네이버 지도 API 연동 — 지도 위 마커·말풍선(호갱노노 스타일)
NAVER_CLIENT_ID (Maps) 필요. st.components.v1.html로 JavaScript SDK 임베드.
"""
from __future__ import annotations

import json
from typing import Any

import streamlit as st
import streamlit.components.v1 as components


def _get_naver_map_client_id() -> str:
    """네이버 지도용 Client ID (NCP Maps)."""
    try:
        cid = st.secrets.get("NAVER_MAP_CLIENT_ID", "") or st.secrets.get("NAVER_CLIENT_ID", "")
        if cid:
            return cid
    except Exception:
        pass
    import os
    return os.getenv("NAVER_MAP_CLIENT_ID", "") or os.getenv("NAVER_CLIENT_ID", "")


def render_naver_map(
    markers: list[dict[str, Any]] | None = None,
    center_lat: float = 37.5665,
    center_lon: float = 126.9780,
    zoom: int = 14,
    height: int = 500,
    show_infra: dict[str, bool] | None = None,
) -> None:
    """
    네이버 지도 렌더링. 아파트 단지별 실거래가 말풍선 표시.
    markers: [{"lat", "lon", "label", "price", "name", "specs", ...}, ...]
    show_infra: {"subway": True, "school": True, "ic": False}
    """
    markers = markers or []
    client_id = _get_naver_map_client_id()
    show_infra = show_infra or {}

    html = _build_map_html(
        client_id=client_id,
        markers=markers,
        center_lat=center_lat,
        center_lon=center_lon,
        zoom=zoom,
        height=height,
        show_infra=show_infra,
    )
    components.html(html, height=height + 50, scrolling=False)


def _build_map_html(
    client_id: str,
    markers: list[dict],
    center_lat: float,
    center_lon: float,
    zoom: int,
    height: int,
    show_infra: dict[str, bool],
) -> str:
    """네이버 지도 JavaScript HTML 생성."""
    markers_js = json.dumps(markers, ensure_ascii=False)
    infra_js = json.dumps(show_infra, ensure_ascii=False)

    if not client_id:
        return _build_folium_fallback(markers, center_lat, center_lon, height)

    return f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <script type="text/javascript" src="https://openapi.map.naver.com/openapi/v3/maps.js?ncpClientId={client_id}"></script>
</head>
<body style="margin:0;padding:0;">
  <div id="map" style="width:100%;height:{height}px;"></div>
  <script>
    const markersData = {markers_js};
    const showInfra = {infra_js};
    const center = new naver.maps.LatLng({center_lat}, {center_lon});

    const map = new naver.maps.Map('map', {{
      center: center,
      zoom: {zoom},
      zoomControl: true
    }});

    markersData.forEach((m, i) => {{
      const pos = new naver.maps.LatLng(m.lat, m.lon);
      const marker = new naver.maps.Marker({{ position: pos, map: map }});
      const content = '<div style="padding:8px;min-width:120px;background:#fff;border:1px solid #ddd;border-radius:6px;font-size:12px;">' +
        '<b>' + (m.name || m.label || '') + '</b><br/>' +
        (m.price ? '<span style="color:#e74c3c;font-weight:bold;">' + m.price + '</span><br/>' : '') +
        (m.specs || '') + '</div>';
      naver.maps.Event.addListener(marker, 'click', function() {{
        new naver.maps.InfoWindow({{ content: content }}).open(map, marker);
      }});
    }});
  </script>
</body>
</html>
"""


def _build_folium_fallback(
    markers: list[dict],
    center_lat: float,
    center_lon: float,
    height: int,
) -> str:
    """네이버 API 미설정 시 Folium(OpenStreetMap) 폴백."""
    try:
        import folium
        m = folium.Map(location=[center_lat, center_lon], zoom_start=14)
        for mk in markers:
            lat = mk.get("lat", center_lat)
            lon = mk.get("lon", center_lon)
            name = mk.get("name", mk.get("label", ""))
            price = mk.get("price", "")
            specs = mk.get("specs", "")
            popup = f"<b>{name}</b><br/>{price}<br/>{specs}"
            folium.Marker([lat, lon], popup=popup).add_to(m)
        return m._repr_html_()
    except ImportError:
        return """
        <div style="padding:20px;text-align:center;background:#f8f9fa;border-radius:8px;">
          <p>지도 표시를 위해 네이버 지도 API 키 설정이 필요합니다.</p>
          <p>.streamlit/secrets.toml 에 NAVER_MAP_CLIENT_ID 를 추가하세요.</p>
          <p>또는 pip install folium 후 Folium 폴백을 사용할 수 있습니다.</p>
        </div>
        """
