"""
配置管理模块

统一管理SRT配音工具的所有配置常量和默认值。
支持从.env文件加载环境配置。
"""

from pathlib import Path
from typing import Dict, Any, Optional
import os
import dotenv


# 加载环境配置
def load_env_config():
    """加载环境配置文件"""
    env_file = Path(__file__).parent.parent / '.env'
    if env_file.exists():
        dotenv.load_dotenv(env_file)
    else:
        # 使用默认配置
        env_file_example = Path(__file__).parent.parent / '.env.example'
        if env_file_example.exists():
            print(f"提示: 请复制 {env_file_example} 为 .env 并修改路径配置")

load_env_config()

# 自动获取项目根目录
PROJECT_ROOT = Path(__file__).parent.parent

# 模型缓存目录 - 仅支持绝对路径
MODEL_CACHE_DIR = Path(os.getenv('MODEL_CACHE_DIR', str(PROJECT_ROOT / 'model-dir')))


class AudioConfig:
    """音频相关配置"""
    # 音频处理常量 - 使用44.1kHz以匹配Fish Speech输出
    DEFAULT_SAMPLE_RATE = 44100
    DEFAULT_CHANNELS = 1
    AUDIO_NORMALIZATION_FACTOR = 32768.0  # int16 to float32 conversion
    
    # 音频合并配置
    DYNAMIC_BUFFER_SIZE = 1024
    MAX_AMPLITUDE = 1.0
    
    # 音频效果配置
    DEFAULT_FADE_DURATION = 0.1
    DEFAULT_GAP_DURATION = 0.1


class StrategyConfig:
    """策略相关配置"""
    # 时间拉伸策略 - 优化音质保护
    TIME_STRETCH_THRESHOLD = 0.05  # 变速阈值 (5%)
    TIME_DURATION_TOLERANCE = 0.1   # 时间偏差容忍度 (0.1秒)
    
    # 标准变速范围 - 放宽限制以支持更多场景
    MAX_SPEED_RATIO = 4.0    # 放宽到4.0倍速（FFmpeg atempo支持上限）
    MIN_SPEED_RATIO = 0.25   # 放宽到0.25倍速（FFmpeg atempo下限）
    
    # 高质量模式的变速范围 - 用于音质敏感场景
    HIGH_QUALITY_MAX_SPEED = 2.0
    HIGH_QUALITY_MIN_SPEED = 0.5
    
    # 超宽变速范围 - 用于极端场景（需用户显式设置）
    ULTRA_WIDE_MAX_SPEED = 10.0
    ULTRA_WIDE_MIN_SPEED = 0.1
    
    # 基础策略 - 保持不变
    SILENCE_THRESHOLD = 0.5
    BASIC_MAX_SPEED_RATIO = 1.2
    BASIC_MIN_SPEED_RATIO = 0.8
    
    # 调试功能开关
    ENABLE_SAVE_ENTRY_WAVFILE = True  # 是否保存各个字幕条目的音频文件到临时目录


class IndexTTSConfig:
    """IndexTTS引擎专用配置"""
    # IndexTTS模型路径 - 从环境变量获取
    MODEL_DIR = str(MODEL_CACHE_DIR / "index_tts")
    CONFIG_FILE = str(MODEL_CACHE_DIR / "index_tts" / "config.yaml")
    SOURCE_DIR = str(Path(os.getenv('INDEX_TTS_DIR', str(PROJECT_ROOT / 'index-tts'))))
    # TTS推理配置
    FP16 = True
    
    @classmethod
    def get_init_kwargs(cls) -> Dict[str, Any]:
        """获取用于IndexTTS初始化的字典"""
        return {
            "cfg_path": cls.CONFIG_FILE,
            "model_dir": cls.MODEL_DIR,
            "is_fp16": cls.FP16,
        }


class F5TTSConfig:
    """F5TTS引擎相关配置"""
    # 参数源自 F5TTS_infer.md
    MODEL = "F5TTS_v1_Base"
    CKPT_FILE = None
    VOCAB_FILE = None
    ODE_METHOD = "euler"
    USE_EMA = True
    VOCODER_LOCAL_PATH = None
    DEVICE = None
    HF_CACHE_DIR = str(MODEL_CACHE_DIR)  # 模型自动缓存到该目录

    @classmethod
    def get_init_kwargs(cls) -> Dict[str, Any]:
        """获取用于F5TTS初始化的字典"""
        return {
            "model": cls.MODEL,
            "ckpt_file": cls.CKPT_FILE,
            "vocab_file": cls.VOCAB_FILE,
            "ode_method": cls.ODE_METHOD,
            "use_ema": cls.USE_EMA,
            "vocoder_local_path": cls.VOCODER_LOCAL_PATH,
            "device": cls.DEVICE,
            "hf_cache_dir": cls.HF_CACHE_DIR,
        }


