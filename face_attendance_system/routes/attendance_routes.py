"""Recognition + attendance API."""
import io
import datetime as _dt

from flask import Blueprint, jsonify, request, send_file

from config import config
from database.models import Attendance, Student, db
from models.face_engine import engine
from utils import registry
from utils.helpers import (
    decode_base64_image,
    determine_status,
    now_time_str,
    today_str,
    valid_date_str,
)

attendance_bp = Blueprint("attendance", __name__)


def _mark(student_id: int, date_str: str = None) -> Attendance:
    """Create (or fetch) today's attendance entry for a student."""
    date_str = date_str or today_str()
    existing = Attendance.query.filter_by(student_id=student_id, date=date_str).first()
    if existing:
        return existing

    entry = Attendance(
        student_id=student_id,
        date=date_str,
        time=now_time_str(),
        status=determine_status(now_time_str(), config.LATE_AFTER),
    )
    db.session.add(entry)
    db.session.commit()
    return entry


@attendance_bp.route("/api/recognize", methods=["POST"])
def recognize():
    """Recognize faces in a single base64 frame.

    Request JSON: {"image": "<data:image/jpeg;base64,...>"}
    """
    body = request.get_json(silent=True) or {}
    image = decode_base64_image(body.get("image") or body.get("image_base64"))
    if image is None:
        return jsonify(error="Invalid or missing image"), 400

    faces = engine.detect_and_embed(image)
    if not faces:
        return jsonify(
            matches=[],
            message="No face detected",
            face_count=0,
        )

    students = registry.snapshot()
    matches = []
    for face in faces:
        best_id, best_name, best_sim = None, None, -1.0
        for s in students:
            sim = engine.cosine_similarity(face["embedding"], s["embedding"])
            if sim > best_sim:
                best_sim = sim
                best_id, best_name = s["id"], s["name"]

        matched = bool(best_id and best_sim >= config.FACE_MATCH_THRESHOLD)
        matches.append(
            {
                "bbox": face["bbox"],
                "det_score": round(face["det_score"], 4),
                "matched": matched,
                "similarity": round(best_sim, 4),
                "student_id": best_id if matched else None,
                "name": best_name if matched else None,
            }
        )

    return jsonify(matches=matches, face_count=len(faces))


@attendance_bp.route("/api/mark-attendance", methods=["POST"])
def mark_attendance():
    """Mark attendance for a recognized student (idempotent per day)."""
    body = request.get_json(silent=True) or {}
    student_id = body.get("student_id")
    date_str = body.get("date") or today_str()

    if student_id is None:
        return jsonify(error="student_id is required"), 400
    if not valid_date_str(date_str):
        return jsonify(error="date must be YYYY-MM-DD"), 400

    student = db.session.get(Student, int(student_id))
    if not student:
        return jsonify(error="Student not found"), 404

    try:
        existing = Attendance.query.filter_by(
            student_id=student.id, date=date_str
        ).first()
        if existing:
            return jsonify(
                message=f"{student.name} is already marked ({existing.status}) today",
                already_marked=True,
                attendance=existing.to_dict(),
            )

        entry = _mark(student.id, date_str)
        return jsonify(
            message=f"Attendance marked — {student.name} ({entry.status})",
            already_marked=False,
            attendance=entry.to_dict(),
        ), 201
    except Exception as exc:  # pragma: no cover
        db.session.rollback()
        return jsonify(error=f"Failed to mark attendance: {exc}"), 500


@attendance_bp.route("/api/attendance", methods=["GET"])
def get_attendance():
    """Attendance records, optionally filtered by date / class / search."""
    date_str = request.args.get("date")
    section = request.args.get("class_section")
    search = (request.args.get("search") or "").strip().lower()
    page = max(int(request.args.get("page", 1)), 1)
    per_page = min(max(int(request.args.get("per_page", 50)), 1), 500)

    query = Attendance.query.join(Student)
    if date_str and valid_date_str(date_str):
        query = query.filter(Attendance.date == date_str)
    if section:
        query = query.filter(Student.class_section == section)
    if search:
        query = query.filter(
            db.or_(
                Student.name.ilike(f"%{search}%"),
                Student.roll_no.ilike(f"%{search}%"),
            )
        )

    query = query.order_by(Attendance.date.desc(), Attendance.time.desc())
    total = query.count()
    rows = (
        query.offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    return jsonify(
        records=[r.to_dict() for r in rows],
        total=total,
        page=page,
        per_page=per_page,
        pages=(total + per_page - 1) // per_page if total else 0,
    )


@attendance_bp.route("/api/attendance/summary", methods=["GET"])
def attendance_summary():
    """Today's attendance summary for the dashboard."""
    date_str = request.args.get("date") or today_str()
    total_students = Student.query.count()
    present_rows = Attendance.query.filter_by(date=date_str).all()
    present_ids = {r.student_id for r in present_rows}
    present_count = len(present_ids)
    late_count = sum(1 for r in present_rows if r.status == "Late")

    recent = (
        Attendance.query.filter_by(date=date_str)
        .order_by(Attendance.time.desc())
        .limit(8)
        .all()
    )

    return jsonify(
        date=date_str,
        total_students=total_students,
        present_count=present_count,
        absent_count=max(total_students - present_count, 0),
        late_count=late_count,
        recent=[r.to_dict() for r in recent],
    )


@attendance_bp.route("/api/attendance/export", methods=["GET"])
def export_attendance():
    """Export attendance to an .xlsx file (optionally filtered)."""
    date_str = request.args.get("date")
    section = request.args.get("class_section")
    search = (request.args.get("search") or "").strip().lower()

    query = Attendance.query.join(Student)
    if date_str and valid_date_str(date_str):
        query = query.filter(Attendance.date == date_str)
    if section:
        query = query.filter(Student.class_section == section)
    if search:
        query = query.filter(
            db.or_(
                Student.name.ilike(f"%{search}%"),
                Student.roll_no.ilike(f"%{search}%"),
            )
        )
    rows = query.order_by(Attendance.date.desc(), Attendance.time.desc()).all()

    try:
        import pandas as pd
    except ImportError:  # pragma: no cover
        return jsonify(error="pandas not installed"), 500

    data = [
        {
            "Date": r.date,
            "Time": r.time,
            "Status": r.status,
            "Name": r.student.name,
            "Roll No": r.student.roll_no,
            "Class": r.student.class_section,
        }
        for r in rows
    ]
    df = pd.DataFrame(data)

    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Attendance")
    buf.seek(0)

    fname = f"attendance_{date_str or 'all'}.xlsx"
    return send_file(
        buf,
        as_attachment=True,
        download_name=fname,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
