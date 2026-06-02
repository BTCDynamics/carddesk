import os
import re
import json
import urllib.error
import urllib.request
from urllib.parse import quote

from flask import current_app

from models import db, Card, CardImportStaging


ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}

PSA_ACCESS_TOKEN = os.environ.get("PSA_ACCESS_TOKEN")
PSA_CERT_LOOKUP_ENDPOINT = os.environ.get(
    "PSA_CERT_LOOKUP_ENDPOINT",
    "https://api.psacard.com/publicapi/cert/GetByCertNumber"
)
PSA_CERT_IMAGES_ENDPOINT = os.environ.get(
    "PSA_CERT_IMAGES_ENDPOINT",
    "https://api.psacard.com/publicapi/cert/GetImagesByCertNumber"
)


def clean_value(value):
    if value:
        return value.strip()
    return None


def normalize_year(value):
    if value in (None, ""):
        return None

    text_value = str(value).strip()

    if not text_value:
        return None

    for token in text_value.replace("/", " ").replace("-", " ").split():
        if token.isdigit() and len(token) == 4:
            try:
                return int(token)
            except ValueError:
                return None

    if text_value.isdigit():
        try:
            return int(text_value)
        except ValueError:
            return None

    return None


def acquisition_value(value):
    value = clean_value(value)
    return value or "Existing Inventory"


def acquisition_date_value(form_data):
    source = acquisition_value(form_data.get("acquisition_source"))

    if source == "Existing Inventory":
        return None

    return form_data.get("acquisition_date") or None


def purchase_date_value(form_data):
    source = acquisition_value(form_data.get("acquisition_source"))

    if source == "Existing Inventory":
        return form_data.get("purchase_date") or None

    return form_data.get("purchase_date") or form_data.get("acquisition_date") or None


def clean_psa_cert_number(cert_number):
    """Return only the PSA cert-number characters a user might paste or type."""
    value = clean_value(cert_number)

    if not value:
        return None

    return re.sub(r"[^A-Za-z0-9]", "", value)


def psa_access_token():
    """Return a trimmed PSA access token from the environment."""
    token = os.environ.get("PSA_ACCESS_TOKEN") or PSA_ACCESS_TOKEN

    if not token:
        return None

    return token.strip()


def lookup_psa_cert(cert_number):
    """Look up one PSA certification number using PSA's public API."""
    cert_number = clean_psa_cert_number(cert_number)

    if not cert_number:
        raise RuntimeError("Missing PSA cert number.")

    token = psa_access_token()

    if not token:
        raise RuntimeError("Missing PSA_ACCESS_TOKEN environment variable.")

    endpoint = PSA_CERT_LOOKUP_ENDPOINT.rstrip("/")
    lookup_url = f"{endpoint}/{quote(cert_number, safe='')}"

    api_request = urllib.request.Request(
        lookup_url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "User-Agent": "CardDesk/1.0 (+https://carddesk.app)",
        },
        method="GET",
    )

    try:
        with urllib.request.urlopen(api_request, timeout=30) as response:
            response_body = response.read().decode("utf-8")
            return json.loads(response_body)
    except urllib.error.HTTPError as error:
        error_body = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"PSA HTTP {error.code}: {error_body}") from error
    except urllib.error.URLError as error:
        raise RuntimeError(f"PSA connection error: {error.reason}") from error


def lookup_psa_cert_images(cert_number):
    """Look up PSA certification front/back images using PSA's public API."""
    cert_number = clean_psa_cert_number(cert_number)

    if not cert_number:
        raise RuntimeError("Missing PSA cert number.")

    token = psa_access_token()

    if not token:
        raise RuntimeError("Missing PSA_ACCESS_TOKEN environment variable.")

    endpoint = PSA_CERT_IMAGES_ENDPOINT.rstrip("/")
    lookup_url = f"{endpoint}/{quote(cert_number, safe='')}"

    api_request = urllib.request.Request(
        lookup_url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "User-Agent": "CardDesk/1.0 (+https://carddesk.app)",
        },
        method="GET",
    )

    try:
        with urllib.request.urlopen(api_request, timeout=30) as response:
            response_body = response.read().decode("utf-8")
            return json.loads(response_body)
    except urllib.error.HTTPError as error:
        error_body = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"PSA Images HTTP {error.code}: {error_body}") from error
    except urllib.error.URLError as error:
        raise RuntimeError(f"PSA Images connection error: {error.reason}") from error


def title_case_psa_value(value):
    """Make PSA's all-caps values easier to read in CardDesk."""
    value = clean_value(value)

    if not value:
        return None

    return " ".join(
        word.capitalize() if not word.isupper() or len(word) > 3 else word
        for word in value.title().split()
    )


