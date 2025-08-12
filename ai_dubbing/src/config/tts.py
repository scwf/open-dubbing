from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Any, Optional
import os

# 自动获取项目根目录
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# 模型缓存目录 - 仅支持绝对路径
MODEL_CACHE_DIR = Path(os.getenv('MODEL_CACHE_DIR', str(PROJECT_ROOT / 'model-dir')))


@dataclass
class IndexTTSConfig:
    """IndexTTS引擎专用配置"""
    MODEL_DIR: str = str(MODEL_CACHE_DIR / "index_tts")
    CONFIG_FILE: str = str(MODEL_CACHE_DIR / "index_tts" / "config.yaml")
    SOURCE_DIR: str = str(Path(os.getenv('INDEX_TTS_DIR', str(PROJECT_ROOT / 'index-tts'))))
    FP16: bool = True

    @classmethod
    def get_init_kwargs(cls) -> Dict[str, Any]:
        """获取用于IndexTTS初始化的字典"""
        return {
            "cfg_path": cls.CONFIG_FILE,
            "model_dir": cls.MODEL_DIR,
            "is_fp16": cls.FP16,
        }


def create_index_tts_config() -> IndexTTSConfig:
    """工厂函数: 创建IndexTTS配置实例"""
    return IndexTTSConfig()


@dataclass
class F5TTSConfig:
    """F5TTS引擎相关配置"""
    MODEL: str = "F5TTS_v1_Base"
    CKPT_FILE: Optional[str] = None
    VOCAB_FILE: Optional[str] = None
    ODE_METHOD: str = "euler"
    USE_EMA: bool = True
    VOCODER_LOCAL_PATH: Optional[str] = None
    DEVICE: Optional[str] = None
    HF_CACHE_DIR: str = str(MODEL_CACHE_DIR)  # 模型自动缓存到该目录

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


def create_f5_tts_config() -> F5TTSConfig:
    """工厂函数: 创建F5TTS配置实例"""
    return F5TTSConfig()


@dataclass
class CosyVoiceConfig:
    """CosyVoice引擎专用配置"""
    MODEL_ID: str = str(MODEL_CACHE_DIR / 'CosyVoice2-0.5B')
    PROMPT_TEXT: Optional[str] = None
    FP16: bool = False
    LOAD_JIT: bool = False
    LOAD_TRT: bool = False
    LOAD_VLLM: bool = False
    SOURCE_DIR: str = str(Path(os.getenv('COSYVOICE_DIR', str(PROJECT_ROOT / 'CosyVoice'))))

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


def create_cosy_voice_config() -> CosyVoiceConfig:
    """工厂函数: 创建CosyVoice配置实例"""
    return CosyVoiceConfig()


@dataclass
class FishSpeechConfig:
    """Fish Speech引擎专用配置"""
    LLAMA_CHECKPOINT_PATH: str = str(MODEL_CACHE_DIR / 'openaudio-s1-mini')
    DECODER_CHECKPOINT_PATH: str = str(Path(LLAMA_CHECKPOINT_PATH) / 'codec.pth')
    SOURCE_DIR: str = str(Path(os.getenv('FISH_SPEECH_DIR', str(PROJECT_ROOT / 'fish-speech'))))
    DEVICE: Optional[str] = None  # 自动检测：cuda或cpu
    PRECISION: Optional[str] = None  # 自动检测：bfloat16或float32
    COMPILE: bool = True

    # Fish Speech返回44.1kHz音频，确保系统配置匹配
    TARGET_SAMPLE_RATE: int = 44100

    # 推理参数默认值 - 优化音质和自然度
    DEFAULT_TEMPERATURE: float = 0.2  # 低温度保持稳定音质，匹配原始示例
    DEFAULT_TOP_P: float = 0.6  # 使用原始示例的top_p值
    DEFAULT_REPETITION_PENALTY: float = 1.2  # 使用原始示例的重复惩罚值
    DEFAULT_CHUNK_LENGTH: int = 150  # 使用原始示例的块长度
    DEFAULT_MAX_NEW_TOKENS: int = 2048  # 使用原始示例的最大token数
    DEFAULT_SEED: int = 42
    DEFAULT_USE_MEMORY_CACHE: str = "on"

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


def create_fish_speech_config() -> FishSpeechConfig:
    """工厂函数: 创建Fish Speech配置实例"""
    return FishSpeechConfig()
