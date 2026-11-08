#!/usr/bin/env bash
# Download AI4Bharat Indic Parler-TTS (the Indian English / Telugu voice, src/models/tts_indicparler.py) into PARLER_DIR.
# The model is gated: accept its terms once at https://huggingface.co/ai4bharat/indic-parler-tts, then run with a
# read token:  HF_TOKEN=hf_... bash scripts/indic_parler_download.sh
# Also installs the parler-tts package into $PY's environment if it is missing. If PARLER_DIR already holds the model
# (copied from someone who downloaded it), no token is needed: only the public description tokenizer is fetched.
set -euo pipefail

PY="${PY:-/home/andyshi2/.conda/envs/ai-livestream/bin/python}"
export PARLER_DIR="${PARLER_DIR:-/home/andyshi2/pre-models/indic-parler-tts}"
[ -f "$PARLER_DIR/config.json" ] || : "${HF_TOKEN:?set HF_TOKEN to a Hugging Face read token that has accepted the model terms}"

"$PY" -c "import parler_tts" 2>/dev/null || "$PY" -m pip install -q "git+https://github.com/huggingface/parler-tts.git"

HF_HUB_OFFLINE=0 "$PY" - <<'EOF'
import json, os
from pathlib import Path
from huggingface_hub import snapshot_download
from transformers import AutoTokenizer

out = Path(os.environ["PARLER_DIR"])
if os.environ.get("HF_TOKEN"):
    snapshot_download("ai4bharat/indic-parler-tts", local_dir=out, token=os.environ["HF_TOKEN"])
encoder = json.loads((out / "config.json").read_text())["text_encoder"]["_name_or_path"]
AutoTokenizer.from_pretrained(encoder).save_pretrained(out / "description_tokenizer")
print(f"Indic Parler-TTS in {out} (description tokenizer from {encoder})")
EOF