def split_psa_brand_set(brand_value):
    """Split PSA's Brand field into CardDesk Brand and Set Name values."""
    display_value = title_case_psa_value(brand_value)

    if not display_value:
        return None, None

    known_manufacturers = [
        "Topps",
        "Panini",
        "Bowman",
        "Upper Deck",
        "Fleer",
        "Donruss",
        "Leaf",
        "Score",
        "Skybox",
        "O-Pee-Chee",
    ]

    upper_value = display_value.upper()

    for manufacturer in known_manufacturers:
        if upper_value == manufacturer.upper() or upper_value.startswith(manufacturer.upper() + " "):
            return manufacturer, display_value

    first_word = display_value.split()[0] if display_value.split() else display_value

    return first_word, display_value


def sport_from_psa_category(category):
    category_text = (category or "").upper()

    if "BASEBALL" in category_text:
        return "Baseball"
    if "FOOTBALL" in category_text:
        return "Football"
    if "BASKETBALL" in category_text:
        return "Basketball"
    if "HOCKEY" in category_text:
        return "Hockey"
    if "SOCCER" in category_text:
        return "Soccer"
    if "GOLF" in category_text:
        return "Golf"
    if "RACING" in category_text:
        return "Racing"
    if "WRESTLING" in category_text:
        return "Wrestling"
    if "BOXING" in category_text:
        return "Boxing"

    return "Other"


def extract_psa_cert_payload(response_json):
    """Return the nested PSACert object from PSA's cert response."""
    payload = response_json or {}
    psa_cert = payload.get("PSACert") or payload.get("psaCert") or payload

    if not isinstance(psa_cert, dict):
        raise RuntimeError("PSA response did not include a usable cert payload.")

    return psa_cert


def normalize_psa_images_response(images_response):
    """Return PSA image records as a list regardless of response wrapper shape."""
    images = images_response or []

    if isinstance(images, dict):
        images = images.get("Images") or images.get("images") or images.get("data") or []

    if not isinstance(images, list):
        return []

    return [image for image in images if isinstance(image, dict)]


def get_psa_image_url(image_record):
    """Return a URL from one PSA image record."""
    if not isinstance(image_record, dict):
        return None

    return clean_value(
        image_record.get("ImageURL")
        or image_record.get("ImageUrl")
        or image_record.get("imageUrl")
        or image_record.get("url")
    )


def select_psa_image_url(images_response, front=True):
    """Return PSA's front or back image URL when available."""
    for image in normalize_psa_images_response(images_response):
        image_url = get_psa_image_url(image)

        if not image_url:
            continue

        if bool(image.get("IsFrontImage")) == front:
            return image_url

    return None


def select_psa_front_image_url(images_response):
    """Return PSA's front image URL when available, otherwise any image URL."""
    front_url = select_psa_image_url(images_response, front=True)

    if front_url:
        return front_url

    for image in normalize_psa_images_response(images_response):
        image_url = get_psa_image_url(image)
        if image_url:
            return image_url

    return None


def select_psa_back_image_url(images_response):
    """Return PSA's back image URL when available."""
    return select_psa_image_url(images_response, front=False)


def unique_upload_filename(base_name, extension, current_filename=None):
    """Return a filename that does not collide inside the upload folder."""
    candidate = f"{base_name}.{extension}"
    candidate_path = os.path.join(current_app.config["UPLOAD_FOLDER"], candidate)

    if current_filename and candidate == current_filename:
        return candidate

    counter = 2
    while os.path.exists(candidate_path):
        candidate = f"{base_name}_{counter}.{extension}"
        candidate_path = os.path.join(current_app.config["UPLOAD_FOLDER"], candidate)
        counter += 1

    return candidate


def download_psa_image_to_uploads(image_url, cert_number, side="front"):
    """Download a PSA cert image into CardDesk's upload folder and return filename."""
    image_url = clean_value(image_url)
    cert_number = clean_psa_cert_number(cert_number)
    side = "back" if str(side).lower() == "back" else "front"

    if not image_url or not cert_number:
        return None

    os.makedirs(current_app.config["UPLOAD_FOLDER"], exist_ok=True)

    url_without_query = image_url.split("?", 1)[0]
    extension = url_without_query.rsplit(".", 1)[-1].lower() if "." in url_without_query else "jpg"

    if extension not in ALLOWED_IMAGE_EXTENSIONS:
        extension = "jpg"

    filename = unique_upload_filename(f"psa_{cert_number}_{side}", extension)
    destination_path = os.path.join(current_app.config["UPLOAD_FOLDER"], filename)

    image_request = urllib.request.Request(
        image_url,
        headers={
            "User-Agent": "CardDesk/1.0 (+https://carddesk.app)",
            "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
        },
        method="GET",
    )

    try:
        with urllib.request.urlopen(image_request, timeout=30) as response:
            image_bytes = response.read()

        if not image_bytes:
            return None

        with open(destination_path, "wb") as image_file:
            image_file.write(image_bytes)

        return filename
    except Exception:
        return None


