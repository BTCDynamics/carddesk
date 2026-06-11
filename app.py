import json
import os
from urllib.parse import quote

from flask import Flask, render_template, url_for, send_from_directory, jsonify
from sqlalchemy import inspect, text

from models import db, CardImportStaging, CompRefreshQueue, IntakeBatch
from helpers.card_code_helpers import generate_card_code
from helpers.image_helpers import (
    save_uploaded_image,
    delete_image_file,
    save_uploaded_image_with_source,
    rename_image_for_inventory,
)
from helpers.recognition_helpers import (
    normalize_year,
    recognize_card_image,
    recognition_configured,
)
from helpers.deal_cart_helpers import get_deal_cart_cards
from helpers.inventory_health_helpers import get_inventory_health_summary
from modules.storage_routes import register_storage_routes
from modules.dashboard_routes import register_dashboard_routes
from modules.inventory_routes import register_inventory_routes
from modules.sales_routes import register_sales_routes
from modules.psa_routes import register_psa_routes
from modules.ai_import_routes import register_ai_import_routes
from modules.capture_routes import register_capture_routes
from modules.fulfillment_routes import register_fulfillment_routes
from modules.comp_refresh_routes import register_comp_refresh_routes
from modules.show_prep_routes import register_show_prep_routes
from modules.batch_routes import register_batch_routes


app = Flask(__name__)

app.secret_key = os.environ.get("CARDWATCH_SECRET_KEY", "cardwatch-dev-secret")

DATA_DIR = os.environ.get(
    "CARDWATCH_DATA_DIR",
    os.path.join(os.path.dirname(__file__), "data")
)
os.makedirs(DATA_DIR, exist_ok=True)



DB_NAME = os.environ.get("CARDWATCH_DB_NAME", "carddesk.db")

print(f"CardDesk DATA_DIR: {DATA_DIR}")
print(f"CardDesk DB: {os.path.join(DATA_DIR, DB_NAME)}")

PERSISTENT_UPLOAD_FOLDER = os.path.join(DATA_DIR, "uploads")

app.config["SQLALCHEMY_DATABASE_URI"] = (
    f"sqlite:///{os.path.join(DATA_DIR, DB_NAME)}"
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["UPLOAD_FOLDER"] = PERSISTENT_UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024  # 8 MB upload limit

db.init_app(app)


def ensure_upload_folder():
    """Create persistent upload storage on Render's mounted disk.

    Images are saved directly to app.config["UPLOAD_FOLDER"], which defaults
    to /var/data/uploads. No symlink, move, or migration logic is used.
    """
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)


