#!/bin/bash
# ─────────────────────────────────────────────────────────────────
# download_vectors.sh
# Downloads the pre-trained FastText Kazakh word vectors from Meta AI.
# Run this ONCE before starting the backend for the first time.
#
# Usage:
#   chmod +x scripts/download_vectors.sh
#   ./scripts/download_vectors.sh
# ─────────────────────────────────────────────────────────────────

set -e

DATA_DIR="$(dirname "$0")/../data"
VEC_FILE="$DATA_DIR/wiki.kk.vec"
URL="https://dl.fbaipublicfiles.com/fasttext/vectors-wiki/wiki.kk.vec"

mkdir -p "$DATA_DIR"

if [ -f "$VEC_FILE" ]; then
  echo "✅  Vectors already exist at $VEC_FILE"
  echo "    Delete the file and re-run if you want to re-download."
  exit 0
fi

echo "📥  Downloading Kazakh FastText vectors (~600 MB)..."
echo "    Source: $URL"
echo ""

if command -v wget &> /dev/null; then
  wget -q --show-progress -O "$VEC_FILE" "$URL"
elif command -v curl &> /dev/null; then
  curl -L --progress-bar -o "$VEC_FILE" "$URL"
else
  echo "❌  Neither wget nor curl found. Please install one and retry."
  exit 1
fi

echo ""
echo "✅  Download complete: $VEC_FILE"
echo ""
echo "Next step: start the backend — it will auto-build a fast numpy"
echo "cache on first run (takes ~2 min, then loads in seconds)."
echo ""
echo "  cd backend && uvicorn main:app --reload"
