from flask import render_template, request, redirect, url_for, flash
from models import db, Card
from helpers.acquisition_helpers import clean_value


def register_fulfillment_routes(app):
    @app.route("/fulfillment")
    def fulfillment_queue():
        """Show sold cards that still need post-sale handling."""
        status_filter = request.args.get("status", "")
    
        query = Card.query.filter(Card.status == "Sold")
    
        if status_filter:
            query = query.filter(Card.fulfillment_status == status_filter)
        else:
            query = query.filter(
                db.or_(
                    Card.fulfillment_status == "Needs Pulling",
                    Card.fulfillment_status == "Pulled",
                    Card.fulfillment_status == "Ready to Ship",
                    Card.fulfillment_status == "Shipped",
                    Card.fulfillment_status == "Delivered",
                    Card.fulfillment_status == "Completed",
                    Card.fulfillment_status.is_(None)
                )
            )
    
        cards = (
            query
            .order_by(Card.sold_date.desc(), Card.storage_location.asc(), Card.player_name.asc())
            .all()
        )
    
        counts = {
            "needs_pulling": Card.query.filter(Card.status == "Sold", Card.fulfillment_status == "Needs Pulling").count(),
            "pulled": Card.query.filter(Card.status == "Sold", Card.fulfillment_status == "Pulled").count(),
            "ready_to_ship": Card.query.filter(Card.status == "Sold", Card.fulfillment_status == "Ready to Ship").count(),
            "shipped": Card.query.filter(Card.status == "Sold", Card.fulfillment_status == "Shipped").count(),
            "delivered": Card.query.filter(Card.status == "Sold", Card.fulfillment_status == "Delivered").count(),
            "completed": Card.query.filter(Card.status == "Sold", Card.fulfillment_status == "Completed").count(),
        }
    
        return render_template(
            "fulfillment.html",
            cards=cards,
            status_filter=status_filter,
            counts=counts
        )
    
    
    @app.route("/fulfillment/<int:card_id>/status", methods=["POST"])
    def update_fulfillment_status(card_id):
        card = Card.query.get_or_404(card_id)
    
        new_status = request.form.get("fulfillment_status") or "Needs Pulling"
        valid_statuses = ["Needs Pulling", "Pulled", "Ready to Ship", "Shipped", "Delivered", "Completed"]
    
        if new_status not in valid_statuses:
            flash("Invalid fulfillment status.")
            return redirect(request.referrer or url_for("fulfillment_queue"))
    
        old_status = card.fulfillment_status or "Needs Pulling"
        card.fulfillment_status = new_status
    
        if new_status == "Ready to Ship":
            card.shipping_carrier = clean_value(request.form.get("shipping_carrier"))
            card.tracking_number = clean_value(request.form.get("tracking_number"))
            card.shipping_cost = request.form.get("shipping_cost") or None
            card.shipped_date = request.form.get("shipped_date")
            card.shipping_notes = clean_value(request.form.get("shipping_notes"))
    
        status_note = f"Fulfillment updated from {old_status} to {new_status}."
        if new_status == "Pulled" and card.storage_location:
            status_note += f" Pulled from: {card.storage_location}."
    
        existing_notes = card.notes or ""
        card.notes = (existing_notes + "\n" if existing_notes else "") + status_note
    
        db.session.commit()
    
        flash(f"{card.card_code} fulfillment updated to {new_status}.")
    
        return redirect(request.referrer or url_for("fulfillment_queue"))
    
    
    @app.route("/fulfillment/mark-selected-pulled", methods=["POST"])
    def mark_selected_fulfillment_pulled():
        card_ids = request.form.getlist("card_ids")
    
        if not card_ids:
            flash("No cards selected.")
            return redirect(request.referrer or url_for("fulfillment_queue"))
    
        clean_ids = []
    
        for card_id in card_ids:
            try:
                clean_ids.append(int(card_id))
            except (TypeError, ValueError):
                continue
    
        cards = Card.query.filter(Card.id.in_(clean_ids)).all()
    
        updated_count = 0
    
        for card in cards:
            old_status = card.fulfillment_status or "Needs Pulling"
            card.fulfillment_status = "Pulled"
    
            status_note = f"Fulfillment updated from {old_status} to Pulled."
            if card.storage_location:
                status_note += f" Pulled from: {card.storage_location}."
    
            existing_notes = card.notes or ""
            card.notes = (existing_notes + "\n" if existing_notes else "") + status_note
    
            updated_count += 1
    
        db.session.commit()
    
        flash(f"{updated_count} card(s) marked Pulled.")
    
        return redirect(request.referrer or url_for("fulfillment_queue"))
