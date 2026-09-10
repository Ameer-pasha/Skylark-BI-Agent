"""In-memory registry of student face embeddings.

Recognition is a hot path (polled every ~1.2 s by the live camera loop),
so we keep a lightweight copy of every student's embedding in memory and
refresh it whenever a student is added / edited / removed. No DB round-trip
per frame.
"""
import threading

from database.models import Student

_lock = threading.Lock()
_cache: list[dict] = []


def _build() -> list[dict]:
    rows = Student.query.all()
    return [
        {
            "id": s.id,
            "name": s.name,
            "roll_no": s.roll_no,
            "class_section": s.class_section,
            "photo_path": s.photo_path,
            "embedding": s.get_embedding(),
        }
        for s in rows
        if s.get_embedding() is not None and s.get_embedding().size > 0
    ]


def refresh() -> None:
    """Re-read all student embeddings from the DB (call after any mutation)."""
    global _cache
    with _lock:
        _cache = _build()


def snapshot() -> list[dict]:
    """Return a shallow copy of the current registry."""
    with _lock:
        return list(_cache)


def count() -> int:
    with _lock:
        return len(_cache)
