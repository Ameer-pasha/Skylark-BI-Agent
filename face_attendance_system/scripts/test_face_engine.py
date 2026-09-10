"""Standalone FaceEngine verification (Step 3).

Uses the real sample photo `t1.jpg` bundled with the insightface package
(a group photo with several detectable faces).

Checks:
  1. detection + embedding produce a 512-d vector;
  2. the *same* faces (photo slightly jittered) still match (sim >= threshold);
  3. two *different* people in the photo do NOT match;
  4. a random embedding does NOT match.

Run from the project root:
    venv/bin/python scripts/test_face_engine.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import cv2
import numpy as np

from config import config
from models.face_engine import engine


def _sample_image() -> np.ndarray:
    import insightface
    img_dir = Path(insightface.__file__).parent / "data" / "images"
    return cv2.imread(str(img_dir / "t1.jpg"))


def jitter(img: np.ndarray) -> np.ndarray:
    """Small brightness/contrast/blur change — same identity, new pixels."""
    out = cv2.convertScaleAbs(img, alpha=1.06, beta=8)
    out = cv2.GaussianBlur(out, (3, 3), 0)
    return out


def iou(a, b) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0, ix2 - ix1), max(0, iy2 - iy1)
    inter = iw * ih
    area_a = (ax2 - ax1) * (ay2 - ay1)
    area_b = (bx2 - bx1) * (by2 - by1)
    return inter / (area_a + area_b - inter + 1e-6)


def pair_by_iou(faces_a, faces_b, min_iou=0.3):
    """Pair faces across two detections of the same scene by bbox overlap."""
    pairs = []
    for fa in faces_a:
        best = None
        for fb in faces_b:
            s = iou(fa["bbox"], fb["bbox"])
            if s >= min_iou and (best is None or s > best[1]):
                best = (fb, s)
        if best:
            pairs.append((fa, best[0]))
    return pairs


def main() -> int:
    img = _sample_image()
    img_j = jitter(img)

    print("Loading FaceEngine — models already present (no download)...")
    engine.configure(
        model_root=config.INSIGHTFACE_ROOT,
        det_size=(config.DET_SIZE, config.DET_SIZE),
        match_threshold=config.FACE_MATCH_THRESHOLD,
    )
    engine.load()
    print("Model ready:", engine.is_ready, "| match threshold:", engine.match_threshold)

    faces = engine.detect_and_embed(img)
    faces_j = engine.detect_and_embed(img_j)
    print(f"\nFaces detected in original: {len(faces)}")
    print(f"Faces detected in jittered: {len(faces_j)}")
    for f in faces:
        print("  bbox:", [round(v, 1) for v in f["bbox"]],
              "det_score:", round(f["det_score"], 4),
              "| embedding:", f["embedding"].shape)

    if not faces or not faces_j:
        print("FAIL: no face detected.")
        return 1

    # (1) 512-d embedding check
    assert faces[0]["embedding"].size == 512, "embedding must be 512-d"

    # (2) same faces -> match
    pairs = pair_by_iou(faces, faces_j)
    print(f"\nMatched face pairs (same identity) by bbox overlap: {len(pairs)}")
    same_ok = True
    for fa, fb in pairs:
        sim = engine.cosine_similarity(fa["embedding"], fb["embedding"])
        match = sim >= engine.match_threshold
        same_ok &= match
        print(f"  same person: sim={sim:.4f}  -> {'MATCH ✔' if match else 'NO-MATCH ✘'}")

    # (3) different people -> no match
    diff_sim = engine.cosine_similarity(faces[0]["embedding"], faces[1]["embedding"])
    diff_ok = diff_sim < engine.match_threshold
    print(f"\nDifferent people: sim={diff_sim:.4f}  -> {'no-match ✔' if diff_ok else 'MATCH ✘ (unexpected)'}")

    # (4) random -> no match
    rng = np.random.default_rng(7)
    rand_sim = engine.cosine_similarity(faces[0]["embedding"], rng.standard_normal(512).astype(np.float32))
    rand_ok = rand_sim < engine.match_threshold
    print(f"Random embedding: sim={rand_sim:.4f}  -> {'no-match ✔' if rand_ok else 'MATCH ✘ (unexpected)'}")

    ok = same_ok and diff_ok and rand_ok and len(pairs) >= 1
    print("\nRESULT:", "PASS ✔" if ok else "FAIL ✘")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
