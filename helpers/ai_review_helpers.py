from models import db, Card
from helpers.acquisition_helpers import clean_value
from helpers.psa_helpers import clean_psa_cert_number, find_duplicate_by_cert_number


def find_probable_duplicate_from_staging(staged_card):
    """Find likely duplicate inventory.

    Graded cards with cert numbers are checked by cert first because a grading
    cert number is stronger than player/year/card-number matching.
    """
    cert_duplicate = find_duplicate_by_cert_number(getattr(staged_card, "cert_number", None))

    if cert_duplicate:
        return cert_duplicate

    if not staged_card.player_name:
        return None

    query = Card.query.filter(Card.player_name.ilike(staged_card.player_name))

    if staged_card.sport:
        query = query.filter(Card.sport == staged_card.sport)
    if staged_card.year:
        query = query.filter(Card.year == staged_card.year)
    if staged_card.brand:
        query = query.filter(Card.brand.ilike(staged_card.brand))
    if staged_card.card_number:
        query = query.filter(Card.card_number.ilike(staged_card.card_number))

    if staged_card.variation:
        query = query.filter(Card.variation.ilike(staged_card.variation))
    else:
        query = query.filter(db.or_(Card.variation.is_(None), Card.variation == ""))

    return query.first()


def duplicate_reason_from_staging(staged_card, duplicate):
    """Return a user-friendly reason for a duplicate match."""
    if not staged_card or not duplicate:
        return None

    staged_cert = clean_psa_cert_number(getattr(staged_card, "cert_number", None))
    duplicate_cert = clean_psa_cert_number(getattr(duplicate, "cert_number", None))

    if staged_cert and duplicate_cert and staged_cert == duplicate_cert:
        return f"Cert #{getattr(staged_card, 'cert_number', None)} already exists in inventory."

    return "Card identity looks similar to an existing inventory record."



