from __future__ import annotations

from pathlib import Path
from typing import List
import uuid
import sys
import configparser

from fastapi import FastAPI, Request, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

from ai_dubbing.src.tts_engines import get_tts_engine, TTS_ENGINES
from ai_dubbing.src.strategies import get_strategy, list_available_strategies
from ai_dubbing.src.parsers import SRTParser, TXTParser
from ai_dubbing.src.audio_processor import AudioProcessor

app = FastAPI()

TEMPLATE_DIR = Path("ai_dubbing/web/templates")
STATIC_DIR = Path("ai_dubbing/web/static")
RESULT_DIR = Path("outputs")
UPLOAD_DIR = Path("uploads")

TEMPLATE_DIR.mkdir(parents=True, exist_ok=True)
STATIC_DIR.mkdir(parents=True, exist_ok=True)
RESULT_DIR.mkdir(exist_ok=True)
UPLOAD_DIR.mkdir(exist_ok=True)

CONFIG_FILE = Path("ai_dubbing/dubbing.conf")

templates = Jinja2Templates(directory=str(TEMPLATE_DIR))
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
app.mount("/results", StaticFiles(directory=str(RESULT_DIR)), name="results")

tasks = {}


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


@app.get("/dubbing/config")
async def get_dubbing_config():
    """Get runtime config from dubbing.conf."""
    config = configparser.ConfigParser()
    config.read(CONFIG_FILE, encoding="utf-8")
    
    config_data = {
        "basic": {
            "voice_files": config.get("基本配置", "voice_files", fallback=""),
            "prompt_texts": config.get("基本配置", "prompt_texts", fallback=""),
            "tts_engine": config.get("基本配置", "tts_engine", fallback="fish_speech"),
            "strategy": config.get("基本配置", "strategy", fallback="stretch"),
            "language": config.get("高级配置", "language", fallback="zh"),
        },
        "concurrency": {
            "tts_max_concurrency": config.getint("并发配置", "tts_max_concurrency", fallback=8),
            "tts_max_retries": config.getint("并发配置", "tts_max_retries", fallback=2),
        },
        "subtitle_optimization": {
            "llm_api_key": config.get("字幕优化配置", "llm_api_key", fallback=""),
            "llm_model": config.get("字幕优化配置", "llm_model", fallback=""),
            "base_url": config.get("字幕优化配置", "base_url", fallback=""),
            "chinese_char_min_time": config.getint("字幕优化配置", "chinese_char_min_time", fallback=150),
            "english_word_min_time": config.getint("字幕优化配置", "english_word_min_time", fallback=250),
            "llm_max_concurrency": config.getint("字幕优化配置", "llm_max_concurrency", fallback=50),
            "llm_max_retries": config.getint("字幕优化配置", "llm_max_retries", fallback=3),
            "llm_timeout": config.getint("字幕优化配置", "llm_timeout", fallback=60),
            "optimized_srt_output_file": config.get("字幕优化配置", "optimized_srt_output_file", fallback=""),
        },
        "time_borrowing": {
            "min_gap_threshold": config.getint("时间借用配置", "min_gap_threshold", fallback=200),
            "borrow_ratio": config.getfloat("时间借用配置", "borrow_ratio", fallback=1.0),
            "extra_buffer": config.getint("时间借用配置", "extra_buffer", fallback=200),
        }
    }
    return config_data


@app.post("/dubbing/config")
async def set_dubbing_config(request: Request):
    """Update runtime config in dubbing.conf."""
    data = await request.json()
    config = configparser.ConfigParser()
    config.read(CONFIG_FILE, encoding="utf-8")

    def ensure_section(section):
        if not config.has_section(section):
            config.add_section(section)

    ensure_section("并发配置")
    for key, value in data["concurrency"].items():
        config.set("并发配置", key, str(value))

    ensure_section("字幕优化配置")
    for key, value in data["subtitle_optimization"].items():
        config.set("字幕优化配置", key, str(value))

    ensure_section("时间借用配置")
    for key, value in data["time_borrowing"].items():
        config.set("时间借用配置", key, str(value))

    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        config.write(f)
    return {"status": "success"}


