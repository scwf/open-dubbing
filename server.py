from __future__ import annotations

from pathlib import Path
from typing import List, Dict, Any, Optional
import uuid
import sys
import configparser
import logging
from dataclasses import dataclass

from fastapi import FastAPI, Request, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

from ai_dubbing.src.tts_engines import get_tts_engine, TTS_ENGINES
from ai_dubbing.src.strategies import get_strategy, list_available_strategies
from ai_dubbing.src.parsers import SRTParser, TXTParser
from ai_dubbing.src.audio_processor import AudioProcessor
from ai_dubbing.src.config import ConfigManager, ConfigError

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants
TEMPLATE_DIR = Path("ai_dubbing/web/templates")
STATIC_DIR = Path("ai_dubbing/web/static")
RESULT_DIR = Path("outputs")
UPLOAD_DIR = Path("uploads")
CONFIG_FILE = Path("ai_dubbing/dubbing.conf")

DEFAULT_LANGUAGES = ["zh", "en", "ja", "ko"]
DEFAULT_CONFIG_SECTIONS = {
    "并发配置": "concurrency",
    "字幕优化配置": "subtitle_optimization", 
    "时间借用配置": "time_borrowing"
}

@dataclass
class TaskStatus:
    """Represents the status of a dubbing task."""
    status: str
    progress: int
    message: str
    result_url: Optional[str] = None
    error: Optional[str] = None

class DirectoryManager:
    """Manages directory creation and setup."""
    
    @staticmethod
    def setup_directories() -> None:
        """Create necessary directories if they don't exist."""
        directories = [TEMPLATE_DIR, STATIC_DIR, RESULT_DIR, UPLOAD_DIR]
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
        logger.info("Directories setup completed")

# Initialize config manager
config_manager = ConfigManager(CONFIG_FILE)

class FileHandler:
    """Handles file upload and processing operations."""
    
    @staticmethod
    async def save_uploaded_file(file: UploadFile, directory: Path) -> Path:
        """Save an uploaded file to the specified directory."""
        file_path = directory / file.filename
        with open(file_path, "wb") as f:
            f.write(await file.read())
        return file_path
    
    @staticmethod
    async def process_voice_files_and_paths_async(
        voice_files: List[UploadFile], 
        voice_files_paths: List[str]
    ) -> List[str]:
        """Process voice files asynchronously, combining new uploads and existing paths."""
        final_voice_paths = []
        
        for i, uploaded_file in enumerate(voice_files):
            if uploaded_file.size > 0:
                file_path = await FileHandler.save_uploaded_file(uploaded_file, UPLOAD_DIR)
                final_voice_paths.append(str(file_path))
            elif i < len(voice_files_paths) and voice_files_paths[i]:
                final_voice_paths.append(voice_files_paths[i])
        
        return final_voice_paths

class DubbingService:
    """Handles the core dubbing processing logic."""
    
    def __init__(self):
        self.tasks: Dict[str, TaskStatus] = {}
    
    def update_task_status(
        self, 
        task_id: str, 
        status: str = None, 
        progress: int = None, 
        message: str = None,
        result_url: str = None,
        error: str = None
    ) -> None:
        """Update task status with new information."""
        if task_id not in self.tasks:
            self.tasks[task_id] = TaskStatus(
                status="processing", 
                progress=0, 
                message="Initializing..."
            )
        
        task = self.tasks[task_id]
        if status is not None:
            task.status = status
        if progress is not None:
            task.progress = progress
        if message is not None:
            task.message = message
        if result_url is not None:
            task.result_url = result_url
        if error is not None:
            task.error = error
    
    def get_task_status(self, task_id: str) -> Optional[TaskStatus]:
        """Get the current status of a task."""
        return self.tasks.get(task_id)
    
    def process_dubbing_task(
        self,
        task_id: str,
        input_path: Path,
        voice_paths: List[str],
        output_path: Path,
        tts_engine_name: str,
        strategy_name: str,
        language: str = "zh",
        prompt_texts: Optional[List[str]] = None,
    ) -> None:
        """Execute the dubbing process and update task status."""
        try:
            self.update_task_status(task_id, status="processing", progress=0, message="Initializing...")
            
            # Load configuration
            config = config_manager.load_config()
            max_concurrency = config.concurrency.tts_max_concurrency
            max_retries = config.concurrency.tts_max_retries

            def progress_callback(current: int, total: int) -> None:
                progress = 50 + int((current / total) * 40)  # Scale from 50 to 90
                self.update_task_status(
                    task_id, 
                    progress=progress, 
                    message=f"正在处理第 {current}/{total} 条字幕"
                )
            
            # Validate inputs
            if prompt_texts is None:
                prompt_texts = []
            
            if len(voice_paths) != len(prompt_texts):
                raise ValueError("The number of voice files and prompt texts must be the same.")

            is_txt_mode = input_path.suffix.lower() == ".txt"

            # Initialize TTS engine
            self.update_task_status(task_id, progress=10, message="初始化TTS引擎...")
            tts_engine_instance = get_tts_engine(tts_engine_name)

            # Parse file
            self.update_task_status(task_id, progress=20, message="解析输入文件...")
            if is_txt_mode:
                parser_instance = TXTParser(language=language)
            else:
                parser_instance = SRTParser()
            entries = parser_instance.parse_file(str(input_path))

            # Initialize processing strategy
            self.update_task_status(task_id, progress=30, message="初始化处理策略...")
            if is_txt_mode and strategy_name != "basic":
                strategy_name = "basic"
            strategy_instance = get_strategy(strategy_name, tts_engine=tts_engine_instance)

            # Generate audio segments
            self.update_task_status(task_id, progress=50, message="开始生成音频片段...")
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

            # Merge and export audio
            self.update_task_status(task_id, progress=90, message="正在合并音频...")
            processor = AudioProcessor()
            merged_audio = processor.merge_audio_segments(
                audio_segments, strategy_name=strategy_name
            )
            processor.export_audio(merged_audio, str(output_path))

            # Task completed successfully
            self.update_task_status(
                task_id, 
                status="completed", 
                progress=100, 
                message="配音任务完成！",
                result_url=f"/results/{output_path.name}"
            )
            logger.info(f"Dubbing task {task_id} completed successfully")

        except Exception as e:
            logger.error(f"Dubbing task {task_id} failed: {str(e)}")
            self.update_task_status(
                task_id, 
                status="failed", 
                message="处理失败",
                error=str(e)
            )

