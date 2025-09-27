from __future__ import annotations

import configparser
import logging
import tempfile
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from ai_dubbing.src.audio_processor import AudioProcessor
from ai_dubbing.src.parsers import SRTParser, TXTParser
from ai_dubbing.src.strategies import get_strategy, list_available_strategies
from ai_dubbing.src.tts_engines import TTS_ENGINES, cleanup_all_engines, get_tts_engine

logger = logging.getLogger("    Open Dubbing Server")

class ConfigManager:
    def __init__(self, config_path: Path) -> None:
        self._config_path = config_path
        self._lock = threading.RLock()

    def _read_no_lock(self) -> configparser.ConfigParser:
        config = configparser.ConfigParser()
        config.read(self._config_path, encoding="utf-8")
        return config

    def read(self) -> configparser.ConfigParser:
        with self._lock:
            return self._read_no_lock()

    def update(self, mutator: Callable[[configparser.ConfigParser], None]) -> None:
        with self._lock:
            config = self._read_no_lock()
            mutator(config)
            self._write_no_lock(config)

    def _write_no_lock(self, config: configparser.ConfigParser) -> None:
        self._config_path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", delete=False, dir=self._config_path.parent
        ) as tmp_file:
            config.write(tmp_file)
            temp_path = Path(tmp_file.name)
        temp_path.replace(self._config_path)


class TaskStatus(str, Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


_FINAL_STATUSES = {TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED}
_SENTINEL = object()


@dataclass
class TaskState:
    status: TaskStatus = TaskStatus.QUEUED
    progress: int = 0
    message: str = ""
    result_url: Optional[str] = None
    error: Optional[str] = None

    def as_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "status": self.status.value,
            "progress": self.progress,
            "message": self.message,
            "result_url": self.result_url,
        }
        if self.error is not None:
            payload["error"] = self.error
        return payload


@dataclass(frozen=True)
class CancelResult:
    success: bool
    was_running: bool
    previous_status: TaskStatus


class TaskStore:
    def __init__(self) -> None:
        self._states: Dict[str, TaskState] = {}
        self._threads: Dict[str, threading.Thread] = {}
        self._lock = threading.RLock()

    def create(self, task_id: str, message: str) -> TaskState:
        with self._lock:
            state = TaskState(message=message)
            self._states[task_id] = state
            return state

    def update(
        self,
        task_id: str,
        *,
        status: Optional[TaskStatus] = None,
        progress: Optional[int] = None,
        message: Optional[str] = None,
        result_url: Any = _SENTINEL,
        error: Any = _SENTINEL,
    ) -> TaskState:
        with self._lock:
            state = self._states[task_id]
            if status is not None:
                state.status = status
            if progress is not None:
                state.progress = progress
            if message is not None:
                state.message = message
            if result_url is not _SENTINEL:
                state.result_url = result_url
            if error is not _SENTINEL:
                state.error = error
            return state

    def attach_thread(self, task_id: str, thread: threading.Thread) -> None:
        with self._lock:
            self._threads[task_id] = thread

    def detach_thread(self, task_id: str) -> None:
        with self._lock:
            self._threads.pop(task_id, None)

    def status(self, task_id: str) -> TaskStatus:
        with self._lock:
            return self._states[task_id].status

    def is_cancelled(self, task_id: str) -> bool:
        return self.status(task_id) == TaskStatus.CANCELLED

    def exists(self, task_id: str) -> bool:
        with self._lock:
            return task_id in self._states

    def as_dict(self, task_id: str) -> Dict[str, Any]:
        with self._lock:
            return self._states[task_id].as_dict()

    def cancel(self, task_id: str, message: str) -> CancelResult:
        with self._lock:
            state = self._states[task_id]
            previous_status = state.status
            was_running = task_id in self._threads
            if previous_status in _FINAL_STATUSES:
                return CancelResult(False, was_running, previous_status)
            state.status = TaskStatus.CANCELLED
            state.message = message
            return CancelResult(True, was_running, previous_status)

    def cancel_all_pending(self, message: str) -> int:
        with self._lock:
            count = 0
            for state in self._states.values():
                if state.status in _FINAL_STATUSES:
                    continue
                state.status = TaskStatus.CANCELLED
                state.message = message
                count += 1
            return count


def ensure_task_not_cancelled(task_store: TaskStore, task_id: str) -> None:
    if shutdown_flag.is_set():
        raise KeyboardInterrupt("服务器正在关闭，任务被取消")
    if task_store.is_cancelled(task_id):
        raise KeyboardInterrupt("任务被用户取消")


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
config_manager = ConfigManager(CONFIG_FILE)