def run_dubbing(
    task_id: str,
    input_path: Path,
    voice_paths: List[str],
    output_path: Path,
    tts_engine_name: str,
    strategy_name: str,
    language: str = "zh",
    prompt_texts: List[str] | None = None,
):
    """Run the dubbing process and update task status."""
    try:
        tasks[task_id] = {"status": "processing", "progress": 0, "result_url": None, "message": "Initializing..."}
        
        config = configparser.ConfigParser()
        config.read(CONFIG_FILE, encoding="utf-8")
        max_concurrency = config.getint("并发配置", "tts_max_concurrency", fallback=1)
        max_retries = config.getint("并发配置", "tts_max_retries", fallback=2)

        def progress_callback(current, total):
            progress = 50 + int((current / total) * 40)  # Scale progress from 50 to 90
            tasks[task_id]["progress"] = progress
            tasks[task_id]["message"] = f"正在处理第 {current}/{total} 条字幕"
        
        if prompt_texts is None:
            prompt_texts = []

        if len(voice_paths) != len(prompt_texts):
            raise ValueError("The number of voice files and prompt texts must be the same.")

        is_txt_mode = input_path.suffix.lower() == ".txt"

        # 1. Initialize TTS engine
        tasks[task_id]["progress"] = 10
        tts_engine_instance = get_tts_engine(tts_engine_name)

        # 2. Parse file
        tasks[task_id]["progress"] = 20
        if is_txt_mode:
            parser_instance = TXTParser(language=language)
        else:
            parser_instance = SRTParser()
        entries = parser_instance.parse_file(str(input_path))

        # 3. Initialize processing strategy
        tasks[task_id]["progress"] = 30
        if is_txt_mode and strategy_name != "basic":
            strategy_name = "basic"
        strategy_instance = get_strategy(strategy_name, tts_engine=tts_engine_instance)

        # 4. Generate audio segments
        tasks[task_id]["progress"] = 50
        tasks[task_id]["message"] = "开始生成音频片段"
        runtime_kwargs = {
            "prompt_text": prompt_texts[0] if prompt_texts else "",
            "ref_text": prompt_texts[0] if prompt_texts else "",
            "voice_files": voice_paths,
            "prompt_texts": prompt_texts,
            "max_concurrency": max_concurrency,
            "max_retries": max_retries,
            "progress_callback": progress_callback,
        }
        audio_segments = strategy_instance.process_entries(
            entries, voice_reference=voice_paths[0], **runtime_kwargs
        )

        # 5. Merge and export audio
        tasks[task_id]["progress"] = 90
        tasks[task_id]["message"] = "正在合并音频"
        processor = AudioProcessor()
        merged_audio = processor.merge_audio_segments(
            audio_segments, strategy_name=strategy_name
        )
        processor.export_audio(merged_audio, str(output_path))

        tasks[task_id]["progress"] = 100
        tasks[task_id]["status"] = "completed"
        tasks[task_id]["result_url"] = f"/results/{output_path.name}"

    except Exception as e:
        tasks[task_id]["status"] = "failed"
        tasks[task_id]["error"] = str(e)
        tasks[task_id]["message"] = "处理失败"


@app.post("/dubbing")
async def create_dubbing(
    background_tasks: BackgroundTasks,
    input_file: UploadFile = File(...),
    voice_files: List[UploadFile] = File(...),
    voice_files_paths: List[str] = Form(...),
    prompt_texts: List[str] = Form(...),
    tts_engine: str = Form(...),
    strategy: str = Form(...),
    language: str = Form("zh"),
):
    """Process an upload and return the generated audio path."""
    task_id = uuid.uuid4().hex
    config = configparser.ConfigParser()
    config.read(CONFIG_FILE, encoding="utf-8")
    optimized_srt_dir = config.get("字幕优化配置", "optimized_srt_output_file", fallback=None)

    input_path = UPLOAD_DIR / input_file.filename
    with open(input_path, "wb") as f:
        f.write(await input_file.read())

    if optimized_srt_dir and Path(optimized_srt_dir).is_dir():
        print(f"Optimized SRT would be saved in: {optimized_srt_dir}")

    # Process voice files, combining new uploads and existing paths
    final_voice_paths = []
    for i, uploaded_file in enumerate(voice_files):
        if uploaded_file.size > 0:
            file_path = UPLOAD_DIR / uploaded_file.filename
            with open(file_path, "wb") as f:
                f.write(await uploaded_file.read())
            final_voice_paths.append(str(file_path))
        elif i < len(voice_files_paths) and voice_files_paths[i]:
            path_from_config = voice_files_paths[i]
            if ".." in path_from_config or path_from_config.startswith(("/", "\\")):
                raise HTTPException(status_code=400, detail=f"Invalid file path: {path_from_config}")
            final_voice_paths.append(path_from_config)

    if len(final_voice_paths) != len(prompt_texts):
        raise HTTPException(
            status_code=400,
            detail=f"Mismatch between voice files ({len(final_voice_paths)}) and prompts ({len(prompt_texts)}).",
        )

    output_path = RESULT_DIR / f"{uuid.uuid4().hex}.wav"

    background_tasks.add_task(
        run_dubbing,
        task_id=task_id,
        input_path=input_path,
        voice_paths=final_voice_paths,
        output_path=output_path,
        tts_engine_name=tts_engine,
        strategy_name=strategy,
        language=language,
        prompt_texts=prompt_texts,
    )

    return {"task_id": task_id}


@app.get("/dubbing/status/{task_id}")
async def get_dubbing_status(task_id: str):
    """Get the status of a dubbing task."""
    task = tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