class CosyVoiceConfig:
    """CosyVoice引擎专用配置"""
    MODEL_ID = str(MODEL_CACHE_DIR / 'CosyVoice2-0.5B')
    PROMPT_TEXT = None
    FP16 = False
    LOAD_JIT = False
    LOAD_TRT = False
    LOAD_VLLM = False
    SOURCE_DIR = str(Path(os.getenv('COSYVOICE_DIR', str(PROJECT_ROOT / 'CosyVoice'))))

    @classmethod
    def get_init_kwargs(cls) -> Dict[str, Any]:
        """获取用于CosyVoice初始化的字典"""
        return {
            "model_dir": cls.MODEL_ID,
            "prompt_text": cls.PROMPT_TEXT,
            "fp16": cls.FP16,
            "load_jit": cls.LOAD_JIT,
            "load_trt": cls.LOAD_TRT,
            "load_vllm": cls.LOAD_VLLM,
        }


class FishSpeechConfig:
    """Fish Speech引擎专用配置"""
    LLAMA_CHECKPOINT_PATH = str(MODEL_CACHE_DIR / 'openaudio-s1-mini')
    DECODER_CHECKPOINT_PATH = str(Path(LLAMA_CHECKPOINT_PATH) / 'codec.pth')
    SOURCE_DIR = str(Path(os.getenv('FISH_SPEECH_DIR', str(PROJECT_ROOT / 'fish-speech'))))
    DEVICE = None  # 自动检测：cuda或cpu
    PRECISION = None  # 自动检测：bfloat16或float32
    COMPILE = True
    
    # Fish Speech返回44.1kHz音频，确保系统配置匹配
    TARGET_SAMPLE_RATE = 44100
    
    # 推理参数默认值 - 优化音质和自然度
    DEFAULT_TEMPERATURE = 0.2  # 低温度保持稳定音质，匹配原始示例
    DEFAULT_TOP_P = 0.6  # 使用原始示例的top_p值
    DEFAULT_REPETITION_PENALTY = 1.2  # 使用原始示例的重复惩罚值
    DEFAULT_CHUNK_LENGTH = 150  # 使用原始示例的块长度
    DEFAULT_MAX_NEW_TOKENS = 2048  # 使用原始示例的最大token数
    DEFAULT_SEED = 42
    DEFAULT_USE_MEMORY_CACHE = "on"

    @classmethod
    def get_init_kwargs(cls) -> Dict[str, Any]:
        """获取用于Fish Speech初始化的字典"""
        return {
            "llama_checkpoint_path": cls.LLAMA_CHECKPOINT_PATH,
            "decoder_checkpoint_path": cls.DECODER_CHECKPOINT_PATH,
            "device": cls.DEVICE,
            "precision": cls.PRECISION,
            "compile": cls.COMPILE,
        }

    @classmethod
    def get_inference_kwargs(cls) -> Dict[str, Any]:
        """获取Fish Speech推理的默认参数字典"""
        return {
            "temperature": cls.DEFAULT_TEMPERATURE,
            "top_p": cls.DEFAULT_TOP_P,
            "repetition_penalty": cls.DEFAULT_REPETITION_PENALTY,
            "chunk_length": cls.DEFAULT_CHUNK_LENGTH,
            "max_new_tokens": cls.DEFAULT_MAX_NEW_TOKENS,
            "seed": cls.DEFAULT_SEED,
            "use_memory_cache": cls.DEFAULT_USE_MEMORY_CACHE,
        }


class PathConfig:
    """路径相关配置"""
    # 默认输出配置
    DEFAULT_OUTPUT_DIR = "output"
    DEFAULT_OUTPUT_FILE = "output.wav"
    
    @classmethod
    def get_default_output_path(cls) -> str:
        """获取默认输出路径"""
        return os.path.join(cls.DEFAULT_OUTPUT_DIR, cls.DEFAULT_OUTPUT_FILE)


class ValidationConfig:
    """验证相关配置"""
    # SRT验证配置
    TIME_MATCH_TOLERANCE = 0.1  # 时间匹配容忍度
    MIN_TEXT_LENGTH = 1
    
    # 音频验证配置
    MIN_AUDIO_DURATION = 0.01


class LogConfig:
    """日志相关配置"""
    # 进度显示配置
    PROGRESS_TEXT_PREVIEW_LENGTH = 30
    
    # 日志格式
    ERROR_PREFIX = "错误"
    WARNING_PREFIX = "警告"
    INFO_PREFIX = "信息"



# 全局配置实例
CONFIG = {
    'audio': AudioConfig,
    'strategy': StrategyConfig,
    'model': IndexTTSConfig,
    'f5_tts': F5TTSConfig,
    'cosy_voice': CosyVoiceConfig,
    'fish_speech': FishSpeechConfig,
    'path': PathConfig,
    'validation': ValidationConfig,
    'log': LogConfig,
}


def get_config(category: str) -> Any:
    """
    获取指定类别的配置
    
    Args:
        category: 配置类别 ('audio', 'strategy', 'model', 'path', 'validation', 'log')
    
    Returns:
        对应的配置类
    """
    return CONFIG.get(category)


# 常用配置的快捷访问
AUDIO = AudioConfig
STRATEGY = StrategyConfig  
PATH = PathConfig
VALIDATION = ValidationConfig
LOG = LogConfig 