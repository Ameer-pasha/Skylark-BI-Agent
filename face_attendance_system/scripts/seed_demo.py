"""Seed 3 demo students from the insightface sample photo (t1.jpg).

These are REAL face crops, so they register real embeddings and can be
recognised if the same sample photo is shown to the camera. For your own
testing, register yourself via the webcam on the Register page instead.

Run from the project root:
    venv/bin/python scripts/seed_demo.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import cv2

from app import app  # noqa: E402 (creates DB + blueprints)
from config import config  # noqa: E402
from database.models import Attendance, Student, db  # noqa: E402
from models.face_engine import engine  # noqa: E402
from utils import registry  # noqa: E402
from utils.helpers import determine_status, now_time_str, today_str  # noqa: E402

DEMO = [
    ("Aisha Khan", "CS-001", "10-A"),
    ("Rohan Mehta", "CS-002", "10-A"),
    ("Priya Sharma", "CS-003", "10-B"),
]


def _sample_image():
    import insightface
    d = Path(insightface.__file__).parent / "data" / "images"
    return cv2.imread(str(d / "t1.jpg"))


def _crop_face(img, bbox, margin=0.55):
    x1, y1, x2, y2 = [int(v) for v in bbox]
    w, h = x2 - x1, y2 - y1
    mx, my = int(w * margin), int(h * margin)
    H, W = img.shape[:2]
    return img[max(0, y1 - my):min(H, y2 + my), max(0, x1 - mx):min(W, x2 + mx)]


def main() -> int:
    with app.app_context():
        engine.configure(
            model_root=config.INSIGHTFACE_ROOT,
            det_size=(config.DET_SIZE, config.DET_SIZE),
            match_threshold=config.FACE_MATCH_THRESHOLD,
        )
        engine.load()
        img = _sample_image()
        faces = engine.detect_and_embed(img)[:3]
        if len(faces) < 3:
            print("Not enough faces in the sample photo to seed.")
            return 1

        for (name, roll, section), face in zip(DEMO, faces):
            if Student.query.filter_by(roll_no=roll).first():
                print(f"skip {name} (already exists)")
                continue
            crop = _crop_face(img, face["bbox"])
            s = Student(name=name, roll_no=roll, class_section=section)
            s.set_embedding(face["embedding"])
            from routes.student_routes import _save_photo
            s.photo_path = _save_photo(crop)
            db.session.add(s)
        db.session.commit()

        today = today_str()
        for i, s in enumerate(Student.query.order_by(Student.id).all()[:3]):
            if not Attendance.query.filter_by(student_id=s.id, date=today).first():
                t = f"09:{i:02d}:0{i}"
                db.session.add(Attendance(
                    student_id=s.id, date=today, time=t,
                    status=determine_status(t, config.LATE_AFTER)))
        db.session.commit()
        registry.refresh()

        print(f"Seeded {Student.query.count()} students + today's attendance.")
        for s in Student.query.order_by(Student.id).all():
            print("  -", s.name, s.roll_no, s.class_section)
    return 0


if __name__ == "__main__":
    sys.exit(main())
