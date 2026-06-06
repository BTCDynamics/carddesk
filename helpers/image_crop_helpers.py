import os
from typing import Optional, Tuple

from flask import current_app


def crop_card_image_for_inventory(image_filename: Optional[str]) -> Optional[str]:
    """Crop a staged card image down to the outside card borders.

    The import workflow calls this right before the image is renamed and attached
    to the permanent inventory record. It intentionally fails safe: if OpenCV is
    unavailable, the file is missing, or the card border cannot be detected with
    enough confidence, the original filename is returned unchanged.
    """
    if not image_filename:
        return image_filename

    try:
        import cv2
        import numpy as np
    except Exception:
        return image_filename

    upload_folder = current_app.config.get("UPLOAD_FOLDER")
    if not upload_folder:
        return image_filename

    image_path = os.path.join(upload_folder, image_filename)
    if not os.path.exists(image_path):
        return image_filename

    image = cv2.imread(image_path)
    if image is None:
        return image_filename

    try:
        warped = _detect_and_crop_card(cv2, np, image)
        if warped is None:
            return image_filename

        extension = image_filename.rsplit(".", 1)[-1].lower() if "." in image_filename else "jpg"
        if extension in {"jpg", "jpeg"}:
            cv2.imwrite(image_path, warped, [int(cv2.IMWRITE_JPEG_QUALITY), 95])
        elif extension == "png":
            cv2.imwrite(image_path, warped, [int(cv2.IMWRITE_PNG_COMPRESSION), 3])
        else:
            cv2.imwrite(image_path, warped)

        return image_filename
    except Exception:
        return image_filename


