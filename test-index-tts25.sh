#!/bin/bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
INPUT_FILE="${1:-$PROJECT_DIR/resources/test-subtitles.srt}"
OUTPUT_FILE="$PROJECT_DIR/output/test-index-tts25.wav"

cd "$PROJECT_DIR"

conda run -n index-tts25 --no-capture-output env INDEX_TTS_VARIANT=2.5 python ai_dubbing/run_dubbing.py \
  --input-file "$INPUT_FILE" \
  --output-file "$OUTPUT_FILE" \
  --tts-engine index_tts25 \
  --language zh
