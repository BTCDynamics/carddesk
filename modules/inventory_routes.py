from urllib.parse import quote
from datetime import date, datetime, timedelta

from flask import render_template, request, redirect, url_for, flash

from models import db, Card, CompRefreshQueue, DealerEvent, IntakeBatch
from helpers.acquisition_helpers import (
    clean_value,
    acquisition_value,
    acquisition_date_value,
    purchase_date_value,
)
from helpers.storage_helpers import get_storage_locations
from helpers.deal_cart_helpers import (
    get_deal_cart_ids,
    get_deal_cart_quantity,
)


def register_inventory_routes(app, generate_card_code, save_uploaded_image, delete_image_file):
    def get_active_event_name():
        active_event = (
            DealerEvent.query
            .filter(DealerEvent.status == "Open")
            .order_by(DealerEvent.id.desc())
            .first()
        )

        return active_event.event_name if active_event else None

    def event_value_from_form(form_data):
        manual_event = clean_value(form_data.get("acquisition_event"))
        return manual_event or get_active_event_name()

    def get_active_intake_batch():
        return (
            IntakeBatch.query
            .filter(IntakeBatch.status == "Active")
            .order_by(IntakeBatch.id.desc())
            .first()
        )

    def batch_default(active_batch, attr_name, fallback=None):
        if not active_batch:
            return fallback
        value = getattr(active_batch, attr_name, None)
        return value if value not in [None, ""] else fallback

    def batch_value_from_form(form_data, field_name, active_batch, batch_attr, fallback=None):
        value = clean_value(form_data.get(field_name))
        if value not in [None, ""]:
            return value
        return batch_default(active_batch, batch_attr, fallback)

    @app.route("/cards")
    def cards():
        sold_range = request.args.get("sold_range")
        acquisition_range = request.args.get("acquisition_range")
        search_query = request.args.get("q", "")
        sport_filter = request.args.get("sport", "")
        status_filter = request.args.get("status", "")
        collection_type_filter = request.args.get("collection_type", "")
        rookie_filter = request.args.get("rookie", "")
        hof_filter = request.args.get("hof", "")
        card_type_filter = request.args.get("card_type", "")
        grade_estimate_filter = request.args.get("grade_estimate", "")
        actual_grade_filter = request.args.get("actual_grade", "")
        year_filter = request.args.get("year", "")
        brand_filter = request.args.get("brand", "")
        storage_filter = request.args.get("storage", "")
        variation_filter = request.args.get("variation", "")
        acquisition_source_filter = request.args.get("acquisition_source", "")
        acquisition_event_filter = request.args.get("acquisition_event", "")
        batch_filter = request.args.get("batch", "")
        min_price = request.args.get("min_price", "")
        max_price = request.args.get("max_price", "")
        scope = request.args.get("scope", "inventory")
        page = request.args.get("page", 1, type=int)
        per_page = request.args.get("per_page", 25, type=int)

        allowed_per_page = [25, 50, 100]
        if per_page not in allowed_per_page:
            per_page = 25
        if page < 1:
            page = 1

        query = Card.query

        # Default inventory view should show cards that are actually available to sell.
        # If the user chooses filters, those filters take control.
        has_manual_scope_filter = any([
            sold_range,
            acquisition_range,
            status_filter,
            collection_type_filter,
        ])

        if scope == "inventory" and not has_manual_scope_filter:
            query = query.filter(Card.status == "Active")
            query = query.filter(Card.collection_type == "Inventory")

        # Do not apply LIMIT until after all filters have been added.
        # SQLAlchemy raises an InvalidRequestError if .filter() is called after .limit().

        if search_query:
            query = query.filter(
                db.or_(
                    Card.card_code.ilike(f"%{search_query}%"),
                    Card.player_name.ilike(f"%{search_query}%"),
                    Card.sport.ilike(f"%{search_query}%"),
                    Card.brand.ilike(f"%{search_query}%"),
                    Card.set_name.ilike(f"%{search_query}%"),
                    Card.card_number.ilike(f"%{search_query}%"),
                    Card.variation.ilike(f"%{search_query}%"),
                    Card.grade_estimate.ilike(f"%{search_query}%"),
                    Card.actual_grade.ilike(f"%{search_query}%"),
                    Card.grading_company.ilike(f"%{search_query}%"),
                    Card.cert_number.ilike(f"%{search_query}%"),
                    Card.status.ilike(f"%{search_query}%"),
                    Card.collection_type.ilike(f"%{search_query}%"),
                    Card.storage_location.ilike(f"%{search_query}%"),
                    Card.acquisition_source.ilike(f"%{search_query}%"),
                    Card.acquisition_event.ilike(f"%{search_query}%")
                )
            )

        if rookie_filter == "yes":
            query = query.filter(Card.is_rookie == True)

        if rookie_filter == "no":
            query = query.filter(Card.is_rookie == False)

        if hof_filter == "yes":
            query = query.filter(Card.is_hof == True)

        if hof_filter == "no":
            query = query.filter(Card.is_hof == False)

        if card_type_filter:
            query = query.filter(Card.card_type == card_type_filter)

        if sport_filter:
            query = query.filter(Card.sport == sport_filter)

        if status_filter:
            query = query.filter(Card.status == status_filter)

        if collection_type_filter:
            query = query.filter(Card.collection_type == collection_type_filter)

        if acquisition_source_filter:
            query = query.filter(Card.acquisition_source == acquisition_source_filter)

        if acquisition_event_filter:
            query = query.filter(Card.acquisition_event.ilike(f"%{acquisition_event_filter}%"))

        if batch_filter:
            try:
                query = query.filter(Card.intake_batch_id == int(batch_filter))
            except (TypeError, ValueError):
                batch_filter = ""

        if grade_estimate_filter:
            query = query.filter(Card.grade_estimate.ilike(f"%{grade_estimate_filter}%"))

        if actual_grade_filter:
            query = query.filter(Card.actual_grade.ilike(f"%{actual_grade_filter}%"))

        if year_filter:
            try:
                query = query.filter(Card.year == int(year_filter))
            except ValueError:
                year_filter = ""

        if brand_filter:
            query = query.filter(Card.brand.ilike(f"%{brand_filter}%"))

        if storage_filter == "__missing__":
            query = query.filter(db.or_(Card.storage_location.is_(None), Card.storage_location == ""))
        elif storage_filter:
            query = query.filter(Card.storage_location.ilike(f"%{storage_filter}%"))

        if variation_filter:
            query = query.filter(Card.variation.ilike(f"%{variation_filter}%"))

        if min_price:
            try:
                query = query.filter(Card.purchase_price >= float(min_price))
            except ValueError:
                min_price = ""

        if max_price:
            try:
                query = query.filter(Card.purchase_price <= float(max_price))
            except ValueError:
                max_price = ""


        if sold_range:
            today_value = date.today()

            if sold_range == "today":
                start_date = today_value
            elif sold_range == "3d":
                start_date = today_value - timedelta(days=3)
            elif sold_range == "7d":
                start_date = today_value - timedelta(days=6)
            elif sold_range == "30d":
                start_date = today_value - timedelta(days=29)
            else:
                start_date = None

            if start_date:
                query = query.filter(Card.sold_date >= start_date.isoformat())

        if acquisition_range:
            today_value = date.today()

            if acquisition_range == "today":
                start_date = today_value
            elif acquisition_range == "3d":
                start_date = today_value - timedelta(days=3)
            elif acquisition_range == "7d":
                start_date = today_value - timedelta(days=6)
            elif acquisition_range == "30d":
                start_date = today_value - timedelta(days=29)
            else:
                start_date = None

            if start_date:
                query = query.filter(Card.acquisition_date >= start_date.isoformat())

        has_active_filter = any([
            sold_range,
            acquisition_range,
            search_query,
            sport_filter,
            status_filter,
            collection_type_filter,
            rookie_filter,
            hof_filter,
            card_type_filter,
            grade_estimate_filter,
            actual_grade_filter,
            year_filter,
            brand_filter,
            storage_filter,
            variation_filter,
            acquisition_source_filter,
            acquisition_event_filter,
            batch_filter,
            min_price,
            max_price,
        ])

        # Keep summary totals tied to the full filtered result set, but only
        # load one display page of cards. This keeps /cards responsive as the
        # inventory grows.
        quantity_expr = db.func.coalesce(Card.quantity, 1)
        filtered_card_count = query.with_entities(
            db.func.coalesce(db.func.sum(quantity_expr), 0)
        ).scalar() or 0

        filtered_total_cost = query.with_entities(
            db.func.coalesce(db.func.sum(db.func.coalesce(Card.purchase_price, 0) * quantity_expr), 0)
        ).scalar() or 0

        filtered_total_asking = query.with_entities(
            db.func.coalesce(db.func.sum(db.func.coalesce(Card.asking_price, 0) * quantity_expr), 0)
        ).scalar() or 0

        filtered_total_sold = query.with_entities(
            db.func.coalesce(db.func.sum(db.func.coalesce(Card.sold_price, 0) * quantity_expr), 0)
        ).scalar() or 0

        filtered_total_profit = query.with_entities(
            db.func.coalesce(
                db.func.sum(
                    (db.func.coalesce(Card.sold_price, 0) - db.func.coalesce(Card.purchase_price, 0)) * quantity_expr
                ),
                0
            )
        ).scalar() or 0

        active_inventory_count = (
            Card.query
            .filter(Card.status == "Active")
            .filter(Card.collection_type == "Inventory")
            .with_entities(db.func.coalesce(db.func.sum(db.func.coalesce(Card.quantity, 1)), 0))
            .scalar()
            or 0
        )

        missing_storage_count = (
            Card.query
            .filter(Card.status == "Active")
            .filter(Card.collection_type == "Inventory")
            .filter(db.or_(Card.storage_location.is_(None), Card.storage_location == ""))
            .with_entities(db.func.coalesce(db.func.sum(db.func.coalesce(Card.quantity, 1)), 0))
            .scalar()
            or 0
        )

        query = query.order_by(Card.id.desc())

        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        all_cards = pagination.items

        first_item = ((pagination.page - 1) * pagination.per_page + 1) if pagination.total else 0
        last_item = min(pagination.page * pagination.per_page, pagination.total) if pagination.total else 0

        pagination_args = request.args.to_dict(flat=True)
        pagination_args.pop("page", None)
        pagination_args.pop("per_page", None)

        def pagination_url(page_number, per_page_value=None):
            args = dict(pagination_args)
            args["page"] = page_number
            args["per_page"] = per_page_value or per_page
            return url_for("cards", **args)

        prev_url = pagination_url(pagination.prev_num) if pagination.has_prev else None
        next_url = pagination_url(pagination.next_num) if pagination.has_next else None

        page_links = [
            {"page": page_number, "url": pagination_url(page_number)}
            if page_number else None
            for page_number in pagination.iter_pages(
                left_edge=1,
                right_edge=1,
                left_current=2,
                right_current=2,
            )
        ]

        per_page_links = [
            {"value": value, "url": pagination_url(1, value)}
            for value in allowed_per_page
        ]

        storage_locations = get_storage_locations()

        acquisition_sources = [
            "Existing Inventory",
            "Cash Purchase",
            "Trade-In",
            "Bulk Collection",
            "Pack Pull",
            "Personal Collection",
            "Other",
        ]

        acquisition_events = [
            row[0]
            for row in db.session.query(Card.acquisition_event)
            .filter(Card.acquisition_event.isnot(None))
            .filter(Card.acquisition_event != "")
            .distinct()
            .order_by(Card.acquisition_event.asc())
            .all()
        ]

        all_batches = IntakeBatch.query.order_by(IntakeBatch.batch_name.asc()).all()
        selected_batch_name = None
        if batch_filter:
            for batch in all_batches:
                if str(batch.id) == str(batch_filter):
                    selected_batch_name = batch.batch_name
                    break

        deal_cart_ids = get_deal_cart_ids()
        deal_cart_count = get_deal_cart_quantity()

        return render_template(
            "card_list.html",
            cards=all_cards,
            filtered_card_count=filtered_card_count,
            filtered_total_cost=filtered_total_cost,
            filtered_total_asking=filtered_total_asking,
            filtered_total_sold=filtered_total_sold,
            filtered_total_profit=filtered_total_profit,
            search_query=search_query,
            acquisition_range=acquisition_range,
            sport_filter=sport_filter,
            status_filter=status_filter,
            collection_type_filter=collection_type_filter,
            rookie_filter=rookie_filter,
            hof_filter=hof_filter,
            card_type_filter=card_type_filter,
            grade_estimate_filter=grade_estimate_filter,
            actual_grade_filter=actual_grade_filter,
            year_filter=year_filter,
            brand_filter=brand_filter,
            storage_filter=storage_filter,
            variation_filter=variation_filter,
            acquisition_source_filter=acquisition_source_filter,
            acquisition_event_filter=acquisition_event_filter,
            batch_filter=batch_filter,
            selected_batch_name=selected_batch_name,
            all_batches=all_batches,
            min_price=min_price,
            max_price=max_price,
            storage_locations=storage_locations,
            acquisition_sources=acquisition_sources,
            acquisition_events=acquisition_events,
            deal_cart_ids=deal_cart_ids,
            deal_cart_count=deal_cart_count,
            active_inventory_count=active_inventory_count,
            missing_storage_count=missing_storage_count,
            scope=scope,
            pagination=pagination,
            page_links=page_links,
            per_page_links=per_page_links,
            prev_url=prev_url,
            next_url=next_url,
            current_page=pagination.page,
            per_page=per_page,
            first_item=first_item,
            last_item=last_item,
            record_total=pagination.total
        )


    @app.route("/labels/preview", methods=["POST"])
    def label_preview():
        """Demo-only price label preview for selected inventory cards.

        This does not communicate with a printer. It only renders a browser
        preview showing what CardDesk would print on price labels.
        """
        raw_card_ids = request.form.getlist("card_ids")
        card_ids = []

        for raw_id in raw_card_ids:
            try:
                card_ids.append(int(raw_id))
            except (TypeError, ValueError):
                continue

        if not card_ids:
            flash("Select at least one card before previewing price labels.")
            return redirect(request.referrer or url_for("cards"))

        cards_by_id = {
            card.id: card
            for card in Card.query.filter(Card.id.in_(card_ids)).all()
        }

        selected_cards = [cards_by_id[card_id] for card_id in card_ids if card_id in cards_by_id]

        label_cards = []
        for card in selected_cards:
            detail_url = url_for("card_detail", card_id=card.id, _external=True)
            qr_url = (
                "https://api.qrserver.com/v1/create-qr-code/"
                f"?size=140x140&data={quote(detail_url, safe='')}"
            )
            label_cards.append({
                "card": card,
                "detail_url": detail_url,
                "qr_url": qr_url,
            })

        return render_template(
            "label_preview.html",
            label_cards=label_cards,
            label_count=len(label_cards),
        )


    @app.route("/inventory-aging")
    def inventory_aging():
        """Dealer view for aging active inventory.

        Supports normal inventory-wide aging and a strict event-loadout scope
        used by Show Prep. When scope=event_loadout, only cards in the exact
        locations saved on the current planned/open event are included.
        """
        bucket_filter = request.args.get("bucket", "all")
        scope_filter = request.args.get("scope", "all")
        event_scope = scope_filter == "event_loadout"

        aging_buckets = {
            "fresh": {
                "label": "Fresh Inventory",
                "range": "0-30 Days",
                "description": "Recently added cards still inside the normal new-inventory window.",
                "accent": "blue",
            },
            "aging": {
                "label": "Aging Inventory",
                "range": "31-90 Days",
                "description": "Cards that may need pricing, promotion, or show placement attention.",
                "accent": "green",
            },
            "old": {
                "label": "Old Inventory",
                "range": "91-180 Days",
                "description": "Inventory that has been sitting long enough to deserve review.",
                "accent": "gold",
            },
            "stale": {
                "label": "Stale Inventory",
                "range": "180+ Days",
                "description": "Long-held cards that may be tying up capital.",
                "accent": "red",
            },
        }

        def parse_card_date(value):
            if not value:
                return None

            if isinstance(value, datetime):
                return value.date()

            if isinstance(value, date):
                return value

            value = str(value).strip()
            if not value:
                return None

            try:
                return datetime.strptime(value[:10], "%Y-%m-%d").date()
            except ValueError:
                pass

            for fmt in ("%m/%d/%Y", "%m-%d-%Y", "%Y/%m/%d"):
                try:
                    return datetime.strptime(value, fmt).date()
                except ValueError:
                    continue

            return None

        def split_locations(value):
            """Split exact saved loadout-location values.

            Accepts newline, pipe, or comma separated values so older and newer
            Show Prep links both work. Values are matched exactly after trim.
            """
            if not value:
                return []

            locations = []
            for separator in ("|", ","):
                value = str(value).replace(separator, "\n")

            for raw_location in str(value).splitlines():
                location = raw_location.strip()
                if location and location not in locations:
                    locations.append(location)

            return locations

        def get_current_event():
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

        def get_aging_basis(card):
            acquisition_dt = parse_card_date(card.acquisition_date)
            if acquisition_dt:
                return acquisition_dt, "Acquisition Date", False

            purchase_dt = parse_card_date(card.purchase_date)
            if purchase_dt:
                return purchase_dt, "Purchase Date", False

            created_dt = parse_card_date(card.created_at)
            if created_dt:
                return created_dt, "Created Date", True

            return date.today(), "Unknown", True

        def bucket_for_days(days_old):
            if days_old <= 30:
                return "fresh"
            if days_old <= 90:
                return "aging"
            if days_old <= 180:
                return "old"
            return "stale"

        def money(value):
            try:
                return float(value or 0)
            except (TypeError, ValueError):
                return 0.0

        current_event = get_current_event() if event_scope else None

        explicit_locations = []
        for location in request.args.getlist("location"):
            explicit_locations.extend(split_locations(location))
        explicit_locations.extend(split_locations(request.args.get("locations", "")))

        if event_scope:
            scoped_locations = explicit_locations
            if not scoped_locations and current_event:
                scoped_locations = split_locations(
                    getattr(current_event, "selected_show_locations", None)
                )
        else:
            scoped_locations = []

        scoped_location_set = set(scoped_locations)

        cards_for_aging = (
            Card.query
            .filter(Card.status != "Sold")
            .filter(Card.collection_type == "Inventory")
            .order_by(Card.created_at.asc())
            .all()
        )

        if event_scope:
            # Strict loadout mode: never fall back to all inventory.
            # If no saved/explicit locations exist, the result should be empty.
            cards_for_aging = [
                card for card in cards_for_aging
                if (card.storage_location or "").strip() in scoped_location_set
            ] if scoped_location_set else []

        bucket_stats = {
            key: {
                **bucket,
                "key": key,
                "count": 0,
                "quantity": 0,
                "cost": 0.0,
                "estimated_value": 0.0,
                "asking": 0.0,
                "estimated_age_count": 0,
                "percent": 0,
            }
            for key, bucket in aging_buckets.items()
        }

        enriched_cards = []
        missing_true_date_count = 0
        today_value = date.today()

        for card in cards_for_aging:
            basis_date, basis_label, estimated_age = get_aging_basis(card)
            days_old = max((today_value - basis_date).days, 0)
            bucket_key = bucket_for_days(days_old)
            quantity = card.quantity or 1

            cost_total = money(card.purchase_price) * quantity
            estimated_total = money(card.estimated_value) * quantity
            asking_total = money(card.asking_price) * quantity

            bucket_stats[bucket_key]["count"] += 1
            bucket_stats[bucket_key]["quantity"] += quantity
            bucket_stats[bucket_key]["cost"] += cost_total
            bucket_stats[bucket_key]["estimated_value"] += estimated_total
            bucket_stats[bucket_key]["asking"] += asking_total

            if estimated_age:
                bucket_stats[bucket_key]["estimated_age_count"] += 1
                missing_true_date_count += 1

            review_flags = []

            if estimated_age:
                review_flags.append("Estimated Age")

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
                "estimated_age": estimated_age,
                "bucket": bucket_key,
                "quantity": quantity,
                "cost_total": cost_total,
                "estimated_total": estimated_total,
                "asking_total": asking_total,
                "review_flags": review_flags,
            })

        total_count = sum(item["count"] for item in bucket_stats.values())

        for stats in bucket_stats.values():
            if total_count:
                stats["percent"] = round((stats["count"] / total_count) * 100)
            else:
                stats["percent"] = 0

        if bucket_filter in aging_buckets:
            visible_cards = [
                item for item in enriched_cards
                if item["bucket"] == bucket_filter
            ]
            current_label = aging_buckets[bucket_filter]["label"]
        else:
            visible_cards = enriched_cards
            current_label = "All Active Inventory"

        if event_scope:
            if current_event:
                current_label = f"{current_label} · {current_event.event_name} Loadout"
            else:
                current_label = f"{current_label} · Event Loadout"

        visible_cards = sorted(
            visible_cards,
            key=lambda item: item["days_old"],
            reverse=True
        )

        old_plus_count = bucket_stats["old"]["count"] + bucket_stats["stale"]["count"]
        stale_count = bucket_stats["stale"]["count"]
        total_cost = sum(item["cost"] for item in bucket_stats.values())
        stale_cost = bucket_stats["stale"]["cost"]
        stale_asking = bucket_stats["stale"]["asking"]
        stale_estimated_value = bucket_stats["stale"]["estimated_value"]
        stale_potential_profit = stale_asking - stale_cost

        if total_count:
            freshness_score = round(((total_count - old_plus_count) / total_count) * 100)
        else:
            freshness_score = 100

        oldest_item = visible_cards[0] if visible_cards else None

        summary = {
            "total_count": total_count,
            "old_plus_count": old_plus_count,
            "stale_count": stale_count,
            "total_cost": total_cost,
            "stale_cost": stale_cost,
            "stale_asking": stale_asking,
            "stale_estimated_value": stale_estimated_value,
            "stale_potential_profit": stale_potential_profit,
            "missing_true_date_count": missing_true_date_count,
            "freshness_score": max(min(freshness_score, 100), 0),
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


    @app.route("/cards/<int:card_id>")
    def card_detail(card_id):
        card = Card.query.get_or_404(card_id)

        return render_template(
            "card_detail.html",
            card=card
        )


    @app.route("/cards/<int:card_id>/edit", methods=["GET", "POST"])
    def edit_card(card_id):
        card = Card.query.get_or_404(card_id)

        if request.method == "POST":
            uploaded_image = save_uploaded_image(request.files.get("card_image"))

            if uploaded_image:
                delete_image_file(card.image_filename)
                card.image_filename = uploaded_image

            if request.form.get("remove_image"):
                delete_image_file(card.image_filename)
                delete_image_file(getattr(card, "image_back_filename", None))
                card.image_filename = None
                card.image_back_filename = None

            card.card_code = request.form["card_code"]
            card.sport = request.form.get("sport")
            card.player_name = clean_value(request.form["player_name"])
            card.year = request.form.get("year") or None
            card.brand = clean_value(request.form.get("brand"))
            card.set_name = clean_value(request.form.get("set_name"))
            card.card_number = clean_value(request.form.get("card_number"))
            card.variation = clean_value(request.form.get("variation"))
            card.is_rookie = True if request.form.get("is_rookie") else False
            card.is_hof = True if request.form.get("is_hof") else False
            card.card_type = request.form.get("card_type") or "Raw"
            card.grading_company = clean_value(request.form.get("grading_company"))
            card.actual_grade = clean_value(request.form.get("actual_grade"))
            card.cert_number = clean_value(request.form.get("cert_number"))
            card.grade_estimate = clean_value(request.form.get("grade_estimate"))
            card.quantity = int(request.form.get("quantity") or 1)
            card.purchase_price = request.form.get("purchase_price") or None
            card.estimated_value = request.form.get("estimated_value") or None
            card.asking_price = request.form.get("asking_price") or None
            card.sold_price = request.form.get("sold_price") or None
            card.sold_date = request.form.get("sold_date")
            card.sales_platform = clean_value(request.form.get("sales_platform"))
            card.payment_type = clean_value(request.form.get("payment_type"))
            card.purchase_date = purchase_date_value(request.form)
            card.acquisition_source = acquisition_value(request.form.get("acquisition_source"))
            card.acquisition_date = acquisition_date_value(request.form)
            card.acquisition_event = clean_value(request.form.get("acquisition_event"))
            card.storage_location = clean_value(request.form.get("storage_location"))
            card.collection_type = request.form.get("collection_type") or "Inventory"
            card.status = request.form.get("status")
            card.notes = request.form.get("notes")

            db.session.commit()

            flash("Card updated successfully.")

            return redirect(url_for("card_detail", card_id=card.id))

        return render_template(
            "edit_card.html",
            card=card
        )


    @app.route("/cards/<int:card_id>/delete", methods=["POST"])
    def delete_card(card_id):
        card = Card.query.get_or_404(card_id)

        # Save image names first. Delete files only after the database delete succeeds.
        image_filename = card.image_filename
        image_back_filename = getattr(card, "image_back_filename", None)

        # Remove staged comp refresh records before deleting the card.
        # This prevents SQLite/SQLAlchemy from trying to null out comp_refresh_queue.card_id.
        CompRefreshQueue.query.filter(
            CompRefreshQueue.card_id == card.id
        ).delete(synchronize_session=False)

        db.session.delete(card)
        db.session.commit()

        delete_image_file(image_filename)
        delete_image_file(image_back_filename)

        flash("Card deleted successfully.")

        return redirect(url_for("cards"))


    @app.route("/cards/<int:card_id>/update-storage", methods=["POST"])
    def update_card_storage(card_id):
        card = Card.query.get_or_404(card_id)

        card.storage_location = clean_value(request.form.get("storage_location"))

        db.session.commit()

        flash(f"{card.card_code} storage location updated.")

        return redirect(request.referrer or url_for("cards"))




    @app.route("/cards/<int:card_id>/update-status", methods=["POST"])
    def update_card_status(card_id):
        card = Card.query.get_or_404(card_id)

        new_status = request.form.get("status") or card.status
        card.status = new_status

        db.session.commit()

        flash(f"{card.card_code} status updated to {card.status}.")

        return redirect(request.referrer or url_for("cards"))


    @app.route("/cards/<int:card_id>/add-duplicate", methods=["POST"])
    def add_duplicate(card_id):
        card = Card.query.get_or_404(card_id)

        old_quantity = card.quantity or 1

        card.quantity = old_quantity + 1

        db.session.commit()

        flash(
            f"Quantity updated from {old_quantity} to {card.quantity}."
        )

        return redirect(url_for("cards"))


    @app.route("/cards/<int:card_id>/clone")
    def clone_card(card_id):
        source_card = Card.query.get_or_404(card_id)

        flash(
            f"Cloning {source_card.card_code}. Review the details, adjust what changed, then save as a new card."
        )

        return render_template(
            "add_card.html",
            clone_source=source_card
        )


    @app.route("/rapid-entry", methods=["GET", "POST"])
    def rapid_entry():
        active_intake_batch = get_active_intake_batch()

        if request.method == "POST":
            quantity_to_add = int(request.form.get("quantity") or 1)
            card_type = request.form.get("card_type") or batch_default(active_intake_batch, "default_card_type", "Raw")
            collection_type = request.form.get("collection_type") or batch_default(active_intake_batch, "default_collection_type", "Inventory")

            player_name = clean_value(request.form["player_name"])
            sport = request.form.get("sport")
            year_value = request.form.get("year")
            brand = clean_value(request.form.get("brand"))
            set_name = clean_value(request.form.get("set_name"))
            card_number = clean_value(request.form.get("card_number"))
            variation = clean_value(request.form.get("variation"))
            force_new_card = request.form.get("force_new") == "1"

            existing_query = Card.query.filter(
                Card.player_name.ilike(player_name),
                Card.sport == sport,
                Card.card_type == card_type
            )

            if year_value:
                existing_query = existing_query.filter(Card.year == int(year_value))

            if brand:
                existing_query = existing_query.filter(Card.brand.ilike(brand))

            if card_number:
                existing_query = existing_query.filter(Card.card_number.ilike(card_number))

            if variation:
                existing_query = existing_query.filter(Card.variation.ilike(variation))
            else:
                existing_query = existing_query.filter(
                    db.or_(Card.variation.is_(None), Card.variation == "")
                )

            existing_card = existing_query.first()

            if existing_card and not force_new_card:
                old_quantity = existing_card.quantity or 1
                existing_card.quantity = old_quantity + quantity_to_add
                existing_card.collection_type = collection_type
                existing_card.acquisition_source = existing_card.acquisition_source or acquisition_value(request.form.get("acquisition_source"))
                existing_card.acquisition_date = existing_card.acquisition_date or acquisition_date_value(request.form)
                existing_card.acquisition_event = existing_card.acquisition_event or batch_value_from_form(request.form, "acquisition_event", active_intake_batch, "default_acquisition_event", get_active_event_name())
                if active_intake_batch and not getattr(existing_card, "intake_batch_id", None):
                    existing_card.intake_batch_id = active_intake_batch.id
                db.session.commit()
                flash(f"Duplicate found. Quantity updated from {old_quantity} to {existing_card.quantity}.")
                saved_card_id = existing_card.id
            else:
                new_card = Card(
                    card_code=generate_card_code(),
                    sport=sport,
                    player_name=player_name,
                    year=year_value or None,
                    brand=brand,
                    set_name=set_name,
                    card_number=card_number,
                    variation=variation,
                    is_rookie=True if request.form.get("is_rookie") else False,
                    is_hof=True if request.form.get("is_hof") else False,
                    card_type=card_type,
                    grading_company=clean_value(request.form.get("grading_company")),
                    actual_grade=clean_value(request.form.get("actual_grade")),
                    cert_number=clean_value(request.form.get("cert_number")),
                    grade_estimate=clean_value(request.form.get("grade_estimate")),
                    quantity=quantity_to_add,
                    purchase_price=request.form.get("purchase_price") or None,
                    estimated_value=request.form.get("estimated_value") or None,
                    asking_price=request.form.get("asking_price") or None,
                    sold_price=request.form.get("sold_price") or None,
                    sold_date=request.form.get("sold_date"),
                    sales_platform=clean_value(request.form.get("sales_platform")),
                    purchase_date=purchase_date_value(request.form),
                    acquisition_source=acquisition_value(request.form.get("acquisition_source") or batch_default(active_intake_batch, "default_acquisition_source", "Existing Inventory")),
                    acquisition_date=acquisition_date_value(request.form) or batch_default(active_intake_batch, "default_acquisition_date"),
                    acquisition_event=batch_value_from_form(request.form, "acquisition_event", active_intake_batch, "default_acquisition_event", get_active_event_name()),
                    intake_batch_id=active_intake_batch.id if active_intake_batch else None,
                    storage_location=batch_value_from_form(request.form, "storage_location", active_intake_batch, "default_storage_location"),
                    collection_type=collection_type,
                    notes=request.form.get("notes"),
                    status=request.form.get("status") or batch_default(active_intake_batch, "default_status", "Active")
                )

                db.session.add(new_card)
                db.session.commit()
                flash("Rapid entry card saved.")
                saved_card_id = new_card.id

            submit_action = request.form.get("submit_action")

            if submit_action == "save_view":
                return redirect(url_for("card_detail", card_id=saved_card_id))

            keep_values = {
                "sport": sport or "",
                "year": year_value or "",
                "brand": brand or "",
                "set_name": set_name or "",
                "card_type": card_type or "Raw",
                "storage_location": request.form.get("storage_location") or "",
                "collection_type": collection_type or "Inventory",
                "status": request.form.get("status") or "Active",
                "purchase_date": purchase_date_value(request.form) or "",
                "acquisition_source": request.form.get("acquisition_source") or "Existing Inventory",
                "acquisition_date": acquisition_date_value(request.form) or "",
                "acquisition_event": request.form.get("acquisition_event") or ""
            }

            return redirect(url_for("rapid_entry", **keep_values))

        return render_template(
            "rapid_entry.html",
            active_intake_batch=active_intake_batch,
        )


    @app.route("/add-card", methods=["GET", "POST"])
    def add_card():
        active_intake_batch = get_active_intake_batch()

        if request.method == "POST":
            quantity_to_add = int(request.form.get("quantity") or 1)

            card_type = request.form.get("card_type") or batch_default(active_intake_batch, "default_card_type", "Raw")
            collection_type = request.form.get("collection_type") or batch_default(active_intake_batch, "default_collection_type", "Inventory")
            card_status = request.form.get("status") or batch_default(active_intake_batch, "default_status") or ("Holding" if collection_type == "Personal Collection" else "Active")

            player_name = clean_value(request.form["player_name"])
            sport = request.form.get("sport")
            year_value = request.form.get("year")
            brand = clean_value(request.form.get("brand"))
            card_number = clean_value(request.form.get("card_number"))
            variation = clean_value(request.form.get("variation"))
            uploaded_image = save_uploaded_image(request.files.get("card_image"))
            force_new_card = request.form.get("force_new") == "1"

            existing_query = Card.query.filter(
                Card.player_name.ilike(player_name),
                Card.sport == sport,
                Card.card_type == card_type
            )

            if year_value:
                existing_query = existing_query.filter(
                    Card.year == int(year_value)
                )

            if brand:
                existing_query = existing_query.filter(
                    Card.brand.ilike(brand)
                )

            if card_number:
                existing_query = existing_query.filter(
                    Card.card_number.ilike(card_number)
                )

            if variation:
                existing_query = existing_query.filter(
                    Card.variation.ilike(variation)
                )
            else:
                existing_query = existing_query.filter(
                    db.or_(
                        Card.variation.is_(None),
                        Card.variation == ""
                    )
                )

            existing_card = existing_query.first()

            if existing_card and not force_new_card:
                old_quantity = existing_card.quantity or 1

                existing_card.quantity = old_quantity + quantity_to_add
                existing_card.collection_type = collection_type
                existing_card.status = card_status
                existing_card.acquisition_source = existing_card.acquisition_source or acquisition_value(request.form.get("acquisition_source"))
                existing_card.acquisition_date = existing_card.acquisition_date or acquisition_date_value(request.form)
                existing_card.acquisition_event = existing_card.acquisition_event or batch_value_from_form(request.form, "acquisition_event", active_intake_batch, "default_acquisition_event", get_active_event_name())
                if active_intake_batch and not getattr(existing_card, "intake_batch_id", None):
                    existing_card.intake_batch_id = active_intake_batch.id

                if uploaded_image:
                    if existing_card.image_filename:
                        delete_image_file(existing_card.image_filename)

                    existing_card.image_filename = uploaded_image

                db.session.commit()

                flash(
                    f"Duplicate card found. Quantity updated from {old_quantity} to {existing_card.quantity}."
                )

                return redirect(
                    url_for(
                        "card_detail",
                        card_id=existing_card.id
                    )
                )

            new_card = Card(
                card_code=generate_card_code(),
                sport=sport,
                player_name=player_name,
                year=year_value or None,
                brand=brand,
                set_name=clean_value(request.form.get("set_name")),
                card_number=card_number,
                variation=variation,
                is_rookie=True if request.form.get("is_rookie") else False,
                is_hof=True if request.form.get("is_hof") else False,
                card_type=card_type,
                grading_company=clean_value(
                    request.form.get("grading_company")
                ),
                actual_grade=clean_value(
                    request.form.get("actual_grade")
                ),
                cert_number=clean_value(
                    request.form.get("cert_number")
                ),
                grade_estimate=clean_value(
                    request.form.get("grade_estimate")
                ),
                quantity=quantity_to_add,
                purchase_price=request.form.get("purchase_price") or None,
                estimated_value=request.form.get("estimated_value") or None,
                asking_price=request.form.get("asking_price") or None,
                sold_price=request.form.get("sold_price") or None,
                sold_date=request.form.get("sold_date"),
                sales_platform=clean_value(request.form.get("sales_platform")),
                purchase_date=purchase_date_value(request.form),
                acquisition_source=acquisition_value(request.form.get("acquisition_source") or batch_default(active_intake_batch, "default_acquisition_source", "Existing Inventory")),
                acquisition_date=acquisition_date_value(request.form) or batch_default(active_intake_batch, "default_acquisition_date"),
                acquisition_event=batch_value_from_form(request.form, "acquisition_event", active_intake_batch, "default_acquisition_event", get_active_event_name()),
                intake_batch_id=active_intake_batch.id if active_intake_batch else None,
                storage_location=batch_value_from_form(
                    request.form, "storage_location", active_intake_batch, "default_storage_location"
                ),
                collection_type=collection_type,
                image_filename=uploaded_image,
                notes=request.form.get("notes"),
                status=card_status
            )

            db.session.add(new_card)
            db.session.commit()

            if force_new_card:
                flash("Cloned card saved as a new inventory record.")
            else:
                flash("New card added successfully.")

            return redirect(url_for("card_detail", card_id=new_card.id))

        return render_template("add_card.html", clone_source=None)
