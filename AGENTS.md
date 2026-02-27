# AGENTS.md

## Cursor Cloud specific instructions

### Project Overview

AI Dubbing (AI配音工具) — a FastAPI web application for AI voice dubbing/cloning. Converts SRT subtitles or TXT text into dubbed audio using TTS engines. See `README.md` for full architecture and usage.

### Running the Application

- **Server**: `python server.py` — starts FastAPI/Uvicorn on port 8000.
- **Tests**: `python -m pytest ai_dubbing/test/ -v` — runs all unit tests (26 tests covering parsers and LLM optimizer).
- The web UI is served at `http://localhost:8000`.

### Key Caveats

- **No GPU in cloud VM**: The TTS engines (fish_speech, index_tts, etc.) require CUDA GPU. The server starts fine without GPU — TTS engine initialization only occurs when a dubbing task is submitted. The web UI, API endpoints, config management, and subtitle optimization features all work without GPU.
- **PyTorch CPU**: Install `torch` from the CPU index (`--index-url https://download.pytorch.org/whl/cpu`) since all TTS engine modules import `torch` at module load time. Without it, the server cannot start.
- **python-multipart**: Required by FastAPI for file upload endpoints but not listed in `requirements.txt`. Must be installed separately.
- **Config files**: The server expects `ai_dubbing/dubbing.conf` (copy from `ai_dubbing/dubbing.conf.example`) and `ai_dubbing/.env` (copy from `ai_dubbing/.env.example`, set absolute paths).
- **No linter configured**: The project has no linting configuration (no pyproject.toml, setup.cfg, or lint scripts). Standard Python linting can be done with `python -m py_compile` on individual files.
- **PATH for pip scripts**: User-installed pip scripts go to `~/.local/bin` which may not be on PATH. Export `PATH="$HOME/.local/bin:$PATH"` if needed.
