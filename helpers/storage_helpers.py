from models import db, Card
from helpers.inventory_health_helpers import (
    get_inventory_health_summary,
    describe_inventory_health_issues,
)


def get_storage_locations():
    """Return all unique storage locations currently used by cards."""
    rows = (
        db.session.query(Card.storage_location)
        .filter(Card.storage_location.isnot(None))
        .filter(Card.storage_location != "")
        .distinct()
        .order_by(Card.storage_location.asc())
        .all()
    )

    return [row[0] for row in rows if row[0]]


def get_storage_summary():
    """Return storage locations with record count, total quantity, and value totals."""
    cards = (
        Card.query
        .filter(Card.status != "Sold")
        .filter(Card.storage_location.isnot(None))
        .filter(Card.storage_location != "")
        .order_by(Card.storage_location.asc(), Card.player_name.asc())
        .all()
    )

    summary = {}

    for card in cards:
        location = card.storage_location

        if location not in summary:
            summary[location] = {
                "location": location,
                "unique_cards": 0,
                "total_cards": 0,
                "purchase_cost": 0,
                "estimated_value": 0,
                "ready_to_sell": 0,
            }

        quantity = card.quantity or 1
        summary[location]["unique_cards"] += 1
        summary[location]["total_cards"] += quantity

        if card.purchase_price:
            summary[location]["purchase_cost"] += card.purchase_price * quantity

        if card.estimated_value:
            summary[location]["estimated_value"] += card.estimated_value * quantity

        if card.status == "Ready to Sell":
            summary[location]["ready_to_sell"] += quantity

    return list(summary.values())
