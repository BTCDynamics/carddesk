from datetime import datetime, timezone
from flask import Blueprint, render_template, request

from models import Card, DealerEvent

inventory_aging_bp = Blueprint("inventory_aging", __name__)

BUCKETS = {
    "fresh": {"label": "Fresh Inventory", "range": "0-30 Days", "description": "Recently added cards still inside the normal new-inventory window.", "accent": "blue"},
    "aging": {"label": "Aging Inventory", "range": "31-90 Days", "description": "Cards that may need pricing, promotion, or show placement attention.", "accent": "green"},
    "old": {"label": "Old Inventory", "range": "91-180 Days", "description": "Inventory that has been sitting long enough to deserve review.", "accent": "gold"},
    "stale": {"label": "Stale Inventory", "range": "180+ Days", "description": "Long-held cards that may be tying up capital.", "accent": "red"},
}


def _money(value):
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _split_show_locations(value):
    """Split exact loadout-location values from saved event text or URL query."""
    if not value:
        return []

    locations = []
    for raw_location in str(value).replace("|", "\n").splitlines():
        location = raw_location.strip()
        if location and location not in locations:
            locations.append(location)

    return locations


def _get_current_event():
    open_event = (
        DealerEvent.query
        .filter(DealerEvent.status == "Open")
        .order_by(DealerEvent.id.desc())
        .first()
    )
    if open_event:
        return open_event

    return (
        DealerEvent.query
        .filter(DealerEvent.status == "Planned")
        .order_by(DealerEvent.id.desc())
        .first()
    )


def _parse_date(value):
    if not value:
        return None

    if isinstance(value, datetime):
        return value.date()

    text_value = str(value).strip()
    if not text_value:
        return None

    for date_format in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y"):
        try:
            return datetime.strptime(text_value, date_format).date()
        except ValueError:
            continue

    return None


def _age_info(card):
    """Use acquisition date first, then purchase date, then created_at fallback."""
    today = datetime.now(timezone.utc).date()

    for field_name, label in (
        ("acquisition_date", "Acquisition Date"),
        ("purchase_date", "Purchase Date"),
    ):
        parsed = _parse_date(getattr(card, field_name, None))
        if parsed:
            return max((today - parsed).days, 0), label, parsed.isoformat(), False

    created_at = getattr(card, "created_at", None)
    if created_at:
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        created_date = created_at.date()
        return max((today - created_date).days, 0), "Estimated Age", created_date.isoformat(), True

    return 0, "Estimated Age", "—", True


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
    scope_filter = request.args.get("scope", "all")
    event_scope = scope_filter == "event_loadout"

    current_event = _get_current_event() if event_scope else None

    # Show Prep sends the exact locations that were checked/saved when building this link.
    # Prefer that explicit list so the clicked stale list matches the Show Prep row exactly.
    explicit_locations = _split_show_locations(request.args.get("locations", ""))

    if event_scope:
        scoped_locations = explicit_locations
        if not scoped_locations:
            scoped_locations = _split_show_locations(
                getattr(current_event, "selected_show_locations", None)
            )
    else:
        scoped_locations = []

    scoped_location_set = set(scoped_locations)

    cards = (
        Card.query
        .filter(Card.status != "Sold")
        .order_by(Card.created_at.asc())
        .all()
    )

    if event_scope:
        # Strict event loadout filter:
        # only exact location names passed from Show Prep or saved on the event are allowed.
        cards = [
            card for card in cards
            if (card.storage_location or "").strip() in scoped_location_set
        ] if scoped_location_set else []

    bucket_stats = {
        key: {**info, "key": key, "count": 0, "quantity": 0, "cost": 0.0, "estimated_value": 0.0, "asking": 0.0, "percent": 0}
        for key, info in BUCKETS.items()
    }

    enriched_cards = []
    missing_true_date_count = 0

    for card in cards:
        days_old, basis_label, basis_date, is_estimated_age = _age_info(card)
        bucket_key = _bucket_for_age(days_old)
        quantity = card.quantity or 1
        cost_total = _money(card.purchase_price) * quantity
        estimated_total = _money(card.estimated_value) * quantity
        asking_total = _money(card.asking_price) * quantity

        if is_estimated_age:
            missing_true_date_count += 1

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
            "basis_label": basis_label,
            "basis_date": basis_date,
            "bucket": bucket_key,
            "quantity": quantity,
            "cost_total": cost_total,
            "estimated_total": estimated_total,
            "asking_total": asking_total,
            "review_flags": review_flags,
        })

    total_count = sum(item["count"] for item in bucket_stats.values())
    for item in bucket_stats.values():
        item["percent"] = round((item["count"] / total_count) * 100) if total_count else 0

    if bucket_filter in BUCKETS:
        visible_cards = [item for item in enriched_cards if item["bucket"] == bucket_filter]
        current_label = BUCKETS[bucket_filter]["label"]
    else:
        visible_cards = enriched_cards
        current_label = "All Active Inventory"

    if event_scope:
        if current_event:
            current_label = f"{current_label} · {current_event.event_name} Loadout"
        else:
            current_label = f"{current_label} · Event Loadout"

    visible_cards = sorted(visible_cards, key=lambda item: item["days_old"], reverse=True)
    oldest_item = visible_cards[0] if visible_cards else None

    old_plus_count = bucket_stats["old"]["count"] + bucket_stats["stale"]["count"]
    freshness_score = round(((total_count - old_plus_count) / total_count) * 100) if total_count else 100

    summary = {
        "total_count": total_count,
        "old_plus_count": old_plus_count,
        "stale_count": bucket_stats["stale"]["count"],
        "total_cost": sum(item["cost"] for item in bucket_stats.values()),
        "stale_cost": bucket_stats["stale"]["cost"],
        "freshness_score": max(min(freshness_score, 100), 0),
        "healthy_percent": max(min(freshness_score, 100), 0),
        "missing_true_date_count": missing_true_date_count,
        "oldest_item": oldest_item,
    }

    return render_template(
        "inventory_aging.html",
        bucket_stats=bucket_stats,
        bucket_filter=bucket_filter,
        scope_filter=scope_filter,
        event_scope=event_scope,
        current_event=current_event,
        scoped_locations=scoped_locations,
        visible_cards=visible_cards[:150],
        current_label=current_label,
        summary=summary,
    )
