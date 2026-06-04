from datetime import date, datetime


def clean_value(value):
    if value:
        return value.strip()
    return None


ACQUISITION_SOURCE_OPTIONS = [
    "Existing Inventory",
    "Cash Purchase",
    "Trade-In",
    "Bulk Collection",
    "Pack Pull",
    "Personal Collection",
    "Other",
]

ACQUISITION_DASHBOARD_SOURCES = {
    "Cash Purchase",
    "Trade-In",
    "Bulk Collection",
    "Pack Pull",
    "Other",
}


def acquisition_value(value):
    value = clean_value(value)
    return value or "Existing Inventory"


def acquisition_date_value(form_data):
    """Return an acquisition date only for true acquisition sources.

    Existing Inventory means the card was already owned before it was entered
    into CardDesk, so it should not appear in dashboard acquisition counts.
    """
    source = acquisition_value(form_data.get("acquisition_source"))

    if source == "Existing Inventory":
        return None

    return form_data.get("acquisition_date") or None


def purchase_date_value(form_data):
    """Keep purchase_date for compatibility without treating entry date as acquisition date."""
    source = acquisition_value(form_data.get("acquisition_source"))

    if source == "Existing Inventory":
        return form_data.get("purchase_date") or None

    return form_data.get("purchase_date") or form_data.get("acquisition_date") or None


def is_dashboard_acquisition(card):
    return getattr(card, "acquisition_source", None) in ACQUISITION_DASHBOARD_SOURCES


def parse_card_date(value):
    """Convert saved card date strings into a date object for reliable range filtering."""
    if not value:
        return None

    value = str(value).strip()

    for date_format in ("%Y-%m-%d", "%m/%d/%Y", "%-m/%-d/%Y"):
        try:
            return datetime.strptime(value, date_format).date()
        except ValueError:
            continue

    # Windows does not support %-m / %-d, so try a manual fallback.
    try:
        month, day, year = value.split("/")
        return date(int(year), int(month), int(day))
    except (ValueError, TypeError):
        return None
