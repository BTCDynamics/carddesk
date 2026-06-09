from datetime import date, datetime

from flask import render_template, request, url_for, redirect, flash
from sqlalchemy import or_

from models import db, Card, CardImportStaging, DealerEvent


STALE_DAYS = 180


SHOW_LOCATION_KEYWORDS = [
    "show",
    "showcase",
    "show box",
    "showbox",
    "case",
    "dollar",
    "value box",
]


def _get_open_event():
    return (
        DealerEvent.query
        .filter(DealerEvent.status == "Open")
        .order_by(DealerEvent.id.desc())
        .first()
    )


def _get_planned_event():
    return (
        DealerEvent.query
        .filter(DealerEvent.status == "Planned")
        .order_by(DealerEvent.id.desc())
        .first()
    )


def _get_current_event():
    return _get_open_event() or _get_planned_event()


def _split_show_locations(value):
    if not value:
        return []

    locations = []
    for raw_location in str(value).replace("|", "\n").splitlines():
        location = raw_location.strip()
        if location and location not in locations:
            locations.append(location)

    return locations


def _join_show_locations(locations):
    clean_locations = []
    for location in locations:
        location = (location or "").strip()
        if location and location not in clean_locations:
            clean_locations.append(location)

    return "\n".join(clean_locations)


def _show_locations_query_value(locations):
    """Return exact loadout locations as a compact query-string value."""
    clean_locations = []
    for location in locations:
        location = (location or "").strip()
        if location and location not in clean_locations:
            clean_locations.append(location)
    return "|".join(clean_locations)


def _is_show_location(location):
    """Return True when a storage location looks like a show-ready box/case."""
    location_text = (location or "").strip().lower()
    return any(keyword in location_text for keyword in SHOW_LOCATION_KEYWORDS)


