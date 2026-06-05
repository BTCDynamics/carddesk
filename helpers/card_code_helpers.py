from models import Card


def generate_card_code():
    last_card = Card.query.order_by(Card.id.desc()).first()

    if not last_card:
        return "CD-000001"

    next_number = last_card.id + 1

    return f"CD-{next_number:06d}"


