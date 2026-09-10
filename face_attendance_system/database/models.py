"""SQLAlchemy models for the Smart Attendance System."""
import datetime

import numpy as np
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class Student(db.Model):
    __tablename__ = "students"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(120), nullable=False)
    roll_no = db.Column(db.String(40), unique=True, nullable=False, index=True)
    class_section = db.Column(db.String(40), nullable=False)
    photo_path = db.Column(db.String(255), nullable=True)
    # 512-d float32 embedding stored as raw bytes (BLOB)
    face_embedding = db.Column(db.LargeBinary, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    attendances = db.relationship(
        "Attendance",
        backref="student",
        lazy=True,
        cascade="all, delete-orphan",
    )

    # ── Embedding helpers ──────────────────────────────────────────────
    def set_embedding(self, arr: np.ndarray) -> None:
        self.face_embedding = np.asarray(arr, dtype=np.float32).tobytes()

    def get_embedding(self) -> np.ndarray | None:
        if not self.face_embedding:
            return None
        return np.frombuffer(self.face_embedding, dtype=np.float32).copy()

    def to_dict(self, with_photo_url: bool = True) -> dict:
        data = {
            "id": self.id,
            "name": self.name,
            "roll_no": self.roll_no,
            "class_section": self.class_section,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
        if with_photo_url:
            data["photo_url"] = (
                f"/static/uploads/{self.photo_path}" if self.photo_path else None
            )
        return data


class Attendance(db.Model):
    __tablename__ = "attendance"
    __table_args__ = (
        db.UniqueConstraint("student_id", "date", name="uq_student_date"),
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=False)
    date = db.Column(db.String(10), nullable=False, index=True)  # YYYY-MM-DD
    time = db.Column(db.String(8), nullable=False)  # HH:MM:SS
    status = db.Column(db.String(10), nullable=False, default="Present")

    def to_dict(self, include_student: bool = True) -> dict:
        data = {
            "id": self.id,
            "student_id": self.student_id,
            "date": self.date,
            "time": self.time,
            "status": self.status,
        }
        if include_student and self.student:
            data["student"] = self.student.to_dict()
        return data
