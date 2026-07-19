# Docker Deployment Guide

This guide explains how to run the FireFleet HQ using Docker Compose.

## Quick Start

1. **Set environment variables** (create a `.env` file):

```bash
SECRET_KEY=your-strong-secret-key-here
# Optional; default in compose is sqlite under /app/data (host ./instance)
DATABASE_URL=sqlite:////app/data/firefleethq.db
SOCKETIO_ASYNC_MODE=threading
SCRAPE_INTERVAL_MINUTES=15
# Host port published by docker compose (container stays on 8000)
HOST_PORT=8000
```

Generate a secret key:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

2. **Build and start the container**:

```bash
docker-compose up -d
```

3. **View logs**:

```bash
docker-compose logs -f
```

4. **Stop the container**:

```bash
docker-compose down
```

## Accessing the Application

Once started, the application will be available at (default `HOST_PORT=8000`):
- **Web Interface**: http://localhost:8000
- **Health Check**: http://localhost:8000/health

On a host that already uses 8000, set a free port in `.env` (for example `HOST_PORT=8010`) and open `http://localhost:8010` instead.

## Data Persistence

By default, `docker-compose.yml` mounts **`./instance`** on the host to **`/app/data`** in the container (SQLite file: `/app/data/firefleethq.db`). Data survives container restarts as long as you keep that folder.

## Adding users (Docker)

Run these **inside the running app container** so they use the same `DATABASE_URL` as the app.

**Service name:** `firefleethq` (must match `docker-compose.yml`). Use either:

- `docker compose exec firefleethq …` (Docker Compose V2), or  
- `docker-compose exec firefleethq …` (older CLI).

**1. Wait until the app has started** (migrations finished). Check logs if needed:

```bash
docker compose logs -f firefleethq
```

### Create an administrator

Replace `admin`, `YourSecurePassword` with your choices:

```bash
docker compose exec firefleethq python -c "
from app import create_app, db
from app.models import User

USERNAME = 'admin'
PASSWORD = 'YourSecurePassword'

app = create_app()
with app.app_context():
    if User.query.filter_by(username=USERNAME).first():
        print('User already exists:', USERNAME)
    else:
        user = User(username=USERNAME, is_admin=True)
        user.set_password(PASSWORD)
        db.session.add(user)
        db.session.commit()
        print('Admin user created:', USERNAME)
"
```

Then open **http://localhost:8000** (or your host) and log in.

### Create a non-admin user

Same pattern with `is_admin=False` (can log in and use the dashboard; only admins get Settings / user management):

```bash
docker compose exec firefleethq python -c "
from app import create_app, db
from app.models import User

USERNAME = 'operator'
PASSWORD = 'YourSecurePassword'

app = create_app()
with app.app_context():
    if User.query.filter_by(username=USERNAME).first():
        print('User already exists:', USERNAME)
    else:
        user = User(username=USERNAME, is_admin=False)
        user.set_password(PASSWORD)
        db.session.add(user)
        db.session.commit()
        print('User created:', USERNAME)
"
```

### Reset a user’s password

```bash
docker compose exec firefleethq python reset_password.py admin --password 'NewSecurePassword'
```

Omit `--password` to be prompted (requires an interactive TTY: add `-it` if needed):

```bash
docker compose exec -it firefleethq python reset_password.py admin
```

**Tip:** If `docker compose exec` fails with “service not running”, use `docker compose ps` to confirm the service name and that the container is up.

## Environment Variables

Key environment variables you can set:

- `SECRET_KEY`: Flask secret key (required, should be strong)
- `DATABASE_URL`: Database connection string (default: SQLite at `/app/data/firefleethq.db` in the container → host `./instance`)
- `SOCKETIO_ASYNC_MODE`: Socket.IO async mode (`threading` for Docker, `gevent` for production)
- `SCRAPE_INTERVAL_MINUTES`: Interval between automatic scrapes
- `FLASK_ENV`: Set to `production` for production mode

## Docker Compose Commands

```bash
# Build the image
docker-compose build

# Start in detached mode
docker-compose up -d

# View logs
docker-compose logs -f firefleethq

# Stop containers
docker-compose stop

# Remove containers
docker-compose down

# Remove containers and volumes (WARNING: deletes data)
docker-compose down -v

# Rebuild and restart
docker-compose up -d --build
```

## Troubleshooting

### Container won't start
- Check logs: `docker-compose logs firefleethq`
- Verify environment variables are set correctly
- Ensure the published host port (`HOST_PORT`, default 8000) is not already in use

### Database errors
- Check that **`./instance`** exists on the host and is writable (matches the default volume in `docker-compose.yml`)
- For SQLite, ensure that directory is writable by the container user

### Fresh deploy / “no such table: task” during migrations
Older images used an empty baseline migration, so a **new** SQLite file could be stamped without creating tables. Current images:
- Create core tables in the baseline migration on first upgrade, and
- **Auto-repair** on startup if `alembic_version` exists but the `user` table is missing (`create_all` + stamp head).

After pulling a fixed image, restart the container. If a volume is still broken, remove the DB file or run:

```bash
docker compose down -v   # removes volumes — backup `./instance` first if you need the DB
docker-compose up -d --build
```

### Socket.IO not working
- Ensure `SOCKETIO_ASYNC_MODE=threading` is set (default in docker-compose.yml)
- Check that the container is accessible from your browser
- Review application logs for Socket.IO connection errors

## Production Considerations

For production deployment:

1. **Use a production WSGI server**: Consider using Gunicorn instead of `run.py`:
   - Update Dockerfile CMD to: `CMD ["gunicorn", "--worker-class", "gevent", "--workers", "4", "--bind", "0.0.0.0:8000", "wsgi:application"]`
   - Update environment: `SOCKETIO_ASYNC_MODE=gevent`

2. **Use PostgreSQL**: Replace SQLite with PostgreSQL:
   ```yaml
   services:
     db:
       image: postgres:15
       environment:
         POSTGRES_DB: firefleethq
         POSTGRES_USER: firefleethq
         POSTGRES_PASSWORD: your-password
       volumes:
         - postgres_data:/var/lib/postgresql/data
   
     firefleethq:
       # ... existing config ...
       depends_on:
         - db
       environment:
         DATABASE_URL: postgresql://firefleethq:your-password@db/firefleethq
   ```

3. **Add reverse proxy**: Use Nginx in front of the application for SSL/TLS

4. **Set strong SECRET_KEY**: Always use a strong, random secret key in production

5. **Monitor logs**: Set up log aggregation and monitoring

