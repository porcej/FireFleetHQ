"""Structured PSTrax Vehicle/Station open alerts."""

from __future__ import annotations

from datetime import datetime

import json

from app import db
from app.pstrax_alerts_map import alert_kwargs_from_pstrax, parse_alert_comments


class PstraxAlert(db.Model):
    """Open alert row from alert-list-station-data.php."""

    __tablename__ = "pstrax_alert"

    alert_id = db.Column(db.Integer, primary_key=True)
    alert_date = db.Column(db.String(64), nullable=True, index=True)
    category = db.Column(db.String(128), nullable=True, index=True)
    app_name = db.Column(db.String(255), nullable=True, index=True)
    post_station = db.Column(db.String(128), nullable=True, index=True)
    current_location = db.Column(db.String(128), nullable=True)
    alert_text = db.Column(db.Text, nullable=True)
    alert_text_raw = db.Column(db.Text, nullable=True)
    opened_by = db.Column(db.String(128), nullable=True)
    priority = db.Column(db.String(64), nullable=True, index=True)
    last_update = db.Column(db.String(64), nullable=True)
    with_image = db.Column(db.Integer, nullable=True, default=0)
    cost = db.Column(db.String(64), nullable=True)
    raw_json = db.Column(db.Text, nullable=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @classmethod
    def from_pstrax_row(cls, item: dict, updated_at: datetime) -> "PstraxAlert":
        kw = alert_kwargs_from_pstrax(item)
        alert_id = kw.pop("alert_id", None)
        if alert_id is None:
            raise ValueError("alert_id required")
        kw["updated_at"] = updated_at
        return cls(alert_id=int(alert_id), **kw)

    def to_api_row(self) -> dict:
        comments = []
        notes = ""
        if self.raw_json:
            try:
                raw = json.loads(self.raw_json)
            except (TypeError, ValueError, json.JSONDecodeError):
                raw = None
            if isinstance(raw, dict):
                comments = parse_alert_comments(raw.get("alertcomments"))
                notes_val = raw.get("notes")
                if notes_val is not None:
                    notes = str(notes_val).strip()

        return {
            "alert_id": self.alert_id,
            "alert_date": self.alert_date or "",
            "category": self.category or "",
            "app_name": self.app_name or "",
            "assignment": self.app_name or "",
            "post_station": self.post_station or "",
            "station": self.post_station or "",
            "current_location": self.current_location or "",
            "location": self.current_location or "",
            "alert_text": self.alert_text or "",
            "description": self.alert_text or "",
            "opened_by": self.opened_by or "",
            "priority": self.priority or "",
            "last_update": self.last_update or "",
            "with_image": self.with_image if self.with_image is not None else 0,
            "cost": self.cost or "",
            "comments": comments,
            "notes": notes,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self):
        return f"<PstraxAlert {self.alert_id}>"
