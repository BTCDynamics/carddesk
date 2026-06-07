from datetime import date, datetime

from flask import render_template, url_for
from sqlalchemy import or_

from models import Card, CardImportStaging


STALE_DAYS = 180


def _parse_date(value):
    """Return a date object for common CardDesk date strings, or None."""
    if not value:
        return None

    if isinstance(value, date):
        return value

    text_value = str(value).strip()
    if not text_value:
        return None

    for date_format in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y"):
        try:
            return datetime.strptime(text_value, date_format).date()
        except ValueError:
            continue

    return None


def _active_inventory_query():
    return Card.query.filter(
        Card.status == "Active",
        Card.collection_type == "Inventory",
    )


def _sold_open_fulfillment_query():
    completed_statuses = ["Delivered", "Completed"]
    return Card.query.filter(
        Card.status == "Sold",
        or_(
            Card.fulfillment_status.is_(None),
            ~Card.fulfillment_status.in_(completed_statuses),
        ),
    )


def _money(value):
    return float(value or 0)


def _total_card_quantity(cards):
    return sum((card.quantity or 1) for card in cards)


def register_show_prep_routes(app):
    @app.route("/show-prep")
    def show_prep():
        active_cards = _active_inventory_query().all()
        today = date.today()

        active_card_count = _total_card_quantity(active_cards)
        total_cost = sum(_money(card.purchase_price) * (card.quantity or 1) for card in active_cards)
        total_estimated_value = sum(_money(card.estimated_value) * (card.quantity or 1) for card in active_cards)
        total_asking_price = sum(_money(card.asking_price) * (card.quantity or 1) for card in active_cards)
        potential_profit = total_asking_price - total_cost

        missing_asking_cards = [card for card in active_cards if not card.asking_price or card.asking_price <= 0]
        missing_comp_cards = [card for card in active_cards if not card.estimated_value or card.estimated_value <= 0]
        missing_storage_cards = [card for card in active_cards if not (card.storage_location or "").strip()]
        missing_cost_cards = [card for card in active_cards if not card.purchase_price or card.purchase_price <= 0]
        missing_acquisition_date_cards = [card for card in active_cards if not (card.acquisition_date or "").strip()]

        stale_cards = []
        for card in active_cards:
            acquired_date = _parse_date(card.acquisition_date or card.purchase_date)
            if acquired_date and (today - acquired_date).days >= STALE_DAYS:
                stale_cards.append(card)

        ai_review_count = CardImportStaging.query.filter(
            CardImportStaging.ai_status.in_(["Pending Review", "Needs Manual Review"])
        ).count()

        open_fulfillment_count = _sold_open_fulfillment_query().count()

        comp_refresh_needed_count = len(missing_comp_cards)

        issue_cards = [
            {
                "key": "missing_asking",
                "title": "Missing Asking Prices",
                "count": len(missing_asking_cards),
                "level": "warning",
                "detail": "Active inventory without an asking price.",
                "action_label": "Review Inventory Health",
                "url": url_for("inventory_health"),
            },
            {
                "key": "missing_comps",
                "title": "Missing Comp Values",
                "count": len(missing_comp_cards),
                "level": "warning",
                "detail": "Cards that need estimated value / comp cleanup.",
                "action_label": "Open Comp Refresh",
                "url": url_for("comp_refresh"),
            },
            {
                "key": "missing_storage",
                "title": "Missing Storage",
                "count": len(missing_storage_cards),
                "level": "warning",
                "detail": "Active inventory without a box, row, or location.",
                "action_label": "Fix Storage",
                "url": url_for("cards", status="Active", collection_type="Inventory", storage="__missing__"),
            },
            {
                "key": "missing_cost",
                "title": "Missing Cost Basis",
                "count": len(missing_cost_cards),
                "level": "warning",
                "detail": "Cards missing purchase cost, which affects profit reporting.",
                "action_label": "Review Inventory Health",
                "url": url_for("inventory_health"),
            },
            {
                "key": "stale_inventory",
                "title": f"Stale Inventory ({STALE_DAYS}+ Days)",
                "count": len(stale_cards),
                "level": "warning",
                "detail": "Older inventory to consider repricing, discounting, or featuring.",
                "action_label": "View Aging",
                "url": url_for("inventory_aging", bucket="stale"),
            },
            {
                "key": "ai_review",
                "title": "AI Review Queue",
                "count": ai_review_count,
                "level": "danger" if ai_review_count else "clear",
                "detail": "Captured cards waiting before they become inventory.",
                "action_label": "Open AI Review",
                "url": url_for("ai_import_review"),
            },
            {
                "key": "fulfillment",
                "title": "Open Fulfillment",
                "count": open_fulfillment_count,
                "level": "danger" if open_fulfillment_count else "clear",
                "detail": "Sold cards still needing pull, ship, or delivery completion.",
                "action_label": "Open Fulfillment",
                "url": url_for("fulfillment_queue"),
            },
        ]

        issue_total = sum(item["count"] for item in issue_cards)
        ready_score = max(0, 100 - min(issue_total * 3, 100))

        ready_to_show_count = max(
            0,
            active_card_count
            - len(set(card.id for card in missing_asking_cards + missing_comp_cards + missing_storage_cards))
        )

        return render_template(
            "show_prep.html",
            stale_days=STALE_DAYS,
            active_card_count=active_card_count,
            total_cost=total_cost,
            total_estimated_value=total_estimated_value,
            total_asking_price=total_asking_price,
            potential_profit=potential_profit,
            issue_cards=issue_cards,
            issue_total=issue_total,
            ready_score=ready_score,
            ready_to_show_count=ready_to_show_count,
            comp_refresh_needed_count=comp_refresh_needed_count,
            ai_review_count=ai_review_count,
            open_fulfillment_count=open_fulfillment_count,
        )
