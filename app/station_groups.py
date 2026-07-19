"""Group and order apparatus by station for the Stations page."""

from __future__ import annotations

from typing import Any, Iterable, Sequence


def station_group_label(station: str | None) -> str:
    label = (station or "").strip()
    return label or "Unassigned"


def sort_station_labels(labels: Iterable[str]) -> list[str]:
    """Stations starting with 'station' first; each tier sorted descending."""
    unique = list(dict.fromkeys(labels))
    station_named = sorted(
        [s for s in unique if s.lower().startswith("station")],
        key=str.lower,
        reverse=True,
    )
    others = sorted(
        [s for s in unique if not s.lower().startswith("station")],
        key=str.lower,
        reverse=True,
    )
    return station_named + others


def group_apparatus_by_station(rows: Sequence[Any]) -> dict:
    """Build API payload: by_station groups with apparatus rows."""
    groups: dict[str, list[dict]] = {}
    for row in rows:
        label = station_group_label(getattr(row, "station", None))
        groups.setdefault(label, []).append({
            "vehicle_id": getattr(row, "vehicle_id", None),
            "name": getattr(row, "unit_name", None) or "",
            "assignment": getattr(row, "unit_name", None) or "",
            "app_unit": getattr(row, "app_unit", None) or "",
            "door_number": getattr(row, "app_unit", None) or "",
            "vehicle_type": getattr(row, "vehicle_type", None) or "",
            "status": getattr(row, "status", None) or "",
            "status_class": getattr(row, "status_class", None) or "",
            "status_display": (
                getattr(row, "status_display_raw", None)
                or getattr(row, "status", None)
                or ""
            ),
            "in_reserve": (
                getattr(row, "in_reserve", None)
                if getattr(row, "in_reserve", None) is not None
                else 0
            ),
            "station": label,
        })

    order = sort_station_labels(groups.keys())
    by_station = [
        {
            "station": station,
            "count": len(groups[station]),
            "apparatus": groups[station],
        }
        for station in order
    ]
    return {
        "total": sum(g["count"] for g in by_station),
        "by_station": by_station,
    }
