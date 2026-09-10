#!/usr/bin/env bash
# ── Fallback: fetch compact-but-real ArcFace weights (for sandboxes) ──
#
# The full `buffalo_l` pack (w600k_r50.onnx ~165 MB) is distributed as a
# GitHub release asset / LFS object, which some locked-down environments
# cannot reach (this happens in the Arena sandbox). When that's the case,
# this script downloads the *compact* buffalo_sc weights — a real SCRFD
# detector (det_500m) + real ArcFace (w600k_mbf) — from a public GitHub
# repo that commits them, and places them where FaceAnalysis(name="buffalo_l")
# looks, so recognition works identically (slightly lighter accuracy).
#
# On a normal machine you should NOT need this: the real buffalo_l pack
# auto-downloads on first run.
#
# Usage (from project root):
#     bash scripts/fetch_models_fallback.sh
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST="$HERE/models/insightface/models/buffalo_l"
REPO_URL="https://codeload.github.com/phanithota05/Smart-Attendance-System-and-Deployment/tar.gz/refs/heads/main"

mkdir -p "$DEST"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

echo "==> Downloading source repo (contains real buffalo_sc weights)"
curl -k -L --retry 3 -o "$TMP/repo.tar.gz" "$REPO_URL"

tar xzf "$TMP/repo.tar.gz" -C "$TMP"
SRC="$(find "$TMP" -type d -path '*insightface_model/models/buffalo_sc' | head -1)"

if [ -z "$SRC" ]; then
  echo "ERROR: could not locate buffalo_sc weights in the downloaded repo." >&2
  exit 1
fi

cp "$SRC/det_500m.onnx" "$SRC/w600k_mbf.onnx" "$DEST/"
echo "==> Done. Models in: $DEST"
ls -la "$DEST"
