import os
import re
from uuid import uuid4

from flask import current_app, flash
from werkzeug.utils import secure_filename


ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}


def allowed_image(filename):
    if not filename or "." not in filename:
        return False

    extension = filename.rsplit(".", 1)[1].lower()

    return extension in ALLOWED_IMAGE_EXTENSIONS


def save_uploaded_image(file_storage):
    if not file_storage or not file_storage.filename:
        return None

    if not allowed_image(file_storage.filename):
        flash("Image must be a PNG, JPG, JPEG, GIF, or WEBP file.")
        return None

    upload_folder = current_app.config["UPLOAD_FOLDER"]
    os.makedirs(upload_folder, exist_ok=True)

    original_filename = secure_filename(file_storage.filename)
    extension = original_filename.rsplit(".", 1)[1].lower()
    unique_filename = f"{uuid4().hex}.{extension}"
    save_path = os.path.join(upload_folder, unique_filename)

    file_storage.save(save_path)

    return unique_filename


def delete_image_file(filename):
    if not filename:
        return

    upload_folder = current_app.config["UPLOAD_FOLDER"]
    image_path = os.path.join(upload_folder, filename)

    if os.path.exists(image_path):
        os.remove(image_path)


def save_uploaded_image_with_source(file_storage):
    """Save an uploaded image and also return the browser/client filename."""
    source_filename = secure_filename(file_storage.filename) if file_storage and file_storage.filename else None
    image_filename = save_uploaded_image(file_storage)
    return image_filename, source_filename


def slugify_image_part(value):
    """Convert a card field into a safe, readable filename part."""
    if value in (None, ""):
        return None

    text_value = str(value).strip().lower()
    text_value = text_value.replace("#", "")
    text_value = re.sub(r"[^a-z0-9]+", "-", text_value)
    text_value = text_value.strip("-")

    return text_value or None


def unique_upload_filename(base_name, extension, current_filename=None):
    """Return a filename that does not collide inside the upload folder."""
    upload_folder = current_app.config["UPLOAD_FOLDER"]

    candidate = f"{base_name}.{extension}"
    candidate_path = os.path.join(upload_folder, candidate)

    if current_filename and candidate == current_filename:
        return candidate

    counter = 2
    while os.path.exists(candidate_path):
        candidate = f"{base_name}_{counter}.{extension}"
        candidate_path = os.path.join(upload_folder, candidate)
        counter += 1

    return candidate


def rename_image_for_inventory(image_filename, card_like):
    """Rename an uploaded image when it becomes an inventory card.

    Format example:
    2024_mike-trout_topps-chrome_77.jpg
    """
    if not image_filename:
        return image_filename

    upload_folder = current_app.config["UPLOAD_FOLDER"]
    source_path = os.path.join(upload_folder, image_filename)

    if not os.path.exists(source_path):
        return image_filename

    original_extension = image_filename.rsplit(".", 1)[-1].lower() if "." in image_filename else "jpg"
    if original_extension not in ALLOWED_IMAGE_EXTENSIONS:
        original_extension = "jpg"

    year_part = slugify_image_part(getattr(card_like, "year", None))
    player_part = slugify_image_part(getattr(card_like, "player_name", None))
    product_part = slugify_image_part(getattr(card_like, "set_name", None) or getattr(card_like, "brand", None))
    number_part = slugify_image_part(getattr(card_like, "card_number", None))

    filename_parts = [part for part in [year_part, player_part, product_part, number_part] if part]

    if not filename_parts:
        return image_filename

    base_name = "_".join(filename_parts)
    new_filename = unique_upload_filename(base_name, original_extension, current_filename=image_filename)

    if new_filename == image_filename:
        return image_filename

    destination_path = os.path.join(upload_folder, new_filename)
    os.replace(source_path, destination_path)

    return new_filename