def _detect_and_crop_card(cv2, np, image):
    original_height, original_width = image.shape[:2]
    max_dimension = 1200
    scale = min(1.0, max_dimension / float(max(original_height, original_width)))
    working = cv2.resize(image, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA) if scale < 1.0 else image.copy()

    gray = cv2.cvtColor(working, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (5, 5), 0)

    edged = cv2.Canny(gray, 40, 140)
    edged = cv2.dilate(edged, None, iterations=2)
    edged = cv2.erode(edged, None, iterations=1)

    contours, _ = cv2.findContours(edged, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    candidates = sorted(contours, key=cv2.contourArea, reverse=True)[:12]

    working_area = working.shape[0] * working.shape[1]
    best_points = None
    best_area = 0

    for contour in candidates:
        area = cv2.contourArea(contour)
        if area < working_area * 0.18:
            continue

        perimeter = cv2.arcLength(contour, True)
        approx = cv2.approxPolyDP(contour, 0.025 * perimeter, True)

        if len(approx) == 4:
            points = approx.reshape(4, 2).astype("float32")
        else:
            rect = cv2.minAreaRect(contour)
            points = cv2.boxPoints(rect).astype("float32")

        if not _looks_like_trading_card(points):
            continue

        if area > best_area:
            best_points = points
            best_area = area

    if best_points is None:
        best_points = _detect_from_background_contrast(cv2, np, working)
        if best_points is None:
            return None

    if scale < 1.0:
        best_points = best_points / scale

    best_points = _clamp_points(np, best_points, original_width, original_height)

    # IMPORTANT: keep the saved file as a plain rectangular crop.
    # Earlier versions used a perspective warp, which can visually shave/round
    # the physical card corners when the detector locks onto the card face.
    # For inventory/eBay-style listing photos, square image corners are safer.
    cropped = _rectangular_crop_from_points(image, best_points, padding_ratio=0.018)

    if cropped is None:
        return None

    # Avoid saving tiny or obviously wrong crops.
    if cropped.shape[0] < original_height * 0.35 or cropped.shape[1] < original_width * 0.35:
        return None

    return cropped


def _detect_from_background_contrast(cv2, np, working):
    """Fallback for photos where Canny misses the outside card edge."""
    hsv = cv2.cvtColor(working, cv2.COLOR_BGR2HSV)
    saturation = hsv[:, :, 1]

    # Card photos usually have a lower-detail tabletop/background around the
    # outside and a high-saturation card area inside.
    _, mask = cv2.threshold(saturation, 45, 255, cv2.THRESH_BINARY)
    kernel = np.ones((9, 9), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None

    working_area = working.shape[0] * working.shape[1]
    for contour in sorted(contours, key=cv2.contourArea, reverse=True)[:8]:
        area = cv2.contourArea(contour)
        if area < working_area * 0.18:
            continue

        rect = cv2.minAreaRect(contour)
        points = cv2.boxPoints(rect).astype("float32")

        if _looks_like_trading_card(points):
            return points

    return None


def _looks_like_trading_card(points) -> bool:
    ordered = _order_points_for_math(points)
    top_width = _distance(ordered[0], ordered[1])
    bottom_width = _distance(ordered[2], ordered[3])
    left_height = _distance(ordered[0], ordered[3])
    right_height = _distance(ordered[1], ordered[2])

    width = max(top_width, bottom_width)
    height = max(left_height, right_height)

    if width <= 0 or height <= 0:
        return False

    aspect_ratio = width / height

    # Standard trading cards are portrait, but allow landscape and minor camera skew.
    return 0.45 <= aspect_ratio <= 1.85


def _rectangular_crop_from_points(image, points, padding_ratio: float = 0.018):
    """Return a square-cornered bounding-box crop around detected card points.

    This deliberately does not mask corners and does not perspective-warp the
    image. A small padding keeps the full physical card edge visible so exports
    remain suitable for marketplace/listing photos.
    """
    height, width = image.shape[:2]

    x_min = int(min(point[0] for point in points))
    x_max = int(max(point[0] for point in points))
    y_min = int(min(point[1] for point in points))
    y_max = int(max(point[1] for point in points))

    crop_width = max(1, x_max - x_min)
    crop_height = max(1, y_max - y_min)
    padding = int(max(crop_width, crop_height) * padding_ratio)

    x_min = max(0, x_min - padding)
    y_min = max(0, y_min - padding)
    x_max = min(width, x_max + padding)
    y_max = min(height, y_max + padding)

    if x_max <= x_min or y_max <= y_min:
        return None

    return image[y_min:y_max, x_min:x_max].copy()


def _four_point_transform(cv2, np, image, points):
    rect = _order_points(np, points)
    top_left, top_right, bottom_right, bottom_left = rect

    width_a = np.linalg.norm(bottom_right - bottom_left)
    width_b = np.linalg.norm(top_right - top_left)
    max_width = int(max(width_a, width_b))

    height_a = np.linalg.norm(top_right - bottom_right)
    height_b = np.linalg.norm(top_left - bottom_left)
    max_height = int(max(height_a, height_b))

    if max_width <= 0 or max_height <= 0:
        return None

    destination = np.array(
        [
            [0, 0],
            [max_width - 1, 0],
            [max_width - 1, max_height - 1],
            [0, max_height - 1],
        ],
        dtype="float32",
    )

    matrix = cv2.getPerspectiveTransform(rect, destination)
    return cv2.warpPerspective(image, matrix, (max_width, max_height))


def _order_points(np, points):
    rect = np.zeros((4, 2), dtype="float32")
    sums = points.sum(axis=1)
    diffs = np.diff(points, axis=1)

    rect[0] = points[np.argmin(sums)]
    rect[2] = points[np.argmax(sums)]
    rect[1] = points[np.argmin(diffs)]
    rect[3] = points[np.argmax(diffs)]

    return rect


def _order_points_for_math(points):
    # This version avoids requiring numpy in the small aspect-ratio helper.
    ordered = sorted(points, key=lambda p: (p[1], p[0]))
    top = sorted(ordered[:2], key=lambda p: p[0])
    bottom = sorted(ordered[2:], key=lambda p: p[0])
    return [top[0], top[1], bottom[1], bottom[0]]


def _distance(a, b) -> float:
    return float(((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5)


def _clamp_points(np, points, width: int, height: int):
    points[:, 0] = np.clip(points[:, 0], 0, width - 1)
    points[:, 1] = np.clip(points[:, 1], 0, height - 1)
    return points
