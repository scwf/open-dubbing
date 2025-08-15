from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from ai_dubbing.src.utils import setup_project_path
from ai_dubbing.src.parsers import SRTParser, TXTParser
from ai_dubbing.src.tts_engines import get_tts_engine
from ai_dubbing.src.strategies import get_strategy
from ai_dubbing.src.audio_processor import AudioProcessor
from ai_dubbing.src.config import PATH

import tempfile
import shutil
from typing import Optional

# Ensure project paths are set up
setup_project_path()

app = FastAPI()


@app.post("/dubbing")
async def dubbing(
    srt: UploadFile | None = File(default=None),
    txt: UploadFile | None = File(default=None),
    voice: UploadFile = File(...),
    tts_engine: str = Form("index_tts"),
    strategy: str = Form("stretch"),
    language: str = Form("zh"),
    prompt_text: Optional[str] = Form(default=None),
    ref_text: Optional[str] = Form(default=None),
):
    """Generate a dubbed audio file from subtitles or plain text."""
    # Validate input: exactly one of srt or txt must be provided
    if (srt is None and txt is None) or (srt is not None and txt is not None):
        raise HTTPException(status_code=400, detail="Either srt or txt file must be provided.")

    is_txt_mode = txt is not None
    input_upload = txt if is_txt_mode else srt

    # Save uploaded files to temporary paths
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt" if is_txt_mode else ".srt") as tmp_in:
            shutil.copyfileobj(input_upload.file, tmp_in)
            input_path = tmp_in.name
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp_voice:
            shutil.copyfileobj(voice.file, tmp_voice)
            voice_path = tmp_voice.name
    finally:
        input_upload.file.close()
        voice.file.close()

    try:
        engine = get_tts_engine(tts_engine)

        parser = TXTParser(language=language) if is_txt_mode else SRTParser()
        entries = parser.parse_file(input_path)

        if is_txt_mode and strategy != "basic":
            strategy = "basic"
        strat = get_strategy(strategy, tts_engine=engine)

        effective_ref_text = ref_text if ref_text else prompt_text
        runtime_kwargs = {"prompt_text": prompt_text, "ref_text": effective_ref_text}

        segments = strat.process_entries(entries, voice_reference=voice_path, **runtime_kwargs)

        processor = AudioProcessor()
        merged = processor.merge_audio_segments(segments, strategy_name=strategy, truncate_on_overflow=False)

        output_path = PATH.get_default_output_path()
        if not processor.export_audio(merged, output_path):
            raise RuntimeError("Failed to export audio")
    except Exception as e:  # pragma: no cover - just wrap any runtime failure
        raise HTTPException(status_code=500, detail=str(e))

    return {"status": "ok", "output": output_path}
