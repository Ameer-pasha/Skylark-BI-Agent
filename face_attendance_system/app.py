"""Smart Attendance System — Flask entry point.

Run:
    venv/bin/python app.py
"""
import os

from flask import Flask, jsonify, render_template
from flask_cors import CORS

from config import config
from database.models import db
from models.face_engine import engine
from utils import registry

# ── App factory-ish setup ─────────────────────────────────────────────
os.makedirs(config.UPLOAD_FOLDER, exist_ok=True)
os.makedirs(os.path.dirname(config.DATABASE_PATH), exist_ok=True)

app = Flask(__name__)
app.config.from_object(config)
CORS(app)

db.init_app(app)

with app.app_context():
    db.create_all()
    registry.refresh()

# ── Blueprints ────────────────────────────────────────────────────────
from routes.attendance_routes import attendance_bp  # noqa: E402
from routes.student_routes import student_bp  # noqa: E402

app.register_blueprint(student_bp)
app.register_blueprint(attendance_bp)

# ── Warm up the face engine (non-fatal on startup) ───────────────────
# The model (buffalo_l) downloads on first run. We kick it off eagerly so
# the first recognize call is fast; if it fails the app still serves the UI.
_engine_warmed = False
_engine_error = None


def _warm_engine() -> None:
    global _engine_warmed, _engine_error
    try:
        engine.configure(
            model_root=config.INSIGHTFACE_ROOT,
            det_size=(config.DET_SIZE, config.DET_SIZE),
            match_threshold=config.FACE_MATCH_THRESHOLD,
        )
        engine.load()
        _engine_warmed = True
    except Exception as exc:  # pragma: no cover
        _engine_error = str(exc)


# ── Pages ─────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return render_template("dashboard.html")


@app.route("/register")
def register_page():
    return render_template("register.html")


@app.route("/live")
def live_page():
    return render_template("live_attendance.html")


@app.route("/records")
def records_page():
    return render_template("records.html")


@app.route("/students")
def students_page():
    return render_template("students.html")


# ── Health ────────────────────────────────────────────────────────────
@app.route("/api/health")
def health():
    return jsonify(
        status="ok",
        face_engine_ready=engine.is_ready,
        face_engine_error=engine.error,
    )


if __name__ == "__main__":
    _warm_engine()
    app.run(host=config.HOST, port=config.PORT, debug=False, threaded=True)
