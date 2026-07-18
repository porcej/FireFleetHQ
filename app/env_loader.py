"""Load project-root .env into os.environ (override existing values)."""

from __future__ import annotations

import os
from pathlib import Path


def project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def load_project_env(env_file: Path | None = None) -> Path | None:
    """
    Load .env from the project root.

    Uses python-dotenv when available; otherwise a minimal parser.
    Values in .env override existing environment variables so local
    project settings win over ambient shell/IDE values.
    """
    path = env_file or (project_root() / '.env')
    if not path.is_file():
        return None

    try:
        from dotenv import load_dotenv

        load_dotenv(path, override=True)
        return path
    except ImportError:
        pass

    # Minimal fallback when python-dotenv is not installed
    for raw in path.read_text(encoding='utf-8').splitlines():
        line = raw.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        if line.startswith('export '):
            line = line[len('export '):].strip()
        key, _, value = line.partition('=')
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
            value = value[1:-1]
        if key:
            os.environ[key] = value
    return path
