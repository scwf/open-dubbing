from __future__ import annotations

from pathlib import Path
from typing import List
import uuid
import sys

from fastapi import FastAPI, Request, UploadFile, File, Form, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

from ai_dubbing.src.tts_engines import TTS_ENGINES
from ai_dubbing.src.strategies import list_available_strategies
from ai_dubbing.src.cli import main as cli_main

app = FastAPI()

TEMPLATE_DIR = Path("ai_dubbing/web/templates")
STATIC_DIR = Path("ai_dubbing/web/static")
RESULT_DIR = Path("outputs")
UPLOAD_DIR = Path("uploads")

TEMPLATE_DIR.mkdir(parents=True, exist_ok=True)
STATIC_DIR.mkdir(parents=True, exist_ok=True)
RESULT_DIR.mkdir(exist_ok=True)
UPLOAD_DIR.mkdir(exist_ok=True)

templates = Jinja2Templates(directory=str(TEMPLATE_DIR))
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
app.mount("/results", StaticFiles(directory=str(RESULT_DIR)), name="results")


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Render the main UI."""
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/dubbing/options")
async def dubbing_options():
    """Expose available engines, strategies and languages."""
    languages = ["zh", "en", "ja", "ko"]
    return {
        "tts_engines": list(TTS_ENGINES.keys()),
        "strategies": list_available_strategies(),
        "languages": languages,
    }


@app.post("/dubbing")
async def create_dubbing(
    input_file: UploadFile = File(...),
    voice_files: List[UploadFile] = File(...),
    prompt_text: str = Form(""),
    tts_engine: str = Form(...),
    strategy: str = Form(...),
    language: str = Form("zh"),
):
    """Process an upload and return the generated audio path."""
    input_path = UPLOAD_DIR / input_file.filename
    with open(input_path, "wb") as f:
        f.write(await input_file.read())

    voice_paths = []
    for vf in voice_files:
        vp = UPLOAD_DIR / vf.filename
        with open(vp, "wb") as f:
            f.write(await vf.read())
        voice_paths.append(str(vp))

    output_path = RESULT_DIR / f"{uuid.uuid4().hex}.wav"

    args = ["prog"]
    if input_path.suffix.lower() == ".srt":
        args += ["--srt", str(input_path)]
    else:
        args += ["--txt", str(input_path), "--lang", language]
    args += [
        "--voice",
        voice_paths[0],
        "--output",
        str(output_path),
        "--tts-engine",
        tts_engine,
        "--strategy",
        strategy,
    ]
    if prompt_text:
        args += ["--prompt-text", prompt_text]

    sys.argv = args
    exit_code = cli_main()
    if exit_code != 0:
        raise HTTPException(status_code=400, detail="dubbing failed")

    return {"result_url": f"/results/{output_path.name}"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
