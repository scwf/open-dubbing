"""
基础自然合成策略

采用自然语音合成 + 静音填充的方式处理SRT字幕，
优先保证语音质量，使用静音来匹配时间间隔。
"""
from typing import List, Dict, Any
import numpy as np

from ai_dubbing.src.tts_engines.base_engine import BaseTTSEngine
from ai_dubbing.src.utils import validate_file_exists
from ai_dubbing.src.config import AUDIO, LOG, STRATEGY
from ai_dubbing.src.parsers.srt_parser import SRTEntry
from ai_dubbing.src.strategies.base_strategy import TimeSyncStrategy
from ai_dubbing.src.logger import get_logger

class BasicStrategy(TimeSyncStrategy):
    """基础自然合成策略实现"""
    
    def __init__(self, tts_engine: 'BaseTTSEngine', **kwargs):
        """
        初始化基础策略
        
        Args:
            tts_engine: TTS引擎实例
        """
        super().__init__(tts_engine)
        self.logger = get_logger()
    
    @staticmethod
    def name() -> str:
        """策略名称"""
        return "basic"
    
    @staticmethod
    def description() -> str:
        """策略描述"""
        return "自然合成策略：使用自然语音合成，不进行时间拉伸"
    
    def synthesize_one(self, entry: SRTEntry, **kwargs) -> Dict[str, Any]:
        """合成单条字幕（由基类并发调度）"""
        voice_reference = kwargs.get('voice_reference')
        if not voice_reference:
            raise ValueError("必须提供参考语音文件路径 (voice_reference)")

        validate_file_exists(voice_reference, "参考语音文件")

        audio_data, sampling_rate = self.tts_engine.synthesize(
            text=entry.text,
            **kwargs
        )

        if STRATEGY.ENABLE_SAVE_ENTRY_WAVFILE:
            import scipy.io.wavfile as wav_test
            import os
            test_output_dir = "/tmp/dubbing_tests"
            os.makedirs(test_output_dir, exist_ok=True)
            test_filename = os.path.join(test_output_dir, f"basic_entry_{entry.index}.wav")
            wav_test.write(test_filename, sampling_rate, (audio_data * 32767).astype(np.int16))
            self.logger.info(f"调试: 基础策略音频已保存到 {test_filename}")

        return {
            'audio_data': audio_data,
            'start_time': entry.start_time,
            'end_time': entry.end_time,
            'text': entry.text,
            'index': entry.index,
            'duration': entry.duration
        }