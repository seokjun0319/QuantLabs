# -*- coding: utf-8 -*-
"""
QuantLabs 실험 로그 DB: 성공/실패 모든 시도 기록.
전략 ID, 부모 ID, 팩터 조합, 파라미터, IS/OOS 수익률·Sharpe, MaxDD, p-value, 채택 여부.
"""
from __future__ import annotations

import csv
import json
import uuid
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
LOG_FILE = DATA_DIR / "experiments_log.csv"
ENCODING = "utf-8"

COLUMNS = [
    "strategy_id",
    "parent_id",
    "factors",
    "params_json",
    "is_return",
    "is_sharpe",
    "oos_return",
    "oos_sharpe",
    "mdd",
    "p_value",
    "passed_gate",
    "created_at",
]


def _next_id() -> str:
    return str(uuid.uuid4())[:8]


def append_experiment(
    params: dict,
    is_return: float,
    is_sharpe: float,
    oos_return: float,
    oos_sharpe: float,
    mdd: float,
    p_value: float,
    passed_gate: bool,
    parent_id: str = "",
    factors: str = "ema_rsi_atr",
) -> str:
    """
    실험 1건 기록 (성공/실패 무관). strategy_id 반환.
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    sid = _next_id()
    row = {
        "strategy_id": sid,
        "parent_id": parent_id or "",
        "factors": factors,
        "params_json": json.dumps(params, ensure_ascii=False),
        "is_return": f"{is_return:.6f}",
        "is_sharpe": f"{is_sharpe:.4f}",
        "oos_return": f"{oos_return:.6f}",
        "oos_sharpe": f"{oos_sharpe:.4f}",
        "mdd": f"{mdd:.6f}",
        "p_value": f"{p_value:.6f}",
        "passed_gate": "1" if passed_gate else "0",
        "created_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    file_exists = LOG_FILE.exists()
    with open(LOG_FILE, "a", newline="", encoding=ENCODING) as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        if not file_exists:
            w.writeheader()
        w.writerow(row)
    return sid


def load_experiments() -> list[dict]:
    """전체 실험 로그 (최신순)."""
    if not LOG_FILE.exists():
        return []
    out = []
    with open(LOG_FILE, "r", encoding=ENCODING) as f:
        r = csv.DictReader(f)
        for row in r:
            out.append(row)
    return list(reversed(out))


def load_top_strategies(
    sharpe_min: float = 1.2,
    passed_only: bool = True,
    limit: int = 20,
) -> list[dict]:
    """
    채택 기준 통과한 상위 전략 로드 (진화 부모 후보).
    """
    rows = load_experiments()
    out = []
    for r in rows:
        if passed_only and r.get("passed_gate") != "1":
            continue
        try:
            sh = float(r.get("oos_sharpe") or r.get("is_sharpe") or 0)
            if sh < sharpe_min:
                continue
            r["_sharpe"] = sh
            r["_params"] = json.loads(r.get("params_json") or "{}")
            out.append(r)
        except Exception:
            continue
    out.sort(key=lambda x: x.get("_sharpe", 0), reverse=True)
    return out[:limit]
