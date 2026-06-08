from datetime import date

from flask import render_template, request, redirect, url_for, flash

from models import db, Card
from helpers.acquisition_helpers import clean_value
from helpers.deal_cart_helpers import (
    get_deal_cart_ids,
    save_deal_cart_ids,
    get_deal_cart_cards,
)


def register_sales_routes(app):
    @app.route("/cards/<int:card_id>/quick-sell", methods=["GET", "POST"])
    def quick_sell(card_id):
        card = Card.query.get_or_404(card_id)

        if request.method == "POST":
            card.sold_price = request.form.get("sold_price") or None
            card.sold_date = request.form.get("sold_date") or date.today().isoformat()
            card.sales_platform = clean_value(request.form.get("sales_platform"))
            card.payment_type = clean_value(request.form.get("payment_type"))
            card.status = "Sold"
            card.fulfillment_status = "Needs Pulling" if card.storage_location else "No Location"

            if card.storage_location:
                existing_notes = card.notes or ""
                pull_note = f"Needs pulling from: {card.storage_location}"
                card.notes = (existing_notes + "\n" if existing_notes else "") + pull_note

            db.session.commit()

            flash(f"{card.card_code} marked as sold.")

            return redirect(url_for("card_detail", card_id=card.id))

        return render_template(
            "quick_sell.html",
            card=card,
            today=date.today().isoformat()
        )


    @app.route("/deal-cart")
    def deal_cart():
        selected_cards = get_deal_cart_cards()

        selected_card_count = sum((card.quantity or 1) for card in selected_cards)
        total_cost = sum((card.purchase_price or 0) * (card.quantity or 1) for card in selected_cards)
        total_asking = sum((card.asking_price or 0) * (card.quantity or 1) for card in selected_cards)
        total_estimated_value = sum((card.estimated_value or 0) * (card.quantity or 1) for card in selected_cards)
        total_estimated_profit_loss = total_estimated_value - total_cost

        return render_template(
            "deal_cart.html",
            selected_cards=selected_cards,
            selected_card_count=selected_card_count,
            total_cost=total_cost,
            total_asking=total_asking,
            total_estimated_value=total_estimated_value,
            total_estimated_profit_loss=total_estimated_profit_loss,
            today=date.today().isoformat()
        )


    @app.route("/deal-cart/add", methods=["POST"])
    def add_to_deal_cart():
        selected_ids = request.form.getlist("card_ids")

        if not selected_ids:
            flash("Select at least one Active card to add to the deal cart.")
            return redirect(request.referrer or url_for("cards"))

        clean_selected_ids = []

        for card_id in selected_ids:
            try:
                clean_selected_ids.append(int(card_id))
            except (TypeError, ValueError):
                continue

        active_cards = (
            Card.query
            .filter(Card.id.in_(clean_selected_ids))
            .filter(Card.status == "Active")
            .all()
        )

        if not active_cards:
            flash("Only Active cards can be added to the deal cart.")
            return redirect(request.referrer or url_for("cards"))

        existing_ids = get_deal_cart_ids()

        for card in active_cards:
            if card.id not in existing_ids:
                existing_ids.append(card.id)

        save_deal_cart_ids(existing_ids)

        flash(f"Added {len(active_cards)} active card(s) to the deal cart.")

        return redirect(request.referrer or url_for("cards"))


    @app.route("/deal-cart/remove/<int:card_id>", methods=["POST"])
    def remove_from_deal_cart(card_id):
        remaining_ids = [existing_id for existing_id in get_deal_cart_ids() if existing_id != card_id]
        save_deal_cart_ids(remaining_ids)

        flash("Card removed from deal cart.")

        return redirect(url_for("deal_cart"))


    @app.route("/deal-cart/clear", methods=["POST"])
    def clear_deal_cart():
        save_deal_cart_ids([])

        flash("Deal cart cleared.")

        return redirect(request.referrer or url_for("cards"))


    @app.route("/bulk-sell", methods=["POST"])
    def bulk_sell():
        card_ids = request.form.getlist("card_ids")

        if not card_ids:
            flash("Select at least one card to sell as a lot.")
            return redirect(url_for("cards"))

        selected_cards = (
            Card.query
            .filter(Card.id.in_([int(card_id) for card_id in card_ids]))
            .order_by(Card.player_name.asc())
            .all()
        )

        selected_cards = [card for card in selected_cards if card.status == "Active"]

        if not selected_cards:
            flash("Selected cards must be Active before they can be sold.")
            return redirect(url_for("cards"))

        if request.form.get("total_sale_price"):
            total_sale_price = float(request.form.get("total_sale_price") or 0)
            trade_credit = float(request.form.get("trade_credit") or 0)
            discount_percent = float(request.form.get("discount_percent") or 0)
            sold_date = request.form.get("sold_date") or date.today().isoformat()
            sales_platform = clean_value(request.form.get("sales_platform"))
            customer_name = clean_value(request.form.get("customer_name"))
            payment_type = clean_value(request.form.get("payment_type"))
            deal_notes = clean_value(request.form.get("deal_notes"))
            mark_pulled_now = request.form.get("mark_pulled_now") == "1"
            fulfillment_status = "Pulled" if mark_pulled_now else "Needs Pulling"

            total_asking = sum((card.asking_price or 0) * (card.quantity or 1) for card in selected_cards)
            total_quantity = sum((card.quantity or 1) for card in selected_cards)

            if total_asking > 0:
                for card in selected_cards:
                    quantity = card.quantity or 1
                    card_asking_total = (card.asking_price or 0) * quantity
                    card_share = card_asking_total / total_asking
                    card.sold_price = total_sale_price * card_share / quantity
                    card.sold_date = sold_date
                    card.sales_platform = sales_platform
                    card.status = "Sold"
                    card.fulfillment_status = fulfillment_status

                    note_parts = []
                    if customer_name:
                        note_parts.append(f"Customer: {customer_name}")
                    if payment_type:
                        note_parts.append(f"Payment: {payment_type}")
                    if trade_credit:
                        note_parts.append(f"Trade credit: ${trade_credit:.2f}")
                    if card.storage_location and not mark_pulled_now:
                        note_parts.append(f"Needs pulling from: {card.storage_location}")
                    if card.storage_location and mark_pulled_now:
                        note_parts.append(f"Pulled from: {card.storage_location}")
                    if discount_percent:
                        note_parts.append(f"Deal discount: {discount_percent:.2f}%")
                    if deal_notes:
                        note_parts.append(f"Deal notes: {deal_notes}")

                    if note_parts:
                        existing_notes = card.notes or ""
                        deal_note_text = " | ".join(note_parts)
                        card.notes = (existing_notes + "\n" if existing_notes else "") + deal_note_text

                split_message = f"split proportionally by asking price with {discount_percent:.2f}% discount"
            else:
                split_price = total_sale_price / total_quantity if total_quantity else 0

                for card in selected_cards:
                    card.sold_price = split_price
                    card.sold_date = sold_date
                    card.sales_platform = sales_platform
                    card.status = "Sold"
                    card.fulfillment_status = fulfillment_status

                split_message = f"split evenly at ${split_price:.2f} each because no asking prices were available"

            db.session.commit()

            sold_ids = [card.id for card in selected_cards]
            remaining_cart_ids = [card_id for card_id in get_deal_cart_ids() if card_id not in sold_ids]
            save_deal_cart_ids(remaining_cart_ids)

            flash(
                f"Deal completed. {len(selected_cards)} records / {total_quantity} cards marked Sold; ${total_sale_price:.2f} sale amount {split_message}."
            )

            return redirect(url_for("cards"))

        total_cost = sum((card.purchase_price or 0) * (card.quantity or 1) for card in selected_cards)
        total_asking = sum((card.asking_price or 0) * (card.quantity or 1) for card in selected_cards)

        return render_template(
            "bulk_sell.html",
            selected_cards=selected_cards,
            total_cost=total_cost,
            total_asking=total_asking,
            today=date.today().isoformat()
        )
