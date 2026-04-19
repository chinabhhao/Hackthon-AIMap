import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any


@dataclass(frozen=True)
class ReplanResult:
    preview: dict[str, Any]
    save_payload: dict[str, Any]


def round_to_hour(dt: datetime) -> datetime:
    dt2 = dt.replace(minute=0, second=0, microsecond=0)
    if dt != dt2 and dt.minute != 0:
        return dt2 + timedelta(hours=1)
    return dt2


def parse_duration_minutes(duration_text: str) -> int:
    s = (duration_text or "").strip()
    if not s:
        return 0
    m = re.search(r"(\d+(?:\.\d+)?)\s*小时", s)
    if m:
        return int(float(m.group(1)) * 60)
    m = re.search(r"(\d+)\s*分钟", s)
    if m:
        return int(m.group(1))
    m = re.search(r"(\d+)\s*min", s, flags=re.IGNORECASE)
    if m:
        return int(m.group(1))
    m = re.search(r"(\d+)", s)
    return int(m.group(1)) if m else 0


def estimate_trip_days(stops: list[dict[str, Any]]) -> int:
    total_min = 0
    for s in stops or []:
        total_min += parse_duration_minutes(str(s.get("visit_duration", ""))) or 60
    return max(1, (total_min + 8 * 60 - 1) // (8 * 60))


def default_end_datetime(start_dt: datetime, stops: list[dict[str, Any]]) -> datetime:
    days = estimate_trip_days(stops)
    return start_dt + timedelta(days=int(days))


def validate_time_range(now: datetime, start_dt: datetime, end_dt: datetime) -> list[dict[str, str]]:
    errs: list[dict[str, str]] = []
    if start_dt < now:
        errs.append({"code": "E_START_IN_PAST", "message": "开始时间不得早于当前系统时间"})
    if end_dt <= start_dt:
        errs.append({"code": "E_END_BEFORE_START", "message": "结束时间必须晚于开始时间"})
    if (end_dt - start_dt) < timedelta(hours=1):
        errs.append({"code": "E_RANGE_TOO_SHORT", "message": "开始与结束时间间隔不得小于 1 小时"})
    return errs


def compute_budget_recommended_upper(stops: list[dict[str, Any]], currency: str) -> float:
    n = len(stops or [])
    base = 300.0 if currency == "CNY" else 60.0 if currency == "USD" else 55.0 if currency == "EUR" else 8000.0 if currency == "JPY" else 300.0
    return float(max(0.0, n * base))


def estimate_cost(stops: list[dict[str, Any]], currency: str) -> float:
    n = len(stops or [])
    base = 220.0 if currency == "CNY" else 45.0 if currency == "USD" else 40.0 if currency == "EUR" else 6000.0 if currency == "JPY" else 220.0
    return float(max(0.0, n * base))


def _checksum(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def replan_itinerary(
    *,
    base_plan: dict[str, Any],
    stops: list[dict[str, Any]],
    now: datetime,
    start_dt: datetime,
    end_dt: datetime,
    budget_amount: float | None,
    budget_currency: str,
    extra_options: dict[str, Any] | None,
    prev_preview: dict[str, Any] | None = None,
) -> ReplanResult:
    errs = validate_time_range(now, start_dt, end_dt)
    if errs:
        raise ValueError(errs[0]["code"] + ":" + errs[0]["message"])

    travel_default_min = 20
    cursor = start_dt
    items: list[dict[str, Any]] = []
    for i, s in enumerate(stops or []):
        name = str(s.get("name", "")).strip() or f"第{i+1}站"
        travel_min = 0 if i == 0 else travel_default_min
        visit_min = parse_duration_minutes(str(s.get("visit_duration", ""))) or 60

        start_item = cursor + timedelta(minutes=travel_min)
        end_item = start_item + timedelta(minutes=visit_min)
        if end_item > end_dt:
            raise ValueError("E_TIME_RANGE_TOO_SHORT:结束时间不足以容纳当前行程，请延后结束时间或减少景点")
        items.append(
            {
                "spot_name": name,
                "start": start_item.isoformat(timespec="minutes"),
                "end": end_item.isoformat(timespec="minutes"),
                "tag": s.get("tag", ""),
                "visit_duration": s.get("visit_duration", ""),
                "ticket": s.get("ticket", ""),
                "best_time": s.get("best_time", ""),
                "recommendation": s.get("recommendation", ""),
            }
        )
        cursor = end_item

    by_day: dict[str, list[dict[str, Any]]] = {}
    for it in items:
        day = it["start"].split("T", 1)[0]
        by_day.setdefault(day, []).append(it)
    days = [{"date": d, "items": by_day[d]} for d in sorted(by_day.keys())]

    old_cost = None
    if prev_preview and isinstance(prev_preview, dict):
        try:
            old_cost = float(prev_preview.get("cost_estimate")) if prev_preview.get("cost_estimate") is not None else None
        except Exception:
            old_cost = None

    cost_estimate = estimate_cost(stops, budget_currency)
    preview = {
        "version": int(base_plan.get("itinerary_version") or 0) + 1,
        "start": start_dt.isoformat(timespec="minutes"),
        "end": end_dt.isoformat(timespec="minutes"),
        "days": days,
        "cost_estimate": round(cost_estimate, 2),
        "cost_previous": round(old_cost, 2) if old_cost is not None else None,
    }
    preview["checksum"] = _checksum(preview)

    save_payload = {
        "plan": {
            "city": base_plan.get("city", ""),
            "route": base_plan.get("route", ""),
            "stops": stops,
        },
        "options": {
            "start": preview["start"],
            "end": preview["end"],
            "budget": {"amount": budget_amount, "currency": budget_currency},
            "extra": extra_options or {},
        },
        "preview": preview,
    }
    save_payload["checksum"] = _checksum(save_payload)

    return ReplanResult(preview=preview, save_payload=save_payload)

