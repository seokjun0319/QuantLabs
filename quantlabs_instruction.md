# -*- coding: utf-8 -*-
# QuantLabs 통신로 (PM 지시 사항)

**인코딩**: 이 파일은 UTF-8입니다. 이 파일을 읽거나 쓸 때는 반드시 `encoding="utf-8"`을 사용하세요.

> **역할**: PM(젬민이)의 지시 사항이 실시간으로 업데이트되는 통로입니다.  
> **Cursor 지시**: 이 파일(`quantlabs_instruction.md`)의 변화를 감시하고, 새로운 기획이나 수정 지시가 올라오면 즉시 프로젝트 코드를 업데이트할 준비를 할 것.

---

## QuantLabs 자동화 코딩 모드 (Cursor 준수 사항)

| 규칙 | 내용 |
|------|------|
| **상시 감시** | 작업 시마다(또는 코드 미수정 시) 이 파일을 리로드해 내용 확인. |
| **자동 실행** | PM의 신규/수정 지시가 있으면 승인 없이 즉시 코드 반영. |
| **진행 보고** | 작업 완료 시 이 파일 하단에 `[Cursor 완료 보고: YYYY-MM-DD HH:MM]` 및 변경 요약 기록. |
| **에러 처리** | 에러 시 즉시 중단 → 로그 분석 → 해결 후 재시도. |

---

## 무한 루프 지시 (대장님 부재 중 감시)

- **5분마다** 이 파일을 체크한다.
- **마지막 완료 보고([Cursor 완료 보고...]) 이후에** 젬민이(PM)가 새로운 지시를 추가했다면, **대장님 개입 없이** 즉시 코딩을 시작한다.
- 코딩이 끝나면 다시 5분간 대기하며 지시서를 감시한다.
- **멈추라고 할 때까지** 이 과정을 무한 반복한다.

**사용 방법 (실제 동작):**
1. **감시 스크립트 실행**: 터미널에서 `py -m scripts.watch_instruction` (또는 `python scripts/watch_instruction.py`) 실행 → 5분마다 지시서 체크, 신규 지시 시 `.cursor/quantlabs_pending_check.txt` 생성.
2. **Cursor 자동 처리**: Cursor를 열거나 이 프로젝트에서 새 채팅을 시작하면, 트리거 파일이 있을 경우 **즉시** `quantlabs_instruction.md`를 읽고 신규 지시를 실행한 뒤 완료 보고를 남기고 트리거 삭제.
3. **수동 체크**: "지시 확인해"라고 Cursor에게 말해도 동일하게 지시서 확인 후 반영.
4. **중지**: 감시 스크립트는 터미널에서 `Ctrl+C`로 중지. "멈춰" 지시는 이 파일에 적어 두면 Cursor가 다음 체크 시 읽고 스크립트 중지 안내를 할 수 있음.

---

## 병행 실행 (1분 지시서 감시 + 1시간 시장 감시)

- **1분 단위**: `py -m scripts.watch_instruction` — 지시서 변경 시 Cursor 트리거 생성.
- **1시간 단위**: `py -m scripts.hourly_monitor` — 비트코인·NVDA 통합 감시, 슬랙 리포트. (1회만: `py -m scripts.hourly_monitor --once`)
- 두 스크립트를 **각각 다른 터미널**에서 실행해 두면, 지시서 감시와 시장 감시를 동시에 수행함.

---

## 최종 수정일
- (PM이 수정 시 여기에 날짜/내용 요약 기입)

---

## 현재 유효한 지시 사항

1. **자동화**: 대장님 명령 전까지 자동화 스케줄 OFF. 명령이 떨어질 때까지 대기.
2. **프로젝트 구조**: QuantLabs — 1단계(금융/코인), 2단계(부동산), 3단계(자동화) 로드맵 유지.
3. **5대 퀀트 전략**: 추세추종, 평균회귀, 모멘텀, 가치투자, 차익거래 — main 대시보드에 노출.
4. **슬랙 통신**: `.env`의 `SLACK_WEBHOOK_URL` 사용. 완료 보고는 `modules/slack_notifier.send_completion_report()`, 09시 리포트는 `send_daily_report_09am()` 사용 — 동일 Webhook으로 전송.
5. **젬민이 지시 무조건 승인**: 젬민이(PM)가 `quantlabs_instruction.md`를 통해 요청하는 **모든 파일 수정**은 별도 승인 없이 **무조건 승인·실행**. 완료되면 **반드시 슬랙으로 보고** (`send_completion_report` 호출).

