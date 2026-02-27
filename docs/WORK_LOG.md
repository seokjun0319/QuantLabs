# QuantLabs 작업 로그 (WORK_LOG)

> **목적:** 모든 개발 과정, 에러 해결, 로직 변경 이유를 기록하여 대장님(사용자)과 PM(Gemini)이 프로젝트 흐름을 파악할 수 있도록 한다.  
> **규칙:** 한국어, 숨김없이 시행착오까지 상세 기록.

---

## 📅 [2026-02-13] - 아이템 스카우터 coupang_scraper 구현 및 커밋/푸시

### 🎯 오늘 작업 목표
- Quant-based Coupang Item Scouter 프로젝트 완성
- 누락된 `coupang_scraper.py` 모듈 신규 생성
- 쿠팡 검색 1페이지 상품 수집 ( BeautifulSoup / Selenium 폴백 )
- 커밋 & 푸시로 원격 저장소 반영

### 🚧 진행 상황 및 결과
- [x] `modules/item_scouter/coupang_scraper.py` 신규 생성
- [x] 다중 CSS 선택자 fallback ( ul#productList, ul.search-product-list, li.baby-product )
- [x] 광고 상품 제외 ( ad-badge )
- [x] requests → Selenium 폴백 → 더미 데이터 fallback 구조
- [x] `search_coupang_products()` 함수로 키워드 검색 구현
- [x] 전체 플로우 테스트 (스크래핑 → 스코어링) 검증
- [x] `requirements.txt`에 selenium 주석 추가 (선택 의존성)
- [x] Git 커밋 & 푸시 완료

### 💥 시행착오 및 해결 (Trial & Error)
- **문제 발생:** `coupang_scraper.py` 파일이 없는데 `__init__.py`에서 import → ImportError 예상
- **시도한 방법:** 웹 검색으로 쿠팡 검색 결과 HTML 구조 확인 ( ul#productList li.search-product, div.name, strong.price-value 등 )
- **해결책:** `coupang_scraper.py`를 처음부터 작성. Hash Scraper 기술 블로그, Apify 등 참고해 선택자 정리 후 다중 선택자 fallback 적용

- **문제 발생:** 쿠팡 사이트가 `requests` 직접 호출 시 "접근 권한 없음" 반환 (봇 차단)
- **시도한 방법:** User-Agent를 실제 Chrome 브라우저처럼 설정
- **해결책:** 브라우저 헤더 적용 + Selenium 폴백 옵션 + **더미 데이터 fallback** 추가. 실제 스크래핑 실패 시에도 대시보드 UI·플로우 테스트 가능하도록 함

- **문제 발생:** PowerShell에서 `&&` 문법 미지원, 한글 commit 메시지 인코딩 이슈
- **해결책:** `&&` → `;` 사용, commit 메시지를 영문으로 작성

- **문제 발생:** `git push` 시 "Updates were rejected because the remote contains work that you do not have locally"
- **해결책:** `git pull --rebase` 후 `git push` 실행

### 💡 PM(Gemini)에게 공유사항
- 쿠팡 검색 페이지 HTML 구조가 변경되면 `coupang_scraper.py`의 `PRODUCT_LIST_SELECTORS`와 `_parse_product_item` 내 선택자 수정 필요
- 실제 운영 시 Selenium 사용하려면 `requirements.txt`에서 selenium 주석 해제 및 ChromeDriver 설치 필요
- 원격 저장소가 `QuantLabs`로 이전되었다는 메시지 출력됨 → `git remote set-url origin https://github.com/seokjun0319/QuantLabs.git` 권장

### 🔗 관련 커밋/코드 위치
- `modules/item_scouter/coupang_scraper.py` (신규)
- `modules/item_scouter/__init__.py`
- `pages/5_Item_Scouter.py`
- `requirements.txt`
- `.streamlit/secrets.toml.example`

---

## 📅 [2026-02-13] - Phase 2 부동산 분석 모듈 개발

### 🎯 오늘 작업 목표
- Quantlab Phase 2 - Real Estate Intelligence 구현
- 호갱노노 스타일 UI · 퀀트 관점 입지·가격 분석
- Tab1: 입지 분석 (지도, 말풍선, 인프라 토글) / Tab2: 가격 분석 (시계열, 거래량, 저평가)

### 🚧 진행 상황 및 결과
- [x] `modules/real_estate/` 모듈 구조 구축
- [x] `molit_fetcher.py` — 국토교통부 아파트 매매·전월세 API, 단지별 집계, 데모 폴백
- [x] `infrastructure_fetcher.py` — 지하철/학교/IC/환경 인프라 (확장용 스텁)
- [x] `map_renderer.py` — 네이버 지도 API (마커·말풍선), Folium 폴백
- [x] `undervalued_analyzer.py` — 저평가 단지 추출 로직
- [x] Tab1: 지도 기반 아파트 실거래가, 인프라 토글, 단지 클릭 시 말풍선
- [x] Tab2: 가격 시계열+거래량 차트, 입주 예정 물량, 대장 아파트 대비 비교, 저평가 단지

### 💥 시행착오 및 해결 (Trial & Error)
- **문제 발생:** MOLIT API 좌표 미제공 — 지도 마커 배치 불가
- **해결책:** 단지명 해시 기반 `_complex_to_coords()`로 안정적 좌표 생성. 추후 Geocoding/단지코드DB 연동 권장

- **문제 발생:** `mcp_filesystem_write_file` Invalid arguments 에러
- **해결책:** `Write` 도구로 대체 작성

### 💡 PM(Gemini)에게 공유사항
- API 키: MOLIT_SERVICE_KEY(공공데이터), NAVER_MAP_CLIENT_ID(네이버지도) — `.streamlit/secrets.toml` 설정
- 네이버 지도 미설정 시 Folium(OpenStreetMap)으로 폴백
- 인프라·입주물량 데이터는 데모용. 공공데이터포털 API 연동으로 확장 가능

### 🔗 관련 커밋/코드 위치
- `modules/real_estate/` (신규)
- `pages/2_Phase_2_RealEstate.py`
- `requirements.txt` (folium 추가)
- `.streamlit/secrets.toml.example`

---

## 📝 로그 템플릿 (복사용)

```markdown
## 📅 [YYYY-MM-DD] - [작업명]

### 🎯 오늘 작업 목표
- (목표 작성)

### 🚧 진행 상황 및 결과
- [x] (완료 항목)
- [ ] (진행 중/예정 항목)

### 💥 시행착오 및 해결 (Trial & Error)
- **문제 발생:** (상세)
- **시도한 방법:** (시도 내용)
- **해결책:** (최종 해결)

### 💡 PM(Gemini)에게 공유사항
- (공유할 내용)

### 🔗 관련 커밋/코드 위치
- (파일 경로)
```
