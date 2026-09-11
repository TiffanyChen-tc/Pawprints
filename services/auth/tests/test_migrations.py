from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import tomllib

from alembic.config import Config
from sqlalchemy import text


def test_auth_migration_uses_auth_schema_version_table(auth_db_session):
    row = auth_db_session.execute(
        text(
            "select to_regclass('auth.users')::text, "
            "to_regclass('auth.refresh_tokens')::text, "
            "to_regclass('auth.alembic_version')::text, "
            "to_regclass('public.alembic_version')::text"
        )
    ).one()

    assert row == ("auth.users", "auth.refresh_tokens", "auth.alembic_version", None)


def test_auth_migration_and_tests_resolve_auth_app_before_other_services():
    repository_root = Path(__file__).resolve().parents[3]
    alembic_config = Config(repository_root / "services/auth/alembic.ini")
    prepend_path = alembic_config.get_main_option("prepend_sys_path")

    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(repository_root / "services/event")
    imported_config = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import pathlib, sys; "
                f"sys.path.insert(0, {prepend_path!r}); "
                "import app.config; "
                "print(pathlib.Path(app.config.__file__).resolve())"
            ),
        ],
        cwd=repository_root,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()

    assert Path(imported_config) == (repository_root / "services/auth/app/config.py").resolve()

    auth_root = repository_root / "services/auth"
    pyproject = tomllib.loads((auth_root / "pyproject.toml").read_text(encoding="utf-8"))
    pytest_path = pyproject["tool"]["pytest"]["ini_options"]["pythonpath"]
    pytest_imported_config = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import pathlib, sys; "
                f"sys.path.insert(0, {pytest_path[0]!r}); "
                "import app.config; "
                "print(pathlib.Path(app.config.__file__).resolve())"
            ),
        ],
        cwd=auth_root,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()

    assert pytest_path == ["."]
    assert Path(pytest_imported_config) == (auth_root / "app/config.py").resolve()


def test_auth_migration_runs_with_only_database_configuration(auth_database_url):
    repository_root = Path(__file__).resolve().parents[3]
    environment = {
        key: os.environ[key]
        for key in ("PATH", "SYSTEMROOT", "WINDIR")
        if key in os.environ
    }
    environment.update(
        {
            "AUTH_DATABASE_URL": auth_database_url,
            "PYTHONPATH": str(repository_root / "services/event"),
        }
    )

    subprocess.run(
        [
            sys.executable,
            "-m",
            "alembic",
            "-c",
            "services/auth/alembic.ini",
            "upgrade",
            "head",
        ],
        cwd=repository_root,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )
