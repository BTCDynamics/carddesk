from models import Card


def generate_card_code():
    last_card = Card.query.order_by(Card.id.desc()).first()

    if not last_card:
        return "CW-000001"

    next_number = last_card.id + 1

    return f"CW-{next_number:06d}"


