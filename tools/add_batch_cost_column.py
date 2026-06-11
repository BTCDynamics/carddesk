"""One-time CardDesk SQLite/SQLAlchemy patch for Batch Performance.

Adds IntakeBatch.total_batch_cost to an existing database.
Safe to run more than once.

Run from the CardDesk project folder while your venv is active:
    python tools/add_batch_cost_column.py
"""

from sqlalchemy import text

try:
    from app import app, db
except Exception as exc:
    raise SystemExit(
        "Could not import app/db. Run this from your CardDesk project root "
        "with the virtual environment active.\n\nOriginal error: " + str(exc)
    )


def main():
    with app.app_context():
        rows = db.session.execute(text("PRAGMA table_info(intake_batch)")).fetchall()
        columns = {row[1] for row in rows}

        if "total_batch_cost" in columns:
            print("OK: intake_batch.total_batch_cost already exists. Nothing to do.")
            return

        db.session.execute(
            text("ALTER TABLE intake_batch ADD COLUMN total_batch_cost FLOAT DEFAULT 0")
        )
        db.session.commit()
        print("OK: Added intake_batch.total_batch_cost column.")


if __name__ == "__main__":
    main()
