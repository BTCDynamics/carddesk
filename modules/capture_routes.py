import json

from flask import render_template, request, url_for

from models import db, CardImportStaging
from helpers.acquisition_helpers import (
    clean_value,
    acquisition_value,
    acquisition_date_value,
    purchase_date_value,
)


def register_capture_routes(app, save_uploaded_image_with_source, recognize_card_image):
    @app.route("/mobile-capture")
    def mobile_capture():
        """Use a phone browser as a CardDesk camera capture station."""
        return render_template("mobile_capture.html")


    @app.route("/mobile-capture/upload", methods=["POST"])
    def mobile_capture_upload():
        """Receive a captured phone image, save it, and send it into the AI import review queue."""
        uploaded_file = request.files.get("card_image")

        if not uploaded_file or not uploaded_file.filename:
            return {"ok": False, "error": "No image received."}, 400

        image_filename, source_filename = save_uploaded_image_with_source(uploaded_file)

        if not image_filename:
            return {"ok": False, "error": "Image could not be saved."}, 400

        staged_card = CardImportStaging(
            image_filename=image_filename,
            source_filename=source_filename or uploaded_file.filename,
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
            notes="Captured from Mobile Capture.",
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

        db.session.add(staged_card)
        db.session.commit()

        return {
            "ok": True,
            "filename": image_filename,
            "staging_id": staged_card.id,
            "ai_status": staged_card.ai_status,
            "review_url": url_for("ai_import_review"),
            "message": "Image saved and added to the AI review queue."
        }
