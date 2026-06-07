import json
import os
from datetime import date

from flask import render_template, request, redirect, url_for
from sqlalchemy import text

from models import db, Card, CardImportStaging
from helpers.storage_helpers import (
    get_storage_summary,
    get_inventory_health_summary,
    describe_inventory_health_issues,
)



def _storage_registry_path(app):
    """Return the local JSON file used for managed storage locations."""
    os.makedirs(app.instance_path, exist_ok=True)
    return os.path.join(app.instance_path, "storage_locations.json")


def _normalize_location(value):
    """Normalize spacing around location parts while preserving the user's labels."""
    value = (value or "").strip()
    parts = [part.strip() for part in value.split("/") if part.strip()]
    return " / ".join(parts)


def _load_managed_storage_locations(app):
    """Load user-created storage location names from the JSON registry."""
    path = _storage_registry_path(app)
    if not os.path.exists(path):
        return []

    try:
        with open(path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return []

    locations = payload.get("locations", []) if isinstance(payload, dict) else []
    cleaned = [_normalize_location(location) for location in locations]
    return sorted({location for location in cleaned if location})


def _save_managed_storage_locations(app, locations):
    """Persist the managed storage location registry."""
    path = _storage_registry_path(app)
    cleaned = sorted({_normalize_location(location) for location in locations if _normalize_location(location)})
    with open(path, "w", encoding="utf-8") as handle:
        json.dump({"locations": cleaned}, handle, indent=2)
    return cleaned


def _get_existing_card_storage_locations():
    """Return distinct storage values already present on card records."""
    rows = (
        db.session.query(Card.storage_location)
        .filter(Card.storage_location.isnot(None))
        .filter(db.func.trim(Card.storage_location) != "")
        .distinct()
        .all()
    )
    cleaned = [_normalize_location(row[0]) for row in rows]
    return sorted({location for location in cleaned if location})


def _get_all_storage_location_choices(app):
    """Combine managed locations with existing card locations for dropdowns."""
    return sorted(set(_load_managed_storage_locations(app)) | set(_get_existing_card_storage_locations()))




def register_storage_routes(app):
    @app.context_processor
    def inject_storage_location_choices():
        """Make managed storage choices available to card templates without route rewrites."""
        try:
            choices = _get_all_storage_location_choices(app)
            managed = _load_managed_storage_locations(app)
        except Exception:
            choices = []
            managed = []

        return {
            "managed_storage_locations": managed,
            "all_storage_location_choices": choices,
        }

    @app.route("/health")
    def health():
        """Render health check endpoint."""
        try:
            upload_folder = app.config["UPLOAD_FOLDER"]

            if not os.path.exists(upload_folder):
                return {"status": "error", "message": "Upload folder unavailable"}, 500

            db.session.execute(text("SELECT 1"))

            return {"status": "ok"}, 200

        except Exception as error:
            return {"status": "error", "message": str(error)}, 500


    @app.route("/inventory-health")
    def inventory_health():
        """Dedicated cleanup page for inventory records that need finishing."""
        issue_filter = request.args.get("issue", "all")

        base_query = Card.query
        active_inventory_query = Card.query.filter(Card.status != "Sold").filter(Card.collection_type == "Inventory")

        # Missing images should be counted for non-sold records, including records
        # where status is blank/null, and should treat whitespace-only filenames as missing.
        non_sold_query = Card.query.filter(
            db.or_(
                Card.status.is_(None),
                db.func.trim(Card.status) == "",
                Card.status != "Sold",
            )
        )

        missing_image_query = non_sold_query.filter(
            db.or_(
                Card.image_filename.is_(None),
                db.func.trim(Card.image_filename) == "",
            )
        )

        missing_image_count = missing_image_query.count()

        issue_definitions = [
            {
                "key": "cost",
                "label": "Missing Cost",
                "description": "Cost protects profit, ROI, and sales analytics.",
                "count": base_query.filter(Card.purchase_price.is_(None)).count(),
            },
            {
                "key": "storage",
                "label": "Missing Storage Location",
                "description": "Storage location helps you find cards when they sell.",
                "count": active_inventory_query.filter(
                    db.or_(
                        Card.storage_location.is_(None),
                        db.func.trim(Card.storage_location) == "",
                    )
                ).count(),
            },
            {
                "key": "asking",
                "label": "Missing Asking Price",
                "description": "Asking price helps estimate potential revenue.",
                "count": active_inventory_query.filter(
                    db.or_(
                        Card.asking_price.is_(None),
                        Card.asking_price == 0,
                    )
                ).count(),
            },
            {
                "key": "value",
                "label": "Missing Comp Value",
                "description": "Comp value helps estimate inventory value.",
                "count": active_inventory_query.filter(
                    db.or_(
                        Card.estimated_value.is_(None),
                        Card.estimated_value == 0,
                    )
                ).count(),
            },
            {
                "key": "image",
                "label": "Missing Images",
                "description": "Images help identify cards and support listings.",
                "count": missing_image_count,
            },
            {
                "key": "ai_review",
                "label": "AI Review Queue",
                "description": "Captured or uploaded cards waiting for import review.",
                "count": CardImportStaging.query.filter(
                    CardImportStaging.ai_status.in_(["Pending Review", "Needs Manual Review"])
                ).count(),
                "external_url": url_for("ai_import_review"),
            },
        ]

        if issue_filter == "cost":
            cards_query = base_query.filter(Card.purchase_price.is_(None))
            current_label = "Missing Cost"
        elif issue_filter == "storage":
            cards_query = active_inventory_query.filter(
                db.or_(
                    Card.storage_location.is_(None),
                    db.func.trim(Card.storage_location) == "",
                )
            )
            current_label = "Missing Storage Location"
        elif issue_filter == "asking":
            cards_query = active_inventory_query.filter(
                db.or_(
                    Card.asking_price.is_(None),
                    Card.asking_price == 0,
                )
            )
            current_label = "Missing Asking Price"
        elif issue_filter == "value":
            cards_query = active_inventory_query.filter(
                db.or_(
                    Card.estimated_value.is_(None),
                    Card.estimated_value == 0,
                )
            )
            current_label = "Missing Comp Value"
        elif issue_filter == "image":
            cards_query = missing_image_query
            current_label = "Missing Images"
        elif issue_filter == "ai_review":
            return redirect(url_for("ai_import_review"))
        else:
            issue_filter = "all"
            cards_query = base_query.filter(
                db.or_(
                    Card.purchase_price.is_(None),
                    db.and_(
                        Card.status != "Sold",
                        Card.collection_type == "Inventory",
                        db.or_(
                            Card.storage_location.is_(None),
                            db.func.trim(Card.storage_location) == "",
                            Card.asking_price.is_(None),
                            Card.asking_price == 0,
                            Card.estimated_value.is_(None),
                            Card.estimated_value == 0,
                        )
                    ),
                    db.and_(
                        db.or_(
                            Card.status.is_(None),
                            db.func.trim(Card.status) == "",
                            Card.status != "Sold",
                        ),
                        db.or_(
                            Card.image_filename.is_(None),
                            db.func.trim(Card.image_filename) == "",
                        )
                    )
                )
            )
            current_label = "All Inventory Health Issues"

        cards_needing_attention = cards_query.order_by(Card.id.desc()).limit(100).all()
        card_issue_map = {
            card.id: describe_inventory_health_issues(card)
            for card in cards_needing_attention
        }

        summary = get_inventory_health_summary()

        # Keep summary total aligned with the route-level missing image calculation.
        # This prevents a stale helper count from making the total look wrong.
        summary["missing_image_count"] = missing_image_count
        summary["health_issue_count"] = (
            summary.get("missing_cost_count", 0)
            + summary.get("missing_storage_count", 0)
            + summary.get("missing_asking_price_count", 0)
            + summary.get("missing_estimated_value_count", 0)
            + missing_image_count
            + summary.get("ai_review_count", 0)
        )

        return render_template(
            "inventory_health.html",
            issue_definitions=issue_definitions,
            cards_needing_attention=cards_needing_attention,
            card_issue_map=card_issue_map,
            issue_filter=issue_filter,
            current_label=current_label,
            summary=summary,
            missing_image_count=missing_image_count,
        )


    @app.route("/storage")
    def storage_explorer():
        storage_summary = get_storage_summary()

        total_locations = len(storage_summary)
        total_cards = sum(item["total_cards"] for item in storage_summary)
        total_purchase_cost = sum(item["purchase_cost"] for item in storage_summary)
        total_estimated_value = sum(item["estimated_value"] for item in storage_summary)

        managed_storage_locations = _load_managed_storage_locations(app)
        all_storage_location_choices = _get_all_storage_location_choices(app)

        return render_template(
            "storage.html",
            storage_summary=storage_summary,
            total_locations=total_locations,
            total_cards=total_cards,
            total_purchase_cost=total_purchase_cost,
            total_estimated_value=total_estimated_value,
            managed_storage_locations=managed_storage_locations,
            all_storage_location_choices=all_storage_location_choices,
        )


    @app.route("/storage/add-location", methods=["POST"])
    def add_storage_location():
        """Add one managed storage location manually."""
        location = _normalize_location(request.form.get("storage_location", ""))
        existing_locations = _load_managed_storage_locations(app)
        if location:
            _save_managed_storage_locations(app, existing_locations + [location])
        return redirect(url_for("storage_explorer"))


    @app.route("/storage/delete-location", methods=["POST"])
    def delete_storage_location():
        """Remove a managed storage location from the dropdown list only.

        This does not edit any existing card records. If cards already use this
        location, it will continue to appear through existing card storage values.
        """
        location = _normalize_location(request.form.get("storage_location", ""))
        existing_locations = _load_managed_storage_locations(app)
        if location:
            _save_managed_storage_locations(app, [item for item in existing_locations if item != location])
        return redirect(url_for("storage_explorer"))


    @app.route("/pull-sheet")
    def pull_sheet():
        """Print a pull sheet for cards matching the current storage/filter view."""
        storage_filter = request.args.get("storage", "")
        status_filter = request.args.get("status", "")
        collection_type_filter = request.args.get("collection_type", "")

        query = Card.query

        if storage_filter == "__missing__":
            query = query.filter(
                db.or_(
                    Card.storage_location.is_(None),
                    db.func.trim(Card.storage_location) == ""
                )
            )
        elif storage_filter:
            query = query.filter(Card.storage_location == storage_filter)

        if status_filter:
            query = query.filter(Card.status == status_filter)

        if collection_type_filter:
            query = query.filter(Card.collection_type == collection_type_filter)

        cards = (
            query
            .order_by(
                Card.storage_location.asc(),
                Card.player_name.asc(),
                Card.year.asc(),
                Card.brand.asc(),
                Card.card_number.asc(),
                Card.id.asc(),
            )
            .all()
        )

        total_quantity = sum((card.quantity or 1) for card in cards)
        total_asking = sum((card.asking_price or 0) * (card.quantity or 1) for card in cards)
        total_estimated_value = sum((card.estimated_value or 0) * (card.quantity or 1) for card in cards)

        return render_template(
            "pull_sheet.html",
            cards=cards,
            storage_filter=storage_filter,
            status_filter=status_filter,
            collection_type_filter=collection_type_filter,
            total_quantity=total_quantity,
            total_asking=total_asking,
            total_estimated_value=total_estimated_value,
            today=date.today().isoformat(),
        )
