from flask_sqlalchemy import SQLAlchemy


db = SQLAlchemy()


class Card(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    card_code = db.Column(db.String(50), unique=True, nullable=False)

    player_name = db.Column(db.String(100), nullable=False)

    year = db.Column(db.Integer)

    sport = db.Column(db.String(50))

    brand = db.Column(db.String(100))

    set_name = db.Column(db.String(100))

    card_number = db.Column(db.String(50))

    variation = db.Column(db.String(100))

    is_hof = db.Column(db.Boolean, default=False)

    is_rookie = db.Column(db.Boolean, default=False)

    card_type = db.Column(db.String(20), default="Raw")

    grading_company = db.Column(db.String(50))

    actual_grade = db.Column(db.String(20))

    cert_number = db.Column(db.String(100))

    grade_estimate = db.Column(db.String(20))

    quantity = db.Column(db.Integer, default=1)

    purchase_price = db.Column(db.Float)

    estimated_value = db.Column(db.Float)

    asking_price = db.Column(db.Float)

    sold_price = db.Column(db.Float)

    sold_date = db.Column(db.String(20))

    sales_platform = db.Column(db.String(100))

    purchase_date = db.Column(db.String(20))

    # Acquisition tracking: separates cards already owned from newly acquired inventory
    acquisition_source = db.Column(db.String(50), default="Existing Inventory")

    acquisition_date = db.Column(db.String(20))

    acquisition_event = db.Column(db.String(150))

    intake_batch_id = db.Column(db.Integer, db.ForeignKey("intake_batch.id"))

    intake_batch = db.relationship(
        "IntakeBatch",
        foreign_keys=[intake_batch_id]
    )

    storage_location = db.Column(db.String(200))

    image_filename = db.Column(db.String(200))

    image_back_filename = db.Column(db.String(200))

    notes = db.Column(db.Text)

    status = db.Column(db.String(50), default="Holding")

    collection_type = db.Column(db.String(50), default="Inventory")

    # Deal / transaction tracking
    deal_id = db.Column(db.String(100))

    customer_name = db.Column(db.String(150))

    payment_type = db.Column(db.String(50))

    deal_discount_percent = db.Column(db.Float)

    trade_credit = db.Column(db.Float)

    cash_received = db.Column(db.Float)

    deal_notes = db.Column(db.Text)

    fulfillment_status = db.Column(db.String(50), default="In Storage")

    # Shipping / fulfillment details
    shipping_carrier = db.Column(db.String(50))

    tracking_number = db.Column(db.String(100))

    shipping_cost = db.Column(db.Float)

    shipped_date = db.Column(db.String(20))

    shipping_notes = db.Column(db.Text)

    created_at = db.Column(db.DateTime, server_default=db.func.now())



class IntakeBatch(db.Model):
    """Optional intake batch defaults for repeated card entry/capture workflows."""

    id = db.Column(db.Integer, primary_key=True)

    batch_name = db.Column(db.String(150), nullable=False)
    status = db.Column(db.String(20), default="Active")
    notes = db.Column(db.Text)

    default_sport = db.Column(db.String(50), default="Baseball")
    default_card_type = db.Column(db.String(20), default="Raw")
    default_collection_type = db.Column(db.String(50), default="Inventory")
    default_status = db.Column(db.String(50), default="Active")
    default_storage_location = db.Column(db.String(200))
    default_acquisition_source = db.Column(db.String(50), default="Existing Inventory")
    default_acquisition_date = db.Column(db.String(20))
    default_acquisition_event = db.Column(db.String(150))

    created_at = db.Column(db.DateTime, server_default=db.func.now())
    closed_at = db.Column(db.DateTime)


class DealerEvent(db.Model):
    """Card show / buying-session tracker for dealer events."""

    id = db.Column(db.Integer, primary_key=True)

    event_name = db.Column(db.String(150), nullable=False)
    location = db.Column(db.String(150))

    start_date = db.Column(db.String(20))
    end_date = db.Column(db.String(20))

    status = db.Column(db.String(20), default="Planned")
    notes = db.Column(db.Text)

    # Event expense tracking. Table fee is prominent because it is the
    # most common fixed card-show cost; the rest are optional for users
    # who want more detailed profitability tracking.
    table_fee = db.Column(db.Float, default=0)
    travel_expense = db.Column(db.Float, default=0)
    lodging_expense = db.Column(db.Float, default=0)
    food_expense = db.Column(db.Float, default=0)
    other_expense = db.Column(db.Float, default=0)
    expense_notes = db.Column(db.Text)

    # Storage locations selected for this event/show prep loadout.
    selected_show_locations = db.Column(db.Text)

    created_at = db.Column(db.DateTime, server_default=db.func.now())
    closed_at = db.Column(db.DateTime)


class CardImportStaging(db.Model):
    """Temporary holding table for AI-recognized cards before they become inventory."""

    id = db.Column(db.Integer, primary_key=True)

    image_filename = db.Column(db.String(200))
    image_back_filename = db.Column(db.String(200))
    source_filename = db.Column(db.String(255))

    player_name = db.Column(db.String(100))
    year = db.Column(db.Integer)
    sport = db.Column(db.String(50), default="Baseball")
    brand = db.Column(db.String(100))
    set_name = db.Column(db.String(100))
    card_number = db.Column(db.String(50))
    variation = db.Column(db.String(100))

    is_hof = db.Column(db.Boolean, default=False)
    is_rookie = db.Column(db.Boolean, default=False)

    card_type = db.Column(db.String(20), default="Raw")
    grading_company = db.Column(db.String(50))
    actual_grade = db.Column(db.String(20))
    cert_number = db.Column(db.String(100))
    grade_estimate = db.Column(db.String(20))

    quantity = db.Column(db.Integer, default=1)
    purchase_price = db.Column(db.Float)
    estimated_value = db.Column(db.Float)
    asking_price = db.Column(db.Float)
    purchase_date = db.Column(db.String(20))
    acquisition_source = db.Column(db.String(50), default="Existing Inventory")
    acquisition_date = db.Column(db.String(20))
    acquisition_event = db.Column(db.String(150))
    intake_batch_id = db.Column(db.Integer, db.ForeignKey("intake_batch.id"))
    storage_location = db.Column(db.String(200))
    collection_type = db.Column(db.String(50), default="Inventory")
    status = db.Column(db.String(50), default="Active")
    notes = db.Column(db.Text)

    ai_confidence = db.Column(db.Float)
    ai_status = db.Column(db.String(50), default="Pending Review")
    ai_error = db.Column(db.Text)
    raw_response_json = db.Column(db.Text)

    imported_card_id = db.Column(db.Integer, db.ForeignKey("card.id"))
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    imported_at = db.Column(db.DateTime)

class CompRefreshQueue(db.Model):
    """Staging table for manual comp refresh review before updating inventory values."""

    id = db.Column(db.Integer, primary_key=True)

    card_id = db.Column(db.Integer, db.ForeignKey("card.id"), nullable=False)

    card = db.relationship("Card", backref="comp_refresh_items")

    search_query = db.Column(db.String(300))

    old_estimated_value = db.Column(db.Float)
    proposed_estimated_value = db.Column(db.Float)

    comp_low = db.Column(db.Float)
    comp_high = db.Column(db.Float)
    comp_count = db.Column(db.Integer, default=0)

    confidence = db.Column(db.String(20), default="Needs Source")
    source = db.Column(db.String(50), default="Manual / Test")

    status = db.Column(db.String(20), default="Pending")

    notes = db.Column(db.Text)


    created_at = db.Column(db.DateTime, server_default=db.func.now())
    applied_at = db.Column(db.DateTime)

