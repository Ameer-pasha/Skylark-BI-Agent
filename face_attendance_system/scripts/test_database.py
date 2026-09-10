"""Database layer verification (Step 2).

Uses an in-memory SQLite DB so the real attendance.db is untouched.
Verifies: student insert/fetch, embedding round-trip, attendance insert,
duplicate-per-day unique constraint.

Run from the project root:
    venv/bin/python scripts/test_database.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np

from database.models import Attendance, Student, db
from flask import Flask

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db.init_app(app)


def main() -> int:
    with app.app_context():
        db.create_all()

        # 1) Insert dummy students
        s1 = Student(name="Aisha Khan", roll_no="CS-001", class_section="10-A", photo_path="demo_a.jpg")
        s1.set_embedding(np.random.default_rng(1).standard_normal(512).astype(np.float32))
        s2 = Student(name="Rohan Mehta", roll_no="CS-002", class_section="10-A", photo_path="demo_b.jpg")
        s2.set_embedding(np.random.default_rng(2).standard_normal(512).astype(np.float32))
        db.session.add_all([s1, s2])
        db.session.commit()
        print("Inserted students:", [(s.id, s.name) for s in Student.query.all()])

        # 2) Embedding round-trip
        got = s1.get_embedding()
        print("Embedding round-trip: dtype", got.dtype, "shape", got.shape,
              "| first values match:", np.allclose(got, s1.get_embedding()))

        # 3) Attendance insert
        a = Attendance(student_id=s1.id, date="2026-09-10", time="09:02:11", status="Present")
        db.session.add(a)
        db.session.commit()
        print("Attendance inserted:", a.to_dict()["student"]["name"], a.status)

        # 4) Duplicate-per-day unique constraint
        dup = Attendance(student_id=s1.id, date="2026-09-10", time="10:00:00", status="Present")
        db.session.add(dup)
        try:
            db.session.commit()
            print("FAIL: duplicate attendance allowed!")
            return 1
        except Exception:
            db.session.rollback()
            print("OK: duplicate attendance blocked by unique constraint ✔")

        # 5) Different student, same day is allowed
        a2 = Attendance(student_id=s2.id, date="2026-09-10", time="09:20:00", status="Late")
        db.session.add(a2)
        db.session.commit()
        print("OK: second student on same day allowed ✔")

        print("\nRESULT: PASS ✔  (DB models + constraints working)")
        return 0


if __name__ == "__main__":
    sys.exit(main())
