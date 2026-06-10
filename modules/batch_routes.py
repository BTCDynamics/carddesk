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

    total_cost = sum(money(card.purchase_price) * (card.quantity or 1) for card in inventory_cards)
    total_comp = sum(money(card.estimated_value) * (card.quantity or 1) for card in inventory_cards)
    total_ask = sum(money(card.asking_price) * (card.quantity or 1) for card in inventory_cards)

    return {
        "inventory_cards": inventory_cards,
        "staged_cards": [
            card for card in staged_cards
            if card.ai_status not in ["Imported", "Rejected"]
        ],
        "card_count": card_count,
        "staged_count": staged_count,
        "imported_staged_count": imported_staged_count,
        "rejected_staged_count": rejected_staged_count,
        "total_cost": total_cost,
        "total_comp": total_comp,
        "total_ask": total_ask,
        "potential_profit": total_ask - total_cost,
    }


def register_batch_routes(app):
    @app.route("/intake-batches")
    def intake_batches():
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
        )

    @app.route("/intake-batches/create", methods=["POST"])
    def create_intake_batch():
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
        batch = IntakeBatch.query.get_or_404(batch_id)
        batch.status = "Closed"
        batch.closed_at = db.func.now()
        db.session.commit()
        flash(f"Closed intake batch: {batch.batch_name}.")
        return redirect(request.referrer or url_for("intake_batch_detail", batch_id=batch.id))
