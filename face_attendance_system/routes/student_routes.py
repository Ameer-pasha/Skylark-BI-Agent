"""Student registration & management API."""
import datetime
import os
import uuid

import cv2
import numpy as np
from flask import Blueprint, jsonify, request

from config import config
from database.models import Student, db
from models.face_engine import engine
from utils import registry
from utils.helpers import allowed_image_file, decode_base64_image

student_bp = Blueprint("students", __name__)

PHOTO_MAX_SIDE = 640


def _save_photo(image_bgr: np.ndarray) -> str | None:
    """Write a BGR image into static/uploads and return the file name."""
    h, w = image_bgr.shape[:2]
    scale = PHOTO_MAX_SIDE / float(max(h, w))
    if scale < 1.0:
        image_bgr = cv2.resize(
            image_bgr, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA
        )
    filename = f"{uuid.uuid4().hex}.jpg"
    os.makedirs(config.UPLOAD_FOLDER, exist_ok=True)
    path = os.path.join(config.UPLOAD_FOLDER, filename)
    cv2.imwrite(path, image_bgr, [cv2.IMWRITE_JPEG_QUALITY, 90])
    return filename


def _extract_image() -> np.ndarray | None:
    """Pull a face image from either a multipart file or a JSON base64 field."""
    if "image" in request.files:
        file = request.files["image"]
        if file and file.filename and allowed_image_file(file.filename):
            data = np.frombuffer(file.read(), dtype=np.uint8)
            return cv2.imdecode(data, cv2.IMREAD_COLOR)

    body = request.get_json(silent=True) or {}
    image_field = body.get("image") or body.get("image_base64")
    return decode_base64_image(image_field)


@student_bp.route("/api/register", methods=["POST"])
def register_student():
    """Create a new student and store their face embedding.

    Accepts multipart/form-data (fields: name, roll_no, class_section, image)
    **or** JSON (fields: name, roll_no, class_section, image = base64 data URL).
    """
    try:
        if request.mimetype and "multipart" in request.mimetype:
            name = (request.form.get("name") or "").strip()
            roll_no = (request.form.get("roll_no") or "").strip()
            class_section = (request.form.get("class_section") or "").strip()
        else:
            body = request.get_json(silent=True) or {}
            name = (body.get("name") or "").strip()
            roll_no = (body.get("roll_no") or "").strip()
            class_section = (body.get("class_section") or "").strip()

        if not name or not roll_no or not class_section:
            return jsonify(error="name, roll_no and class_section are required"), 400

        if Student.query.filter_by(roll_no=roll_no).first():
            return jsonify(error=f"Roll number '{roll_no}' already exists"), 409

        image = _extract_image()
        if image is None:
            return jsonify(
                error="No valid image received (multipart 'image' or JSON 'image' base64)"
            ), 400

        faces = engine.detect_and_embed(image)
        if not faces:
            return jsonify(
                error="No face detected in the image. Use a clear, well-lit photo."
            ), 422
        if len(faces) > 1:
            return jsonify(
                error="Multiple faces detected. Please upload a photo with a single face."
            ), 422

        # Keep the best-detected face
        face = max(faces, key=lambda f: f["det_score"])
        if face["det_score"] < config.DETECTION_THRESHOLD:
            return jsonify(
                error="Face quality too low. Please capture in better lighting."
            ), 422

        photo_name = _save_photo(image)

        student = Student(
            name=name,
            roll_no=roll_no,
            class_section=class_section,
            photo_path=photo_name,
        )
        student.set_embedding(face["embedding"])
        db.session.add(student)
        db.session.commit()
        registry.refresh()

        return jsonify(
            message=f"Student {name} registered successfully",
            student=student.to_dict(),
        ), 201

    except Exception as exc:  # pragma: no cover
        db.session.rollback()
        return jsonify(error=f"Registration failed: {exc}"), 500


@student_bp.route("/api/students", methods=["GET"])
def list_students():
    students = Student.query.order_by(Student.name.asc()).all()
    return jsonify(students=[s.to_dict() for s in students])


@student_bp.route("/api/students/<int:student_id>", methods=["GET"])
def get_student(student_id):
    student = db.session.get(Student, student_id)
    if not student:
        return jsonify(error="Student not found"), 404
    return jsonify(student=student.to_dict())


@student_bp.route("/api/students/<int:student_id>", methods=["PUT"])
def update_student(student_id):
    """Edit name / class (and optionally re-register a new photo)."""
    student = db.session.get(Student, student_id)
    if not student:
        return jsonify(error="Student not found"), 404

    try:
        if request.mimetype and "multipart" in request.mimetype:
            data = request.form.to_dict()
        else:
            data = request.get_json(silent=True) or {}

        if "name" in data and data["name"].strip():
            student.name = data["name"].strip()
        if "class_section" in data and data["class_section"].strip():
            student.class_section = data["class_section"].strip()
        if "roll_no" in data and data["roll_no"].strip():
            new_roll = data["roll_no"].strip()
            existing = Student.query.filter_by(roll_no=new_roll).first()
            if existing and existing.id != student.id:
                return jsonify(error=f"Roll number '{new_roll}' already exists"), 409
            student.roll_no = new_roll

        # Optional: replace the face photo + embedding
        image = _extract_image()
        if image is not None:
            faces = engine.detect_and_embed(image)
            if not faces:
                return jsonify(error="No face detected in the new image"), 422
            if len(faces) > 1:
                return jsonify(
                    error="Multiple faces detected. Use a single-face photo."
                ), 422
            face = max(faces, key=lambda f: f["det_score"])
            old_photo = student.photo_path
            student.photo_path = _save_photo(image)
            student.set_embedding(face["embedding"])
            if old_photo:
                try:
                    os.remove(os.path.join(config.UPLOAD_FOLDER, old_photo))
                except OSError:
                    pass

        db.session.commit()
        registry.refresh()
        return jsonify(message="Student updated", student=student.to_dict())

    except Exception as exc:  # pragma: no cover
        db.session.rollback()
        return jsonify(error=f"Update failed: {exc}"), 500


@student_bp.route("/api/students/<int:student_id>", methods=["DELETE"])
def delete_student(student_id):
    student = db.session.get(Student, student_id)
    if not student:
        return jsonify(error="Student not found"), 404
    try:
        photo = student.photo_path
        db.session.delete(student)
        db.session.commit()
        registry.refresh()
        if photo:
            try:
                os.remove(os.path.join(config.UPLOAD_FOLDER, photo))
            except OSError:
                pass
        return jsonify(message="Student deleted")
    except Exception as exc:  # pragma: no cover
        db.session.rollback()
        return jsonify(error=f"Delete failed: {exc}"), 500
