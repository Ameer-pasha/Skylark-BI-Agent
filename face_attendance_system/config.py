"""Central configuration for the Smart Attendance System.

All tunables can be overridden through environment variables / `.env`.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

# Project root: face_attendance_system/
BASE_DIR = Path(__file__).resolve().parent

# Load .env if present (values in the real environment always win)
load_dotenv(BASE_DIR / ".env")


def _get(key: str, default: str) -> str:
    return os.environ.get(key, default)


class Config:
    SECRET_KEY = _get("SECRET_KEY", "smart-attendance-dev-secret")

    # ── Folders ────────────────────────────────────────────────────────
    UPLOAD_FOLDER = str(BASE_DIR / "static" / "uploads")
    DATABASE_PATH = str(BASE_DIR / "database" / "attendance.db")
    # InsightFace model zoo root (buffalo_l downloads here on first run)
    INSIGHTFACE_ROOT = str(BASE_DIR / "models" / "insightface")

    # ── SQLAlchemy (SQLite) ────────────────────────────────────────────
    SQLALCHEMY_DATABASE_URI = "sqlite:///" + DATABASE_PATH
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # ── Face recognition ───────────────────────────────────────────────
    FACE_MATCH_THRESHOLD = float(_get("FACE_MATCH_THRESHOLD", "0.45"))
    DETECTION_THRESHOLD = float(_get("DETECTION_THRESHOLD", "0.5"))
    DET_SIZE = int(_get("DET_SIZE", "640"))

    # ── Attendance rules ───────────────────────────────────────────────
    LATE_AFTER = _get("LATE_AFTER", "09:15")

    # ── Server ─────────────────────────────────────────────────────────
    HOST = _get("HOST", "0.0.0.0")
    PORT = int(_get("PORT", "5000"))

    # ── Upload limits ──────────────────────────────────────────────────
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB


config = Config()
