# -*- coding: utf-8 -*-
"""
최적화 히스토리 DB: data/optimization_log.csv 누적 저장.
날짜, 목표치, 반복횟수, 결과, 파라미터 JSON 등 포함. UTF-8.
"""
from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
LOG_FILE = DATA_DIR / "optimization_log.csv"
ENCODING = "utf-8"

COLUMNS = [
    "timestamp",
    "source",
    "target_ann_ret",
    "target_mdd",
    "target_sharpe",
    "iteration_count",
    "returns",
    "mdd",
    "annualized_return",
    "sharpe_ratio",
    "strategy_summary",
    "params_json",
]

# UI 표시용 한글 필드명
COLUMNS_KR = {
    "timestamp": "일시",
    "source": "출처",
    "target_ann_ret": "목표 연수익률",
    "target_mdd": "목표 MDD",
    "target_sharpe": "목표 샤프",
    "iteration_count": "반복횟수",
    "returns": "수익률",
    "mdd": "MDD",
    "annualized_return": "연간수익률",
    "sharpe_ratio": "샤프지수",
    "strategy_summary": "전략요약",
    "params_json": "파라미터(JSON)",
}


def append_log(
    source: str,
    params: dict,
    result: dict,
    iteration_count: int = 1,
    target_ann_ret: float | None = None,
    target_mdd: float | None = None,
    target_sharpe: float | None = None,
    strategy_summary: str = "",
) -> None:
    """
    최적화 완료 시 한 줄 추가.
    result: returns, mdd, (optional) annualized_return, sharpe_ratio
    strategy_summary: 전략 특징 한 줄 요약 (한글 권장).
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    row = {
        "timestamp": ts,
        "source": source,
        "target_ann_ret": "" if target_ann_ret is None else str(target_ann_ret),
        "target_mdd": "" if target_mdd is None else str(target_mdd),
        "target_sharpe": "" if target_sharpe is None else str(target_sharpe),
        "iteration_count": str(iteration_count),
        "returns": str(result.get("returns", "")),
        "mdd": str(result.get("mdd", "")),
        "annualized_return": str(result.get("annualized_return", "")),
        "sharpe_ratio": str(result.get("sharpe_ratio", "")),
        "strategy_summary": strategy_summary or "",
        "params_json": json.dumps(params, ensure_ascii=False),
    }
    file_exists = LOG_FILE.exists()
    if file_exists:
        with open(LOG_FILE, "r", encoding=ENCODING) as f:
            reader = csv.DictReader(f)
            old_fn = reader.fieldnames or []
            if "strategy_summary" not in old_fn:
                existing = []
                for r in reader:
                    for c in COLUMNS:
                        if c not in r:
                            r[c] = ""
                    existing.append(r)
                existing.append(row)
                with open(LOG_FILE, "w", newline="", encoding=ENCODING) as fw:
                    w = csv.DictWriter(fw, fieldnames=COLUMNS)
                    w.writeheader()
                    w.writerows(existing)
                return
    with open(LOG_FILE, "a", newline="", encoding=ENCODING) as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)


def read_log():
    """로그 전체를 리스트[dict]로 반환. UI/복구용. 구 컬럼(전략요약 없음)도 허용."""
    if not LOG_FILE.exists():
        return []
    out = []
    with open(LOG_FILE, "r", encoding=ENCODING) as f:
        reader = csv.DictReader(f)
        for row in reader:
            for c in COLUMNS:
                if c not in row:
                    row[c] = ""
            out.append(row)
    return out
