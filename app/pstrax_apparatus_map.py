"""Pure PSTrax Fleet Status row -> structured apparatus fields (no Flask/db imports)."""

from __future__ import annotations

import json
import re
from typing import Any, Optional

from bs4 import BeautifulSoup

_MDY = re.compile(r"\b(\d{1,2}/\d{1,2}/\d{4})\b")
_MDY_ONLY = re.compile(r"^\s*(\d{1,2}/\d{1,2}/\d{4})\s*$")
_INT = re.compile(r"-?\d+")


def _safe_str(v: Any, max_len: int = 512) -> str:
    if v is None:
        return ""
    if isinstance(v, dict):
        for key in ("display", "name", "label", "text", "value"):
            if key in v and v[key] is not None:
                return _safe_str(v[key], max_len)
        return ""
    s = BeautifulSoup(str(v), "html.parser").get_text(" ", strip=True)
    return s[:max_len] if len(s) > max_len else s


def _first(item: dict, *keys: str) -> Any:
    for key in keys:
        if key in item and item[key] is not None and item[key] != "":
            return item[key]
    # case-insensitive fallback
    lower_map = {str(k).lower(): v for k, v in item.items()}
    for key in keys:
        lk = key.lower()
        if lk in lower_map and lower_map[lk] is not None and lower_map[lk] != "":
            return lower_map[lk]
    return None


def _as_int(v: Any) -> Optional[int]:
    if v is None or v == "":
        return None
    if isinstance(v, bool):
        return int(v)
    if isinstance(v, int):
        return v
    if isinstance(v, float):
        return int(v)
    if isinstance(v, dict):
        for key in ("count", "value", "sort", "n", "total"):
            if key in v:
                parsed = _as_int(v.get(key))
                if parsed is not None:
                    return parsed
        text = _safe_str(v.get("display"))
        return _as_int(text) if text else None
    text = BeautifulSoup(str(v), "html.parser").get_text(" ", strip=True)
    if not text:
        return None
    if text.isdigit() or (text.startswith("-") and text[1:].isdigit()):
        return int(text)
    m = _INT.search(text)
    return int(m.group(0)) if m else None


def _mdy_from_value(v: Any) -> Optional[str]:
    if v is None or v == "":
        return None
    if isinstance(v, dict):
        for key in ("nxtsort", "duesort", "sort", "date", "value"):
            sort_v = v.get(key)
            if isinstance(sort_v, str) and _MDY_ONLY.match(sort_v):
                return sort_v.strip()
        disp = _safe_str(v.get("display"))
        m = _MDY.search(disp)
        if m:
            return m.group(1)
        return None
    text = _safe_str(v)
    if _MDY_ONLY.match(text):
        return text.strip()
    m = _MDY.search(text)
    return m.group(1) if m else None


def _display_raw(v: Any) -> Optional[str]:
    if v is None:
        return None
    if isinstance(v, dict):
        disp = v.get("display")
        if disp is not None:
            return str(disp)
        return None
    s = str(v)
    return s if "<" in s else None


def _css_class(v: Any) -> Optional[str]:
    if not isinstance(v, dict):
        return None
    for key in ("class", "cssclass", "css_class", "className"):
        if v.get(key):
            return _safe_str(v.get(key), 128) or None
    return None


def extract_vehicle_id(item: dict) -> Optional[int]:
    """Best-effort primary key for a fleet status row."""
    direct = _as_int(
        _first(
            item,
            "app_id",
            "appid",
            "vehicleid",
            "vehicle_id",
            "vid",
            "id",
            "apparatusid",
            "apparatus_id",
            "unitid",
            "unit_id",
            "DT_RowId",
        )
    )
    if direct is not None:
        return direct
    row_id = item.get("DT_RowId") or item.get("dt_row_id")
    if row_id is not None:
        m = _INT.search(str(row_id))
        if m:
            return int(m.group(0))
    return None


