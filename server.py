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

from ai_dubbing.src.tts_engines import get_tts_engine, TTS_ENGINES, cleanup_all_engines
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

tasks = {}  # 配音任务
optimization_tasks = {}  # 字幕优化任务


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


@app.get("/dubbing/built-in-audios")
async def get_built_in_audios():
    """Get built-in reference audios from dubbing.conf."""
    config = configparser.ConfigParser()
    config.read(CONFIG_FILE, encoding="utf-8")

    prefix = "内置音频:"

    audio_sections = [s for s in config.sections() if s.startswith(prefix)]

    return {
        section[len(prefix):]: {
            "path": config.get(section, "path"),
            "text": config.get(section, "text"),
        }
        for section in audio_sections
        if config.has_option(section, "path") and config.has_option(section, "text")
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
        },
        "index_tts2_emotion": {
            "emotion_mode": config.get("IndexTTS2情感控制", "emotion_mode", fallback="auto"),
            "emotion_audio_file": config.get("IndexTTS2情感控制", "emotion_audio_file", fallback=""),
            "emotion_vector": config.get("IndexTTS2情感控制", "emotion_vector", fallback=""),
            "emotion_text": config.get("IndexTTS2情感控制", "emotion_text", fallback=""),
            "emotion_alpha": config.getfloat("IndexTTS2情感控制", "emotion_alpha", fallback=0.8),
            "use_random": config.getboolean("IndexTTS2情感控制", "use_random", fallback=False),
        }
    }
    return config_data


@app.post("/dubbing/config")
async def set_dubbing_config(request: Request):
    """Update subtitile optimization runtime config in dubbing.conf."""
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


def run_subtitle_optimization(
    task_id: str,
    input_path: Path,
    output_path: Path,
):
    """Run the subtitle optimization process and update task status."""
    try:
        optimization_tasks[task_id] = {"status": "processing", "progress": 0, "result_url": None, "message": "初始化字幕优化..."}
        
        # 导入字幕优化相关模块
        from ai_dubbing.run_optimize_subtitles import optimize_srt_file, load_config_from_file
        
        optimization_tasks[task_id]["progress"] = 10
        optimization_tasks[task_id]["message"] = "加载配置文件..."
        
        # 加载配置
        config = load_config_from_file()
        if not config.get('api_key'):
            raise ValueError("未配置LLM API密钥，请在配置中设置 llm_api_key")
        
        optimization_tasks[task_id]["progress"] = 30
        optimization_tasks[task_id]["message"] = "开始字幕优化处理..."
        
        # 执行字幕优化
        result_path = optimize_srt_file(str(input_path), str(output_path), config)
        
        if result_path:
            optimization_tasks[task_id]["progress"] = 100
            optimization_tasks[task_id]["status"] = "completed"
            optimization_tasks[task_id]["result_url"] = f"/results/{Path(result_path).name}"
            optimization_tasks[task_id]["message"] = "字幕优化完成"
        else:
            raise ValueError("字幕优化失败")
            
    except Exception as e:
        optimization_tasks[task_id]["status"] = "failed"
        optimization_tasks[task_id]["error"] = str(e)
        optimization_tasks[task_id]["message"] = "字幕优化失败"