def _location_summary(cards):
    """Summarize active cards by storage location for show-loadout planning."""
    summaries = {}

    for card in cards:
        location = (card.storage_location or "").strip()
        if not location:
            continue

        if location not in summaries:
            summaries[location] = {
                "location": location,
                "record_count": 0,
                "card_count": 0,
                "cost": 0.0,
                "estimated_value": 0.0,
                "asking_price": 0.0,
                "is_show_location": _is_show_location(location),
            }

        quantity = card.quantity or 1
        summaries[location]["record_count"] += 1
        summaries[location]["card_count"] += quantity
        summaries[location]["cost"] += _money(card.purchase_price) * quantity
        summaries[location]["estimated_value"] += _money(card.estimated_value) * quantity
        summaries[location]["asking_price"] += _money(card.asking_price) * quantity

    return sorted(
        summaries.values(),
        key=lambda item: (not item["is_show_location"], item["location"].lower()),
    )


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
    @app.route("/show-prep", methods=["GET", "POST"])
    def show_prep():
        active_cards = _active_inventory_query().all()
        today = date.today()
        active_event = _get_current_event()

        if request.method == "POST":
            if not active_event:
                flash("Create an event before saving a show prep loadout.")
                return redirect(url_for("events"))

            selected_locations = request.form.getlist("show_location")
            active_event.selected_show_locations = _join_show_locations(selected_locations)
            db.session.commit()

            flash(f"Show loadout saved for {active_event.event_name}.")
            return redirect(url_for("show_prep"))

        active_card_count = _total_card_quantity(active_cards)
        total_cost = sum(_money(card.purchase_price) * (card.quantity or 1) for card in active_cards)
        total_estimated_value = sum(_money(card.estimated_value) * (card.quantity or 1) for card in active_cards)
        total_asking_price = sum(_money(card.asking_price) * (card.quantity or 1) for card in active_cards)
        potential_profit = total_asking_price - total_cost

        location_summaries = _location_summary(active_cards)
        event_show_locations = _split_show_locations(
            getattr(active_event, "selected_show_locations", None)
        )

        # For real event prep, selected locations must mean only the
        # locations the dealer explicitly checked and saved for this event.
        # Do not auto-load "show-like" names such as Showcase, Case, or Vintage Box.
        selected_show_locations = event_show_locations if active_event else []

        selected_show_location_set = set(selected_show_locations)
        show_cards = [
            card for card in active_cards
            if (card.storage_location or "").strip() in selected_show_location_set
        ]

        show_card_count = _total_card_quantity(show_cards)
        show_total_cost = sum(_money(card.purchase_price) * (card.quantity or 1) for card in show_cards)
        show_total_estimated_value = sum(_money(card.estimated_value) * (card.quantity or 1) for card in show_cards)
        show_total_asking_price = sum(_money(card.asking_price) * (card.quantity or 1) for card in show_cards)
        show_potential_profit = show_total_asking_price - show_total_cost
        selected_location_summaries = [
            item for item in location_summaries
            if item["location"] in selected_show_location_set
        ]

        # Show Prep should only check cards that are actually in the selected
        # event loadout. Inventory-wide cleanup belongs on Inventory Health/Aging.
        show_missing_asking_cards = [card for card in show_cards if not card.asking_price or card.asking_price <= 0]
        show_missing_comp_cards = [card for card in show_cards if not card.estimated_value or card.estimated_value <= 0]
        show_missing_cost_cards = [card for card in show_cards if not card.purchase_price or card.purchase_price <= 0]

        show_stale_cards = []
        for card in show_cards:
            acquired_date = _parse_date(card.acquisition_date or card.purchase_date)
            if acquired_date and (today - acquired_date).days >= STALE_DAYS:
                show_stale_cards.append(card)

        show_issue_card_ids = set(
            card.id
            for card in (
                show_missing_asking_cards
                + show_missing_comp_cards
                + show_missing_cost_cards
                + show_stale_cards
            )
        )
        show_issue_count = len(show_issue_card_ids)
        show_ready_count = max(0, show_card_count - show_issue_count)

        ai_review_count = CardImportStaging.query.filter(
            CardImportStaging.ai_status.in_(["Pending Review", "Needs Manual Review"])
        ).count()

        open_fulfillment_count = _sold_open_fulfillment_query().count()

        comp_refresh_needed_count = len(show_missing_comp_cards)

        issue_cards = [
            {
                "key": "show_missing_asking",
                "title": "Missing Asking Prices",
                "count": len(show_missing_asking_cards),
                "level": "warning",
                "detail": "Cards in this event loadout without an asking price.",
                "action_label": "Review Loadout Pricing",
                "url": url_for("inventory_health"),
            },
            {
                "key": "show_missing_comps",
                "title": "Missing Comp Values",
                "count": len(show_missing_comp_cards),
                "level": "warning",
                "detail": "Cards in this event loadout that need estimated value / comp cleanup.",
                "action_label": "Open Comp Refresh",
                "url": url_for("comp_refresh"),
            },
            {
                "key": "show_missing_cost",
                "title": "Missing Cost Basis",
                "count": len(show_missing_cost_cards),
                "level": "warning",
                "detail": "Cards in this event loadout missing purchase cost, which affects profit reporting.",
                "action_label": "Review Loadout Costs",
                "url": url_for("inventory_health"),
            },
            {
                "key": "show_stale_inventory",
                "title": f"Stale Cards in Loadout ({STALE_DAYS}+ Days)",
                "count": len(show_stale_cards),
                "level": "warning",
                "detail": "Older cards in this event loadout to consider repricing, discounting, or featuring.",
                "action_label": "View Aging",
                "url": url_for(
                    "inventory_aging",
                    bucket="stale",
                    scope="event_loadout",
                    locations=_show_locations_query_value(selected_show_locations),
                ),
            },
        ]

        issue_total = sum(item["count"] for item in issue_cards)
        ready_score = (
            100
            if show_card_count == 0
            else max(0, int(((show_card_count - show_issue_count) / show_card_count) * 100))
        )

        ready_to_show_count = show_ready_count

        return render_template(
            "show_prep.html",
            stale_days=STALE_DAYS,
            active_event=active_event,
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
            location_summaries=location_summaries,
            selected_show_locations=selected_show_locations,
            selected_location_summaries=selected_location_summaries,
            show_cards=show_cards,
            show_card_count=show_card_count,
            show_total_cost=show_total_cost,
            show_total_estimated_value=show_total_estimated_value,
            show_total_asking_price=show_total_asking_price,
            show_potential_profit=show_potential_profit,
            show_ready_count=show_ready_count,
            show_missing_asking_count=len(show_missing_asking_cards),
            show_missing_comp_count=len(show_missing_comp_cards),
            show_missing_cost_count=len(show_missing_cost_cards),
            show_issue_count=show_issue_count,
        )

    @app.route("/show-prep/print")
    def show_prep_print():
        """Printable event loadout sheet for the current planned/open event."""
        active_cards = _active_inventory_query().all()
        today = date.today()
        active_event = _get_current_event()

        if not active_event:
            flash("Create an event before printing a show prep loadout.")
            return redirect(url_for("events"))

        location_summaries = _location_summary(active_cards)
        selected_show_locations = _split_show_locations(
            getattr(active_event, "selected_show_locations", None)
        )
        selected_show_location_set = set(selected_show_locations)

        show_cards = [
            card for card in active_cards
            if (card.storage_location or "").strip() in selected_show_location_set
        ]

        selected_location_summaries = [
            item for item in location_summaries
            if item["location"] in selected_show_location_set
        ]

        show_card_count = _total_card_quantity(show_cards)
        show_total_cost = sum(_money(card.purchase_price) * (card.quantity or 1) for card in show_cards)
        show_total_estimated_value = sum(_money(card.estimated_value) * (card.quantity or 1) for card in show_cards)
        show_total_asking_price = sum(_money(card.asking_price) * (card.quantity or 1) for card in show_cards)
        show_potential_profit = show_total_asking_price - show_total_cost

        show_missing_asking_cards = [
            card for card in show_cards
            if not card.asking_price or card.asking_price <= 0
        ]
        show_missing_comp_cards = [
            card for card in show_cards
            if not card.estimated_value or card.estimated_value <= 0
        ]
        show_missing_cost_cards = [
            card for card in show_cards
            if not card.purchase_price or card.purchase_price <= 0
        ]

        show_stale_cards = []
        for card in show_cards:
            acquired_date = _parse_date(card.acquisition_date or card.purchase_date)
            if acquired_date and (today - acquired_date).days >= STALE_DAYS:
                show_stale_cards.append(card)

        issue_cards = [
            {
                "title": "Missing Asking Prices",
                "count": len(show_missing_asking_cards),
                "detail": "Cards in this loadout without an asking price.",
            },
            {
                "title": "Missing Comp Values",
                "count": len(show_missing_comp_cards),
                "detail": "Cards in this loadout without an estimated value / comp.",
            },
            {
                "title": "Missing Cost Basis",
                "count": len(show_missing_cost_cards),
                "detail": "Cards in this loadout missing purchase cost.",
            },
            {
                "title": f"Stale Cards ({STALE_DAYS}+ Days)",
                "count": len(show_stale_cards),
                "detail": "Older cards in this loadout to review before the show.",
            },
        ]

        issue_total = sum(item["count"] for item in issue_cards)

        supplies_checklist = [
            "Cash box / change",
            "Card reader / Square reader",
            "Phone charger / battery pack",
            "Pricing labels / marker",
            "Penny sleeves",
            "Top loaders",
            "Team bags",
            "Table cover",
            "Banner / signage",
            "Receipt book / notebook",
        ]

        return render_template(
            "show_prep_print.html",
            print_date=today,
            stale_days=STALE_DAYS,
            active_event=active_event,
            selected_show_locations=selected_show_locations,
            selected_location_summaries=selected_location_summaries,
            show_cards=show_cards,
            show_card_count=show_card_count,
            show_total_cost=show_total_cost,
            show_total_estimated_value=show_total_estimated_value,
            show_total_asking_price=show_total_asking_price,
            show_potential_profit=show_potential_profit,
            issue_cards=issue_cards,
            issue_total=issue_total,
            supplies_checklist=supplies_checklist,
        )

