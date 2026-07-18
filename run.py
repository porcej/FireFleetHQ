import os
import sys
from pathlib import Path

# Bootstrap .env BEFORE importing the app package (importing app runs Config).
_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import importlib.util

_spec = importlib.util.spec_from_file_location(
    'firefleethq_env_loader',
    _ROOT / 'app' / 'env_loader.py',
)
_env_loader = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_env_loader)
_env_path = _env_loader.load_project_env(_ROOT / '.env')

from gevent import monkey
monkey.patch_all()

from app import create_app, db, socketio

app = create_app()

# Initialize database and start background tasks
with app.app_context():
    from sqlalchemy import inspect

    insp = inspect(db.engine)
    if insp.has_table("alembic_version") and not insp.has_table("user"):
        print(
            "Repairing database: Alembic version recorded but schema missing; "
            "creating tables from models and stamping head."
        )
        from flask_migrate import stamp

        db.create_all()
        stamp(revision="heads")
    else:
        try:
            from flask_migrate import upgrade

            print("Running database migrations...")
            upgrade()
            print("Database migrations completed.")
        except Exception as e:
            print(f"Warning: Migration failed ({e}), falling back to db.create_all()")
            db.create_all()
            try:
                from flask_migrate import stamp

                stamp(revision="heads")
                print("Database stamped at head after create_all fallback.")
            except Exception as se:
                print(f"Warning: Could not stamp database: {se}")

    from app.tasks import start_background_tasks
    start_background_tasks(app)

if __name__ == '__main__':
    # Use debug mode only if FLASK_ENV is not 'production'
    debug = os.environ.get('FLASK_ENV') != 'production'

    # When using gevent, disable reloader to avoid fork issues
    # The reloader uses fork() which doesn't work well with gevent monkey patching
    use_reloader = debug and os.environ.get('SOCKETIO_ASYNC_MODE') != 'gevent'

    # Allow unsafe Werkzeug in Docker/production when explicitly using run.py
    # For true production, use Gunicorn instead (see wsgi.py and start_gunicorn.sh)
    allow_unsafe = os.environ.get('FLASK_ENV') == 'production'

    port = int(os.environ.get('PORT', '8000'))

    if _env_path:
        print(f"Loaded environment from {_env_path}")
    else:
        print("Warning: no .env file found; using process environment / defaults")
    print(
        f"Starting FireFleet HQ on port {port} "
        f"(FLASK_ENV={os.environ.get('FLASK_ENV', '')!r}, "
        f"SOCKETIO_ASYNC_MODE={os.environ.get('SOCKETIO_ASYNC_MODE', '')!r})"
    )

    socketio.run(
        app,
        debug=debug,
        host='0.0.0.0',
        port=port,
        use_reloader=use_reloader,
        allow_unsafe_werkzeug=allow_unsafe,
    )
