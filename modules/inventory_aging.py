from datetime import datetime, timezone
from flask import Blueprint, render_template, request

from models import Card

inventory_aging_bp = Blueprint("inventory_aging", __name__)

BUCKETS = {
    "fresh": {"label": "Fresh Inventory", "range": "0-30 Days", "description": "Recently added cards still inside the normal new-inventory window.", "accent": "blue"},
    "aging": {"label": "Aging Inventory", "range": "31-90 Days", "description": "Cards that may need pricing, promotion, or show placement attention.", "accent": "green"},
    "old": {"label": "Old Inventory", "range": "91-180 Days", "description": "Inventory that has been sitting long enough to deserve review.", "accent": "gold"},
    "stale": {"label": "Stale Inventory", "range": "180+ Days", "description": "Long-held cards that may be tying up capital.", "accent": "red"},
}


def _money(value):
    return float(value or 0)


def _card_age_days(card):
    if not card.created_at:
        return 0
    created_at = card.created_at
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    return max((datetime.now(timezone.utc) - created_at).days, 0)


def _bucket_for_age(days_old):
    if days_old <= 30:
        return "fresh"
    if days_old <= 90:
        return "aging"
    if days_old <= 180:
        return "old"
    return "stale"


@inventory_aging_bp.route("/inventory-aging")
def inventory_aging():
    bucket_filter = request.args.get("bucket", "all")

    cards = (
        Card.query
        .filter(Card.status != "Sold")
        .order_by(Card.created_at.asc())
        .all()
    )

    bucket_stats = {
        key: {**info, "key": key, "count": 0, "quantity": 0, "cost": 0.0, "estimated_value": 0.0, "asking": 0.0}
        for key, info in BUCKETS.items()
    }

    enriched_cards = []

    for card in cards:
        days_old = _card_age_days(card)
        bucket_key = _bucket_for_age(days_old)
        quantity = card.quantity or 1
        cost_total = _money(card.purchase_price) * quantity
        estimated_total = _money(card.estimated_value) * quantity
        asking_total = _money(card.asking_price) * quantity

        bucket_stats[bucket_key]["count"] += 1
        bucket_stats[bucket_key]["quantity"] += quantity
        bucket_stats[bucket_key]["cost"] += cost_total
        bucket_stats[bucket_key]["estimated_value"] += estimated_total
        bucket_stats[bucket_key]["asking"] += asking_total

        review_flags = []
        if days_old > 180:
            review_flags.append("180+ Days")
        elif days_old > 90:
            review_flags.append("90+ Days")
        if not card.asking_price:
            review_flags.append("No Ask")
        if not card.estimated_value:
            review_flags.append("No Comp")
        if not card.storage_location:
            review_flags.append("No Storage")
        if not card.image_filename:
            review_flags.append("No Image")

        enriched_cards.append({
            "card": card,
            "days_old": days_old,
            "bucket": bucket_key,
            "quantity": quantity,
            "cost_total": cost_total,
            "estimated_total": estimated_total,
            "asking_total": asking_total,
            "review_flags": review_flags,
        })

    if bucket_filter in BUCKETS:
        visible_cards = [item for item in enriched_cards if item["bucket"] == bucket_filter]
        current_label = BUCKETS[bucket_filter]["label"]
    else:
        visible_cards = enriched_cards
        current_label = "All Active Inventory"

    visible_cards = sorted(visible_cards, key=lambda item: item["days_old"], reverse=True)

    total_count = sum(item["count"] for item in bucket_stats.values())
    old_plus_count = bucket_stats["old"]["count"] + bucket_stats["stale"]["count"]
    healthy_percent = round(((total_count - old_plus_count) / total_count) * 100) if total_count else 100

    summary = {
        "total_count": total_count,
        "old_plus_count": old_plus_count,
        "stale_count": bucket_stats["stale"]["count"],
        "total_cost": sum(item["cost"] for item in bucket_stats.values()),
        "stale_cost": bucket_stats["stale"]["cost"],
        "healthy_percent": max(min(healthy_percent, 100), 0),
    }

    return render_template(
        "inventory_aging.html",
        bucket_stats=bucket_stats,
        bucket_filter=bucket_filter,
        visible_cards=visible_cards[:150],
        current_label=current_label,
        summary=summary,
    )