def build_psa_notes(psa_cert, images_response=None, image_filename=None, image_back_filename=None):
    """Build human-readable notes from PSA fields worth preserving."""
    note_parts = ["Imported from PSA Cert Lookup."]

    if psa_cert.get("TotalPopulation") not in (None, ""):
        note_parts.append(f"PSA total population: {psa_cert.get('TotalPopulation')}.")
    if psa_cert.get("PopulationHigher") not in (None, ""):
        note_parts.append(f"PSA population higher: {psa_cert.get('PopulationHigher')}.")
    if psa_cert.get("SpecID") not in (None, ""):
        note_parts.append(f"PSA Spec ID: {psa_cert.get('SpecID')}.")
    if image_filename:
        note_parts.append("Official PSA front image saved.")
    if image_back_filename:
        note_parts.append("Official PSA back image saved.")

    return "\n".join(note_parts)


def stage_psa_cert_lookup(cert_number, form_data):
    """Create a CardImportStaging row from a PSA cert lookup."""
    cert_number = clean_psa_cert_number(cert_number)

    if not cert_number:
        raise RuntimeError("Enter a PSA cert number.")

    cert_response = lookup_psa_cert(cert_number)
    psa_cert = extract_psa_cert_payload(cert_response)

    images_response = []
    image_filename = None
    image_back_filename = None

    try:
        images_response = lookup_psa_cert_images(cert_number)
        front_image_url = select_psa_front_image_url(images_response)
        back_image_url = select_psa_back_image_url(images_response)
        image_filename = download_psa_image_to_uploads(front_image_url, cert_number, side="front")
        image_back_filename = download_psa_image_to_uploads(back_image_url, cert_number, side="back")
    except Exception:
        images_response = []

    brand, set_name = split_psa_brand_set(psa_cert.get("Brand"))
    grade_value = clean_value(psa_cert.get("CardGrade") or psa_cert.get("GradeDescription"))
    subject = title_case_psa_value(psa_cert.get("Subject"))
    variety = title_case_psa_value(psa_cert.get("Variety"))

    raw_response = {
        "source": "PSA Cert Lookup",
        "cert_response": cert_response,
        "images_response": images_response,
        "stored_front_image_filename": image_filename,
        "stored_back_image_filename": image_back_filename,
    }

    staged_card = CardImportStaging(
        image_filename=image_filename,
        image_back_filename=image_back_filename,
        source_filename=f"PSA Cert {cert_number}",
        player_name=subject,
        year=normalize_year(psa_cert.get("Year")),
        sport=sport_from_psa_category(psa_cert.get("Category")),
        brand=brand,
        set_name=set_name,
        card_number=clean_value(psa_cert.get("CardNumber")),
        variation=variety,
        card_type="Graded",
        grading_company="PSA",
        actual_grade=grade_value,
        cert_number=clean_value(psa_cert.get("CertNumber") or cert_number),
        quantity=1,
        collection_type=form_data.get("collection_type") or "Inventory",
        status=form_data.get("status") or "Active",
        purchase_date=purchase_date_value(form_data),
        acquisition_source=acquisition_value(form_data.get("acquisition_source")),
        acquisition_date=acquisition_date_value(form_data),
        acquisition_event=clean_value(form_data.get("acquisition_event")),
        storage_location=clean_value(form_data.get("storage_location")),
        ai_confidence=100,
        ai_status="Pending Review",
        raw_response_json=json.dumps(raw_response, indent=2, sort_keys=True),
        notes=build_psa_notes(psa_cert, images_response, image_filename, image_back_filename),
    )

    db.session.add(staged_card)
    db.session.commit()

    return staged_card


def find_duplicate_by_cert_number(cert_number):
    """Return an existing inventory card with the same grading cert number."""
    clean_cert = clean_psa_cert_number(cert_number)

    if not clean_cert:
        return None

    exact_match = Card.query.filter(Card.cert_number == clean_cert).first()
    if exact_match:
        return exact_match

    candidates = Card.query.filter(Card.cert_number.isnot(None)).all()

    for card in candidates:
        if clean_psa_cert_number(card.cert_number) == clean_cert:
            return card

    return None
