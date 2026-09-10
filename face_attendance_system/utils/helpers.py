"""Utility helpers: image encoding/decoding, dates, status logic."""
import base64
import datetime
import re

import cv2
import numpy as np

ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}


# ── Images ─────────────────────────────────────────────────────────────
def decode_base64_image(data_url: str) -> np.ndarray | None:
    """Decode a base64 data-URL (or raw base64) JPEG/PNG frame to BGR.

    Returns ``None`` when the payload cannot be parsed.
    """
    if not data_url:
        return None
    try:
        # Strip the "data:image/...;base64," prefix when present
        if "," in data_url and data_url.strip().startswith("data:"):
            data_url = data_url.split(",", 1)[1]
        raw = base64.b64decode(data_url)
        arr = np.frombuffer(raw, dtype=np.uint8)
        image = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        return image
    except Exception:
        return None


def encode_image_to_data_url(image_bgr: np.ndarray, fmt: str = ".jpg") -> str:
    """Encode a BGR image to a JPEG data URL."""
    ok, buf = cv2.imencode(fmt, image_bgr)
    if not ok:
        return ""
    b64 = base64.b64encode(buf.tobytes()).decode("utf-8")
    return f"data:image/jpeg;base64,{b64}"


def allowed_image_file(filename: str) -> bool:
    if not filename or "." not in filename:
        return False
    ext = filename.rsplit(".", 1)[1].lower()
    return ext in ALLOWED_IMAGE_EXTENSIONS


def resize_to_width(image_bgr: np.ndarray, width: int = 800) -> np.ndarray:
    """Downscale a frame to `width` px (keeping aspect ratio) to save bandwidth."""
    h, w = image_bgr.shape[:2]
    if w <= width:
        return image_bgr
    ratio = width / float(w)
    return cv2.resize(image_bgr, (width, int(h * ratio)), interpolation=cv2.INTER_AREA)


# ── Dates / time ───────────────────────────────────────────────────────
def today_str() -> str:
    return datetime.date.today().isoformat()


def now_time_str() -> str:
    return datetime.datetime.now().strftime("%H:%M:%S")


def determine_status(time_str: str, late_after: str = "09:15") -> str:
    """Return 'Late' when `time_str` > `late_after`, else 'Present'."""
    try:
        now = datetime.datetime.strptime(time_str, "%H:%M:%S").time()
        cutoff = datetime.datetime.strptime(late_after, "%H:%M").time()
        return "Late" if now > cutoff else "Present"
    except ValueError:
        return "Present"


def valid_date_str(value: str) -> bool:
    return bool(value) and bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}", value))
