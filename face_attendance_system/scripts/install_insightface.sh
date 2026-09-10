#!/usr/bin/env bash
# ── Install insightface WITHOUT its C++ 3D-mesh extension ─────────────
# insightface 0.7.3 ships source-only and its setup.py builds a Cython/C++
# extension (mesh_core_cython, used only for 3D face rendering) that needs
# CPython dev headers (Python.h). Face detection (RetinaFace) + recognition
# (ArcFace) do NOT use that extension, so we patch it out and install a
# pure-Python build. Run from the project root:
#
#     bash scripts/install_insightface.sh
#
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="${PY:-$HERE/venv/bin/python}"

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

echo "==> Downloading insightface sdist"
"$PY" -m pip download insightface==0.7.3 --no-deps -d "$TMP" >/dev/null

echo "==> Extracting + patching setup.py"
tar xzf "$TMP"/insightface-0.7.3.tar.gz -C "$TMP"

python3 - <<'PY' "$TMP/insightface-0.7.3"
import sys, re, os
root = sys.argv[1]

# 1) Patch setup.py — drop the C++ mesh_core extension
sp = os.path.join(root, "setup.py")
src = open(sp).read()
src = src.replace("from distutils.core import Extension", "")
src = src.replace("from Cython.Distutils import build_ext", "")
src = src.replace("from Cython.Build import cythonize", "")
src = re.sub(r"extensions\s*=\s*\[.*?\],", "extensions = [],", src, flags=re.S)
src = re.sub(r"ext_modules\s*=\s*cythonize\(extensions\)", "ext_modules = []", src)
src = re.sub(r"\n\s*headers\s*=.*?,", "\n", src)
open(sp, "w").write(src)

# 2) Patch app/__init__.py — skip mask_renderer (needs albumentations/face3d,
#    neither of which is used by FaceAnalysis)
ai = os.path.join(root, "insightface", "app", "__init__.py")
open(ai, "w").write("from .face_analysis import *\n")

print("patched", root)
PY

echo "==> Installing (no build isolation, no deps)"
"$PY" -m pip install --no-deps --no-build-isolation "$TMP/insightface-0.7.3"

echo "==> Done. Verify:"
"$PY" -c "import insightface; print('insightface', insightface.__version__)"
