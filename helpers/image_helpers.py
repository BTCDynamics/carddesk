import os
import re
from math import atan2, degrees
from uuid import uuid4

from flask import current_app, flash
from werkzeug.utils import secure_filename


ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}

# Straighten-only image cleanup for AI intake and Mobile Capture.
# Set CARD_DESK_AUTO_STRAIGHTEN=0 in Render/local env to disable instantly.
AUTO_STRAIGHTEN_IMAGES = os.environ.get("CARD_DESK_AUTO_STRAIGHTEN", "1") == "1"
MAX_STRAIGHTEN_ANGLE = 10.0
MIN_STRAIGHTEN_ANGLE = 0.7


def allowed_image(filename):
    if not filename or "." not in filename:
        return False

    extension = filename.rsplit(".", 1)[1].lower()

    return extension in ALLOWED_IMAGE_EXTENSIONS


def _rotate_image_without_cropping(cv2, image, angle_degrees):
    """Rotate an OpenCV image while expanding the canvas so edges are not cropped."""
    height, width = image.shape[:2]
    center_x = width / 2
    center_y = height / 2

    rotation_matrix = cv2.getRotationMatrix2D((center_x, center_y), angle_degrees, 1.0)

    absolute_cos = abs(rotation_matrix[0, 0])
    absolute_sin = abs(rotation_matrix[0, 1])

    new_width = int((height * absolute_sin) + (width * absolute_cos))
    new_height = int((height * absolute_cos) + (width * absolute_sin))

    rotation_matrix[0, 2] += (new_width / 2) - center_x
    rotation_matrix[1, 2] += (new_height / 2) - center_y

    return cv2.warpAffine(
        image,
        rotation_matrix,
        (new_width, new_height),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(255, 255, 255),
    )


def auto_straighten_image(image_path):
    """Straighten a slightly tilted card photo without cropping or perspective warping.

    This is intentionally conservative. If OpenCV is unavailable, the file type
    is not a good candidate, or the detected angle looks risky, the image is
    left untouched.
    """
    if not AUTO_STRAIGHTEN_IMAGES:
        return False

    extension = image_path.rsplit(".", 1)[-1].lower() if "." in image_path else ""

    # Animated/transparent formats are better left untouched for now.
    if extension not in {"jpg", "jpeg", "png", "webp"}:
        return False

    try:
        import cv2
        import numpy as np
    except Exception:
        return False

    try:
        image = cv2.imread(image_path)

        if image is None:
            return False

        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (5, 5), 0)
        edges = cv2.Canny(gray, 50, 150, apertureSize=3)

        min_line_length = max(80, min(image.shape[0], image.shape[1]) // 4)
        lines = cv2.HoughLinesP(
            edges,
            rho=1,
            theta=np.pi / 180,
            threshold=80,
            minLineLength=min_line_length,
            maxLineGap=20,
        )

        if lines is None:
            return False

        angles = []

        for line in lines:
            x1, y1, x2, y2 = line[0]
            dx = x2 - x1
            dy = y2 - y1
            line_length = (dx * dx + dy * dy) ** 0.5

            if line_length < min_line_length:
                continue

            angle = degrees(atan2(dy, dx))

            # Normalize vertical and horizontal card edges to the same small
            # deskew angle range.
            while angle <= -45:
                angle += 90
            while angle > 45:
                angle -= 90

            if abs(angle) <= MAX_STRAIGHTEN_ANGLE:
                angles.append(angle)

        if len(angles) < 3:
            return False

        detected_angle = float(np.median(angles))

        if abs(detected_angle) < MIN_STRAIGHTEN_ANGLE:
            return False

        if abs(detected_angle) > MAX_STRAIGHTEN_ANGLE:
            return False

        straightened = _rotate_image_without_cropping(cv2, image, -detected_angle)

        if extension in {"jpg", "jpeg"}:
            cv2.imwrite(image_path, straightened, [cv2.IMWRITE_JPEG_QUALITY, 95])
        elif extension == "png":
            cv2.imwrite(image_path, straightened, [cv2.IMWRITE_PNG_COMPRESSION, 3])
        else:
            cv2.imwrite(image_path, straightened)

        return True
    except Exception:
        return False


def save_uploaded_image(file_storage, straighten=False):
    if not file_storage or not file_storage.filename:
        return None

    if not allowed_image(file_storage.filename):
        flash("Image must be a PNG, JPG, JPEG, GIF, or WEBP file.")
        return None

    os.makedirs(current_app.config["UPLOAD_FOLDER"], exist_ok=True)

    original_filename = secure_filename(file_storage.filename)
    extension = original_filename.rsplit(".", 1)[1].lower()
    unique_filename = f"{uuid4().hex}.{extension}"
    save_path = os.path.join(current_app.config["UPLOAD_FOLDER"], unique_filename)

    file_storage.save(save_path)

    if straighten:
        auto_straighten_image(save_path)

    return unique_filename


def delete_image_file(filename):
    if not filename:
        return

    image_path = os.path.join(current_app.config["UPLOAD_FOLDER"], filename)

    if os.path.exists(image_path):
        os.remove(image_path)


def save_uploaded_image_with_source(file_storage):
    """Save an uploaded image and also return the browser/client filename."""
    source_filename = secure_filename(file_storage.filename) if file_storage and file_storage.filename else None
    image_filename = save_uploaded_image(file_storage, straighten=True)
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


def rename_image_for_inventory(image_filename, card_like):
    """Rename an uploaded image when it becomes an inventory card.

    Format example:
    2024_mike-trout_topps-chrome_77.jpg
    """
    if not image_filename:
        return image_filename

    source_path = os.path.join(current_app.config["UPLOAD_FOLDER"], image_filename)

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

    destination_path = os.path.join(current_app.config["UPLOAD_FOLDER"], new_filename)
    os.replace(source_path, destination_path)

    return new_filename