def run_dubbing(
    task_id: str,
    input_path: Path,
    voice_paths: List[str],
    output_path: Path,
    tts_engine_name: str,
    strategy_name: str,
    language: str = "zh",
    prompt_texts: List[str] | None = None,
    emotion_config: dict = None,
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
        
        # 添加IndexTTS2情感控制参数
        if emotion_config:
            # 将emotion_config（情感控制参数字典）中的所有键值对，合并到runtime_kwargs参数字典中，用于后续TTS处理时传递情感相关配置
            runtime_kwargs.update(emotion_config)
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
    input_mode: str = Form("file"),  # 新增：输入模式，默认为文件模式
    input_file: UploadFile = File(None),  # 修改：变为可选
    input_text: str = Form(None),  # 新增：文本输入内容
    text_format: str = Form("txt"),  # 新增：文本格式
    voice_files: List[UploadFile] = File(...),
    voice_files_paths: List[str] = Form(...),
    prompt_texts: List[str] = Form(...),
    tts_engine: str = Form(...),
    strategy: str = Form(...),
    language: str = Form("zh"),
    # IndexTTS2情感控制参数 (可选)
    emotion_mode: str = Form("auto"),
    emotion_audio_file: UploadFile = File(None),
    emotion_vector: str = Form(""),
    emotion_text: str = Form(""),
    emotion_alpha: float = Form(0.8),
    use_random: bool = Form(False),
):
    """Process an upload and return the generated audio path."""
    task_id = uuid.uuid4().hex
    config = configparser.ConfigParser()
    config.read(CONFIG_FILE, encoding="utf-8")
    optimized_srt_dir = config.get("字幕优化配置", "optimized_srt_output_file", fallback=None)

    # 验证输入模式和参数
    if input_mode == "file":
        if not input_file:
            raise HTTPException(status_code=400, detail="文件模式下必须提供输入文件")
        input_path = UPLOAD_DIR / input_file.filename
        with open(input_path, "wb") as f:
            f.write(await input_file.read())
    elif input_mode == "text":
        if not input_text or not input_text.strip():
            raise HTTPException(status_code=400, detail="文本模式下必须提供输入文本")
        
        allowed_text_formats = {"txt", "srt"}
        normalized_text_format = (text_format or "").strip().lower()
        if normalized_text_format not in allowed_text_formats:
            raise HTTPException(status_code=400, detail="不支持的文本格式")
        
        # 创建临时文件保存文本内容
        temp_filename = f"temp_{task_id}.{normalized_text_format}"
        input_path = UPLOAD_DIR / temp_filename
        with open(input_path, "w", encoding="utf-8") as f:
            f.write(input_text.strip())
    else:
        raise HTTPException(status_code=400, detail="不支持的输入模式")

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
            final_voice_paths.append(path_from_config)

    if len(final_voice_paths) != len(prompt_texts):
        raise HTTPException(
            status_code=400,
            detail=f"Mismatch between voice files ({len(final_voice_paths)}) and prompts ({len(prompt_texts)}).",
        )

    # 处理IndexTTS2情感音频文件
    emotion_audio_path = None
    if tts_engine == "index_tts2" and emotion_mode == "audio" and emotion_audio_file and emotion_audio_file.size > 0:
        emotion_audio_path = UPLOAD_DIR / f"emotion_{uuid.uuid4().hex}_{emotion_audio_file.filename}"
        with open(emotion_audio_path, "wb") as f:
            f.write(await emotion_audio_file.read())

    # 构建情感配置参数
    emotion_config = {}
    if tts_engine == "index_tts2":
        if emotion_mode == "audio" and emotion_audio_path:
            emotion_config["emotion_audio_file"] = str(emotion_audio_path)
        elif emotion_mode == "vector" and emotion_vector:
            try:
                emotion_config["emotion_vector"] = [float(x.strip()) for x in emotion_vector.split(',')]
            except ValueError:
                pass  # 忽略格式错误，使用默认值
        elif emotion_mode == "text" and emotion_text:
            emotion_config["emotion_text"] = emotion_text
        elif emotion_mode == "auto":
            emotion_config["auto_emotion"] = True
        
        emotion_config["emotion_alpha"] = emotion_alpha
        emotion_config["use_random"] = use_random

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
        emotion_config=emotion_config,
    )

    return {"task_id": task_id}


@app.get("/dubbing/status/{task_id}")
async def get_dubbing_status(task_id: str):
    """Get the status of a dubbing task."""
    task = tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@app.get("/subtitle-optimization/status/{task_id}")
async def get_optimization_status(task_id: str):
    """Get the status of a subtitle optimization task."""
    task = optimization_tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@app.post("/subtitle-optimization")
async def create_subtitle_optimization(
    background_tasks: BackgroundTasks,
    input_file: UploadFile = File(...),
):
    """Process subtitle optimization and return the optimized file."""
    task_id = uuid.uuid4().hex
    
    # 检查文件类型
    if not input_file.filename.lower().endswith('.srt'):
        raise HTTPException(status_code=400, detail="仅支持.srt格式的字幕文件")
    
    # 保存上传的文件
    input_path = UPLOAD_DIR / input_file.filename
    with open(input_path, "wb") as f:
        f.write(await input_file.read())
    
    # 生成输出文件路径
    output_filename = f"optimized_{uuid.uuid4().hex}.srt"
    output_path = RESULT_DIR / output_filename
    
    # 启动后台任务
    background_tasks.add_task(
        run_subtitle_optimization,
        task_id=task_id,
        input_path=input_path,
        output_path=output_path,
    )
    
    return {"task_id": task_id}


@app.post("/dubbing/cleanup")
async def cleanup_gpu_memory():
    """手动清理所有TTS引擎的GPU内存"""
    try:
        cleanup_all_engines()
        return {"status": "success", "message": "GPU内存已清理"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"清理GPU内存失败: {str(e)}")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
