from datetime import datetime

from flask import render_template, request, redirect, url_for, flash

from models import db, Card, CompRefreshQueue


def build_comp_search_query(card):
    """Build a dealer-friendly eBay sold-search query from Card fields."""
    parts = []

    if card.year:
        parts.append(str(card.year))

    for value in [
        card.brand,
        card.set_name,
        card.player_name,
    ]:
        if value:
            parts.append(str(value).strip())

    if card.card_number:
        card_number = str(card.card_number).strip()
        if not card_number.startswith("#"):
            card_number = f"#{card_number}"
        parts.append(card_number)

    if card.variation:
        parts.append(str(card.variation).strip())

    if card.card_type == "Graded":
        if card.grading_company:
            parts.append(str(card.grading_company).strip())
        if card.actual_grade:
            parts.append(str(card.actual_grade).strip())
    elif card.grade_estimate:
        # For raw cards, include the estimate softly to help dealer review,
        # but this can be removed later if it makes eBay matching too narrow.
        parts.append(str(card.grade_estimate).strip())

    parts.append("sold")

    return " ".join(part for part in parts if part)


def calculate_test_comp(card):
    """Temporary Phase 1 placeholder.

    This does NOT call eBay yet. It creates a realistic review workflow
    using the current estimated value / asking price / cost as a seed.

    Phase 2 will replace this with eBay Sold Listings data.
    """
    current = card.estimated_value
    ask = card.asking_price
    cost = card.purchase_price

    base_value = None

    if current:
        base_value = float(current)
    elif ask:
        base_value = float(ask) * 0.90
    elif cost:
        base_value = float(cost) * 1.35

    if not base_value:
        return {
            "proposed": None,
            "low": None,
            "high": None,
            "count": 0,
            "confidence": "Needs Data",
            "notes": "No current value, ask price, or cost basis available to seed test comp. Phase 2 eBay lookup should fill this.",
        }

    proposed = round(base_value, 2)
    low = round(base_value * 0.88, 2)
    high = round(base_value * 1.12, 2)

    return {
        "proposed": proposed,
        "low": low,
        "high": high,
        "count": 0,
        "confidence": "Test",
        "notes": "Phase 1 placeholder. Review workflow only. Replace with eBay Sold Listings in Phase 2.",
    }


def register_comp_refresh_routes(app):
    @app.route("/comp-refresh")
    def comp_refresh():
        pending_items = (
            CompRefreshQueue.query
            .filter(CompRefreshQueue.status == "Pending")
            .order_by(CompRefreshQueue.created_at.desc())
            .all()
        )

        applied_items = (
            CompRefreshQueue.query
            .filter(CompRefreshQueue.status == "Applied")
            .order_by(CompRefreshQueue.applied_at.desc())
            .limit(25)
            .all()
        )

        active_inventory_count = (
            Card.query
            .filter(Card.status == "Active")
            .filter(Card.collection_type == "Inventory")
            .count()
        )

        pending_count = len(pending_items)
        needs_data_count = sum(
            1 for item in pending_items
            if not item.proposed_estimated_value
        )

        ready_count = pending_count - needs_data_count

        return render_template(
            "comp_refresh.html",
            pending_items=pending_items,
            applied_items=applied_items,
            active_inventory_count=active_inventory_count,
            pending_count=pending_count,
            ready_count=ready_count,
            needs_data_count=needs_data_count,
        )


    @app.route("/comp-refresh/run", methods=["POST"])
    def comp_refresh_run():
        replace_existing = request.form.get("replace_existing") == "1"

        if replace_existing:
            CompRefreshQueue.query.filter(
                CompRefreshQueue.status == "Pending"
            ).delete()
            db.session.commit()

        cards = (
            Card.query
            .filter(Card.status == "Active")
            .filter(Card.collection_type == "Inventory")
            .order_by(Card.id.asc())
            .all()
        )

        created_count = 0
        skipped_count = 0

        existing_pending_card_ids = {
            row[0]
            for row in db.session.query(CompRefreshQueue.card_id)
            .filter(CompRefreshQueue.status == "Pending")
            .all()
        }

        for card in cards:
            if card.id in existing_pending_card_ids:
                skipped_count += 1
                continue

            search_query = build_comp_search_query(card)
            test_comp = calculate_test_comp(card)

            queue_item = CompRefreshQueue(
                card_id=card.id,
                search_query=search_query,
                old_estimated_value=card.estimated_value,
                proposed_estimated_value=test_comp["proposed"],
                comp_low=test_comp["low"],
                comp_high=test_comp["high"],
                comp_count=test_comp["count"],
                confidence=test_comp["confidence"],
                source="Phase 1 Test",
                notes=test_comp["notes"],
                status="Pending",
            )

            db.session.add(queue_item)
            created_count += 1

        db.session.commit()

        flash(
            f"Comp refresh queue built: {created_count} active inventory card(s) added"
            + (f", {skipped_count} skipped because they were already pending." if skipped_count else ".")
        )

        return redirect(url_for("comp_refresh"))


    @app.route("/comp-refresh/<int:item_id>/apply", methods=["POST"])
    def comp_refresh_apply(item_id):
        item = CompRefreshQueue.query.get_or_404(item_id)
        card = Card.query.get_or_404(item.card_id)

        manual_value = request.form.get("manual_value", "").strip()

        if manual_value:
            try:
                new_value = float(manual_value)
            except ValueError:
                flash("Manual value must be a valid number.")
                return redirect(url_for("comp_refresh"))
        else:
            new_value = item.proposed_estimated_value

        if new_value is None:
            flash("No comp value available to apply. Enter a manual value first.")
            return redirect(url_for("comp_refresh"))

        card.estimated_value = new_value

        item.proposed_estimated_value = new_value
        item.status = "Applied"
        item.applied_at = datetime.utcnow()

        db.session.commit()

        flash(f"Updated comp value for {card.card_code} to ${new_value:.2f}.")

        return redirect(url_for("comp_refresh"))


    @app.route("/comp-refresh/<int:item_id>/skip", methods=["POST"])
    def comp_refresh_skip(item_id):
        item = CompRefreshQueue.query.get_or_404(item_id)
        item.status = "Skipped"
        db.session.commit()

        flash("Comp refresh item skipped.")

        return redirect(url_for("comp_refresh"))


    @app.route("/comp-refresh/apply-all", methods=["POST"])
    def comp_refresh_apply_all():
        items = (
            CompRefreshQueue.query
            .filter(CompRefreshQueue.status == "Pending")
            .filter(CompRefreshQueue.proposed_estimated_value.isnot(None))
            .all()
        )

        updated_count = 0

        for item in items:
            card = Card.query.get(item.card_id)

            if not card:
                item.status = "Skipped"
                continue

            card.estimated_value = item.proposed_estimated_value
            item.status = "Applied"
            item.applied_at = datetime.utcnow()
            updated_count += 1

        db.session.commit()

        flash(f"Applied {updated_count} comp value update(s).")

        return redirect(url_for("comp_refresh"))


    @app.route("/comp-refresh/clear", methods=["POST"])
    def comp_refresh_clear():
        deleted_count = CompRefreshQueue.query.filter(
            CompRefreshQueue.status == "Pending"
        ).delete()

        db.session.commit()

        flash(f"Cleared {deleted_count} pending comp refresh item(s).")

        return redirect(url_for("comp_refresh"))
