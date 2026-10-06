"""Locations for configuration and the local database."""

from __future__ import annotations

import os
from pathlib import Path


def screener_root() -> Path:
    """Directory that contains config/ and prompts/.

    Override with SCREENER_ROOT when the package is not running from a checkout.
    """

    override = os.environ.get("SCREENER_ROOT")
    if override:
        return Path(override).expanduser().resolve()
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "config" / "thresholds.yaml").is_file():
            return parent
    raise FileNotFoundError(
        "Cannot find screener config. Set SCREENER_ROOT to the directory that contains config/."
    )


def project_root() -> Path:
    """Repository root, parent of the screener package directory."""

    return screener_root().parent


def load_project_env() -> None:
    """Load KEY=VALUE lines from the repository .env file.

    Existing environment variables win, so a shell export is left as-is.
    """

    path = project_root() / ".env"
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if not text or text.startswith("#") or "=" not in text:
            continue
        key, value = text.split("=", 1)
        key = key.strip()
        value = value.strip().strip("\"'")
        if key and key not in os.environ:
            os.environ[key] = value


def data_dir() -> Path:
    """Snapshot files and screener.db. Defaults to the repository data/ directory."""

    override = os.environ.get("SCREENER_DATA_DIR")
    if override:
        return Path(override).expanduser().resolve()
    return screener_root().parent / "data"


def database_url() -> str:
    """SQLite by default. Set SCREENER_DATABASE_URL to point the same models at Postgres."""

    override = os.environ.get("SCREENER_DATABASE_URL")
    if override:
        return override
    path = data_dir() / "screener.db"
    return f"sqlite:///{path}"
