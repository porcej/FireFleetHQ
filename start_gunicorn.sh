#!/bin/bash
# Start script for Gunicorn with gevent

# Prefer local ./venv, then a shared project venv if present
if [ -d "venv" ]; then
    # shellcheck source=/dev/null
    source venv/bin/activate
elif [ -f "${HOME}/.venv/firefleethq/bin/activate" ]; then
    # shellcheck source=/dev/null
    source "${HOME}/.venv/firefleethq/bin/activate"
elif [ -f "${HOME}/.venv/scba_dash/bin/activate" ]; then
    # shellcheck source=/dev/null
    source "${HOME}/.venv/scba_dash/bin/activate"
fi

export SOCKETIO_ASYNC_MODE=gevent
export FLASK_ENV=production

gunicorn \
    --worker-class gevent \
    --workers 1 \
    --bind 0.0.0.0:8000 \
    --timeout 30 \
    --access-logfile - \
    --error-logfile - \
    --log-level info \
    wsgi:application