def apparatus_kwargs_from_pstrax(item: dict) -> dict:
    """Column kwargs for Apparatus (includes vehicle_id)."""
    vehicle_id = extract_vehicle_id(item)
    status_val = _first(
        item,
        "service_param",
        "status",
        "vehiclestatus",
        "vehicle_status",
        "oos",
        "servicestatus",
    )
    next_due_val = _first(item, "nextdue", "next_due", "duedate", "due_date", "nextcheck", "next_check")
    alerts_val = _first(
        item,
        "alerts",
        "openalerts",
        "open_alerts",
        "alertcount",
        "alert_count",
        "numalerts",
        "alertsopen",
    )
    checks_val = _first(
        item,
        "checks_due",
        "checksdue",
        "inspectionsdue",
        "inspections_due",
        "due",
        "numdue",
        "checksduecount",
    )

    # Dashboard "Assignment" column — PSTrax Fleet Status uses app_name
    unit_name = _safe_str(
        _first(
            item,
            "app_name",
            "appname",
            "assignment",
            "vehiclename",
            "vehicle_name",
            "apparatus",
            "name",
            "designator",
            "radioid",
            "radio_id",
        ),
        128,
    ) or None

    # Dashboard "Door #" column — PSTrax app_unit (e.g. #5563)
    app_unit = _safe_str(
        _first(item, "app_unit", "appunit", "door_number", "door", "unit_number"),
        64,
    ) or None

    station = _safe_str(
        _first(item, "station_name", "stationname", "station", "location"),
        128,
    ) or None

    vehicle_type = _safe_str(
        _first(item, "vehicle_type", "vehicletype", "type", "apparatus_type", "class", "category"),
        128,
    ) or None

    status = _safe_str(status_val, 64) or None
    status_class = _css_class(status_val) if isinstance(status_val, dict) else None
    if not status_class:
        status_class = _safe_str(_first(item, "service_class"), 128) or None
    # In-service reserve units should show as Reserve on the dashboard
    in_reserve = _as_int(_first(item, "in_reserve", "inreserve", "reserve"))
    in_service = _as_int(_first(item, "in_service", "inservice"))
    if status and status.strip().upper() == "IN SERVICE" and in_reserve == 1:
        status = "Reserve"
    open_alerts = _as_int(alerts_val)
    checks_due = _as_int(checks_val)
    if checks_due is None:
        # Sum module due counts when a single total is absent
        parts = [
            _as_int(_first(item, "scbadue", "scba_due", "scba")),
            _as_int(_first(item, "assetsdue", "assets_due", "assets")),
            _as_int(_first(item, "suppliesdue", "supplies_due", "supplies")),
        ]
        present = [p for p in parts if p is not None]
        if present:
            checks_due = sum(present)

    try:
        raw_json = json.dumps(item, default=str)
    except (TypeError, ValueError):
        raw_json = None

    return {
        "vehicle_id": vehicle_id,
        "unit_name": unit_name,
        "app_unit": app_unit,
        "station": station,
        "vehicle_type": vehicle_type,
        "status": status,
        "status_class": status_class,
        "status_display_raw": _display_raw(status_val),
        "in_service": in_service if in_service is not None else 0,
        "in_reserve": in_reserve if in_reserve is not None else 0,
        "open_alerts": open_alerts if open_alerts is not None else 0,
        "open_alerts_display": _display_raw(alerts_val) or (_safe_str(alerts_val) or None),
        "checks_due": checks_due if checks_due is not None else 0,
        "checks_due_display": _display_raw(checks_val) or (_safe_str(checks_val) or None),
        "scba_due": _as_int(_first(item, "scbadue", "scba_due", "scba")),
        "assets_due": _as_int(_first(item, "assetsdue", "assets_due", "assets")),
        "supplies_due": _as_int(_first(item, "suppliesdue", "supplies_due", "supplies")),
        "next_due": _mdy_from_value(next_due_val),
        "next_due_display": _display_raw(next_due_val) or (_safe_str(next_due_val) or None),
        "next_due_class": _css_class(next_due_val) if isinstance(next_due_val, dict) else None,
        "raw_json": raw_json,
    }


def parse_department_status_payload(payload: Any) -> list[dict]:
    """Normalize JSON/HTML-derived payload into a list of row dicts."""
    if payload is None:
        return []
    if isinstance(payload, list):
        return [r for r in payload if isinstance(r, dict)]
    if not isinstance(payload, dict):
        return []
    for key in ("data", "aaData", "rows", "vehicles", "apparatus", "results"):
        rows = payload.get(key)
        if isinstance(rows, list):
            return [r for r in rows if isinstance(r, dict)]
    # Single nested object with data list
    for value in payload.values():
        if isinstance(value, dict):
            nested = parse_department_status_payload(value)
            if nested:
                return nested
    return []


def parse_department_status_html(html: str) -> list[dict]:
    """Parse an HTML Fleet Status table into row dicts when JSON is unavailable."""
    soup = BeautifulSoup(html or "", "html.parser")
    table = (
        soup.find("table", id=re.compile(r"status|fleet|department|vehicle", re.I))
        or soup.find("table", class_=re.compile(r"status|fleet|datatable", re.I))
        or soup.find("table")
    )
    if not table:
        return []

    headers = []
    thead = table.find("thead")
    if thead:
        headers = [
            re.sub(r"\W+", "_", th.get_text(" ", strip=True).lower()).strip("_")
            for th in thead.find_all(["th", "td"])
        ]
    if not headers:
        first_row = table.find("tr")
        if first_row and first_row.find("th"):
            headers = [
                re.sub(r"\W+", "_", th.get_text(" ", strip=True).lower()).strip("_")
                for th in first_row.find_all("th")
            ]

    body = table.find("tbody") or table
    rows = []
    for tr in body.find_all("tr"):
        cells = tr.find_all("td")
        if not cells:
            continue
        item: dict[str, Any] = {}
        row_id = tr.get("id") or tr.get("data-id") or tr.get("data-vehicleid")
        if row_id:
            item["DT_RowId"] = str(row_id)
            m = _INT.search(str(row_id))
            if m:
                item["vehicleid"] = int(m.group(0))
        for idx, cell in enumerate(cells):
            key = headers[idx] if idx < len(headers) and headers[idx] else f"col_{idx}"
            html_val = cell.decode_contents().strip()
            text_val = cell.get_text(" ", strip=True)
            item[key] = html_val if "<" in html_val else text_val
            # Helpful aliases from common header labels
            if key in ("unit", "vehicle", "apparatus", "name"):
                item.setdefault("unit_name", text_val)
            elif key in ("station", "location"):
                item.setdefault("station", text_val)
            elif key in ("status",):
                item.setdefault("status", text_val)
            elif "alert" in key:
                item.setdefault("open_alerts", text_val)
            elif "due" in key or "check" in key or "inspect" in key:
                item.setdefault("checks_due", text_val)
        if item:
            rows.append(item)
    return rows
