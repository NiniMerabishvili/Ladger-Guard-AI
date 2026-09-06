"""Run Alembic migrations with clear errors for deploy environments."""

from __future__ import annotations

import sys

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from alembic.util.exc import CommandError
from sqlalchemy import create_engine, inspect, text

from app.config import settings


def _config() -> Config:
    cfg = Config("alembic.ini")
    # Escape % so ConfigParser does not treat passwords as interpolation.
    cfg.set_main_option("sqlalchemy.url", settings.DATABASE_URL.replace("%", "%%"))
    return cfg


def _known_revisions(cfg: Config) -> set[str]:
    script = ScriptDirectory.from_config(cfg)
    return {rev.revision for rev in script.walk_revisions()}


def _db_revision(engine) -> str | None:
    with engine.connect() as conn:
        inspector = inspect(conn)
        if "alembic_version" not in inspector.get_table_names():
            return None
        row = conn.execute(text("SELECT version_num FROM alembic_version LIMIT 1")).fetchone()
        return row[0] if row else None


def _schema_has_projects(engine) -> bool:
    with engine.connect() as conn:
        return "projects" in inspect(conn).get_table_names()


def main() -> int:
    cfg = _config()
    script = ScriptDirectory.from_config(cfg)
    known = _known_revisions(cfg)
    heads = script.get_heads()
    print(f"alembic heads={heads}")
    print(f"alembic revisions={sorted(known)}")

    engine = create_engine(settings.DATABASE_URL)
    current = _db_revision(engine)
    print(f"database revision={current!r}")

    # Production DB is already migrated — never block boot on a missing revision file.
    if current is not None and current not in known:
        if _schema_has_projects(engine):
            print(
                f"WARNING: database revision {current!r} is missing from this image, "
                "but projects schema is present — skipping alembic and starting the API.",
                file=sys.stderr,
            )
            return 0
        print(
            f"ERROR: database revision {current!r} is not in this image. "
            f"Known revisions: {sorted(known)}",
            file=sys.stderr,
        )
        return 1

    if current is not None and heads and current in heads:
        print("already at head — skipping upgrade")
        return 0

    try:
        command.upgrade(cfg, "head")
    except CommandError as exc:
        message = str(exc)
        if "Can't locate revision" in message and _schema_has_projects(engine):
            print(
                f"WARNING: {message} — schema already has projects; starting API anyway.",
                file=sys.stderr,
            )
            return 0
        print(f"ERROR: alembic upgrade failed: {exc}", file=sys.stderr)
        return 1

    print("migrations ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
