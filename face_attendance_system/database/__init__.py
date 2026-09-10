"""Database package — exposes the shared SQLAlchemy instance."""
from .models import db, Student, Attendance

__all__ = ["db", "Student", "Attendance"]
