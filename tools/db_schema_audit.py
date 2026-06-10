"""
CardDesk Database Schema Audit
==============================

Run from the CardDesk project root:

    python tools/db_schema_audit.py

What it checks:
- Loads the Flask app and SQLAlchemy models
- Connects to the configured database
- Compares each model's expected columns to the actual DB table columns
- Reports missing tables, missing columns, and extra DB columns

This utility does NOT change your database.
It is read-only.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _load_app_and_db():
    """Import the CardDesk Flask app and SQLAlchemy db object."""
    try:
        import app as carddesk_app_module  # type: ignore
        from models import db  # type: ignore
    except Exception as exc:  # pragma: no cover - developer diagnostic
        print("ERROR: Could not import CardDesk app/models.")
        print(f"Detail: {exc}")
        sys.exit(1)

    flask_app = getattr(carddesk_app_module, "app", None)
    if flask_app is None:
        create_app = getattr(carddesk_app_module, "create_app", None)
        if callable(create_app):
            flask_app = create_app()

    if flask_app is None:
        print("ERROR: Could not find Flask app instance in app.py.")
        print("Expected either `app = Flask(...)` or a callable `create_app()`.")
        sys.exit(1)

    return flask_app, db


def _iter_models(db) -> Iterable[Tuple[str, object]]:
    """Return mapped SQLAlchemy models discovered from db.Model registry."""
    seen_tables = set()

    for mapper in db.Model.registry.mappers:
        model = mapper.class_
        table = getattr(model, "__table__", None)
        if table is None:
            continue
        table_name = table.name
        if table_name in seen_tables:
            continue
        seen_tables.add(table_name)
        yield table_name, model


def _format_columns(columns: Iterable[str]) -> str:
    values = sorted(columns)
    if not values:
        return "(none)"
    return ", ".join(values)


def main() -> int:
    flask_app, db = _load_app_and_db()

    print("\nCardDesk DB Schema Audit")
    print("========================")

    with flask_app.app_context():
        try:
            inspector = db.inspect(db.engine)
            actual_tables = set(inspector.get_table_names())
        except Exception as exc:
            print("ERROR: Could not inspect the configured database.")
            print(f"Detail: {exc}")
            return 1

        database_uri = flask_app.config.get("SQLALCHEMY_DATABASE_URI", "(unknown)")
        safe_uri = str(database_uri)
        if "@" in safe_uri and "://" in safe_uri:
            # Avoid printing credentials if Render/Postgres style URI is used.
            prefix, rest = safe_uri.split("://", 1)
            safe_uri = f"{prefix}://***@{rest.split('@', 1)[-1]}"

        print(f"Database: {safe_uri}")

        models = list(_iter_models(db))
        print(f"Models found: {len(models)}")
        print(f"Database tables found: {len(actual_tables)}")

        missing_tables: List[str] = []
        missing_columns: Dict[str, List[str]] = {}
        extra_columns: Dict[str, List[str]] = {}

        for table_name, model in sorted(models, key=lambda item: item[0]):
            expected_cols = {column.name for column in model.__table__.columns}

            if table_name not in actual_tables:
                missing_tables.append(table_name)
                continue

            actual_cols = {column["name"] for column in inspector.get_columns(table_name)}

            missing = sorted(expected_cols - actual_cols)
            extra = sorted(actual_cols - expected_cols)

            if missing:
                missing_columns[table_name] = missing
            if extra:
                extra_columns[table_name] = extra

        print("\nResults")
        print("-------")

        if not missing_tables and not missing_columns:
            print("PASS: Database has all tables and columns required by the models.")
        else:
            print("FAIL: Database schema is missing required tables or columns.")

        if missing_tables:
            print("\nMissing tables:")
            for table in missing_tables:
                print(f"  - {table}")

        if missing_columns:
            print("\nMissing columns:")
            for table, columns in missing_columns.items():
                print(f"  - {table}: {_format_columns(columns)}")

        if extra_columns:
            print("\nExtra columns in database not currently defined on models:")
            for table, columns in extra_columns.items():
                print(f"  - {table}: {_format_columns(columns)}")
            print("\nNote: Extra columns are not always a problem. They may be old columns left over from earlier versions.")

        print("\nThis audit is read-only. It did not modify the database.")

        return 0 if not missing_tables and not missing_columns else 2


if __name__ == "__main__":
    raise SystemExit(main())
