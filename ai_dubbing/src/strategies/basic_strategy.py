"""
基础自然合成策略

采用自然语音合成 + 静音填充的方式处理SRT字幕，
优先保证语音质量，使用静音来匹配时间间隔。
"""
from typing import List, Dict, Any
import numpy as np

from ai_dubbing.src.tts_engines.base_engine import BaseTTSEngine
from ai_dubbing.src.utils import validate_file_exists
from ai_dubbing.src.config import AUDIO, LOG
from ai_dubbing.src.parsers.srt_parser import SRTEntry
from ai_dubbing.src.strategies.base_strategy import TimeSyncStrategy
from ai_dubbing.src.logger import get_logger, create_process_logger

class BasicStrategy(TimeSyncStrategy):
    """基础自然合成策略实现"""
    
    def __init__(self, tts_engine: 'BaseTTSEngine', **kwargs):
        """
        初始化基础策略
        
        Args:
            tts_engine: TTS引擎实例
        """
        super().__init__(tts_engine)
    
    @staticmethod
    def name() -> str:
        """策略名称"""
        return "basic"
    
    @staticmethod
    def description() -> str:
        """策略描述"""
        return "自然合成策略：使用自然语音合成，不进行时间拉伸"
    
    def process_entries(self, entries: List[SRTEntry], **kwargs) -> List[Dict[str, Any]]:
        """
        处理SRT条目，生成音频片段
        
        Args:
            entries: SRT条目列表
            **kwargs: 可选参数
                - voice_reference: 参考语音文件路径
        
        Returns:
            音频片段信息列表
        """
        voice_reference = kwargs.get('voice_reference')
        if not voice_reference:
            raise ValueError("必须提供参考语音文件路径 (voice_reference)")
        
        validate_file_exists(voice_reference, "参考语音文件")
        
        logger = get_logger()
        audio_segments = []
        
        process_logger = create_process_logger("基础策略音频生成")
        process_logger.start(f"处理 {len(entries)} 个字幕条目")
        
        for i, entry in enumerate(entries):
            try:
                text_preview = entry.text[:LOG.PROGRESS_TEXT_PREVIEW_LENGTH] + "..." if len(entry.text) > LOG.PROGRESS_TEXT_PREVIEW_LENGTH else entry.text
                process_logger.progress(i + 1, len(entries), f"条目 {entry.index}: {text_preview}")
                
                # 使用注入的TTS引擎合成语音
                audio_data, _ = self.tts_engine.synthesize(
                    text=entry.text, 
                    **kwargs
                )
                
                segment = {
                    'audio_data': audio_data,
                    'start_time': entry.start_time,
                    'end_time': entry.end_time,
                    'text': entry.text,
                    'index': entry.index,
                    'duration': entry.duration
                }
                audio_segments.append(segment)
                
            except Exception as e:
                logger.error(f"条目 {entry.index} 处理失败: {e}")
                raise e
        
        process_logger.complete(f"生成 {len(audio_segments)} 个音频片段")
        return audio_segments 