"""
策略抽象基类
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import List, Dict, Any

from ai_dubbing.src.tts_engines.base_engine import BaseTTSEngine
from ai_dubbing.src.parsers.srt_parser import SRTEntry

class TimeSyncStrategy(ABC):
    """时间同步策略抽象基类"""
    
    def __init__(self, tts_engine: 'BaseTTSEngine'):
        """
        初始化策略。
        
        Args:
            tts_engine: 一个遵循BaseTTSEngine接口的TTS引擎实例。
        """
        self.tts_engine = tts_engine
    
    @staticmethod
    @abstractmethod
    def name() -> str:
        """策略名称"""
        pass
    
    @staticmethod
    @abstractmethod
    def description() -> str:
        """策略描述"""
        pass
    
    @abstractmethod
    def process_entries(self, entries: List[SRTEntry], **kwargs) -> List[Dict[str, Any]]:
        """处理SRT条目，返回音频片段信息"""
        pass 