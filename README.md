# FireFleet HQ

A Flask-based dashboard for Fire Department apparatus fleets. PSTrax is the authoritative data source via the **Fleet Status Report** (`/department-status-report.php`).

This project follows the same architecture as the SCBA Dashboard reference (Flask + Jinja/Bootstrap + SQLAlchemy + SocketIO + APScheduler + `requests`/BeautifulSoup scraper), adapted for apparatus inventory and due dates instead of SCBA cylinders/fills.

## Features

- Bootstrap 5 UI with dark/light theme toggle
- Real-time updates via Flask-SocketIO
- Task management and scheduled banner alerts
- PSTrax apparatus sync from the Department / Fleet Status Report
- Settings for encrypted PSTrax credentials, sync intervals, timezone, and station/status filters
- Docker / Gunicorn deployment path

## Requirements

- Python 3.8+
- pip

## Installation

```bash
cd FireFleetHQ
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env and set a strong SECRET_KEY
python init_db.py
python run.py
```

The app listens on `http://localhost:8000`.

## PSTrax setup

1. Log in as an admin user
2. Open **Settings**
3. Set base URL (often `https://app1.pstrax.com`), username, and password
4. Click **Sync Apparatus Now** or **Capture Sample Response**

### Capture helper (discovery)

```bash
python capture_department_status.py
```

Writes a raw response under `PSTrax Example/` (gitignored) and stores parsed rows when possible. Use this to confirm field names if mapping needs tuning in `app/pstrax_apparatus_map.py`.

## Database migrations

```bash
flask --app "app:create_app" db upgrade
flask --app "app:create_app" db migrate -m "Description"
```

`run.py` / `wsgi.py` also attempt `upgrade()` on startup.

## Adding users

```bash
python add_user.py
```

Admins can also manage users from the **Users** page.

## Reset a password

Interactive:

```bash
python reset_password.py
# or
python reset_password.py someuser
```

Non-interactive (scripts / Docker):

```bash
python reset_password.py someuser --password 'NewSecurePassword'
```

## Environment variables

| Variable | Purpose | Default |
|----------|---------|---------|
| `SECRET_KEY` | Flask sessions + Fernet seed | weak dev default |
| `DATABASE_URL` | SQLAlchemy URI | `sqlite:///firefleethq.db` |
| `ENCRYPTION_KEY` | Fernet for PSTrax password | derived from `SECRET_KEY` |
| `SCRAPE_INTERVAL_MINUTES` | Config default only | `15` |
| `SOCKETIO_ASYNC_MODE` | `gevent` / `threading` | `gevent` |
| `SESSION_COOKIE_SECURE` | HTTPS cookies | `False` |
| `FLASK_ENV` | production vs debug | |
| `TZ` / `APP_TIMEZONE` | timezone | `America/New_York` |

PSTrax credentials are stored encrypted in `scrape_config` via Settings, not as env vars.

## Docker

```bash
docker compose up --build
```

Health check: `GET /health`.

## Project layout

- `app/scraper.py` — PSTrax login + department status fetch
- `app/pstrax_apparatus_map.py` — row → `Apparatus` field mapping
- `app/models/apparatus.py` — fleet inventory table
- `capture_department_status.py` — CLI sample capture
- `Reference/` — gitignored SCBA_dash reference clone

## Notes

- v1 is **read-only** against PSTrax (no write-back).
- Gear-type IDs from the SCBA gear list do not apply to the Fleet Status Report.
- If the report page is HTML-only, the scraper parses tables and also tries companion `*-data.php` endpoints.
