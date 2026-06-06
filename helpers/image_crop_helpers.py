import os
from typing import Optional

from flask import current_app


def straighten_card_image_for_inventory(image_filename: Optional[str]) -> Optional[str]:
    """Auto-rotate a staged card image so the card is upright/plumb.

    This intentionally does NOT crop the image and does NOT mask or round the
    card corners. The full photo canvas is preserved with a little added border
    if rotation needs extra space.

    The workflow calls this before the staged image is renamed and attached to
    the permanent inventory record. It fails safe: if OpenCV is unavailable, the
    file is missing, or the card angle cannot be detected confidently, the
    original filename is returned unchanged.
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
        corrected = _detect_and_straighten_card(cv2, np, image)
        if corrected is None:
            return image_filename

        extension = image_filename.rsplit(".", 1)[-1].lower() if "." in image_filename else "jpg"
        if extension in {"jpg", "jpeg"}:
            cv2.imwrite(image_path, corrected, [int(cv2.IMWRITE_JPEG_QUALITY), 95])
        elif extension == "png":
            cv2.imwrite(image_path, corrected, [int(cv2.IMWRITE_PNG_COMPRESSION), 3])
        else:
            cv2.imwrite(image_path, corrected)

        return image_filename
    except Exception:
        return image_filename


def crop_card_image_for_inventory(image_filename: Optional[str]) -> Optional[str]:
    """Backward-compatible name kept for older imports.

    Cropping is currently disabled. This now performs only the safe
    straighten/plumb step and leaves the full image canvas intact.
    """
    return straighten_card_image_for_inventory(image_filename)


def _detect_and_straighten_card(cv2, np, image):
    original_height, original_width = image.shape[:2]
    max_dimension = 1200
    scale = min(1.0, max_dimension / float(max(original_height, original_width)))
    working = cv2.resize(image, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA) if scale < 1.0 else image.copy()

    points = _detect_card_points(cv2, np, working)
    if points is None:
        return None

    if scale < 1.0:
        points = points / scale

    points = _clamp_points(np, points, original_width, original_height)
    angle = _rotation_angle_from_points(np, points)

    # Avoid unnecessary re-encoding and avoid wild corrections from bad detection.
    if abs(angle) < 0.75:
        return None
    if abs(angle) > 18:
        return None

    return _rotate_image_keep_full_canvas(cv2, np, image, angle)


def _detect_card_points(cv2, np, working):
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

    if best_points is not None:
        return best_points

    return _detect_from_background_contrast(cv2, np, working)


def _detect_from_background_contrast(cv2, np, working):
    """Fallback for photos where Canny misses the outside card edge."""
    hsv = cv2.cvtColor(working, cv2.COLOR_BGR2HSV)
    saturation = hsv[:, :, 1]

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


def _rotation_angle_from_points(np, points) -> float:
    """Return degrees needed to make the card's vertical edge plumb."""
    rect = _order_points(np, points)
    top_left, top_right, bottom_right, bottom_left = rect

    left_edge = bottom_left - top_left
    right_edge = bottom_right - top_right
    vertical_edge = left_edge if np.linalg.norm(left_edge) >= np.linalg.norm(right_edge) else right_edge

    # Angle is relative to the vertical axis. Negative sign rotates image back.
    edge_angle_from_vertical = np.degrees(np.arctan2(vertical_edge[0], vertical_edge[1]))
    return -float(edge_angle_from_vertical)


def _rotate_image_keep_full_canvas(cv2, np, image, angle_degrees: float):
    height, width = image.shape[:2]
    center = (width / 2.0, height / 2.0)

    matrix = cv2.getRotationMatrix2D(center, angle_degrees, 1.0)
    cos = abs(matrix[0, 0])
    sin = abs(matrix[0, 1])

    new_width = int((height * sin) + (width * cos))
    new_height = int((height * cos) + (width * sin))

    matrix[0, 2] += (new_width / 2.0) - center[0]
    matrix[1, 2] += (new_height / 2.0) - center[1]

    border_color = _estimate_border_color(np, image)
    return cv2.warpAffine(
        image,
        matrix,
        (new_width, new_height),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=border_color,
    )


def _estimate_border_color(np, image):
    """Use image edge pixels for any added canvas after rotation."""
    top = image[0, :, :]
    bottom = image[-1, :, :]
    left = image[:, 0, :]
    right = image[:, -1, :]
    edge_pixels = np.concatenate([top, bottom, left, right], axis=0)
    median = np.median(edge_pixels, axis=0)
    return tuple(int(channel) for channel in median.tolist())


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
    return 0.45 <= aspect_ratio <= 1.85


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