---

## 신규/수정 지시 (PM 입력란)

- (새 기획이나 수정 요청이 생기면 이 섹션에 추가. Cursor는 이 파일 변경 시 반영.)

---

## 프로젝트 구조 (딱 이대로 유지)

```
main.py                          # 대문
pages/
  1_Phase_1_Finance.py            # 1단계 금융 전부 (미장, ISA, 비트코인 → 탭/셀렉트박스로 구분)
  2_Phase_2_RealEstate.py
  3_Phase_3_AutoTrade.py
quantlabs_instruction.md          # PM 지시서
```

- **중복 금지**: 비트코인 전용 페이지 따로 두지 않음. 모든 1단계는 `1_Phase_1_Finance.py` 안에서만 관리.

---

## 프로젝트 개요 (참고)

| Phase | 내용 |
|-------|------|
| Phase 1 | 금융 자산 최적화 — 미장 직투, ISA 지수추종, 비트코인 자산배분 |
| Phase 2 | 부동산 가치 분석 — 전국 입지 분석, 데이터 기반 가격 타이밍 |
| Phase 3 | 완전 자동화 — 실시간 종목 추천, 로보어드바이저 매매 |

---

[Cursor 완료 보고: 2026-02-13 16:05]
- QuantLabs 자동화 코딩 모드 규칙 등록: `.cursor/rules/quantlabs-automation-mode.mdc` 생성 (상시 감시·자동 실행·진행 보고·에러 처리).
- `quantlabs_instruction.md`에 "QuantLabs 자동화 코딩 모드" 섹션 추가 및 Cursor 준수 사항 표 기입.

---
[Cursor 완료 보고: 2026-02-13 16:12]
- 무한 루프 지시 반영: `scripts/watch_instruction.py` 추가 — 5분마다 지시서 체크, 신규 지시 시 `.cursor/quantlabs_pending_check.txt` 생성.
- Cursor 규칙 보강: 트리거 파일 존재 시 자동으로 지시 실행 후 완료 보고 및 트리거 삭제.
- `quantlabs_instruction.md`에 "무한 루프 지시" 섹션 및 사용 방법(감시 스크립트 실행·Cursor 자동 처리·중지 방법) 정리.

---
[Cursor 완료 보고: 2026-02-13 16:18]
- 슬랙 통신 강제 복구: `scripts/test_slack_direct.py` 생성 — 지정 Webhook으로 "대장님, 노예가 직접 보고드립니다. 통신 성공!" 전송, 즉시 실행 후 전송 성공 확인.
- 연동 로직 준비: `modules/slack_notifier`에 `send_completion_report(summary_lines)`, `send_daily_report_09am(content)` 추가. 완료 보고·09시 리포트는 동일 Webhook(.env의 SLACK_WEBHOOK_URL) 사용. `.env.example` 및 지시서에 슬랙 연동 방식 명시.

---
[Cursor 완료 보고: 2026-02-13 16:22]
- 젬민이 지시 무조건 승인·실행: `quantlabs_instruction.md` 현재 유효 지시에 "젬민이가 요청하는 모든 파일 수정은 무조건 승인·실행, 완료 시 슬랙 보고" 추가.
- Cursor 규칙 갱신: 자동 실행에 "PM 요청 무조건 승인" 명시, 진행 보고에 "완료 시 send_completion_report로 슬랙 전송" 필수화.

---
[Cursor 완료 보고: 2026-02-13 16:35] — 미션 1호: 비트코인 무한 동력 시스템
- 인코딩/주기: report_to_slack UTF-8·watch_instruction 1분 적용 완료(기존 반영).
- 데이터 파이프라인: Upbit(pyupbit) BTC/KRW 30일 일봉 → modules/upbit_fetcher.py, data/btc_daily.csv 저장, scripts/update_btc_daily.py(매시간 갱신용).
- VBS 백테스트: modules/vbs_backtest.py — backtest_vbs(k), get_best_k(0.3~0.7), get_today_target_and_remaining.
- Phase1 비트코인 탭: 추천 K값, 현재가 vs 목표가 게이지, 돌파까지 남은 % 실시간 표시.
- monitor_vbs.py: 1분마다 목표가 체크, 돌파 시 슬랙 알림 1회(당일 중복 방지).
- 09시 리포트: scripts/send_09_report.py — 스케줄러 09:00 실행 시 전체 요약 발송.

