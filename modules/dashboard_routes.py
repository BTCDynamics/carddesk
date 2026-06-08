from datetime import date, timedelta
from urllib.parse import quote

from flask import render_template, request, url_for, redirect, flash

from models import db, Card, CardImportStaging, DealerEvent
from helpers.acquisition_helpers import is_dashboard_acquisition, parse_card_date
from helpers.deal_cart_helpers import get_deal_cart_quantity


def register_dashboard_routes(app):
    @app.route("/")
    def home():
        return render_template("home.html")

    @app.route("/dashboard")
    def dashboard():
        today_value = date.today()
        today = today_value.isoformat()

        recent_sales_range = request.args.get("recent_sales_range", "30d")
        purchase_summary_range = request.args.get("purchase_summary_range", "30d")

        recent_sales_range_days = {
        "today": 0,
        "3d": 3,
        "7d": 6,
        "30d": 29,
        }

        recent_sales_range_labels = {
            "today": "Today",
            "3d": "Last 3 Days",
            "7d": "Last 7 Days",
            "30d": "Last 30 Days",
        }

        if recent_sales_range not in recent_sales_range_days:
            recent_sales_range = "3d"

        recent_sales_start_date_value = (
            today_value - timedelta(days=recent_sales_range_days[recent_sales_range])
        )
        recent_sales_start_date = recent_sales_start_date_value.isoformat()

        recent_sales_label = recent_sales_range_labels[recent_sales_range]

        if purchase_summary_range not in recent_sales_range_days:
            purchase_summary_range = "30d"

        purchase_summary_start_date_value = (
            today_value - timedelta(days=recent_sales_range_days[purchase_summary_range])
        )
        purchase_summary_start_date = purchase_summary_start_date_value.isoformat()
        purchase_summary_label = recent_sales_range_labels[purchase_summary_range]

        cards = Card.query.all()

        active_cards = [
            card for card in cards
            if card.status != "Sold"
        ]

        sold_cards_all_time = [
            card for card in cards
            if card.status == "Sold"
        ]

        sales_range_cards = [
            card for card in sold_cards_all_time
            if parse_card_date(card.sold_date)
            and parse_card_date(card.sold_date) >= recent_sales_start_date_value
        ]

        sold_cards_today = [
            card for card in sold_cards_all_time
            if parse_card_date(card.sold_date) == today_value
        ]

        recent_sales = list(sales_range_cards)

        recent_sales = sorted(
            recent_sales,
            key=lambda card: (parse_card_date(card.sold_date) or date.min, card.id or 0),
            reverse=True
        )[:12]

        dealer_inventory_active_available = [
            card for card in active_cards
            if card.collection_type == "Inventory"
            and card.status == "Active"
        ]

        dealer_inventory_holding = [
            card for card in active_cards
            if card.collection_type == "Inventory"
            and card.status == "Holding"
        ]

        personal_collection = [
            card for card in active_cards
            if card.collection_type == "Personal Collection"
        ]

        grading_queue = [
            card for card in active_cards
            if card.collection_type == "Grading Queue"
        ]

        trade_bait = [
            card for card in active_cards
            if card.collection_type == "Trade Bait"
        ]

        fulfillment_queue = [
            card for card in sold_cards_all_time
            if getattr(card, "fulfillment_status", None) in ["Needs Pulling", "In Storage"]
            or (
                getattr(card, "fulfillment_status", None) is None
                and card.storage_location
            )
        ]

        pulled_not_shipped_queue = [
            card for card in sold_cards_all_time
            if getattr(card, "fulfillment_status", None) == "Pulled"
        ]

        shipped_not_delivered_queue = [
            card for card in sold_cards_all_time
            if getattr(card, "fulfillment_status", None) == "Shipped"
        ]

        delivered_queue = [
            card for card in sold_cards_all_time
            if getattr(card, "fulfillment_status", None) in ["Delivered", "Completed"]
        ]

        dealer_inventory_cards = sum((card.quantity or 1) for card in dealer_inventory_active_available)
        available_to_sell_cards = dealer_inventory_cards
        inventory_holding_cards = sum((card.quantity or 1) for card in dealer_inventory_holding)
        pc_cards = sum((card.quantity or 1) for card in personal_collection)
        grading_queue_cards = sum((card.quantity or 1) for card in grading_queue)
        trade_bait_cards = sum((card.quantity or 1) for card in trade_bait)
        fulfillment_queue_cards = sum((card.quantity or 1) for card in fulfillment_queue)
        pulled_not_shipped_cards = sum((card.quantity or 1) for card in pulled_not_shipped_queue)
        shipped_not_delivered_cards = sum((card.quantity or 1) for card in shipped_not_delivered_queue)
        delivered_cards = sum((card.quantity or 1) for card in delivered_queue)

        missing_storage_cards = sum(
            (card.quantity or 1)
            for card in active_cards
            if not card.storage_location
        )

        sales_7d_start_date_value = today_value - timedelta(days=6)

        sales_7d_cards = sum(
            (card.quantity or 1)
            for card in sold_cards_all_time
            if parse_card_date(card.sold_date)
            and parse_card_date(card.sold_date) >= sales_7d_start_date_value
        )

        sales_7d_total = sum(
            ((card.sold_price or 0) * (card.quantity or 1))
            for card in sold_cards_all_time
            if parse_card_date(card.sold_date)
            and parse_card_date(card.sold_date) >= sales_7d_start_date_value
        )

        open_workflow_tasks = (
            fulfillment_queue_cards
            + pulled_not_shipped_cards
            + shipped_not_delivered_cards
            + grading_queue_cards
            + inventory_holding_cards
        )

        dealer_inventory_cost = 0
        dealer_inventory_value = 0
        available_asking_price = 0
        available_estimated_value = 0
        available_potential_profit = 0
        pc_total_cost = 0
        pc_estimated_value = 0

        for card in dealer_inventory_active_available:
            quantity = card.quantity or 1
            purchase_cost = card.purchase_price or 0
            estimated_value = card.estimated_value or 0
            asking_price = card.asking_price or 0

            dealer_inventory_cost += purchase_cost * quantity
            dealer_inventory_value += estimated_value * quantity
            available_asking_price += asking_price * quantity
            available_estimated_value += estimated_value * quantity
            available_potential_profit += (asking_price - purchase_cost) * quantity

        for card in personal_collection:
            quantity = card.quantity or 1
            purchase_cost = card.purchase_price or 0
            estimated_value = card.estimated_value or 0

            pc_total_cost += purchase_cost * quantity
            pc_estimated_value += estimated_value * quantity

        dealer_unrealized_gain_loss = (
            dealer_inventory_value - dealer_inventory_cost
        )

        pc_estimated_profit_loss = (
            pc_estimated_value - pc_total_cost
        )

        dealer_unrealized_gain_loss_percent = (
            (dealer_unrealized_gain_loss / dealer_inventory_cost) * 100
            if dealer_inventory_cost
            else 0
        )

        dealer_inventory_value_percent = (
            (dealer_inventory_value / dealer_inventory_cost) * 100
            if dealer_inventory_cost
            else 0
        )

        available_potential_profit_percent = (
            (available_potential_profit / dealer_inventory_cost) * 100
            if dealer_inventory_cost
            else 0
        )

        pc_estimated_profit_loss_percent = (
            (pc_estimated_profit_loss / pc_total_cost) * 100
            if pc_total_cost
            else 0
        )

        pc_estimated_value_percent = (
            (pc_estimated_value / pc_total_cost) * 100
            if pc_total_cost
            else 0
        )

        selected_range_sold_price = 0
        selected_range_sold_cost = 0
        selected_range_profit = 0

        for card in sales_range_cards:
            quantity = card.quantity or 1
            sold_price = card.sold_price or 0
            purchase_cost = card.purchase_price or 0

            selected_range_sold_price += sold_price * quantity
            selected_range_sold_cost += purchase_cost * quantity
            selected_range_profit += (sold_price * quantity) - (purchase_cost * quantity)

        selected_range_sold_cards = sum(
            (card.quantity or 1)
            for card in sales_range_cards
        )

        selected_range_profit_percent = (
            (selected_range_profit / selected_range_sold_cost) * 100
            if selected_range_sold_cost
            else 0
        )

        selected_range_sales_margin_percent = (
            (selected_range_profit / selected_range_sold_price) * 100
            if selected_range_sold_price
            else 0
        )


        # Acquisition activity for the selected dashboard range.
        # This separates newly acquired inventory from cards that were only entered into CardDesk.
        bought_range_cards = [
            card for card in active_cards
            if card.collection_type == "Inventory"
            and card.status == "Active"
            and is_dashboard_acquisition(card)
            and parse_card_date(getattr(card, "acquisition_date", None))
            and parse_card_date(getattr(card, "acquisition_date", None)) >= purchase_summary_start_date_value
        ]

        cards_bought_in_range = sum(
            (card.quantity or 1)
            for card in bought_range_cards
        )

        cost_bought_in_range = sum(
            ((card.purchase_price or 0) * (card.quantity or 1))
            for card in bought_range_cards
        )

        value_bought_in_range = sum(
            ((card.estimated_value or 0) * (card.quantity or 1))
            for card in bought_range_cards
        )

        comp_value_bought_in_range = value_bought_in_range

        recent_acquisitions = sorted(
            bought_range_cards,
            key=lambda card: (
                parse_card_date(getattr(card, "acquisition_date", None)) or date.min,
                card.id or 0
            ),
            reverse=True
        )[:12]

        # Keep the original template variable names, but make them follow the selected dashboard sales range.
        today_sold_price = selected_range_sold_price
        today_sold_cost = selected_range_sold_cost
        today_profit = selected_range_profit
        today_sold_cards = selected_range_sold_cards
        today_profit_percent = selected_range_profit_percent
        today_sales_margin_percent = selected_range_sales_margin_percent

        rookie_cards = sum(
            (card.quantity or 1)
            for card in active_cards
            if card.is_rookie
        )

        hof_cards = sum(
            (card.quantity or 1)
            for card in active_cards
            if card.is_hof
        )

        raw_cards = sum(
            (card.quantity or 1)
            for card in active_cards
            if card.card_type == "Raw"
        )

        graded_cards = sum(
            (card.quantity or 1)
            for card in active_cards
            if card.card_type == "Graded"
        )

        ai_pending_review_cards = CardImportStaging.query.filter(
            CardImportStaging.ai_status == "Pending Review"
        ).count()

        ai_manual_review_cards = CardImportStaging.query.filter(
            CardImportStaging.ai_status == "Needs Manual Review"
        ).count()

        ai_imported_cards = CardImportStaging.query.filter(
            CardImportStaging.ai_status == "Imported"
        ).count()

        ai_rejected_cards = CardImportStaging.query.filter(
            CardImportStaging.ai_status == "Rejected"
        ).count()

        ai_action_needed_cards = ai_pending_review_cards + ai_manual_review_cards

        mobile_capture_url = url_for("mobile_capture", _external=True)
        mobile_capture_qr_url = (
            "https://api.qrserver.com/v1/create-qr-code/"
            f"?size=220x220&data={quote(mobile_capture_url, safe='')}"
        )

        return render_template(
            "dashboard.html",
            today=today,
            dealer_inventory_cards=dealer_inventory_cards,
            available_to_sell_cards=available_to_sell_cards,
            pc_cards=pc_cards,
            grading_queue_cards=grading_queue_cards,
            trade_bait_cards=trade_bait_cards,
            inventory_holding_cards=inventory_holding_cards,
            fulfillment_queue_cards=fulfillment_queue_cards,
            pulled_not_shipped_cards=pulled_not_shipped_cards,
            shipped_not_delivered_cards=shipped_not_delivered_cards,
            delivered_cards=delivered_cards,
            missing_storage_cards=missing_storage_cards,
            sales_7d_cards=sales_7d_cards,
            sales_7d_total=sales_7d_total,
            open_workflow_tasks=open_workflow_tasks,
            dealer_inventory_cost=dealer_inventory_cost,
            dealer_inventory_value=dealer_inventory_value,
            dealer_inventory_value_percent=dealer_inventory_value_percent,
            dealer_unrealized_gain_loss=dealer_unrealized_gain_loss,
            dealer_unrealized_gain_loss_percent=dealer_unrealized_gain_loss_percent,
            available_asking_price=available_asking_price,
            available_estimated_value=available_estimated_value,
            available_potential_profit=available_potential_profit,
            available_potential_profit_percent=available_potential_profit_percent,
            pc_total_cost=pc_total_cost,
            pc_estimated_value=pc_estimated_value,
            pc_estimated_value_percent=pc_estimated_value_percent,
            pc_estimated_profit_loss=pc_estimated_profit_loss,
            pc_estimated_profit_loss_percent=pc_estimated_profit_loss_percent,
            rookie_cards=rookie_cards,
            hof_cards=hof_cards,
            raw_cards=raw_cards,
            graded_cards=graded_cards,
            sold_cards=today_sold_cards,
            total_sold_price=today_sold_price,
            total_profit=today_profit,
            today_profit_percent=today_profit_percent,
            today_sales_margin_percent=today_sales_margin_percent,
            cards_bought_in_range=cards_bought_in_range,
            cost_bought_in_range=cost_bought_in_range,
            value_bought_in_range=value_bought_in_range,
            comp_value_bought_in_range=comp_value_bought_in_range,
            purchase_summary_range=purchase_summary_range,
            purchase_summary_label=purchase_summary_label,
            purchase_summary_start_date=purchase_summary_start_date,
            recent_sales=recent_sales,
            recent_acquisitions=recent_acquisitions,
            recent_sales_start_date=recent_sales_start_date,
            recent_sales_range=recent_sales_range,
            recent_sales_label=recent_sales_label,
            sales_summary_label=recent_sales_label,
            sales_summary_range=recent_sales_range,
            sales_summary_start_date=recent_sales_start_date,
            deal_cart_count=get_deal_cart_quantity(),
            ai_pending_review_cards=ai_pending_review_cards,
            ai_manual_review_cards=ai_manual_review_cards,
            ai_imported_cards=ai_imported_cards,
            ai_rejected_cards=ai_rejected_cards,
            ai_action_needed_cards=ai_action_needed_cards,
            mobile_capture_url=mobile_capture_url,
            mobile_capture_qr_url=mobile_capture_qr_url
        )


    def get_open_event():
        return (
            DealerEvent.query
            .filter(DealerEvent.status == "Open")
            .order_by(DealerEvent.id.desc())
            .first()
        )

    def get_planned_event():
        return (
            DealerEvent.query
            .filter(DealerEvent.status == "Planned")
            .order_by(DealerEvent.id.desc())
            .first()
        )

    def get_current_event():
        # Open event takes priority. If no event is open, use the most recent
        # planned event so the dealer can prep locations/expenses before showtime.
        return get_open_event() or get_planned_event()

    def event_date_bounds(event):
        if not event or event.status == "Planned":
            return None, None

        start_date = parse_card_date(event.start_date)
        end_date = parse_card_date(event.end_date) if event.end_date else date.today()
        return start_date, end_date

    def event_money(value):
        try:
            return float(value or 0)
        except (TypeError, ValueError):
            return 0.0

    def event_expense_total(event):
        if not event:
            return 0.0

        return sum([
            event_money(getattr(event, "table_fee", 0)),
            event_money(getattr(event, "travel_expense", 0)),
            event_money(getattr(event, "lodging_expense", 0)),
            event_money(getattr(event, "food_expense", 0)),
            event_money(getattr(event, "other_expense", 0)),
        ])

    def split_show_locations(value):
        if not value:
            return []

        locations = []
        for raw_location in str(value).replace("|", "\n").splitlines():
            location = raw_location.strip()
            if location and location not in locations:
                locations.append(location)

        return locations

    def cards_for_event(event, cards):
        """Return acquisition and sales cards for an event.

        Acquisitions use Card.acquisition_event because that field already exists.
        Sales use sold_date inside the event date window so we avoid a database
        migration for sales-event tagging in this first version.
        """
        if not event:
            return [], []

        start_date, end_date = event_date_bounds(event)

        acquisition_cards = [
            card for card in cards
            if getattr(card, "acquisition_event", None) == event.event_name
        ]

        sales_cards = []
        if start_date:
            for card in cards:
                sold_dt = parse_card_date(getattr(card, "sold_date", None))
                if sold_dt and sold_dt >= start_date and sold_dt <= end_date:
                    sales_cards.append(card)

        return acquisition_cards, sales_cards

    def event_stats(event, cards):
        acquisition_cards, sales_cards = cards_for_event(event, cards)

        acquired_count = sum((card.quantity or 1) for card in acquisition_cards)
        acquisition_cost = sum((card.purchase_price or 0) * (card.quantity or 1) for card in acquisition_cards)
        acquisition_value = sum((card.estimated_value or 0) * (card.quantity or 1) for card in acquisition_cards)
        acquisition_potential_profit = sum(
            ((card.asking_price or 0) - (card.purchase_price or 0)) * (card.quantity or 1)
            for card in acquisition_cards
        )

        sold_count = sum((card.quantity or 1) for card in sales_cards)
        sales_revenue = sum((card.sold_price or 0) * (card.quantity or 1) for card in sales_cards)
        sales_cost = sum((card.purchase_price or 0) * (card.quantity or 1) for card in sales_cards)
        sales_profit = sales_revenue - sales_cost
        event_expenses = event_expense_total(event)
        net_profit = sales_profit - event_expenses
        sales_margin = (sales_profit / sales_revenue * 100) if sales_revenue else 0
        net_margin = (net_profit / sales_revenue * 100) if sales_revenue else 0

        show_locations = split_show_locations(
            getattr(event, "selected_show_locations", None)
        )
        show_location_set = set(show_locations)
        show_inventory_cards = [
            card for card in cards
            if card.status == "Active"
            and card.collection_type == "Inventory"
            and (card.storage_location or "").strip() in show_location_set
        ]

        show_card_count = sum((card.quantity or 1) for card in show_inventory_cards)
        show_cost = sum((card.purchase_price or 0) * (card.quantity or 1) for card in show_inventory_cards)
        show_estimated_value = sum((card.estimated_value or 0) * (card.quantity or 1) for card in show_inventory_cards)
        show_asking_price = sum((card.asking_price or 0) * (card.quantity or 1) for card in show_inventory_cards)
        show_potential_profit = show_asking_price - show_cost

        return {
            "acquisition_cards": acquisition_cards,
            "sales_cards": sales_cards,
            "show_inventory_cards": show_inventory_cards,
            "show_locations": show_locations,
            "show_location_count": len(show_locations),
            "show_card_count": show_card_count,
            "show_cost": show_cost,
            "show_estimated_value": show_estimated_value,
            "show_asking_price": show_asking_price,
            "show_potential_profit": show_potential_profit,
            "acquired_count": acquired_count,
            "acquisition_cost": acquisition_cost,
            "acquisition_value": acquisition_value,
            "acquisition_potential_profit": acquisition_potential_profit,
            "sold_count": sold_count,
            "sales_revenue": sales_revenue,
            "sales_profit": sales_profit,
            "sales_margin": sales_margin,
            "event_expenses": event_expenses,
            "net_profit": net_profit,
            "net_margin": net_margin,
            "table_fee": event_money(getattr(event, "table_fee", 0)),
            "travel_expense": event_money(getattr(event, "travel_expense", 0)),
            "lodging_expense": event_money(getattr(event, "lodging_expense", 0)),
            "food_expense": event_money(getattr(event, "food_expense", 0)),
            "other_expense": event_money(getattr(event, "other_expense", 0)),
            "net_cash": sales_revenue - acquisition_cost - event_expenses,
        }

    @app.route("/events", methods=["GET"])
    def events():
        all_cards = Card.query.all()
        active_event = get_open_event()
        current_event = get_current_event()
        events_list = DealerEvent.query.order_by(DealerEvent.id.desc()).all()

        event_summaries = []
        for event in events_list:
            event_summaries.append({
                "event": event,
                "stats": event_stats(event, all_cards),
            })

        return render_template(
            "events.html",
            today=date.today().isoformat(),
            active_event=active_event,
            current_event=current_event,
            event_summaries=event_summaries,
        )

    @app.route("/events/create", methods=["POST"])
    @app.route("/events/start", methods=["POST"])  # Backward-compatible URL. Creates a Planned event now.
    def create_event():
        event_name = (request.form.get("event_name") or "").strip()
        location = (request.form.get("location") or "").strip() or None
        start_date = request.form.get("start_date") or date.today().isoformat()
        notes = (request.form.get("notes") or "").strip() or None
        table_fee = event_money(request.form.get("table_fee"))
        travel_expense = event_money(request.form.get("travel_expense"))
        lodging_expense = event_money(request.form.get("lodging_expense"))
        food_expense = event_money(request.form.get("food_expense"))
        other_expense = event_money(request.form.get("other_expense"))
        expense_notes = (request.form.get("expense_notes") or "").strip() or None

        if not event_name:
            flash("Event name is required.")
            return redirect(request.referrer or url_for("events"))

        current_event = get_current_event()
        if current_event:
            flash(f"Finish {current_event.event_name} before creating another event.")
            return redirect(request.referrer or url_for("dealer_hub"))

        new_event = DealerEvent(
            event_name=event_name,
            location=location,
            start_date=start_date,
            status="Planned",
            notes=notes,
            table_fee=table_fee,
            travel_expense=travel_expense,
            lodging_expense=lodging_expense,
            food_expense=food_expense,
            other_expense=other_expense,
            expense_notes=expense_notes,
        )

        db.session.add(new_event)
        db.session.commit()

        flash(f"Created event: {new_event.event_name}. Use Show Prep now, then start it when business begins.")
        return redirect(url_for("event_detail", event_id=new_event.id))

    @app.route("/events/<int:event_id>/start", methods=["POST"])
    def start_existing_event(event_id):
        event = DealerEvent.query.get_or_404(event_id)

        if event.status == "Closed":
            flash("Closed events cannot be restarted.")
            return redirect(url_for("event_detail", event_id=event.id))

        open_event = get_open_event()
        if open_event and open_event.id != event.id:
            flash(f"Close {open_event.event_name} before starting another event.")
            return redirect(url_for("event_detail", event_id=event.id))

        event.status = "Open"
        event.start_date = request.form.get("start_date") or date.today().isoformat()
        event.end_date = None
        event.closed_at = None

        db.session.commit()

        flash(f"Started event: {event.event_name}.")
        return redirect(url_for("event_detail", event_id=event.id))

    @app.route("/events/<int:event_id>")
    def event_detail(event_id):
        event = DealerEvent.query.get_or_404(event_id)
        all_cards = Card.query.all()
        stats = event_stats(event, all_cards)

        recent_acquisitions = sorted(
            stats["acquisition_cards"],
            key=lambda card: (
                parse_card_date(getattr(card, "acquisition_date", None)) or date.min,
                card.id or 0,
            ),
            reverse=True,
        )

        recent_sales = sorted(
            stats["sales_cards"],
            key=lambda card: (
                parse_card_date(getattr(card, "sold_date", None)) or date.min,
                card.id or 0,
            ),
            reverse=True,
        )

        return render_template(
            "event_detail.html",
            event=event,
            today=date.today().isoformat(),
            stats=stats,
            recent_acquisitions=recent_acquisitions,
            recent_sales=recent_sales,
        )

    @app.route("/events/<int:event_id>/close", methods=["POST"])
    def close_event(event_id):
        event = DealerEvent.query.get_or_404(event_id)

        event.status = "Closed"
        event.end_date = request.form.get("end_date") or date.today().isoformat()
        event.closed_at = db.func.now()

        db.session.commit()

        flash(f"Closed event: {event.event_name}.")
        return redirect(url_for("event_detail", event_id=event.id))

    @app.route("/dealer-hub")
    def dealer_hub():
        """Show Mode / Dealer Hub view with selectable event/show timeframe."""
        today_value = date.today()
        today = today_value.isoformat()

        dealer_hub_range = request.args.get("range", "3d")

        dealer_hub_range_days = {
            "today": 0,
            "3d": 3,
            "7d": 6,
            "30d": 29,
        }

        dealer_hub_range_labels = {
            "today": "Today",
            "3d": "Last 3 Days",
            "7d": "Last 7 Days",
            "30d": "Last 30 Days",
        }

        if dealer_hub_range not in dealer_hub_range_days:
            dealer_hub_range = "3d"

        dealer_hub_start_date_value = (
            today_value - timedelta(days=dealer_hub_range_days[dealer_hub_range])
        )
        dealer_hub_start_date = dealer_hub_start_date_value.isoformat()
        dealer_hub_range_label = dealer_hub_range_labels[dealer_hub_range]

        cards = Card.query.all()
        current_event = get_current_event()
        active_event = get_open_event()
        active_event_stats = event_stats(current_event, cards) if current_event else None

        active_cards = [
            card for card in cards
            if card.status != "Sold"
        ]

        sold_cards_all_time = [
            card for card in cards
            if card.status == "Sold"
        ]

        sold_cards_range = [
            card for card in sold_cards_all_time
            if parse_card_date(card.sold_date)
            and parse_card_date(card.sold_date) >= dealer_hub_start_date_value
        ]

        acquired_range_cards = [
            card for card in active_cards
            if card.collection_type == "Inventory"
            and card.status == "Active"
            and is_dashboard_acquisition(card)
            and parse_card_date(getattr(card, "acquisition_date", None))
            and parse_card_date(getattr(card, "acquisition_date", None)) >= dealer_hub_start_date_value
        ]

        dealer_inventory_active_available = [
            card for card in active_cards
            if card.collection_type == "Inventory"
            and card.status == "Active"
        ]

        dealer_inventory_holding = [
            card for card in active_cards
            if card.collection_type == "Inventory"
            and card.status == "Holding"
        ]

        grading_queue = [
            card for card in active_cards
            if card.collection_type == "Grading Queue"
        ]

        fulfillment_queue = [
            card for card in sold_cards_all_time
            if getattr(card, "fulfillment_status", None) in ["Needs Pulling", "In Storage"]
            or (
                getattr(card, "fulfillment_status", None) is None
                and card.storage_location
            )
        ]

        pulled_not_shipped_queue = [
            card for card in sold_cards_all_time
            if getattr(card, "fulfillment_status", None) == "Pulled"
        ]

        shipped_not_delivered_queue = [
            card for card in sold_cards_all_time
            if getattr(card, "fulfillment_status", None) == "Shipped"
        ]

        available_to_sell_cards = sum((card.quantity or 1) for card in dealer_inventory_active_available)
        inventory_holding_cards = sum((card.quantity or 1) for card in dealer_inventory_holding)
        grading_queue_cards = sum((card.quantity or 1) for card in grading_queue)
        fulfillment_queue_cards = sum((card.quantity or 1) for card in fulfillment_queue)
        pulled_not_shipped_cards = sum((card.quantity or 1) for card in pulled_not_shipped_queue)
        shipped_not_delivered_cards = sum((card.quantity or 1) for card in shipped_not_delivered_queue)
        missing_storage_cards = sum((card.quantity or 1) for card in dealer_inventory_active_available if not card.storage_location)

        dealer_inventory_cost = 0
        dealer_inventory_value = 0
        available_asking_price = 0
        available_potential_profit = 0

        for card in dealer_inventory_active_available:
            quantity = card.quantity or 1
            purchase_cost = card.purchase_price or 0
            estimated_value = card.estimated_value or 0
            asking_price = card.asking_price or 0

            dealer_inventory_cost += purchase_cost * quantity
            dealer_inventory_value += estimated_value * quantity
            available_asking_price += asking_price * quantity
            available_potential_profit += (asking_price - purchase_cost) * quantity

        range_acquired_count = sum((card.quantity or 1) for card in acquired_range_cards)
        range_acquisition_cost = sum((card.purchase_price or 0) * (card.quantity or 1) for card in acquired_range_cards)
        range_acquisition_value = sum((card.estimated_value or 0) * (card.quantity or 1) for card in acquired_range_cards)
        range_acquisition_potential_profit = sum(((card.asking_price or 0) - (card.purchase_price or 0)) * (card.quantity or 1) for card in acquired_range_cards)

        range_sold_cards = sum((card.quantity or 1) for card in sold_cards_range)
        range_sold_price = sum((card.sold_price or 0) * (card.quantity or 1) for card in sold_cards_range)
        range_sold_cost = sum((card.purchase_price or 0) * (card.quantity or 1) for card in sold_cards_range)
        range_profit = range_sold_price - range_sold_cost
        range_sales_margin_percent = (range_profit / range_sold_price * 100) if range_sold_price else 0

        ai_pending_review_cards = CardImportStaging.query.filter(CardImportStaging.ai_status == "Pending Review").count()
        ai_manual_review_cards = CardImportStaging.query.filter(CardImportStaging.ai_status == "Needs Manual Review").count()
        ai_action_needed_cards = ai_pending_review_cards + ai_manual_review_cards

        action_needed_total = (
            fulfillment_queue_cards
            + pulled_not_shipped_cards
            + shipped_not_delivered_cards
            + missing_storage_cards
            + ai_action_needed_cards
            + inventory_holding_cards
        )

        recent_sales = sorted(
            sold_cards_range,
            key=lambda card: (parse_card_date(card.sold_date) or date.min, card.id or 0),
            reverse=True
        )[:6]

        recent_acquisitions = sorted(
            acquired_range_cards,
            key=lambda card: (
                parse_card_date(getattr(card, "acquisition_date", None)) or date.min,
                card.id or 0
            ),
            reverse=True
        )[:6]

        mobile_capture_url = url_for("mobile_capture", _external=True)
        mobile_capture_qr_url = (
            "https://api.qrserver.com/v1/create-qr-code/"
            f"?size=220x220&data={quote(mobile_capture_url, safe='')}"
        )

        return render_template(
            "dealer_hub.html",
            today=today,
            active_event=active_event,
            current_event=current_event,
            active_event_stats=active_event_stats,
            dealer_hub_range=dealer_hub_range,
            dealer_hub_range_label=dealer_hub_range_label,
            dealer_hub_start_date=dealer_hub_start_date,
            available_to_sell_cards=available_to_sell_cards,
            dealer_inventory_cost=dealer_inventory_cost,
            dealer_inventory_value=dealer_inventory_value,
            available_asking_price=available_asking_price,
            available_potential_profit=available_potential_profit,
            range_acquired_count=range_acquired_count,
            range_acquisition_cost=range_acquisition_cost,
            range_acquisition_value=range_acquisition_value,
            range_acquisition_potential_profit=range_acquisition_potential_profit,
            range_sold_cards=range_sold_cards,
            range_sold_price=range_sold_price,
            range_profit=range_profit,
            range_sales_margin_percent=range_sales_margin_percent,
            fulfillment_queue_cards=fulfillment_queue_cards,
            pulled_not_shipped_cards=pulled_not_shipped_cards,
            shipped_not_delivered_cards=shipped_not_delivered_cards,
            missing_storage_cards=missing_storage_cards,
            inventory_holding_cards=inventory_holding_cards,
            grading_queue_cards=grading_queue_cards,
            ai_action_needed_cards=ai_action_needed_cards,
            ai_pending_review_cards=ai_pending_review_cards,
            ai_manual_review_cards=ai_manual_review_cards,
            action_needed_total=action_needed_total,
            deal_cart_count=get_deal_cart_quantity(),
            recent_sales=recent_sales,
            recent_acquisitions=recent_acquisitions,
            mobile_capture_url=mobile_capture_url,
            mobile_capture_qr_url=mobile_capture_qr_url,
        )
