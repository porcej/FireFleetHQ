"""Pure PSTrax alert-list-station row -> structured fields (no Flask/db imports)."""

from __future__ import annotations

import json
import re
from typing import Any, Optional

from bs4 import BeautifulSoup

_INT = re.compile(r"-?\d+")


def _safe_str(v: Any, max_len: int = 2000) -> str:
    if v is None:
        return ""
    if isinstance(v, dict):
        for key in ("display", "text", "value", "label", "name"):
            if key in v and v[key] is not None:
                return _safe_str(v[key], max_len)
        return ""
    s = str(v).strip()
    return s[:max_len] if len(s) > max_len else s


def _plain_text(v: Any, max_len: int = 2000) -> str:
    raw = _safe_str(v, max_len=max_len * 2)
    if not raw:
        return ""
    if "<" in raw and ">" in raw:
        text = BeautifulSoup(raw, "html.parser").get_text(" ", strip=True)
    else:
        text = raw
    text = re.sub(r"\s+", " ", text).strip()
    return text[:max_len] if len(text) > max_len else text


def _as_int(v: Any) -> Optional[int]:
    if v is None or v == "":
        return None
    if isinstance(v, bool):
        return int(v)
    if isinstance(v, int):
        return v
    if isinstance(v, float):
        return int(v)
    text = _plain_text(v, 64)
    if not text:
        return None
    if text.isdigit() or (text.startswith("-") and text[1:].isdigit()):
        return int(text)
    m = _INT.search(text)
    return int(m.group(0)) if m else None


def extract_alert_id(item: dict) -> Optional[int]:
    direct = _as_int(item.get("alertid") or item.get("alert_id") or item.get("aid"))
    if direct is not None:
        return direct
    row_id = item.get("DT_RowId") or item.get("dt_row_id")
    if row_id is not None:
        m = _INT.search(str(row_id))
        if m:
            return int(m.group(0))
    return None


def parse_alert_comments(raw_html: Any) -> list[dict]:
    """Turn PSTrax alertcomments HTML (<dt>/<dd> pairs) into plain entries."""
    html = _safe_str(raw_html, max_len=50000)
    if not html:
        return []
    soup = BeautifulSoup(html, "html.parser")
    entries: list[dict] = []
    for dt in soup.find_all("dt"):
        dd = dt.find_next_sibling("dd")
        header = dt.get_text(" ", strip=True)
        body = dd.get_text(" ", strip=True) if dd else ""
        if header or body:
            entries.append({"header": header, "body": body})
    if entries:
        return entries
    text = soup.get_text("\n", strip=True)
    if text:
        return [{"header": "", "body": text}]
    return []


def alert_kwargs_from_pstrax(item: dict) -> dict:
    """Column kwargs for PstraxAlert (includes alert_id)."""
    alert_id = extract_alert_id(item)
    alerttext_raw = _safe_str(item.get("alerttext"), 8000) or None
    try:
        raw_json = json.dumps(item, default=str)
    except (TypeError, ValueError):
        raw_json = None

    return {
        "alert_id": alert_id,
        "alert_date": _safe_str(item.get("alertdate"), 64) or None,
        "category": _safe_str(item.get("category"), 128) or None,
        "app_name": _safe_str(item.get("appname") or item.get("app_name"), 255) or None,
        "post_station": _safe_str(item.get("poststation") or item.get("post_station"), 128) or None,
        "current_location": _safe_str(
            item.get("currentlocation") or item.get("current_location"), 128
        ) or None,
        "alert_text": _plain_text(alerttext_raw, 4000) or None,
        "alert_text_raw": alerttext_raw,
        "opened_by": _safe_str(item.get("openedby") or item.get("opened_by"), 128) or None,
        "priority": _safe_str(item.get("priority"), 64) or None,
        "last_update": _safe_str(item.get("lastupdate") or item.get("last_update"), 64) or None,
        "with_image": _as_int(item.get("withimage") or item.get("with_image")) or 0,
        "cost": _safe_str(item.get("cost"), 64) or None,
        "raw_json": raw_json,
    }


def parse_alerts_payload(payload: Any) -> list[dict]:
    if payload is None:
        return []
    if isinstance(payload, list):
        return [r for r in payload if isinstance(r, dict)]
    if not isinstance(payload, dict):
        return []
    for key in ("data", "aaData", "rows", "alerts", "results"):
        rows = payload.get(key)
        if isinstance(rows, list):
            return [r for r in rows if isinstance(r, dict)]
    return []
