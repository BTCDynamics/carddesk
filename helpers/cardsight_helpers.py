import json
import os
import urllib.error
import urllib.request
from uuid import uuid4


CARDSIGHT_DEFAULT_IDENTIFY_ENDPOINT = "https://api.cardsight.ai/v1/identify/card"


def cardsight_api_key():
    """Return the configured CardSight API key, if present."""
    return os.environ.get("CARDSIGHT_API_KEY")


def cardsight_identify_endpoint():
    """Return the CardSight identify endpoint from environment or default."""
    return os.environ.get(
        "CARDSIGHT_IDENTIFY_ENDPOINT",
        CARDSIGHT_DEFAULT_IDENTIFY_ENDPOINT,
    )


def clean_value(value):
    """Normalize optional text values returned by CardSight."""
    if value in (None, ""):
        return None

    cleaned = str(value).strip()
    return cleaned or None


def normalize_year(value):
    """Extract a 4-digit year from a provider value."""
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


def confidence_to_score(value):
    """Convert CardSight confidence labels into a numeric 0-100 score."""
    if value in (None, ""):
        return None

    try:
        number = float(value)
        if number <= 1:
            number *= 100
        return number
    except (TypeError, ValueError):
        pass

    normalized = str(value).strip().lower()

    confidence_map = {
        "very high": 98,
        "high": 95,
        "medium": 70,
        "moderate": 70,
        "low": 40,
        "very low": 20,
    }

    return confidence_map.get(normalized)


def normalize_card_attributes(attributes):
    """Return a clean list of CardSight card attributes."""
    if not attributes:
        return []

    if isinstance(attributes, list):
        return [
            str(attribute).strip()
            for attribute in attributes
            if str(attribute).strip()
        ]

    if isinstance(attributes, str):
        return [
            attribute.strip()
            for attribute in attributes.replace(";", ",").split(",")
            if attribute.strip()
        ]

    return []


def extract_card_data_from_cardsight(response_json):
    """Parse CardSight response JSON into CardDesk staging fields.

    Expected CardSight shape:
    {
      "success": true,
      "detections": [
        {
          "confidence": "High",
          "card": {
            "year": "1989",
            "manufacturer": "Topps",
            "releaseName": "Topps",
            "setName": "Base Set",
            "name": "Randy Johnson",
            "number": "647",
            "attributes": ["RC"]
          }
        }
      ]
    }
    """
    payload = response_json or {}
    detections = payload.get("detections") or []

    if not detections:
        raise RuntimeError("CardSight returned no card detections.")

    detection = detections[0] or {}
    card = detection.get("card") or {}

    attributes = normalize_card_attributes(card.get("attributes"))
    attributes_upper = {attribute.upper() for attribute in attributes}

    release_name = clean_value(card.get("releaseName"))
    set_name_value = clean_value(card.get("setName"))

    if release_name and set_name_value:
        if release_name.lower() == set_name_value.lower():
            set_name = release_name
        else:
            set_name = f"{release_name} {set_name_value}"
    else:
        set_name = release_name or set_name_value

    return {
        "player_name": clean_value(card.get("name")),
        "year": normalize_year(card.get("year")),
        "sport": None,
        "brand": clean_value(card.get("manufacturer")),
        "set_name": set_name,
        "card_number": clean_value(card.get("number")),
        "variation": ", ".join(attributes) if attributes else None,
        "is_rookie": "RC" in attributes_upper or "ROOKIE" in attributes_upper,
        "grading_company": None,
        "actual_grade": None,
        "cert_number": None,
        "card_type": "Raw",
        "ai_confidence": confidence_to_score(detection.get("confidence")),
    }


def call_cardsight_for_image(image_filename, upload_folder):
    """Send one saved image to CardSight and return the raw JSON response."""
    api_key = cardsight_api_key()

    if not api_key:
        raise RuntimeError("Missing CARDSIGHT_API_KEY environment variable.")

    image_path = os.path.join(upload_folder, image_filename)

    if not os.path.exists(image_path):
        raise RuntimeError(f"Image file not found: {image_filename}")

    extension = image_filename.rsplit(".", 1)[-1].lower() if "." in image_filename else "jpg"
    content_type_by_extension = {
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "png": "image/png",
        "gif": "image/gif",
        "webp": "image/webp",
    }
    image_content_type = content_type_by_extension.get(extension, "application/octet-stream")
    boundary = f"----CardDeskBoundary{uuid4().hex}"

    with open(image_path, "rb") as image_file:
        image_bytes = image_file.read()

    body = b"".join([
        f"--{boundary}\r\n".encode("utf-8"),
        f'Content-Disposition: form-data; name="image"; filename="{image_filename}"\r\n'.encode("utf-8"),
        f"Content-Type: {image_content_type}\r\n\r\n".encode("utf-8"),
        image_bytes,
        b"\r\n",
        f"--{boundary}--\r\n".encode("utf-8"),
    ])

    api_request = urllib.request.Request(
        cardsight_identify_endpoint(),
        data=body,
        headers={
            "X-API-Key": api_key,
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "User-Agent": "CardDesk/1.0 (+https://carddesk.app)",
            "Accept": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(api_request, timeout=45) as response:
            response_body = response.read().decode("utf-8")
            return json.loads(response_body)
    except urllib.error.HTTPError as error:
        error_body = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"CardSight HTTP {error.code}: {error_body}") from error
    except urllib.error.URLError as error:
        raise RuntimeError(f"CardSight connection error: {error.reason}") from error