templates = Jinja2Templates(directory=str(TEMPLATE_DIR))

shutdown_flag = threading.Event()
executor_lock = threading.Lock()
task_executor: Optional[ThreadPoolExecutor] = None

dubbing_tasks = TaskStore()
optimization_tasks = TaskStore()


def get_task_executor(force_new: bool = False) -> ThreadPoolExecutor:
    global task_executor
    with executor_lock:
        executor_closed = bool(task_executor and getattr(task_executor, "_shutdown", False))
        if force_new or task_executor is None or executor_closed:
            if task_executor and not executor_closed:
                task_executor.shutdown(wait=False)
            task_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="dubbing-task-")
            logger.info("Task executor created")
        return task_executor


def create_task_executor() -> ThreadPoolExecutor:
    return get_task_executor(force_new=True)


def safe_shutdown_executor(wait: bool = False) -> bool:
    global task_executor
    with executor_lock:
        if task_executor and not getattr(task_executor, "_shutdown", False):
            task_executor.shutdown(wait=wait)
            logger.info("Task executor shut down")
            return True
    return False


async def save_upload_file(upload: UploadFile, destination: Path, chunk_size: int = 1024 * 1024) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with open(destination, "wb") as buffer:
        while True:
            chunk = await upload.read(chunk_size)
            if not chunk:
                break
            buffer.write(chunk)
    await upload.seek(0)
    return destination


async def prepare_input_source(
    input_mode: str,
    input_file: Optional[UploadFile],
    input_text: Optional[str],
    text_format: Optional[str],
    task_id: str,
) -> Path:
    if input_mode == "file":
        if not input_file:
            raise HTTPException(status_code=400, detail="文件模式下必须提供输入文件")
        destination = UPLOAD_DIR / input_file.filename
        return await save_upload_file(input_file, destination)

    if input_mode == "text":
        if not input_text or not input_text.strip():
            raise HTTPException(status_code=400, detail="文本模式下必须提供输入文本")
        allowed_text_formats = {"txt", "srt"}
        normalized_text_format = (text_format or "txt").strip().lower()
        if normalized_text_format not in allowed_text_formats:
            raise HTTPException(status_code=400, detail="不支持的文本格式")
        temp_filename = f"temp_{task_id}.{normalized_text_format}"
        destination = UPLOAD_DIR / temp_filename
        destination.write_text(input_text.strip(), encoding="utf-8")
        return destination

    raise HTTPException(status_code=400, detail="不支持的输入模式")


async def collect_voice_paths(
    uploaded_files: List[UploadFile],
    builtin_files: List[str],
) -> List[str]:
    paths: List[str] = []
    for index, uploaded_file in enumerate(uploaded_files):
        has_upload = bool(uploaded_file.filename) and (
            uploaded_file.size is None or uploaded_file.size > 0
        )
        if has_upload:
            destination = UPLOAD_DIR / uploaded_file.filename
            await save_upload_file(uploaded_file, destination)
            paths.append(str(destination))
        elif index < len(builtin_files) and builtin_files[index]:
            paths.append(resolve_audio_path(builtin_files[index]))
    return paths


def build_emotion_config(
    tts_engine: str,
    emotion_mode: str,
    emotion_audio_path: Optional[Path],
    emotion_vector: str,
    emotion_text: str,
    emotion_alpha: float,
    use_random: bool,
) -> Dict[str, Any]:
    if tts_engine != "index_tts2":
        return {}

    config: Dict[str, Any] = {
        "emotion_alpha": emotion_alpha,
        "use_random": use_random,
    }
    if emotion_mode == "audio" and emotion_audio_path:
        config["emotion_audio_file"] = str(emotion_audio_path)
    elif emotion_mode == "vector" and emotion_vector:
        try:
            config["emotion_vector"] = [float(x.strip()) for x in emotion_vector.split(",")]
        except ValueError:
            logger.warning("Invalid emotion vector provided; ignoring value")
    elif emotion_mode == "text" and emotion_text:
        config["emotion_text"] = emotion_text
    elif emotion_mode == "auto":
        config["auto_emotion"] = True
    return config


def resolve_audio_path(path_str: str) -> str:
    path = Path(path_str)
    if path.is_absolute():
        return str(path)
    return str(PROJECT_ROOT / path)


