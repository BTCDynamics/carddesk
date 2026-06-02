from urllib.parse import quote

from flask import render_template, request, redirect, url_for, flash

from models import CardImportStaging
from helpers.acquisition_helpers import clean_value
from helpers.psa_helpers import (
    clean_psa_cert_number,
    psa_access_token,
    stage_psa_cert_lookup,
)


def register_psa_routes(app):
    @app.route("/psa-lookup", methods=["GET", "POST"])
    def psa_lookup():
        """Look up a PSA cert number, save the official PSA image, and stage it for review."""
        if request.method == "POST":
            cert_number = clean_psa_cert_number(request.form.get("cert_number"))

            if not cert_number:
                flash("Enter a PSA cert number.")
                return redirect(url_for("psa_lookup"))

            try:
                staged_card = stage_psa_cert_lookup(cert_number, request.form)
                flash(f"PSA cert {cert_number} staged for review.")
                return redirect(
                    url_for(
                        "ai_import_review",
                        status="Pending Review",
                        focus=staged_card.id
                    )
                )
            except Exception as error:
                flash(f"PSA lookup failed: {error}")
                return redirect(url_for("psa_lookup"))

        pending_count = CardImportStaging.query.filter(
            CardImportStaging.ai_status.in_(["Pending Review", "Needs Manual Review"])
        ).count()

        psa_mobile_scan_url = url_for("psa_mobile_scan", _external=True)
        psa_mobile_scan_qr_url = (
            "https://api.qrserver.com/v1/create-qr-code/"
            f"?size=220x220&data={quote(psa_mobile_scan_url, safe='')}"
        )

        return render_template(
            "psa_lookup.html",
            token_configured=bool(psa_access_token()),
            pending_count=pending_count,
            psa_mobile_scan_url=psa_mobile_scan_url,
            psa_mobile_scan_qr_url=psa_mobile_scan_qr_url,
        )


    @app.route("/psa-mobile-scan", methods=["GET", "POST"])
    def psa_mobile_scan():
        """Mobile-first PSA barcode scanner that stages a PSA cert for review."""
        scanned_cert = clean_psa_cert_number(request.form.get("cert_number")) if request.method == "POST" else ""
        staged_success = False

        if request.method == "POST":
            if not scanned_cert:
                flash("Scan or enter a PSA cert number.")
                return redirect(url_for("psa_mobile_scan"))

            try:
                staged_card = stage_psa_cert_lookup(scanned_cert, request.form)
                staged_success = True
                scanned_cert = clean_value(staged_card.cert_number) or scanned_cert
            except Exception as error:
                flash(f"PSA lookup failed: {error}")
                return redirect(url_for("psa_mobile_scan"))

        pending_count = CardImportStaging.query.filter(
            CardImportStaging.ai_status.in_(["Pending Review", "Needs Manual Review"])
        ).count()

        return render_template(
            "psa_mobile_scan.html",
            token_configured=bool(psa_access_token()),
            pending_count=pending_count,
            scanned_cert=scanned_cert or "",
            staged_success=staged_success,
        )
