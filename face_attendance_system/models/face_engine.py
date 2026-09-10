"""InsightFace wrapper — face detection + ArcFace embeddings + matching.

The ``buffalo_l`` model pack (RetinaFace detection + ArcFace recognition)
is loaded **once** and reused for every request. GPU is used automatically
when available, otherwise CPU.
"""
import threading

import numpy as np

EMBEDDING_DIM = 512


class FaceEngine:
    """Thread-safe wrapper around ``insightface.app.FaceAnalysis``."""

    def __init__(self, model_root: str | None = None,
                 det_size: tuple[int, int] = (640, 640),
                 match_threshold: float = 0.45):
        self._app = None
        self._lock = threading.Lock()
        self._ready = threading.Event()
        self._error: str | None = None
        self._model_root = model_root
        self._det_size = det_size
        self.match_threshold = match_threshold

    # ── Model loading ──────────────────────────────────────────────────
    def configure(self, model_root: str | None = None,
                  det_size: tuple[int, int] | None = None,
                  match_threshold: float | None = None) -> None:
        """Apply project config before first load (idempotent)."""
        if model_root is not None:
            self._model_root = model_root
        if det_size is not None:
            self._det_size = tuple(det_size)
        if match_threshold is not None:
            self.match_threshold = match_threshold

    @staticmethod
    def _resolve_providers() -> list[str]:
        """Prefer CUDA when onnxruntime-gpu is installed, else CPU."""
        try:
            import onnxruntime as ort
            available = ort.get_available_providers()
            if "CUDAExecutionProvider" in available:
                return ["CUDAExecutionProvider", "CPUExecutionProvider"]
        except Exception:
            pass
        return ["CPUExecutionProvider"]

    def load(self) -> None:
        """Load the model pack exactly once (thread-safe, idempotent)."""
        if self._ready.is_set():
            return
        with self._lock:
            if self._ready.is_set():
                return
            try:
                from insightface.app import FaceAnalysis

                providers = self._resolve_providers()
                self._app = FaceAnalysis(
                    name="buffalo_l",
                    root=self._model_root,
                    providers=providers,
                )
                # ctx_id >= 0 -> GPU device, -1 -> CPU
                ctx_id = 0 if "CUDAExecutionProvider" in providers else -1
                self._app.prepare(ctx_id=ctx_id, det_size=self._det_size)
                self._ready.set()
            except Exception as exc:  # pragma: no cover - runtime error path
                self._error = str(exc)
                raise

    def ensure_loaded(self) -> None:
        if not self._ready.is_set():
            self.load()

    @property
    def is_ready(self) -> bool:
        return self._ready.is_set()

    @property
    def error(self) -> str | None:
        return self._error

    # ── Detection + embedding ──────────────────────────────────────────
    def detect_and_embed(self, image_bgr: np.ndarray) -> list[dict]:
        """Detect every face in ``image_bgr`` and return embeddings.

        Returns a list of dicts::

            {
                "bbox": [x1, y1, x2, y2],   # float pixel coords
                "det_score": 0.99,          # RetinaFace confidence
                "embedding": np.float32(512,)
            }

        Empty list when no face is found.
        """
        self.ensure_loaded()
        if image_bgr is None or getattr(image_bgr, "size", 0) == 0:
            return []

        faces = self._app.get(image_bgr)
        results = []
        for face in faces:
            embedding = getattr(face, "embedding", None)
            if embedding is None:
                continue
            results.append(
                {
                    "bbox": [
                        float(face.bbox[0]),
                        float(face.bbox[1]),
                        float(face.bbox[2]),
                        float(face.bbox[3]),
                    ],
                    "det_score": float(getattr(face, "det_score", 0.0)),
                    "embedding": np.asarray(embedding, dtype=np.float32).ravel(),
                }
            )
        return results

    # ── Comparison ─────────────────────────────────────────────────────
    @staticmethod
    def cosine_similarity(emb1, emb2) -> float:
        """Cosine similarity between two embeddings (defensively normalised)."""
        a = np.asarray(emb1, dtype=np.float32).ravel()
        b = np.asarray(emb2, dtype=np.float32).ravel()
        if a.size == 0 or b.size == 0:
            return 0.0
        na = np.linalg.norm(a) + 1e-10
        nb = np.linalg.norm(b) + 1e-10
        return float(np.dot(a, b) / (na * nb))

    def compare_embeddings(self, emb1, emb2) -> tuple[float, bool]:
        """Return ``(similarity, is_match)`` using the configured threshold."""
        sim = self.cosine_similarity(emb1, emb2)
        return sim, bool(sim >= self.match_threshold)


# Process-wide singleton (created once, warmed up on app startup)
engine = FaceEngine()
