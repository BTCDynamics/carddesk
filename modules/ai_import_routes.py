import json
from datetime import datetime
from urllib.parse import quote

from flask import render_template, request, redirect, url_for, flash

from models import db, Card, CardImportStaging, IntakeBatch
from helpers.acquisition_helpers import (
    clean_value,
    acquisition_value,
    acquisition_date_value,
    purchase_date_value,
)
from helpers.storage_helpers import get_storage_locations
from helpers.psa_helpers import (
    clean_psa_cert_number,
    find_duplicate_by_cert_number,
)


def build_reference_search_query(staged_card):
    parts = [
        staged_card.year,
        staged_card.brand,
        staged_card.set_name,
        staged_card.player_name,
        f"#{staged_card.card_number}" if staged_card.card_number else None,
        staged_card.variation,
    ]

    return " ".join(str(part).strip() for part in parts if part).strip()


def build_reference_links(staged_card):
    query = build_reference_search_query(staged_card)
    encoded = quote(query, safe="")

    return {
        "query": query,
        "google_images": f"https://www.google.com/search?tbm=isch&q={encoded}",
        "ebay": f"https://www.ebay.com/sch/i.html?_nkw={encoded}",
        "comc": f"https://www.comc.com/Cards,sr,{encoded}",
        "sports_cards_pro": f"https://www.sportscardspro.com/search-products?q={encoded}",
    }


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


def apply_staged_import_form(staged_card, form_data, normalize_year):
    """Apply review form values to a staged card before validation/import."""
    staged_card.player_name = clean_value(form_data.get("player_name"))
    staged_card.sport = form_data.get("sport") or "Baseball"
    staged_card.year = normalize_year(form_data.get("year"))
    staged_card.brand = clean_value(form_data.get("brand"))
    staged_card.set_name = clean_value(form_data.get("set_name"))
    staged_card.card_number = clean_value(form_data.get("card_number"))
    staged_card.variation = clean_value(form_data.get("variation"))
    staged_card.is_rookie = True if form_data.get("is_rookie") else False
    staged_card.is_hof = True if form_data.get("is_hof") else False
    staged_card.card_type = form_data.get("card_type") or "Raw"
    staged_card.grading_company = clean_value(form_data.get("grading_company"))
    staged_card.actual_grade = clean_value(form_data.get("actual_grade"))
    staged_card.cert_number = clean_value(form_data.get("cert_number"))
    staged_card.grade_estimate = clean_value(form_data.get("grade_estimate"))
    staged_card.quantity = int(form_data.get("quantity") or 1)
    staged_card.purchase_price = form_data.get("purchase_price") or None
    staged_card.estimated_value = form_data.get("estimated_value") or None
    staged_card.asking_price = form_data.get("asking_price") or None
    staged_card.purchase_date = purchase_date_value(form_data)
    staged_card.acquisition_source = acquisition_value(form_data.get("acquisition_source"))
    staged_card.acquisition_date = acquisition_date_value(form_data)
    staged_card.acquisition_event = clean_value(form_data.get("acquisition_event"))
    staged_card.storage_location = clean_value(form_data.get("storage_location"))
    staged_card.collection_type = form_data.get("collection_type") or "Inventory"
    staged_card.status = form_data.get("status") or "Active"
    staged_card.notes = form_data.get("notes")


def validate_staged_card_for_import(staged_card):
    """Return missing required fields for AI import.

    AI recognition is trusted for card identity fields during fast intake.
    Cost stays required because it protects profit, ROI, and sales analytics.
    """
    missing_fields = []

    if staged_card.purchase_price is None:
        missing_fields.append("Cost")
    elif isinstance(staged_card.purchase_price, str) and not staged_card.purchase_price.strip():
        missing_fields.append("Cost")

    return missing_fields


def next_staged_review_card(current_staging_id):
    """Return the next non-imported/non-rejected staged card for fast intake."""
    return (
        CardImportStaging.query
        .filter(CardImportStaging.id != current_staging_id)
        .filter(CardImportStaging.ai_status.in_(["Needs Manual Review", "Pending Review"]))
        .order_by(CardImportStaging.created_at.desc(), CardImportStaging.id.desc())
        .first()
    )


