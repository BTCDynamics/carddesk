from models import Card


def generate_card_code():
    """Generate the next CardDesk inventory code.

    Uses the highest existing CW/CD card-code number instead of database ID,
    so numbering stays stable even if cards are deleted or database IDs jump.

    Existing CW codes are respected for numbering, but all new codes use CD.
    """
    highest_number = 0

    for card in Card.query.all():
        card_code = (card.card_code or "").strip().upper()

        if not card_code:
            continue

        if card_code.startswith("CD-"):
            number_part = card_code.replace("CD-", "", 1)
        elif card_code.startswith("CW-"):
            number_part = card_code.replace("CW-", "", 1)
        else:
            continue

        try:
            number = int(number_part)
        except ValueError:
            continue

        highest_number = max(highest_number, number)

    next_number = highest_number + 1

    return f"CD-{next_number:06d}"
