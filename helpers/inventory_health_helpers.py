from models import db, Card, CardImportStaging


def get_inventory_health_summary():
    """Return quick counts for records that need cleanup or business follow-up."""
    try:
        active_inventory_query = Card.query.filter(Card.status != "Sold").filter(Card.collection_type == "Inventory")
        all_cards_query = Card.query

        missing_cost_count = all_cards_query.filter(Card.purchase_price.is_(None)).count()
        missing_storage_count = active_inventory_query.filter(
            db.or_(Card.storage_location.is_(None), Card.storage_location == "")
        ).count()
        missing_asking_price_count = active_inventory_query.filter(
            db.or_(Card.asking_price.is_(None), Card.asking_price == 0)
        ).count()
        missing_estimated_value_count = active_inventory_query.filter(
            db.or_(Card.estimated_value.is_(None), Card.estimated_value == 0)
        ).count()
        ai_review_count = CardImportStaging.query.filter(
            CardImportStaging.ai_status.in_(["Pending Review", "Needs Manual Review"])
        ).count()

        health_issue_count = (
            missing_cost_count
            + missing_storage_count
            + missing_asking_price_count
            + missing_estimated_value_count
            + ai_review_count
        )

        return {
            "missing_cost_count": missing_cost_count,
            "missing_storage_count": missing_storage_count,
            "missing_asking_price_count": missing_asking_price_count,
            "missing_estimated_value_count": missing_estimated_value_count,
            "ai_review_count": ai_review_count,
            "health_issue_count": health_issue_count,
        }
    except Exception:
        return {
            "missing_cost_count": 0,
            "missing_storage_count": 0,
            "missing_asking_price_count": 0,
            "missing_estimated_value_count": 0,
            "ai_review_count": 0,
            "health_issue_count": 0,
        }


def describe_inventory_health_issues(card):
    """Return readable cleanup labels for one card."""
    issues = []

    if card.purchase_price is None:
        issues.append("Missing Cost")

    if card.status != "Sold" and card.collection_type == "Inventory":
        if not card.storage_location:
            issues.append("Missing Storage")
        if card.asking_price in (None, 0):
            issues.append("Missing Asking Price")
        if card.estimated_value in (None, 0):
            issues.append("Missing Comp Value")

    return issues