def ensure_database_columns():
    """Add newer columns to an existing SQLite database without wiping data."""
    inspector = inspect(db.engine)

    if "card" not in inspector.get_table_names():
        return

    existing_columns = {
        column["name"]
        for column in inspector.get_columns("card")
    }

    if "image_filename" not in existing_columns:
        db.session.execute(
            text("ALTER TABLE card ADD COLUMN image_filename VARCHAR(200)")
        )
        db.session.commit()

    if "image_back_filename" not in existing_columns:
        db.session.execute(
            text("ALTER TABLE card ADD COLUMN image_back_filename VARCHAR(200)")
        )
        db.session.commit()

    if "estimated_value" not in existing_columns:
        db.session.execute(
            text("ALTER TABLE card ADD COLUMN estimated_value FLOAT")
        )
        db.session.commit()

    if "asking_price" not in existing_columns:
        db.session.execute(
            text("ALTER TABLE card ADD COLUMN asking_price FLOAT")
        )
        db.session.commit()

    if "sold_price" not in existing_columns:
        db.session.execute(
            text("ALTER TABLE card ADD COLUMN sold_price FLOAT")
        )
        db.session.commit()

    if "sold_date" not in existing_columns:
        db.session.execute(
            text("ALTER TABLE card ADD COLUMN sold_date VARCHAR(20)")
        )
        db.session.commit()

    if "sales_platform" not in existing_columns:
        db.session.execute(
            text("ALTER TABLE card ADD COLUMN sales_platform VARCHAR(100)")
        )
        db.session.commit()

    if "collection_type" not in existing_columns:
        db.session.execute(
            text("ALTER TABLE card ADD COLUMN collection_type VARCHAR(50) DEFAULT 'Inventory'")
        )
        db.session.commit()

    if "fulfillment_status" not in existing_columns:
        db.session.execute(
            text("ALTER TABLE card ADD COLUMN fulfillment_status VARCHAR(50) DEFAULT 'In Storage'")
        )
        db.session.commit()

    if "shipping_carrier" not in existing_columns:
        db.session.execute(
            text("ALTER TABLE card ADD COLUMN shipping_carrier VARCHAR(50)")
        )
        db.session.commit()

    if "tracking_number" not in existing_columns:
        db.session.execute(
            text("ALTER TABLE card ADD COLUMN tracking_number VARCHAR(100)")
        )
        db.session.commit()

    if "shipping_cost" not in existing_columns:
        db.session.execute(
            text("ALTER TABLE card ADD COLUMN shipping_cost FLOAT")
        )
        db.session.commit()

    if "shipped_date" not in existing_columns:
        db.session.execute(
            text("ALTER TABLE card ADD COLUMN shipped_date VARCHAR(20)")
        )
        db.session.commit()

    if "shipping_notes" not in existing_columns:
        db.session.execute(
            text("ALTER TABLE card ADD COLUMN shipping_notes TEXT")
        )
        db.session.commit()


    add_column_if_missing(
        "card",
        "acquisition_source",
        "ALTER TABLE card ADD COLUMN acquisition_source VARCHAR(50) DEFAULT 'Existing Inventory'"
    )
    add_column_if_missing(
        "card",
        "acquisition_date",
        "ALTER TABLE card ADD COLUMN acquisition_date VARCHAR(20)"
    )
    add_column_if_missing(
        "card",
        "acquisition_event",
        "ALTER TABLE card ADD COLUMN acquisition_event VARCHAR(150)"
    )

    # Deal / transaction tracking fields. These are safe no-op checks on newer databases.
    add_column_if_missing(
        "card",
        "deal_id",
        "ALTER TABLE card ADD COLUMN deal_id VARCHAR(100)"
    )
    add_column_if_missing(
        "card",
        "customer_name",
        "ALTER TABLE card ADD COLUMN customer_name VARCHAR(150)"
    )
    add_column_if_missing(
        "card",
        "payment_type",
        "ALTER TABLE card ADD COLUMN payment_type VARCHAR(50)"
    )
    add_column_if_missing(
        "card",
        "deal_discount_percent",
        "ALTER TABLE card ADD COLUMN deal_discount_percent FLOAT"
    )
    add_column_if_missing(
        "card",
        "trade_credit",
        "ALTER TABLE card ADD COLUMN trade_credit FLOAT"
    )
    add_column_if_missing(
        "card",
        "cash_received",
        "ALTER TABLE card ADD COLUMN cash_received FLOAT"
    )
    add_column_if_missing(
        "card",
        "deal_notes",
        "ALTER TABLE card ADD COLUMN deal_notes TEXT"
    )

    add_column_if_missing(
        "card_import_staging",
        "acquisition_source",
        "ALTER TABLE card_import_staging ADD COLUMN acquisition_source VARCHAR(50) DEFAULT 'Existing Inventory'"
    )
    add_column_if_missing(
        "card_import_staging",
        "acquisition_date",
        "ALTER TABLE card_import_staging ADD COLUMN acquisition_date VARCHAR(20)"
    )
    add_column_if_missing(
        "card_import_staging",
        "acquisition_event",
        "ALTER TABLE card_import_staging ADD COLUMN acquisition_event VARCHAR(150)"
    )

    add_column_if_missing(
        "card_import_staging",
        "image_back_filename",
        "ALTER TABLE card_import_staging ADD COLUMN image_back_filename VARCHAR(200)"
    )

    add_column_if_missing(
        "card",
        "intake_batch_id",
        "ALTER TABLE card ADD COLUMN intake_batch_id INTEGER"
    )
    add_column_if_missing(
        "card_import_staging",
        "intake_batch_id",
        "ALTER TABLE card_import_staging ADD COLUMN intake_batch_id INTEGER"
    )



