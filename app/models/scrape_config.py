from app import db
from datetime import datetime
from cryptography.fernet import Fernet
import base64
import os
import re


class ScrapeConfig(db.Model):
    """Configuration for PSTrax apparatus scraping"""
    id = db.Column(db.Integer, primary_key=True)
    pstrax_base_url = db.Column(db.String(255), default='https://pstrax.com', nullable=False)
    pstrax_username = db.Column(db.String(255), nullable=True)
    pstrax_password_encrypted = db.Column(db.Text, nullable=True)
    last_scrape = db.Column(db.DateTime, nullable=True)
    scrape_interval = db.Column(db.Integer, default=15)  # minutes (PSTrax alerts sync)
    last_alerts_scrape = db.Column(db.DateTime, nullable=True)
    apparatus_scrape_interval_minutes = db.Column(db.Integer, default=15, nullable=False)
    last_apparatus_scrape = db.Column(db.DateTime, nullable=True)
    default_alert_color = db.Column(db.String(20), default='danger', nullable=False)
    alerts_font_size = db.Column(db.Integer, default=16, nullable=False)  # pixels
    apparatus_statuses = db.Column(db.String(255), default='', nullable=False)
    apparatus_stations = db.Column(db.String(512), default='', nullable=False)
    # Stations where reserve apparatus are stored (empty = none configured).
    reserve_homes = db.Column(db.String(512), default='', nullable=False)
    app_timezone = db.Column(db.String(64), default='America/New_York', nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @staticmethod
    def _get_encryption_key():
        """Get or generate encryption key"""
        from app.config import Config
        key = os.environ.get('ENCRYPTION_KEY')
        if not key:
            key = Config.SECRET_KEY.encode()
            key = base64.urlsafe_b64encode(key[:32].ljust(32, b'0'))
        else:
            key = key.encode()
            if len(key) != 44:
                key = base64.urlsafe_b64encode(key[:32].ljust(32, b'0'))
        return key

    def set_password(self, password):
        """Encrypt and store password"""
        if not password:
            self.pstrax_password_encrypted = None
            return
        f = Fernet(self._get_encryption_key())
        self.pstrax_password_encrypted = f.encrypt(password.encode()).decode()

    def get_password(self):
        """Decrypt and return password"""
        if not self.pstrax_password_encrypted:
            return None
        try:
            f = Fernet(self._get_encryption_key())
            return f.decrypt(self.pstrax_password_encrypted.encode()).decode()
        except Exception:
            return None

    def __repr__(self):
        return f'<ScrapeConfig {self.id}>'

    def get_default_alert_color(self):
        return (self.default_alert_color or 'danger').lower()

    def get_alert_font_size(self):
        try:
            return int(self.alerts_font_size or 16)
        except (TypeError, ValueError):
            return 16

    def get_app_timezone(self):
        from app.timezone_utils import normalize_timezone_name
        return normalize_timezone_name(self.app_timezone or 'America/New_York')

    def _split_labels(self, raw, default=None):
        text = (raw or "").strip()
        if not text:
            return list(default or [])
        parts = re.split(r"[\n,]+", text)
        normalized = []
        seen = set()
        for part in parts:
            label = str(part).strip()
            if not label:
                continue
            key = label.lower()
            if key in seen:
                continue
            seen.add(key)
            normalized.append(label)
        return normalized

    def get_apparatus_statuses(self):
        """Return configured status filters; empty means all statuses."""
        return self._split_labels(self.apparatus_statuses)

    def set_apparatus_statuses(self, value):
        if value is None:
            self.apparatus_statuses = ""
            return
        if isinstance(value, (list, tuple, set)):
            parts = [str(v).strip() for v in value if str(v).strip()]
        else:
            parts = self._split_labels(str(value))
        self.apparatus_statuses = ",".join(parts)

    def get_apparatus_stations(self):
        """Return configured station filters; empty means all stations."""
        return self._split_labels(self.apparatus_stations)

    def set_apparatus_stations(self, value):
        if value is None:
            self.apparatus_stations = ""
            return
        if isinstance(value, (list, tuple, set)):
            parts = [str(v).strip() for v in value if str(v).strip()]
        else:
            parts = self._split_labels(str(value))
        self.apparatus_stations = ",".join(parts)

    def get_reserve_homes(self):
        """Return configured reserve-home stations; empty means none set."""
        return self._split_labels(self.reserve_homes)

    def set_reserve_homes(self, value):
        if value is None:
            self.reserve_homes = ""
            return
        if isinstance(value, (list, tuple, set)):
            parts = [str(v).strip() for v in value if str(v).strip()]
        else:
            parts = self._split_labels(str(value))
        self.reserve_homes = ",".join(parts)