---
[Cursor 완료 보고: 2026-02-13 17:00] — 야간 특명: 1시간 통합 감시 & 엔비디아 분석
- 1시간 주기 통합 감시: scripts/hourly_monitor.py — 비트코인(현재가, VBS 돌파 거리, 추천 K), NVDA(시세, 20/50일 이격도), PM급 인사이트 1줄 포함. 한글 UTF-8·이모지(🚨📈📉) 슬랙 보고. 야간(한국 22~07시)엔 NVDA 최우선 배치. --once 또는 무한 루프(1시간 간격) 지원.
- 미장 직투 고도화: pages/1_Phase_1_Finance.py '미장 직투' 탭에 NVDA 섹션 — 최근 5일 거래량, RSI(14), 지지/저항선 시각화(Plotly).
- 모듈: modules/nvda_fetcher.py (yfinance), requirements에 yfinance 추가.
- 지시서 동기화: 1분 단위 지시서 감시(scripts/watch_instruction.py)와 1시간 단위 시장 감시(scripts/hourly_monitor.py) 병행 실행. 둘 다 터미널에서 각각 실행해 두면 됨.

---

## 최종 전략 파라미터 (NVDA Alpha-V1)

- **전략명**: NVDA Alpha-V1 (멀티 팩터)
- **로직**: 이동평균 정배열(5>20) + RSI 과매수 해소 + ATR 변동성 돌파. 가중치로 매수 점수(Buy Score) 0~100 산출.
- **저장 위치**: `data/nvda_golden_params.json` (최적화 실행 시 갱신)
- **목표**: 연간 수익률 30% 이상, MDD 15% 이하. 미달 시 가중치/파라미터 0.1 단위 조정, 최대 50회 시뮬레이션으로 Golden Parameter 추출.
- **보조지표 5종**: RSI, MACD, Bollinger Bands, ATR, OBV (+ 세력 매집 지표: 가격·거래량 상관/누적). `modules/nvda_engine.py`에서 일괄 생성.

---
[Cursor 완료 보고: 2026-02-13 17:25] — 퀀트 고도화: NVDA Alpha-V1 & 무한 백테스팅
- modules/nvda_engine.py: 5종 지표(RSI,MACD,BB,ATR,OBV) + 세력 매집 지표, Alpha-V1 매수점수, 백테스트·50회 최적화·Golden Parameter 저장/로드, valuation_vs_volatility.
- Phase1 미장 직투: 전문가용 대시보드 — 주가 위 수익곡선 겹침, 매수점수 게이지, 최적화 Status, Golden Parameter 실행 버튼.
- hourly_monitor: NVDA 기술적 점수(Alpha-V1) 및 "역사적 변동성 대비 저평가/고평가" 금융 공학적 인사이트 추가.
- quantlabs_instruction.md에 '최종 전략 파라미터' 섹션 기록. 슬랙 최종 보고 발송.

---
[Cursor 완료 보고: 2026-02-13 17:35] — 슬랙 리포트 강화 (실시간 연구 보고)
- NVDA 최적화 루프 10회마다 슬랙 중간 보고: optimize_golden_params_with_slack(), "[NVDA 연구 N회차] 현재 최고 수익률 XX% 달성, 파라미터 조정 중..."
- 최적화 완료 시 종합 리포트: ✅최종 전략 / 📈예상 수익률·MDD / 🛠️최적 RSI·ATR K·매수점수 기준 / 💡PM 한줄평(진입 시점 유효성). UTF-8·이모지 가독성 유지.
- scripts/run_nvda_research_slack.py: 연구 시작 즉시 첫 보고 → 50회 시뮬레이션(10회마다 보고) → 최종 리포트 → "실시간 감시 들어갑니다" 전송. 실행 완료.

2026-02-14 리포트 명령

자동화 테스트 중
