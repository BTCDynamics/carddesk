import base64
import json
import os
import urllib.error
import urllib.request

from flask import current_app

from helpers.cardsight_helpers import (
    cardsight_api_key,
    call_cardsight_for_image,
    extract_card_data_from_cardsight,
)


XIMILAR_API_TOKEN = os.environ.get("XIMILAR_API_TOKEN") or os.environ.get("XIMILAR_API_KEY")
XIMILAR_SPORT_CARD_ENDPOINT = os.environ.get(
    "XIMILAR_SPORT_CARD_ENDPOINT",
    "https://api.ximilar.com/collectibles/v2/sport_id"
)


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


def recursive_values_by_key(data, wanted_keys):
    """Return values whose key name loosely matches one of wanted_keys anywhere in nested JSON."""
    matches = []
    wanted = {key.lower().replace("_", "").replace(" ", "") for key in wanted_keys}

    def walk(node):
        if isinstance(node, dict):
            for key, value in node.items():
                normalized_key = str(key).lower().replace("_", "").replace(" ", "")
                if normalized_key in wanted and value not in (None, "", [], {}):
                    matches.append(value)
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(data)
    return matches


def first_text_value(data, keys):
    for value in recursive_values_by_key(data, keys):
        if isinstance(value, dict):
            for nested_key in ("name", "value", "text", "label"):
                if value.get(nested_key):
                    return str(value.get(nested_key)).strip()
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    for nested_key in ("name", "value", "text", "label"):
                        if item.get(nested_key):
                            return str(item.get(nested_key)).strip()
                elif item not in (None, ""):
                    return str(item).strip()
        else:
            return str(value).strip()
    return None


def best_confidence(data):
    candidates = []
    for value in recursive_values_by_key(data, ["confidence", "probability", "score"]):
        try:
            number = float(value)
            if number <= 1:
                number *= 100
            candidates.append(number)
        except (TypeError, ValueError):
            continue
    return max(candidates) if candidates else None


def infer_card_type(grading_company, actual_grade, cert_number):
    if grading_company or actual_grade or cert_number:
        return "Graded"
    return "Raw"


def extract_card_data_from_ximilar(response_json):
    """Best-effort parser for Ximilar's nested response formats."""
    payload = response_json or {}

    player_name = first_text_value(payload, [
        "player", "player_name", "name", "subject", "person", "athlete"
    ])
    year = normalize_year(first_text_value(payload, ["year", "season", "date", "released"]))
    brand = first_text_value(payload, ["brand", "manufacturer", "company", "producer"])
    set_name = first_text_value(payload, ["set", "set_name", "series", "product", "subset"])
    card_number = first_text_value(payload, ["card_number", "card number", "number", "card no", "card_no"])
    variation = first_text_value(payload, ["variation", "parallel", "refractor", "insert", "features"])
    sport = first_text_value(payload, ["sport", "category", "league"]) or "Baseball"
    grading_company = first_text_value(payload, ["grading_company", "grader", "grading", "slab_company"])
    actual_grade = first_text_value(payload, ["actual_grade", "grade", "rating"])
    cert_number = first_text_value(payload, ["cert_number", "certificate", "cert", "serial", "certification_number"])

    # Avoid using the overall object name as player when it looks like a full card title.
    if player_name and any(piece in player_name.lower() for piece in ["topps", "panini", "upper deck", "fleer", "donruss"]):
        # Keep it as notes/context instead of forcing it into player.
        player_name = first_text_value(payload, ["player_name", "athlete", "subject", "person"]) or player_name

    return {
        "player_name": player_name,
        "year": year,
        "sport": sport,
        "brand": brand,
        "set_name": set_name,
        "card_number": card_number,
        "variation": variation,
        "grading_company": grading_company,
        "actual_grade": actual_grade,
        "cert_number": cert_number,
        "card_type": infer_card_type(grading_company, actual_grade, cert_number),
        "ai_confidence": best_confidence(payload),
    }


def call_ximilar_for_image(image_filename):
    """Send one saved image to Ximilar and return the raw JSON response."""
    if not XIMILAR_API_TOKEN:
        raise RuntimeError("Missing XIMILAR_API_TOKEN environment variable.")

    image_path = os.path.join(current_app.config["UPLOAD_FOLDER"], image_filename)

    with open(image_path, "rb") as image_file:
        encoded_image = base64.b64encode(image_file.read()).decode("utf-8")

    payload = {
        "records": [
            {
                "_base64": encoded_image
            }
        ]
    }

    request_data = json.dumps(payload).encode("utf-8")
    api_request = urllib.request.Request(
        XIMILAR_SPORT_CARD_ENDPOINT,
        data=request_data,
        headers={
            "Authorization": f"Token {XIMILAR_API_TOKEN}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(api_request, timeout=45) as response:
            response_body = response.read().decode("utf-8")
            return json.loads(response_body)
    except urllib.error.HTTPError as error:
        error_body = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Ximilar HTTP {error.code}: {error_body}") from error
    except urllib.error.URLError as error:
        raise RuntimeError(f"Ximilar connection error: {error.reason}") from error




def recognize_card_image(image_filename):
    """Recognize a card image and return (provider_name, raw_response, extracted_fields).

    CardSight is preferred when CARDSIGHT_API_KEY is configured.
    Ximilar remains as a fallback while testing.
    """
    if cardsight_api_key():
        raw_response = call_cardsight_for_image(
            image_filename,
            current_app.config["UPLOAD_FOLDER"]
        )
        return "CardSight", raw_response, extract_card_data_from_cardsight(raw_response)

    raw_response = call_ximilar_for_image(image_filename)
    return "Ximilar", raw_response, extract_card_data_from_ximilar(raw_response)


def recognition_configured():
    """Return True when at least one card-recognition provider is configured."""
    return bool(cardsight_api_key() or XIMILAR_API_TOKEN)