# Initialize services
DirectoryManager.setup_directories()
dubbing_service = DubbingService()

# Initialize FastAPI app
app = FastAPI(title="AI Dubbing Service", description="AI-powered voice dubbing service")
templates = Jinja2Templates(directory=str(TEMPLATE_DIR))

# Mount static files
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
app.mount("/results", StaticFiles(directory=str(RESULT_DIR)), name="results")

@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    """Render the main UI."""
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/dubbing/options")
async def dubbing_options() -> Dict[str, List[str]]:
    """Expose available engines, strategies and languages."""
    return {
        "tts_engines": list(TTS_ENGINES.keys()),
        "strategies": list_available_strategies(),
        "languages": DEFAULT_LANGUAGES,
    }

@app.get("/dubbing/config")
async def get_dubbing_config() -> Dict[str, Any]:
    """Get runtime config from dubbing.conf."""
    try:
        config = config_manager.load_config()
        return config.to_dict()
    except ConfigError as e:
        logger.error(f"Failed to load config: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to load configuration")
    except Exception as e:
        logger.error(f"Unexpected error loading config: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to load configuration")

@app.post("/dubbing/config")
async def set_dubbing_config(request: Request) -> Dict[str, str]:
    """Update runtime config in dubbing.conf."""
    try:
        data = await request.json()
        config_manager.update_config_from_dict(data)
        logger.info("Configuration updated successfully")
        return {"status": "success"}
        
    except ConfigError as e:
        logger.error(f"Failed to save config: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to save configuration")
    except Exception as e:
        logger.error(f"Unexpected error saving config: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to save configuration")

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
) -> Dict[str, str]:
    """Process an upload and return the generated audio path."""
    try:
        task_id = uuid.uuid4().hex
        logger.info(f"Starting dubbing task {task_id}")
        
        # Save input file
        input_path = await FileHandler.save_uploaded_file(input_file, UPLOAD_DIR)
        
        # Process voice files
        final_voice_paths = await FileHandler.process_voice_files_and_paths_async(
            voice_files, voice_files_paths
        )
        
        # Validate voice files and prompts count
        if len(final_voice_paths) != len(prompt_texts):
            raise HTTPException(
                status_code=400,
                detail=f"Mismatch between voice files ({len(final_voice_paths)}) and prompts ({len(prompt_texts)}).",
            )

        output_path = RESULT_DIR / f"{uuid.uuid4().hex}.wav"

        # Start background task
        background_tasks.add_task(
            dubbing_service.process_dubbing_task,
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
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create dubbing task: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to process request: {str(e)}")



@app.get("/dubbing/status/{task_id}")
async def get_dubbing_status(task_id: str) -> Dict[str, Any]:
    """Get the status of a dubbing task."""
    task = dubbing_service.get_task_status(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return {
        "status": task.status,
        "progress": task.progress,
        "message": task.message,
        "result_url": task.result_url,
        "error": task.error
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
