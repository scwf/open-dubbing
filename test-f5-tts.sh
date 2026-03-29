#!/bin/bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
INPUT_FILE="${1:-$PROJECT_DIR/resources/test-subtitles.srt}"
OUTPUT_FILE="$PROJECT_DIR/output/test-f5-tts.wav"

cd "$PROJECT_DIR"

conda run -n f5-tts --no-capture-output python ai_dubbing/run_dubbing.py \
  --input-file "$INPUT_FILE" \
  --output-file "$OUTPUT_FILE" \
  --tts-engine f5_tts
