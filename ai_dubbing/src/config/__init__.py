"""
配置管理模块

统一管理SRT配音工具的所有配置常量和默认值。
支持从.env文件加载环境配置。
"""

from pathlib import Path
from typing import Dict, Any
import os
import dotenv

# 加载环境配置

def load_env_config() -> None:
    """加载环境配置文件"""
    env_file = Path(__file__).resolve().parents[2] / '.env'
    if env_file.exists():
        dotenv.load_dotenv(env_file)
    else:
        env_file_example = Path(__file__).resolve().parents[2] / '.env.example'
        if env_file_example.exists():
            print(f"提示: 请复制 {env_file_example} 为 .env 并修改路径配置")


load_env_config()

# 自动获取项目根目录
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# 模型缓存目录 - 仅支持绝对路径
MODEL_CACHE_DIR = Path(os.getenv('MODEL_CACHE_DIR', str(PROJECT_ROOT / 'model-dir')))

# 引入子模块配置
from .audio import AudioConfig, create_audio_config
from .strategy import StrategyConfig, create_strategy_config
from .tts import (
    IndexTTSConfig,
    F5TTSConfig,
    CosyVoiceConfig,
    FishSpeechConfig,
    create_index_tts_config,
    create_f5_tts_config,
    create_cosy_voice_config,
    create_fish_speech_config,
)

from dataclasses import dataclass


@dataclass
class PathConfig:
    """路径相关配置"""
    DEFAULT_OUTPUT_DIR: str = "output"
    DEFAULT_OUTPUT_FILE: str = "output.wav"

    @classmethod
    def get_default_output_path(cls) -> str:
        """获取默认输出路径"""
        return os.path.join(cls.DEFAULT_OUTPUT_DIR, cls.DEFAULT_OUTPUT_FILE)


@dataclass
class ValidationConfig:
    """验证相关配置"""
    TIME_MATCH_TOLERANCE: float = 0.1  # 时间匹配容忍度
    MIN_TEXT_LENGTH: int = 1
    MIN_AUDIO_DURATION: float = 0.01


@dataclass
class LogConfig:
    """日志相关配置"""
    PROGRESS_TEXT_PREVIEW_LENGTH: int = 30
    ERROR_PREFIX: str = "错误"
    WARNING_PREFIX: str = "警告"
    INFO_PREFIX: str = "信息"


CONFIG: Dict[str, Any] = {
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
AUDIO = create_audio_config()
STRATEGY = create_strategy_config()
PATH = PathConfig
VALIDATION = ValidationConfig
LOG = LogConfig

__all__ = [
    'AUDIO', 'STRATEGY', 'PATH', 'VALIDATION', 'LOG',
    'AudioConfig', 'StrategyConfig', 'IndexTTSConfig', 'F5TTSConfig',
    'CosyVoiceConfig', 'FishSpeechConfig', 'PathConfig', 'ValidationConfig', 'LogConfig',
    'create_audio_config', 'create_strategy_config', 'create_index_tts_config',
    'create_f5_tts_config', 'create_cosy_voice_config', 'create_fish_speech_config',
    'get_config'
]
