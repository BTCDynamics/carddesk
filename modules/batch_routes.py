from datetime import date

from flask import render_template, request, redirect, url_for, flash

from models import db, Card, CardImportStaging, IntakeBatch
from helpers.acquisition_helpers import clean_value, acquisition_value, acquisition_date_value
from helpers.storage_helpers import get_storage_locations


BATCH_STATUSES = ["Active", "Closed"]


def money(value):
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def percent(numerator, denominator):
    denominator = money(denominator)
    if not denominator:
        return 0.0
    return (money(numerator) / denominator) * 100


def ensure_batch_performance_columns():
    """Add lightweight SQLite columns for older local databases.

    db.create_all() creates new tables, but it does not alter existing SQLite
    tables. This keeps the update safe for the user's current carddesk.db.
    """
    engine_name = db.engine.url.get_backend_name()

    if engine_name != "sqlite":
        return

    with db.engine.begin() as connection:
        columns = {
            row[1]
            for row in connection.exec_driver_sql("PRAGMA table_info(intake_batch)").fetchall()
        }

        if "total_batch_cost" not in columns:
            connection.exec_driver_sql(
                "ALTER TABLE intake_batch ADD COLUMN total_batch_cost FLOAT DEFAULT 0"
            )


def get_active_intake_batch():
    return (
        IntakeBatch.query
        .filter(IntakeBatch.status == "Active")
        .order_by(IntakeBatch.id.desc())
        .first()
    )


def apply_batch_form(batch, form_data):
    batch.batch_name = clean_value(form_data.get("batch_name"))
    batch.status = form_data.get("status") or "Active"
    batch.total_batch_cost = money(form_data.get("total_batch_cost"))
    batch.default_sport = form_data.get("default_sport") or "Baseball"
    batch.default_card_type = form_data.get("default_card_type") or "Raw"
    batch.default_collection_type = form_data.get("default_collection_type") or "Inventory"
    batch.default_status = form_data.get("default_status") or "Active"
    batch.default_storage_location = clean_value(form_data.get("default_storage_location"))
    batch.default_acquisition_source = acquisition_value(form_data.get("default_acquisition_source"))
    batch.default_acquisition_date = acquisition_date_value({
        "acquisition_source": batch.default_acquisition_source,
        "acquisition_date": form_data.get("default_acquisition_date"),
    })
    batch.default_acquisition_event = clean_value(form_data.get("default_acquisition_event"))
    batch.notes = form_data.get("notes")


def batch_defaults(batch):
    if not batch:
        return {}

    return {
        "sport": batch.default_sport or "Baseball",
        "card_type": batch.default_card_type or "Raw",
        "collection_type": batch.default_collection_type or "Inventory",
        "status": batch.default_status or "Active",
        "storage_location": batch.default_storage_location or "",
        "acquisition_source": batch.default_acquisition_source or "Existing Inventory",
        "acquisition_date": batch.default_acquisition_date or "",
        "purchase_date": batch.default_acquisition_date or "",
        "acquisition_event": batch.default_acquisition_event or "",
    }


def batch_stats(batch):
    inventory_cards = Card.query.filter(Card.intake_batch_id == batch.id).all()
    staged_cards = CardImportStaging.query.filter(CardImportStaging.intake_batch_id == batch.id).all()

    card_count = sum((card.quantity or 1) for card in inventory_cards)
    staged_count = len([card for card in staged_cards if card.ai_status not in ["Imported", "Rejected"]])
    imported_staged_count = len([card for card in staged_cards if card.ai_status == "Imported"])
    rejected_staged_count = len([card for card in staged_cards if card.ai_status == "Rejected"])

    entered_card_count = card_count or len(inventory_cards)
    batch_cost = money(getattr(batch, "total_batch_cost", 0))
    manual_cost_total = sum(money(card.purchase_price) * (card.quantity or 1) for card in inventory_cards)
    total_cost = batch_cost if batch_cost else manual_cost_total
    average_cost = (batch_cost / entered_card_count) if batch_cost and entered_card_count else 0.0

    active_cards = []
    sold_cards = []
    card_rows = []

    sold_revenue = 0.0
    sold_cost = 0.0
    active_cost = 0.0
    active_comp = 0.0
    active_ask = 0.0
    total_comp = 0.0
    total_ask = 0.0

    for card in inventory_cards:
        quantity = card.quantity or 1
        manual_card_cost = money(card.purchase_price)
        allocated_card_cost = average_cost if batch_cost else manual_card_cost
        row_cost_total = allocated_card_cost * quantity
        comp_total = money(card.estimated_value) * quantity
        ask_total = money(card.asking_price) * quantity
        sold_total = money(card.sold_price) * quantity
        is_sold = card.status == "Sold" or bool(card.sold_price)

        total_comp += comp_total
        total_ask += ask_total

        if is_sold:
            sold_cards.append(card)
            sold_revenue += sold_total
            sold_cost += row_cost_total
        else:
            active_cards.append(card)
            active_cost += row_cost_total
            active_comp += comp_total
            active_ask += ask_total

        card_rows.append({
            "card": card,
            "quantity": quantity,
            "manual_card_cost": manual_card_cost,
            "allocated_card_cost": allocated_card_cost,
            "allocated_total_cost": row_cost_total,
            "comp_total": comp_total,
            "ask_total": ask_total,
            "sold_total": sold_total,
            "is_sold": is_sold,
        })

    realized_profit = sold_revenue - sold_cost
    remaining_value = active_comp if active_comp else active_ask
    projected_revenue = sold_revenue + remaining_value
    projected_profit = projected_revenue - total_cost
    recovery_percent = percent(sold_revenue, total_cost)
    projected_roi_percent = percent(projected_profit, total_cost)

    return {
        "inventory_cards": inventory_cards,
        "card_rows": card_rows,
        "staged_cards": [
            card for card in staged_cards
            if card.ai_status not in ["Imported", "Rejected"]
        ],
        "card_count": card_count,
        "entered_card_count": entered_card_count,
        "active_count": sum((card.quantity or 1) for card in active_cards),
        "sold_count": sum((card.quantity or 1) for card in sold_cards),
        "staged_count": staged_count,
        "imported_staged_count": imported_staged_count,
        "rejected_staged_count": rejected_staged_count,
        "batch_cost": batch_cost,
        "manual_cost_total": manual_cost_total,
        "total_cost": total_cost,
        "average_cost": average_cost,
        "total_comp": total_comp,
        "total_ask": total_ask,
        "active_cost": active_cost,
        "active_comp": active_comp,
        "active_ask": active_ask,
        "remaining_value": remaining_value,
        "sold_revenue": sold_revenue,
        "sold_cost": sold_cost,
        "realized_profit": realized_profit,
        "projected_revenue": projected_revenue,
        "projected_profit": projected_profit,
        "recovery_percent": recovery_percent,
        "projected_roi_percent": projected_roi_percent,
        "potential_profit": total_ask - total_cost,
        "uses_average_cost": bool(batch_cost and entered_card_count),
    }


