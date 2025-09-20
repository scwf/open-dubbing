from __future__ import annotations

from pathlib import Path
from typing import List
import uuid
import configparser
import threading
from concurrent.futures import ThreadPoolExecutor

from fastapi import FastAPI, Request, UploadFile, File, Form, HTTPException
from contextlib import asynccontextmanager
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

from ai_dubbing.src.tts_engines import get_tts_engine, TTS_ENGINES, cleanup_all_engines
from ai_dubbing.src.strategies import get_strategy, list_available_strategies
from ai_dubbing.src.parsers import SRTParser, TXTParser
from ai_dubbing.src.audio_processor import AudioProcessor

@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI应用生命周期管理器 - 处理启动和关闭"""
    # 启动时：清除之前可能残留的关闭标志（重要：支持应用重启）
    shutdown_flag.clear()
    
    # 创建新的任务执行器（重要：支持应用重启）
    create_task_executor()
    
    yield
    # 关闭时的清理操作
    print("\n🛑 正在优雅关闭服务器...")
    try:
        # 设置关闭标志
        shutdown_flag.set()
        
        # 标记所有正在运行的任务为已取消
        cancelled_count = 0
        for task_id in list(running_tasks.keys()):
            if task_id in tasks:
                tasks[task_id]["status"] = "cancelled"
                tasks[task_id]["message"] = "服务器关闭，任务被取消"
                cancelled_count += 1
        
        if cancelled_count > 0:
            print(f"📋 已标记 {cancelled_count} 个任务为已取消")
        
        # 关闭线程池（重要：先等待worker线程停止）
        print("🔒 正在关闭任务执行器...")
        safe_shutdown_executor(wait=True)
        print("✅ 任务执行器已关闭")
        
        # 清理GPU内存（重要：在worker线程停止后才清理）
        print("🧹 正在清理GPU资源...")
        cleanup_all_engines()
        print("✅ GPU资源已清理")
        
        print("🎉 服务器已优雅关闭")
        
    except Exception as e:
        print(f"❌ 关闭过程中出错: {e}")

app = FastAPI(lifespan=lifespan)

# 获取项目根目录（server.py所在目录）
PROJECT_ROOT = Path(__file__).parent.resolve()

TEMPLATE_DIR = PROJECT_ROOT / "ai_dubbing/web/templates"
STATIC_DIR = PROJECT_ROOT / "ai_dubbing/web/static"
RESULT_DIR = PROJECT_ROOT / "outputs"
UPLOAD_DIR = PROJECT_ROOT / "uploads"

TEMPLATE_DIR.mkdir(parents=True, exist_ok=True)
STATIC_DIR.mkdir(parents=True, exist_ok=True)
RESULT_DIR.mkdir(exist_ok=True)
UPLOAD_DIR.mkdir(exist_ok=True)

CONFIG_FILE = PROJECT_ROOT / "ai_dubbing/dubbing.conf"

templates = Jinja2Templates(directory=str(TEMPLATE_DIR))
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
app.mount("/results", StaticFiles(directory=str(RESULT_DIR)), name="results")

tasks = {}  # 配音任务
optimization_tasks = {}  # 字幕优化任务
running_tasks = {}  # 正在运行的任务线程
shutdown_flag = threading.Event()  # 关闭标志
executor_lock = threading.Lock()  # 线程池关闭锁
task_executor = None  # 线程池执行器（将在启动时创建）

def create_task_executor():
    """创建新的任务执行器"""
    global task_executor
    with executor_lock:
        # 如果旧的执行器存在且未关闭，先关闭它
        if task_executor and hasattr(task_executor, '_shutdown') and not task_executor._shutdown:
            task_executor.shutdown(wait=False)
        
        # 创建新的执行器
        task_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="dubbing-task-")
        print("✅ 任务执行器已创建")

def safe_shutdown_executor(wait=False):
    """安全关闭线程池，避免重复关闭"""
    with executor_lock:
        if task_executor and hasattr(task_executor, '_shutdown') and not task_executor._shutdown:
            task_executor.shutdown(wait=wait)
            print("任务执行器已关闭")
            return True
    return False

def resolve_audio_path(path_str: str) -> str:
    """Resolve audio file path relative to project root."""
    path = Path(path_str)
    if path.is_absolute():
        return str(path)
    else:
        # 相对路径基于项目根目录解析
        resolved_path = PROJECT_ROOT / path
        return str(resolved_path)

def resolve_audio_paths_list(paths_str: str) -> str:
    """Resolve comma-separated audio file paths relative to project root."""
    if not paths_str.strip():
        return ""
    
    paths = [path.strip() for path in paths_str.split(',')]
    resolved_paths = [resolve_audio_path(path) for path in paths if path.strip()]
    return ','.join(resolved_paths)

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
            "path": resolve_audio_path(config.get(section, "path")),
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
            "voice_files": resolve_audio_paths_list(config.get("基本配置", "voice_files", fallback="")),
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


@app.post("/dubbing")
async def create_dubbing(
    input_mode: str = Form("file"),  # 新增：输入模式，默认为文件模式
    input_file: UploadFile = File(None),  # 修改：变为可选
    input_text: str = Form(None),  # 新增：文本输入内容
    text_format: str = Form("txt"),  # 新增：文本格式
    upload_voice_files: List[UploadFile] = File(...),
    builtin_voice_files: List[str] = Form(...),
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
    for i, uploaded_file in enumerate(upload_voice_files):
        if uploaded_file.size > 0:
            file_path = UPLOAD_DIR / uploaded_file.filename
            with open(file_path, "wb") as f:
                f.write(await uploaded_file.read())
            final_voice_paths.append(str(file_path))
        elif i < len(builtin_voice_files) and builtin_voice_files[i]:
            path_from_config = resolve_audio_path(builtin_voice_files[i])
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

    # 立即注册任务状态（重要：支持排队期间的状态查询和取消）
    tasks[task_id] = {
        "status": "queued", 
        "progress": 0, 
        "result_url": None, 
        "message": "任务已接收，等待处理..."
    }

    # 使用自定义线程池执行任务，以便更好地控制中断
    task_executor.submit(
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

def run_subtitle_optimization(
    task_id: str,
    input_path: Path,
    output_path: Path,
):
    """Run the subtitle optimization process and update task status."""
    
    def check_optimization_cancellation():
        """检查字幕优化任务是否应该被取消"""
        if shutdown_flag.is_set():
            raise KeyboardInterrupt("服务器正在关闭，任务被取消")
        if task_id in optimization_tasks and optimization_tasks[task_id].get("status") == "cancelled":
            raise KeyboardInterrupt("任务被用户取消")
    
    try:
        # 立即检查是否应该取消
        check_optimization_cancellation()
        
        # 更新任务状态为处理中（从排队状态转换）
        optimization_tasks[task_id]["status"] = "processing"
        optimization_tasks[task_id]["message"] = "字幕优化任务开始处理..."
        
        # 导入字幕优化相关模块
        from ai_dubbing.run_optimize_subtitles import optimize_srt_file, load_subtitile_optimize_config
        
        optimization_tasks[task_id]["progress"] = 10
        optimization_tasks[task_id]["message"] = "加载配置文件..."
        
        # 检查取消状态
        check_optimization_cancellation()
        
        # 加载配置
        config = load_subtitile_optimize_config()
        
        optimization_tasks[task_id]["progress"] = 30
        optimization_tasks[task_id]["message"] = "开始字幕优化处理..."
        
        # 检查取消状态
        check_optimization_cancellation()
        
        # 执行字幕优化
        result_path = optimize_srt_file(str(input_path), str(output_path), config)
        
        if result_path:
            optimization_tasks[task_id]["progress"] = 100
            optimization_tasks[task_id]["status"] = "completed"
            optimization_tasks[task_id]["result_url"] = f"/results/{Path(result_path).name}"
            optimization_tasks[task_id]["message"] = "字幕优化完成"
        else:
            raise ValueError("字幕优化失败")
            
    except KeyboardInterrupt as e:
        # 处理用户中断或服务器关闭
        optimization_tasks[task_id]["status"] = "cancelled"
        optimization_tasks[task_id]["message"] = str(e)
        print(f"字幕优化任务 {task_id} 被中断: {e}")
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
    # 将任务添加到运行任务列表
    running_tasks[task_id] = threading.current_thread()
    
    def check_cancellation():
        """检查任务是否应该被取消"""
        if shutdown_flag.is_set():
            raise KeyboardInterrupt("服务器正在关闭，任务被取消")
        if task_id in tasks and tasks[task_id].get("status") == "cancelled":
            raise KeyboardInterrupt("任务被用户取消")
    
    try:
        # 立即检查是否应该取消（避免在关闭时执行昂贵的初始化操作）
        check_cancellation()
        # 更新任务状态为处理中（从排队状态转换）
        tasks[task_id]["status"] = "processing"
        tasks[task_id]["message"] = "任务开始处理..."
        
        config = configparser.ConfigParser()
        config.read(CONFIG_FILE, encoding="utf-8")
        max_concurrency = config.getint("并发配置", "tts_max_concurrency", fallback=1)
        max_retries = config.getint("并发配置", "tts_max_retries", fallback=2)

        def progress_callback(current, total):
            # 在每次进度更新时检查是否需要取消
            check_cancellation()
            progress = 50 + int((current / total) * 40)  # Scale progress from 50 to 90
            tasks[task_id]["progress"] = progress
            tasks[task_id]["message"] = f"正在处理第 {current}/{total} 条字幕"
        
        if prompt_texts is None:
            prompt_texts = []

        if len(voice_paths) != len(prompt_texts):
            raise ValueError("The number of voice files and prompt texts must be the same.")

        is_txt_mode = input_path.suffix.lower() == ".txt"

        # 1. Initialize TTS engine
        check_cancellation()  # 在昂贵的TTS引擎加载前检查取消
        tasks[task_id]["progress"] = 10
        tasks[task_id]["message"] = "正在初始化TTS引擎"
        tts_engine_instance = get_tts_engine(tts_engine_name)

        # 2. Parse file
        check_cancellation()  # 在文件解析前检查取消
        tasks[task_id]["progress"] = 20
        tasks[task_id]["message"] = "正在解析输入文件"
        if is_txt_mode:
            parser_instance = TXTParser(language=language)
        else:
            parser_instance = SRTParser()
        entries = parser_instance.parse_file(str(input_path))

        # 3. Initialize processing strategy
        check_cancellation()  # 在策略初始化前检查取消
        tasks[task_id]["progress"] = 30
        tasks[task_id]["message"] = "正在初始化处理策略"
        if is_txt_mode and strategy_name != "basic":
            strategy_name = "basic"
        strategy_instance = get_strategy(strategy_name, tts_engine=tts_engine_instance)

        # 4. Generate audio segments
        check_cancellation()
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
        check_cancellation()
        tasks[task_id]["progress"] = 90
        tasks[task_id]["message"] = "正在合并音频"
        processor = AudioProcessor()
        merged_audio = processor.merge_audio_segments(
            audio_segments, strategy_name=strategy_name
        )
        
        tasks[task_id]["message"] = "正在导出音频文件"
        processor.export_audio(merged_audio, str(output_path))

        tasks[task_id]["progress"] = 100
        tasks[task_id]["status"] = "completed"
        tasks[task_id]["result_url"] = f"/results/{output_path.name}"
        tasks[task_id]["message"] = "任务完成"

    except KeyboardInterrupt as e:
        # 处理用户中断或服务器关闭
        tasks[task_id]["status"] = "cancelled"
        tasks[task_id]["message"] = str(e)
        print(f"任务 {task_id} 被中断: {e}")
    except Exception as e:
        tasks[task_id]["status"] = "failed"
        tasks[task_id]["error"] = str(e)
        tasks[task_id]["message"] = "处理失败"
        print(f"任务 {task_id} 失败: {e}")
    finally:
        # 从运行任务列表中移除
        running_tasks.pop(task_id, None)


@app.get("/dubbing/status/{task_id}")
async def get_dubbing_status(task_id: str):
    """Get the status of a dubbing task."""
    task = tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task

@app.post("/dubbing/cancel/{task_id}")
async def cancel_dubbing_task(task_id: str):
    """Cancel a dubbing task (queued, running, or processing)."""
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    
    current_status = tasks[task_id]["status"]
    
    # 只有未完成的任务才能取消
    if current_status in ["completed", "failed", "cancelled"]:
        return {"status": "failed", "message": f"任务已{current_status}，无法取消"}
    
    # 标记任务为取消状态（无论是排队还是运行中）
    tasks[task_id]["status"] = "cancelled"
    tasks[task_id]["message"] = "任务已被用户取消"
    
    if task_id in running_tasks:
        return {"status": "success", "message": f"运行中的任务 {task_id} 已标记为取消"}
    else:
        return {"status": "success", "message": f"排队中的任务 {task_id} 已标记为取消"}


@app.get("/subtitle-optimization/status/{task_id}")
async def get_optimization_status(task_id: str):
    """Get the status of a subtitle optimization task."""
    task = optimization_tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task

@app.post("/subtitle-optimization/cancel/{task_id}")
async def cancel_optimization_task(task_id: str):
    """Cancel a subtitle optimization task (queued, running, or processing)."""
    if task_id not in optimization_tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    
    current_status = optimization_tasks[task_id]["status"]
    
    # 只有未完成的任务才能取消
    if current_status in ["completed", "failed", "cancelled"]:
        return {"status": "failed", "message": f"任务已{current_status}，无法取消"}
    
    # 标记任务为取消状态（无论是排队还是运行中）
    optimization_tasks[task_id]["status"] = "cancelled"
    optimization_tasks[task_id]["message"] = "任务已被用户取消"
    
    return {"status": "success", "message": f"字幕优化任务 {task_id} 已标记为取消"}


@app.post("/subtitle-optimization")
async def create_subtitle_optimization(
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
    
    # 立即注册任务状态（重要：支持排队期间的状态查询和取消）
    optimization_tasks[task_id] = {
        "status": "queued", 
        "progress": 0, 
        "result_url": None, 
        "message": "任务已接收，等待处理..."
    }
    
    # 使用自定义线程池执行任务
    task_executor.submit(
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
    
    print("🚀 AI配音服务器启动中...")
    print("⚡ 按 Ctrl+C 可优雅关闭服务器")
    print("-" * 50)
    
    uvicorn.run(app, host="0.0.0.0", port=8000)