def resolve_audio_paths_list(paths_str: str) -> str:
    if not paths_str.strip():
        return ""
    paths = [path.strip() for path in paths_str.split(",")]
    resolved_paths = [resolve_audio_path(path) for path in paths if path.strip()]
    return ",".join(resolved_paths)


@asynccontextmanager
async def lifespan(app: FastAPI):
    shutdown_flag.clear()
    create_task_executor()
    yield
    try:
        logger.info("Shutting down server...")
        shutdown_flag.set()
        cancelled = dubbing_tasks.cancel_all_pending("服务器关闭，任务被取消")
        cancelled += optimization_tasks.cancel_all_pending("服务器关闭，任务被取消")
        if cancelled:
            logger.info("Marked %s tasks as cancelled during shutdown", cancelled)
        if safe_shutdown_executor(wait=True):
            logger.info("Executor closed")
        cleanup_all_engines()
        logger.info("GPU resources cleaned up")
    except Exception as exc:
        logger.exception(f"Failed to shutdown server: {str(exc)}")

app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
app.mount("/results", StaticFiles(directory=str(RESULT_DIR)), name="results")


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/dubbing/options")
async def dubbing_options():
    languages = ["zh", "en", "ja", "ko"]
    return {
        "tts_engines": list(TTS_ENGINES.keys()),
        "strategies": list_available_strategies(),
        "languages": languages,
    }


@app.get("/dubbing/built-in-audios")
async def get_built_in_audios():
    config = config_manager.read()
    prefix = "内置音频:"
    audio_sections = [section for section in config.sections() if section.startswith(prefix)]
    return {
        section[len(prefix) :]: {
            "path": resolve_audio_path(config.get(section, "path")),
            "text": config.get(section, "text"),
        }
        for section in audio_sections
        if config.has_option(section, "path") and config.has_option(section, "text")
    }


@app.get("/dubbing/config")
async def get_dubbing_config():
    config = config_manager.read()
    return {
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
        },
    }


@app.post("/dubbing/config")
async def set_dubbing_config(request: Request):
    data = await request.json()

    def mutator(config: configparser.ConfigParser) -> None:
        def ensure_section(section: str) -> None:
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

    config_manager.update(mutator)
    return {"status": "success"}


