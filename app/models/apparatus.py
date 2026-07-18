"""Structured PSTrax apparatus / fleet status rows."""

from __future__ import annotations

from datetime import datetime

from app import db
from app.pstrax_apparatus_map import apparatus_kwargs_from_pstrax


class Apparatus(db.Model):
    """PSTrax vehicle/apparatus row from the Fleet Status Report."""

    __tablename__ = "apparatus"

    vehicle_id = db.Column(db.Integer, primary_key=True)
    unit_name = db.Column(db.String(128), nullable=True, index=True)  # Assignment (app_name)
    app_unit = db.Column(db.String(64), nullable=True, index=True)  # Door # (app_unit)
    station = db.Column(db.String(128), nullable=True, index=True)
    vehicle_type = db.Column(db.String(128), nullable=True, index=True)
    status = db.Column(db.String(64), nullable=True, index=True)
    status_class = db.Column(db.String(128), nullable=True)
    status_display_raw = db.Column(db.Text, nullable=True)
    in_service = db.Column(db.Integer, nullable=True, default=0, index=True)
    in_reserve = db.Column(db.Integer, nullable=True, default=0, index=True)

    open_alerts = db.Column(db.Integer, nullable=True, default=0)
    open_alerts_display = db.Column(db.Text, nullable=True)

    checks_due = db.Column(db.Integer, nullable=True, default=0)
    checks_due_display = db.Column(db.Text, nullable=True)
    scba_due = db.Column(db.Integer, nullable=True)
    assets_due = db.Column(db.Integer, nullable=True)
    supplies_due = db.Column(db.Integer, nullable=True)

    next_due = db.Column(db.String(20), nullable=True, index=True)
    next_due_display = db.Column(db.Text, nullable=True)
    next_due_class = db.Column(db.String(128), nullable=True)

    raw_json = db.Column(db.Text, nullable=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @classmethod
    def from_pstrax_row(cls, item: dict, updated_at: datetime) -> "Apparatus":
        kw = apparatus_kwargs_from_pstrax(item)
        vehicle_id = kw.pop("vehicle_id", None)
        if vehicle_id is None:
            raise ValueError("vehicle_id required")
        kw["updated_at"] = updated_at
        return cls(vehicle_id=int(vehicle_id), **kw)

    def to_api_row(self) -> dict:
        """Shape expected by the fleet dashboard client."""
        return {
            "vehicle_id": self.vehicle_id,
            # Assignment is the PSTrax app_name (stored in unit_name)
            "assignment": self.unit_name or "",
            "unit_name": self.unit_name or "",
            # Door # is the PSTrax app_unit
            "app_unit": self.app_unit or "",
            "door_number": self.app_unit or "",
            "station": self.station or "",
            "vehicle_type": self.vehicle_type or "",
            "status": self.status or "",
            "status_class": self.status_class or "",
            "status_display": self.status_display_raw or self.status or "",
            "in_service": self.in_service if self.in_service is not None else 0,
            "in_reserve": self.in_reserve if self.in_reserve is not None else 0,
            "open_alerts": self.open_alerts if self.open_alerts is not None else 0,
            "open_alerts_display": self.open_alerts_display
            if self.open_alerts_display is not None
            else str(self.open_alerts or 0),
            "checks_due": self.checks_due if self.checks_due is not None else 0,
            "checks_due_display": self.checks_due_display
            if self.checks_due_display is not None
            else str(self.checks_due or 0),
            "scba_due": self.scba_due,
            "assets_due": self.assets_due,
            "supplies_due": self.supplies_due,
            "next_due": self.next_due or "",
            "next_due_display": self.next_due_display or self.next_due or "",
            "next_due_class": self.next_due_class or "",
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self):
        return f"<Apparatus {self.vehicle_id} {self.unit_name}>"
