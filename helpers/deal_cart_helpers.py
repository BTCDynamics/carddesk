from flask import session

from models import Card


def get_deal_cart_ids():
    """Return selected deal-cart card IDs stored in the user session."""
    return [int(card_id) for card_id in session.get("deal_cart", [])]


def save_deal_cart_ids(card_ids):
    """Store unique deal-cart card IDs in the session."""
    clean_ids = []

    for card_id in card_ids:
        try:
            clean_id = int(card_id)
        except (TypeError, ValueError):
            continue

        if clean_id not in clean_ids:
            clean_ids.append(clean_id)

    session["deal_cart"] = clean_ids
    session.modified = True


def get_deal_cart_cards():
    """Return active, unsold cards currently in the deal cart."""
    cart_ids = get_deal_cart_ids()

    if not cart_ids:
        return []

    cards = (
        Card.query
        .filter(Card.id.in_(cart_ids))
        .order_by(Card.player_name.asc())
        .all()
    )

    active_cards = [card for card in cards if card.status == "Active"]

    if len(active_cards) != len(cards):
        save_deal_cart_ids([card.id for card in active_cards])

    return active_cards


def get_deal_cart_quantity():
    """Return total card quantity represented by active deal-cart records."""
    return sum((card.quantity or 1) for card in get_deal_cart_cards())