def add_column_if_missing(table_name, column_name, ddl):
    """Safely add a SQLite column only if it does not already exist."""
    inspector = inspect(db.engine)

    if table_name not in inspector.get_table_names():
        return

    existing_columns = {
        column["name"]
        for column in inspector.get_columns(table_name)
    }

    if column_name not in existing_columns:
        db.session.execute(text(ddl))
        db.session.commit()

@app.route("/uploads/<path:filename>")
def uploaded_file(filename):
    """Serve uploaded card images from persistent disk."""
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)


@app.route("/static/uploads/<path:filename>")
def uploaded_static_file(filename):
    """Keep existing template image URLs working without a symlink."""
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)


with app.app_context():
    db.create_all()
    ensure_database_columns()
    ensure_upload_folder()


# Route modules
register_storage_routes(app)
register_dashboard_routes(app)
register_batch_routes(app)



@app.route("/intake-tools")
def intake_tools():
    active_intake_batch = (
        IntakeBatch.query
        .filter(IntakeBatch.status == "Active")
        .order_by(IntakeBatch.id.desc())
        .first()
    )
    mobile_capture_url = url_for("mobile_capture", _external=True)
    mobile_capture_qr_url = (
        "https://api.qrserver.com/v1/create-qr-code/"
        f"?size=220x220&data={quote(mobile_capture_url, safe='')}"
    )

    return render_template(
        "intake_tools.html",
        active_intake_batch=active_intake_batch,
        mobile_capture_url=mobile_capture_url,
        mobile_capture_qr_url=mobile_capture_qr_url,
    )


@app.context_processor
def inject_global_counts():
    pending_import_count = 0
    manual_review_count = 0
    ai_import_action_count = 0

    try:
        pending_import_count = CardImportStaging.query.filter(
            CardImportStaging.ai_status == "Pending Review"
        ).count()

        manual_review_count = CardImportStaging.query.filter(
            CardImportStaging.ai_status == "Needs Manual Review"
        ).count()

        ai_import_action_count = pending_import_count + manual_review_count
    except Exception:
        pending_import_count = 0
        manual_review_count = 0
        ai_import_action_count = 0

    inventory_health = get_inventory_health_summary()

    return {
        "deal_cart_count": sum(
            (card.quantity or 1)
            for card in get_deal_cart_cards()
        ),
        "pending_import_count": pending_import_count,
        "manual_review_count": manual_review_count,
        "ai_import_action_count": ai_import_action_count,
        "health_issue_count": inventory_health["health_issue_count"],
        "missing_cost_count": inventory_health["missing_cost_count"],
        "missing_storage_health_count": inventory_health["missing_storage_count"],
        "missing_asking_price_count": inventory_health["missing_asking_price_count"],
        "missing_estimated_value_count": inventory_health["missing_estimated_value_count"],
    }


@app.route("/api/nav-counts")
def nav_counts():
    """Return small live counts used by the navbar badges.

    This lets an already-open Dealer Hub or dashboard update after Mobile Capture
    saves a staged card from another device, without requiring a full page refresh.
    """
    pending_import_count = CardImportStaging.query.filter(
        CardImportStaging.ai_status == "Pending Review"
    ).count()

    manual_review_count = CardImportStaging.query.filter(
        CardImportStaging.ai_status == "Needs Manual Review"
    ).count()

    ai_import_action_count = pending_import_count + manual_review_count

    return jsonify({
        "pending_import_count": pending_import_count,
        "manual_review_count": manual_review_count,
        "ai_import_action_count": ai_import_action_count,
    })


# Route modules that depend on helper functions defined above.
register_inventory_routes(app, generate_card_code, save_uploaded_image, delete_image_file)
register_sales_routes(app)
register_psa_routes(app)
register_ai_import_routes(
    app,
    generate_card_code,
    save_uploaded_image_with_source,
    recognize_card_image,
    normalize_year,
    rename_image_for_inventory,
    delete_image_file,
    recognition_configured,
)
register_capture_routes(app, save_uploaded_image_with_source, recognize_card_image)
register_fulfillment_routes(app)
register_comp_refresh_routes(app)
register_show_prep_routes(app)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=os.environ.get("FLASK_DEBUG", "0") == "1")
