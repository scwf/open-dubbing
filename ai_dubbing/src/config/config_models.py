"""
Configuration Data Models

Defines data models for different configuration sections.
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from pathlib import Path


@dataclass
class BasicConfig:
    """基本配置"""
    voice_files: str = ""
    prompt_texts: str = ""
    tts_engine: str = "fish_speech"
    strategy: str = "stretch"
    language: str = "zh"


@dataclass
class ConcurrencyConfig:
    """并发配置"""
    tts_max_concurrency: int = 8
    tts_max_retries: int = 2


@dataclass  
class SubtitleOptimizationConfig:
    """字幕优化配置"""
    llm_api_key: str = ""
    llm_model: str = ""
    base_url: str = ""
    chinese_char_min_time: int = 150
    english_word_min_time: int = 250
    llm_max_concurrency: int = 50
    llm_max_retries: int = 3
    llm_timeout: int = 60
    optimized_srt_output_file: str = ""


@dataclass
class TimeBorrowingConfig:
    """时间借用配置"""
    min_gap_threshold: int = 200
    borrow_ratio: float = 1.0
    extra_buffer: int = 200


@dataclass
class DubbingConfig:
    """完整的配音配置"""
    basic: BasicConfig = field(default_factory=BasicConfig)
    concurrency: ConcurrencyConfig = field(default_factory=ConcurrencyConfig)
    subtitle_optimization: SubtitleOptimizationConfig = field(default_factory=SubtitleOptimizationConfig)
    time_borrowing: TimeBorrowingConfig = field(default_factory=TimeBorrowingConfig)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "basic": {
                "voice_files": self.basic.voice_files,
                "prompt_texts": self.basic.prompt_texts,
                "tts_engine": self.basic.tts_engine,
                "strategy": self.basic.strategy,
                "language": self.basic.language,
            },
            "concurrency": {
                "tts_max_concurrency": self.concurrency.tts_max_concurrency,
                "tts_max_retries": self.concurrency.tts_max_retries,
            },
            "subtitle_optimization": {
                "llm_api_key": self.subtitle_optimization.llm_api_key,
                "llm_model": self.subtitle_optimization.llm_model,
                "base_url": self.subtitle_optimization.base_url,
                "chinese_char_min_time": self.subtitle_optimization.chinese_char_min_time,
                "english_word_min_time": self.subtitle_optimization.english_word_min_time,
                "llm_max_concurrency": self.subtitle_optimization.llm_max_concurrency,
                "llm_max_retries": self.subtitle_optimization.llm_max_retries,
                "llm_timeout": self.subtitle_optimization.llm_timeout,
                "optimized_srt_output_file": self.subtitle_optimization.optimized_srt_output_file,
            },
            "time_borrowing": {
                "min_gap_threshold": self.time_borrowing.min_gap_threshold,
                "borrow_ratio": self.time_borrowing.borrow_ratio,
                "extra_buffer": self.time_borrowing.extra_buffer,
            }
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DubbingConfig':
        """从字典创建配置对象"""
        return cls(
            basic=BasicConfig(**data.get("basic", {})),
            concurrency=ConcurrencyConfig(**data.get("concurrency", {})),
            subtitle_optimization=SubtitleOptimizationConfig(**data.get("subtitle_optimization", {})),
            time_borrowing=TimeBorrowingConfig(**data.get("time_borrowing", {}))
        )