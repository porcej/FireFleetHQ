"""
WSGI entry point for Gunicorn
"""
import importlib.util
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

_spec = importlib.util.spec_from_file_location(
    'firefleethq_env_loader',
    _ROOT / 'app' / 'env_loader.py',
)
_env_loader = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_env_loader)
_env_loader.load_project_env(_ROOT / '.env')

from gevent import monkey
monkey.patch_all()

from app import create_app, db, socketio
from app.tasks import start_background_tasks

# Create the Flask application
app = create_app()

# Initialize database and start background tasks
with app.app_context():
    from sqlalchemy import inspect

    insp = inspect(db.engine)
    if insp.has_table("alembic_version") and not insp.has_table("user"):
        from flask_migrate import stamp

        db.create_all()
        stamp(revision="heads")
    else:
        try:
            from flask_migrate import upgrade

            upgrade()
        except Exception:
            db.create_all()
            try:
                from flask_migrate import stamp

                stamp(revision="heads")
            except Exception:
                pass
    start_background_tasks(app)

# Export the Flask app for Gunicorn
application = app