@app.post("/dubbing")
async def create_dubbing(
    input_mode: str = Form("file"),
    input_file: UploadFile = File(None),
    input_text: str = Form(None),
    text_format: str = Form("txt"),
    upload_voice_files: List[UploadFile] = File(...),
    builtin_voice_files: List[str] = Form(...),
    prompt_texts: List[str] = Form(...),
    tts_engine: str = Form(...),
    strategy: str = Form(...),
    language: str = Form("zh"),
    emotion_mode: str = Form("auto"),
    emotion_audio_file: UploadFile = File(None),
    emotion_vector: str = Form(""),
    emotion_text: str = Form(""),
    emotion_alpha: float = Form(0.8),
    use_random: bool = Form(False),
):
    task_id = uuid.uuid4().hex
    config = config_manager.read()
    optimized_srt_dir = config.get("字幕优化配置", "optimized_srt_output_file", fallback=None)

    input_path = await prepare_input_source(input_mode, input_file, input_text, text_format, task_id)
    if optimized_srt_dir and Path(optimized_srt_dir).is_dir():
        logger.info("Optimized SRT would be saved in: %s", optimized_srt_dir)

    final_voice_paths = await collect_voice_paths(upload_voice_files, builtin_voice_files)

    if len(final_voice_paths) != len(prompt_texts):
        raise HTTPException(
            status_code=400,
            detail=f"Mismatch between voice files ({len(final_voice_paths)}) and prompts ({len(prompt_texts)}).",
        )

    emotion_audio_path: Optional[Path] = None
    if (
        tts_engine == "index_tts2"
        and emotion_mode == "audio"
        and emotion_audio_file
        and emotion_audio_file.size is not None
        and emotion_audio_file.size > 0
    ):
        emotion_audio_path = UPLOAD_DIR / f"emotion_{uuid.uuid4().hex}_{emotion_audio_file.filename}"
        await save_upload_file(emotion_audio_file, emotion_audio_path)

    emotion_config = build_emotion_config(
        tts_engine,
        emotion_mode,
        emotion_audio_path,
        emotion_vector,
        emotion_text,
        emotion_alpha,
        use_random,
    )

    output_path = RESULT_DIR / f"{uuid.uuid4().hex}.wav"
    dubbing_tasks.create(task_id, "任务已接收，等待处理...")

    executor = get_task_executor()
    executor.submit(
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


def run_subtitle_optimization(task_id: str, input_path: Path, output_path: Path) -> None:
    optimization_tasks.attach_thread(task_id, threading.current_thread())

    try:
        ensure_task_not_cancelled(optimization_tasks, task_id)
        optimization_tasks.update(task_id, status=TaskStatus.PROCESSING, message="字幕优化任务开始处理...")

        from ai_dubbing.run_optimize_subtitles import (
            load_subtitile_optimize_config,
            optimize_srt_file,
        )

        optimization_tasks.update(task_id, progress=10, message="加载配置文件...")
        ensure_task_not_cancelled(optimization_tasks, task_id)

        config = load_subtitile_optimize_config()

        optimization_tasks.update(task_id, progress=30, message="开始字幕优化处理...")
        ensure_task_not_cancelled(optimization_tasks, task_id)

        result_path = optimize_srt_file(str(input_path), str(output_path), config)
        if result_path:
            optimization_tasks.update(
                task_id,
                progress=100,
                status=TaskStatus.COMPLETED,
                result_url=f"/results/{Path(result_path).name}",
                message="字幕优化完成",
            )
        else:
            raise ValueError("字幕优化失败")
    except KeyboardInterrupt as exc:
        optimization_tasks.update(task_id, status=TaskStatus.CANCELLED, message=str(exc))
        logger.info("字幕优化任务 %s cancelled: %s", task_id, exc)
    except Exception as exc:  # noqa: BLE001
        optimization_tasks.update(
            task_id,
            status=TaskStatus.FAILED,
            message="字幕优化失败",
            error=str(exc),
        )
        logger.exception("字幕优化任务 %s failed", task_id)
    finally:
        optimization_tasks.detach_thread(task_id)


def run_dubbing(
    task_id: str,
    input_path: Path,
    voice_paths: List[str],
    output_path: Path,
    tts_engine_name: str,
    strategy_name: str,
    language: str = "zh",
    prompt_texts: Optional[List[str]] = None,
    emotion_config: Optional[Dict[str, Any]] = None,
) -> None:
    dubbing_tasks.attach_thread(task_id, threading.current_thread())

    try:
        ensure_task_not_cancelled(dubbing_tasks, task_id)
        dubbing_tasks.update(task_id, status=TaskStatus.PROCESSING, message="任务开始处理...")

        config = config_manager.read()
        max_concurrency = config.getint("并发配置", "tts_max_concurrency", fallback=1)
        max_retries = config.getint("并发配置", "tts_max_retries", fallback=2)

        def progress_callback(current: int, total: int) -> None:
            ensure_task_not_cancelled(dubbing_tasks, task_id)
            progress = 90 if total == 0 else 50 + int((current / total) * 40)
            dubbing_tasks.update(
                task_id,
                progress=progress,
                message=f"正在处理第 {current}/{total} 条字幕",
            )

        prompt_texts = prompt_texts or []
        if len(voice_paths) != len(prompt_texts):
            raise ValueError("The number of voice files and prompt texts must be the same.")

        is_txt_mode = input_path.suffix.lower() == ".txt"

        ensure_task_not_cancelled(dubbing_tasks, task_id)
        dubbing_tasks.update(task_id, progress=10, message="正在初始化TTS引擎")
        tts_engine_instance = get_tts_engine(tts_engine_name)

        ensure_task_not_cancelled(dubbing_tasks, task_id)
        dubbing_tasks.update(task_id, progress=20, message="正在解析输入文件")
        parser_instance = TXTParser(language=language) if is_txt_mode else SRTParser()
        entries = parser_instance.parse_file(str(input_path))

        ensure_task_not_cancelled(dubbing_tasks, task_id)
        dubbing_tasks.update(task_id, progress=30, message="正在初始化处理策略")
        if is_txt_mode and strategy_name != "basic":
            strategy_name = "basic"
        strategy_instance = get_strategy(strategy_name, tts_engine=tts_engine_instance)

        ensure_task_not_cancelled(dubbing_tasks, task_id)
        dubbing_tasks.update(task_id, progress=50, message="开始生成音频片段")
        runtime_kwargs: Dict[str, Any] = {
            "prompt_text": prompt_texts[0] if prompt_texts else "",
            "ref_text": prompt_texts[0] if prompt_texts else "",
            "voice_files": voice_paths,
            "prompt_texts": prompt_texts,
            "max_concurrency": max_concurrency,
            "max_retries": max_retries,
            "progress_callback": progress_callback,
        }
        if emotion_config:
            runtime_kwargs.update(emotion_config)
        audio_segments = strategy_instance.process_entries(
            entries,
            voice_reference=voice_paths[0] if voice_paths else None,
            **runtime_kwargs,
        )

        ensure_task_not_cancelled(dubbing_tasks, task_id)
        dubbing_tasks.update(task_id, progress=90, message="正在合并音频")
        processor = AudioProcessor()
        merged_audio = processor.merge_audio_segments(audio_segments, strategy_name=strategy_name)

        dubbing_tasks.update(task_id, message="正在导出音频文件")
        processor.export_audio(merged_audio, str(output_path))

        dubbing_tasks.update(
            task_id,
            status=TaskStatus.COMPLETED,
            progress=100,
            result_url=f"/results/{output_path.name}",
            message="任务完成",
        )
    except KeyboardInterrupt as exc:
        dubbing_tasks.update(task_id, status=TaskStatus.CANCELLED, message=str(exc))
        logger.info("配音任务 %s cancelled: %s", task_id, exc)
    except Exception as exc:  # noqa: BLE001
        dubbing_tasks.update(
            task_id,
            status=TaskStatus.FAILED,
            message="处理失败",
            error=str(exc),
        )
        logger.exception("配音任务 %s failed", task_id)
    finally:
        dubbing_tasks.detach_thread(task_id)


@app.get("/dubbing/status/{task_id}")
async def get_dubbing_status(task_id: str):
    if not dubbing_tasks.exists(task_id):
        raise HTTPException(status_code=404, detail="Task not found")
    return dubbing_tasks.as_dict(task_id)


@app.post("/dubbing/cancel/{task_id}")
async def cancel_dubbing_task(task_id: str):
    if not dubbing_tasks.exists(task_id):
        raise HTTPException(status_code=404, detail="Task not found")

    result = dubbing_tasks.cancel(task_id, "任务已被用户取消")
    if not result.success:
        return {
            "status": "failed",
            "message": f"任务已{result.previous_status.value}，无法取消",
        }

    return {
        "status": "success",
        "message": (
            f"运行中的任务 {task_id} 已标记为取消"
            if result.was_running
            else f"排队中的任务 {task_id} 已标记为取消"
        ),
    }


@app.get("/subtitle-optimization/status/{task_id}")
async def get_optimization_status(task_id: str):
    if not optimization_tasks.exists(task_id):
        raise HTTPException(status_code=404, detail="Task not found")
    return optimization_tasks.as_dict(task_id)


@app.post("/subtitle-optimization/cancel/{task_id}")
async def cancel_optimization_task(task_id: str):
    if not optimization_tasks.exists(task_id):
        raise HTTPException(status_code=404, detail="Task not found")

    result = optimization_tasks.cancel(task_id, "任务已被用户取消")
    if not result.success:
        return {
            "status": "failed",
            "message": f"任务已{result.previous_status.value}，无法取消",
        }

    return {
        "status": "success",
        "message": f"字幕优化任务 {task_id} 已标记为取消",
    }


@app.post("/subtitle-optimization")
async def create_subtitle_optimization(input_file: UploadFile = File(...)):
    if not input_file.filename.lower().endswith(".srt"):
        raise HTTPException(status_code=400, detail="仅支持.srt格式的字幕文件")

    task_id = uuid.uuid4().hex
    input_path = UPLOAD_DIR / input_file.filename
    await save_upload_file(input_file, input_path)

    output_filename = f"optimized_{uuid.uuid4().hex}.srt"
    output_path = RESULT_DIR / output_filename

    optimization_tasks.create(task_id, "任务已接收，等待处理...")

    executor = get_task_executor()
    executor.submit(
        run_subtitle_optimization,
        task_id=task_id,
        input_path=input_path,
        output_path=output_path,
    )

    return {"task_id": task_id}


@app.post("/dubbing/cleanup")
async def cleanup_gpu_memory():
    try:
        cleanup_all_engines()
        return {"status": "success", "message": "GPU内存已清理"}
    except Exception as exc:  # noqa: BLE001
        logger.exception("GPU cleanup failed")
        raise HTTPException(status_code=500, detail=f"清理GPU内存失败: {str(exc)}") from exc


if __name__ == "__main__":
    import uvicorn

    if not logger.handlers:
        logging.basicConfig(level=logging.INFO)

    logger.info("Starting AI dubbing server...")
    uvicorn.run(app, host="0.0.0.0", port=8000)