def register_batch_routes(app):
    @app.route("/intake-batches")
    def intake_batches():
        ensure_batch_performance_columns()
        active_batch = get_active_intake_batch()
        batches = IntakeBatch.query.order_by(IntakeBatch.id.desc()).all()
        batch_rows = [
            {
                "batch": batch,
                "stats": batch_stats(batch),
            }
            for batch in batches
        ]

        return render_template(
            "batches.html",
            today=date.today().isoformat(),
            active_batch=active_batch,
            batch_rows=batch_rows,
            all_storage_location_choices=get_storage_locations(),
        )

    @app.route("/intake-batches/create", methods=["POST"])
    def create_intake_batch():
        ensure_batch_performance_columns()
        batch = IntakeBatch()
        apply_batch_form(batch, request.form)

        if not batch.batch_name:
            flash("Batch name is required.")
            return redirect(url_for("intake_batches"))

        if batch.status == "Active":
            IntakeBatch.query.filter(IntakeBatch.status == "Active").update({"status": "Closed"})

        db.session.add(batch)
        db.session.commit()

        flash(f"Created intake batch: {batch.batch_name}.")
        return redirect(url_for("intake_batch_detail", batch_id=batch.id))

    @app.route("/intake-batches/<int:batch_id>")
    def intake_batch_detail(batch_id):
        ensure_batch_performance_columns()
        batch = IntakeBatch.query.get_or_404(batch_id)
        stats = batch_stats(batch)

        return render_template(
            "batch_detail.html",
            batch=batch,
            stats=stats,
            defaults=batch_defaults(batch),
            all_storage_location_choices=get_storage_locations(),
        )

    @app.route("/intake-batches/<int:batch_id>/update", methods=["POST"])
    def update_intake_batch(batch_id):
        ensure_batch_performance_columns()
        batch = IntakeBatch.query.get_or_404(batch_id)
        previous_status = batch.status
        apply_batch_form(batch, request.form)

        if not batch.batch_name:
            flash("Batch name is required.")
            return redirect(url_for("intake_batch_detail", batch_id=batch.id))

        if batch.status == "Active":
            IntakeBatch.query.filter(IntakeBatch.id != batch.id, IntakeBatch.status == "Active").update({"status": "Closed"})

        if previous_status != "Closed" and batch.status == "Closed" and not batch.closed_at:
            batch.closed_at = db.func.now()
        elif batch.status == "Active":
            batch.closed_at = None

        db.session.commit()
        flash("Intake batch updated.")
        return redirect(url_for("intake_batch_detail", batch_id=batch.id))

    @app.route("/intake-batches/<int:batch_id>/activate", methods=["POST"])
    def activate_intake_batch(batch_id):
        ensure_batch_performance_columns()
        batch = IntakeBatch.query.get_or_404(batch_id)
        IntakeBatch.query.filter(IntakeBatch.status == "Active").update({"status": "Closed"})
        batch.status = "Active"
        batch.closed_at = None
        db.session.commit()
        flash(f"Active intake batch set to {batch.batch_name}.")
        return redirect(request.referrer or url_for("intake_batch_detail", batch_id=batch.id))


    @app.route("/intake-batches/<int:batch_id>/update-storage", methods=["POST"])
    def update_intake_batch_storage(batch_id):
        """Update the active batch storage default without leaving Mobile Capture."""
        ensure_batch_performance_columns()
        batch = IntakeBatch.query.get_or_404(batch_id)
        batch.default_storage_location = clean_value(request.form.get("default_storage_location"))
        db.session.commit()

        if batch.default_storage_location:
            flash(f"Current capture storage updated to {batch.default_storage_location}.")
        else:
            flash("Current capture storage cleared.")

        return redirect(request.referrer or url_for("intake_batch_detail", batch_id=batch.id))

    @app.route("/intake-batches/<int:batch_id>/close", methods=["POST"])
    def close_intake_batch(batch_id):
        ensure_batch_performance_columns()
        batch = IntakeBatch.query.get_or_404(batch_id)
        batch.status = "Closed"
        batch.closed_at = db.func.now()
        db.session.commit()
        flash(f"Closed intake batch: {batch.batch_name}.")
        return redirect(request.referrer or url_for("intake_batch_detail", batch_id=batch.id))