def register_ai_import_routes(
    app,
    generate_card_code,
    save_uploaded_image_with_source,
    recognize_card_image,
    normalize_year,
    rename_image_for_inventory,
    delete_image_file,
    recognition_configured,
):
    @app.route("/ai-import", methods=["GET", "POST"])
    def ai_import_upload():
        """Upload one or more card images and stage card recognition results."""
        if request.method == "POST":
            uploaded_files = request.files.getlist("card_images")
            uploaded_files = [file for file in uploaded_files if file and file.filename]

            if not uploaded_files:
                flash("Choose at least one card image to scan.")
                return redirect(url_for("ai_import_upload"))

            staged_count = 0
            error_count = 0

            for uploaded_file in uploaded_files:
                image_filename, source_filename = save_uploaded_image_with_source(uploaded_file)

                if not image_filename:
                    error_count += 1
                    continue

                staged_card = CardImportStaging(
                    image_filename=image_filename,
                    source_filename=source_filename,
                    sport=request.form.get("default_sport") or "Baseball",
                    collection_type=request.form.get("collection_type") or "Inventory",
                    status=request.form.get("status") or "Active",
                    purchase_date=purchase_date_value(request.form),
                    acquisition_source=acquisition_value(request.form.get("acquisition_source")),
                    acquisition_date=acquisition_date_value(request.form),
                    acquisition_event=clean_value(request.form.get("acquisition_event")),
                    storage_location=clean_value(request.form.get("storage_location")),
                    quantity=1,
                    ai_status="Pending Review",
                )

                try:
                    recognition_provider, raw_response, extracted = recognize_card_image(image_filename)

                    staged_card.raw_response_json = json.dumps(raw_response, indent=2, sort_keys=True)
                    staged_card.player_name = clean_value(extracted.get("player_name"))
                    staged_card.year = extracted.get("year")
                    staged_card.sport = extracted.get("sport") or staged_card.sport
                    staged_card.brand = clean_value(extracted.get("brand"))
                    staged_card.set_name = clean_value(extracted.get("set_name"))
                    staged_card.card_number = clean_value(extracted.get("card_number"))
                    staged_card.variation = clean_value(extracted.get("variation"))
                    staged_card.is_rookie = True if extracted.get("is_rookie") else staged_card.is_rookie
                    staged_card.card_type = extracted.get("card_type") or "Raw"
                    staged_card.grading_company = clean_value(extracted.get("grading_company"))
                    staged_card.actual_grade = clean_value(extracted.get("actual_grade"))
                    staged_card.cert_number = clean_value(extracted.get("cert_number"))
                    staged_card.ai_confidence = extracted.get("ai_confidence")
                except Exception as error:
                    staged_card.ai_status = "Needs Manual Review"
                    staged_card.ai_error = str(error)
                    error_count += 1

                db.session.add(staged_card)
                staged_count += 1

            db.session.commit()

            if staged_count:
                flash(f"{staged_count} image(s) added to the AI review queue.")
            if error_count:
                flash(f"{error_count} image(s) need manual review because card recognition did not return usable data.")

            return redirect(url_for("ai_import_review"))

        pending_count = CardImportStaging.query.filter(CardImportStaging.ai_status.in_(["Pending Review", "Needs Manual Review"])).count()
        imported_count = CardImportStaging.query.filter(CardImportStaging.ai_status == "Imported").count()

        return render_template(
            "ai_import_upload.html",
            pending_count=pending_count,
            imported_count=imported_count,
            token_configured=recognition_configured(),
            active_intake_batch=active_intake_batch,
            all_storage_location_choices=get_storage_locations(),
        )

    @app.route("/ai-import/review")
    def ai_import_review():
        status_filter = request.args.get("status", "Pending Review")

        query = CardImportStaging.query

        if status_filter == "All":
            pass
        elif status_filter == "Needs Manual Review":
            query = query.filter(CardImportStaging.ai_status == "Needs Manual Review")
        elif status_filter == "Imported":
            query = query.filter(CardImportStaging.ai_status == "Imported")
        elif status_filter == "Rejected":
            query = query.filter(CardImportStaging.ai_status == "Rejected")
        else:
            status_filter = "Pending Review"
            query = query.filter(CardImportStaging.ai_status == "Pending Review")

        staged_cards = query.order_by(CardImportStaging.created_at.desc(), CardImportStaging.id.desc()).all()

        focus_id = request.args.get("focus", type=int)
        missing_fields = [
            field.strip()
            for field in request.args.get("missing", "").split(",")
            if field.strip()
        ]
        imported_success = request.args.get("imported") == "1"

        if focus_id:
            staged_cards = sorted(
                staged_cards,
                key=lambda card: 0 if card.id == focus_id else 1
            )

        duplicate_map = {card.id: find_probable_duplicate_from_staging(card) for card in staged_cards}
        duplicate_reason_map = {card.id: duplicate_reason_from_staging(card, duplicate_map.get(card.id)) for card in staged_cards}
        reference_links_map = {card.id: build_reference_links(card) for card in staged_cards}

        counts = {
            "pending": CardImportStaging.query.filter(CardImportStaging.ai_status == "Pending Review").count(),
            "manual": CardImportStaging.query.filter(CardImportStaging.ai_status == "Needs Manual Review").count(),
            "imported": CardImportStaging.query.filter(CardImportStaging.ai_status == "Imported").count(),
            "rejected": CardImportStaging.query.filter(CardImportStaging.ai_status == "Rejected").count(),
        }

        return render_template(
            "ai_import_review.html",
            staged_cards=staged_cards,
            duplicate_map=duplicate_map,
            duplicate_reason_map=duplicate_reason_map,
            reference_links_map=reference_links_map,
            status_filter=status_filter,
            counts=counts,
            focus_id=focus_id,
            missing_fields=missing_fields,
            imported_success=imported_success,
            all_storage_location_choices=get_storage_locations(),
        )

    @app.route("/ai-import/<int:staging_id>/update", methods=["POST"])
    def update_staged_import(staging_id):
        staged_card = CardImportStaging.query.get_or_404(staging_id)

        staged_card.player_name = clean_value(request.form.get("player_name"))
        staged_card.sport = request.form.get("sport") or "Baseball"
        staged_card.year = normalize_year(request.form.get("year"))
        staged_card.brand = clean_value(request.form.get("brand"))
        staged_card.set_name = clean_value(request.form.get("set_name"))
        staged_card.card_number = clean_value(request.form.get("card_number"))
        staged_card.variation = clean_value(request.form.get("variation"))
        staged_card.is_rookie = True if request.form.get("is_rookie") else False
        staged_card.is_hof = True if request.form.get("is_hof") else False
        staged_card.card_type = request.form.get("card_type") or "Raw"
        staged_card.grading_company = clean_value(request.form.get("grading_company"))
        staged_card.actual_grade = clean_value(request.form.get("actual_grade"))
        staged_card.cert_number = clean_value(request.form.get("cert_number"))
        staged_card.grade_estimate = clean_value(request.form.get("grade_estimate"))
        staged_card.quantity = int(request.form.get("quantity") or 1)
        staged_card.purchase_price = request.form.get("purchase_price") or None
        staged_card.estimated_value = request.form.get("estimated_value") or None
        staged_card.asking_price = request.form.get("asking_price") or None
        staged_card.purchase_date = purchase_date_value(request.form)
        staged_card.acquisition_source = acquisition_value(request.form.get("acquisition_source"))
        staged_card.acquisition_date = acquisition_date_value(request.form)
        staged_card.acquisition_event = clean_value(request.form.get("acquisition_event"))
        staged_card.storage_location = clean_value(request.form.get("storage_location"))
        staged_card.collection_type = request.form.get("collection_type") or "Inventory"
        staged_card.status = request.form.get("status") or "Active"
        staged_card.notes = request.form.get("notes")

        if staged_card.ai_status not in ["Imported", "Rejected"]:
            staged_card.ai_status = "Pending Review"

        db.session.commit()
        flash("AI import draft updated.")

        return redirect(url_for("ai_import_review", status=request.args.get("status", "Pending Review")))

    @app.route("/ai-import/<int:staging_id>/import", methods=["POST"])
    def import_staged_card(staging_id):
        staged_card = CardImportStaging.query.get_or_404(staging_id)

        if staged_card.ai_status == "Imported":
            flash("This staged card has already been imported.")
            return redirect(url_for("ai_import_review"))

        apply_staged_import_form(staged_card, request.form, normalize_year)

        missing_fields = validate_staged_card_for_import(staged_card)

        if missing_fields:
            staged_card.ai_status = "Needs Manual Review"
            db.session.commit()

            flash(
                "Please complete these required fields before importing: "
                + ", ".join(missing_fields)
            )

            return redirect(
                url_for(
                    "ai_import_review",
                    status=staged_card.ai_status,
                    focus=staged_card.id,
                    missing=",".join(missing_fields)
                )
            )

        duplicate_action = request.form.get("duplicate_action") or "create_new"
        probable_duplicate = find_probable_duplicate_from_staging(staged_card)
        next_card = next_staged_review_card(staged_card.id)

        if probable_duplicate and duplicate_action == "increase_quantity":
            old_quantity = probable_duplicate.quantity or 1
            probable_duplicate.quantity = old_quantity + (staged_card.quantity or 1)

            if staged_card.image_filename and not probable_duplicate.image_filename:
                probable_duplicate.image_filename = rename_image_for_inventory(
                    staged_card.image_filename,
                    staged_card
                )
                staged_card.image_filename = None

            if getattr(staged_card, "image_back_filename", None) and not getattr(probable_duplicate, "image_back_filename", None):
                probable_duplicate.image_back_filename = rename_image_for_inventory(
                    staged_card.image_back_filename,
                    staged_card
                )
                staged_card.image_back_filename = None

            staged_card.imported_card_id = probable_duplicate.id
            staged_card.ai_status = "Imported"
            staged_card.imported_at = datetime.utcnow()

            db.session.commit()

            if next_card:
                flash("Card imported successfully. Loading next card...")
                return redirect(
                    url_for(
                        "ai_import_review",
                        status=next_card.ai_status,
                        focus=next_card.id,
                        imported="1"
                    )
                )

            flash("Card imported successfully. Review queue is clear.")
            return redirect(url_for("ai_import_review", status="Pending Review", imported="1"))

        new_card = Card(
            card_code=generate_card_code(),
            sport=staged_card.sport or "Baseball",
            player_name=staged_card.player_name,
            year=staged_card.year,
            brand=staged_card.brand,
            set_name=staged_card.set_name,
            card_number=staged_card.card_number,
            variation=staged_card.variation,
            is_rookie=staged_card.is_rookie,
            is_hof=staged_card.is_hof,
            card_type=staged_card.card_type or "Raw",
            grading_company=staged_card.grading_company,
            actual_grade=staged_card.actual_grade,
            cert_number=staged_card.cert_number,
            grade_estimate=staged_card.grade_estimate,
            quantity=staged_card.quantity or 1,
            purchase_price=staged_card.purchase_price,
            estimated_value=staged_card.estimated_value,
            asking_price=staged_card.asking_price,
            purchase_date=staged_card.purchase_date,
            acquisition_source=staged_card.acquisition_source or "Existing Inventory",
            acquisition_date=staged_card.acquisition_date,
            acquisition_event=staged_card.acquisition_event,
            storage_location=staged_card.storage_location,
            collection_type=staged_card.collection_type or "Inventory",
            image_filename=rename_image_for_inventory(staged_card.image_filename, staged_card),
            image_back_filename=rename_image_for_inventory(getattr(staged_card, "image_back_filename", None), staged_card),
            notes=staged_card.notes,
            status=staged_card.status or "Active",
        )

        db.session.add(new_card)
        db.session.flush()

        staged_card.imported_card_id = new_card.id
        staged_card.ai_status = "Imported"
        staged_card.imported_at = datetime.utcnow()
        staged_card.image_filename = None
        staged_card.image_back_filename = None

        db.session.commit()

        if next_card:
            flash("Card imported successfully. Loading next card...")
            return redirect(
                url_for(
                    "ai_import_review",
                    status=next_card.ai_status,
                    focus=next_card.id,
                    imported="1"
                )
            )

        flash("Card imported successfully. Review queue is clear.")
        return redirect(url_for("ai_import_review", status="Pending Review", imported="1"))

    @app.route("/ai-import/<int:staging_id>/reject", methods=["POST"])
    def reject_staged_import(staging_id):
        staged_card = CardImportStaging.query.get_or_404(staging_id)
        staged_card.ai_status = "Rejected"
        db.session.commit()
        flash("AI import rejected.")
        return redirect(request.referrer or url_for("ai_import_review"))

    @app.route("/ai-import/<int:staging_id>/delete", methods=["POST"])
    def delete_staged_import(staging_id):
        staged_card = CardImportStaging.query.get_or_404(staging_id)
        delete_image_file(staged_card.image_filename)
        delete_image_file(getattr(staged_card, "image_back_filename", None))
        db.session.delete(staged_card)
        db.session.commit()
        flash("AI import draft deleted.")
        return redirect(request.referrer or url_for("ai_import_review"))
