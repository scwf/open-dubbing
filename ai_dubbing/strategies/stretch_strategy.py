"""
时间拉伸策略

通过时间拉伸技术，将合成的语音精确匹配到SRT字幕的规定时长，
在保证语音完整性的同时，实现与视频的精确同步。

优化：
1. 音频时长小于字幕时长：用静音拼接
2. 音频时长大于字幕时长：使用FFmpeg的atempo滤镜调整播放速率
"""
import numpy as np
import tempfile
import os
from typing import List, Dict, Any, Optional
import ffmpeg

from ..tts_engines.base_engine import BaseTTSEngine
from ..config import STRATEGY, LOG
from ..parsers.srt_parser import SRTEntry
from .base_strategy import TimeSyncStrategy
from ..logger import get_logger

class StretchStrategy(TimeSyncStrategy):
    """时间拉伸同步策略实现"""

    def __init__(self, 
                 tts_engine: 'BaseTTSEngine',
                 max_speed_ratio: Optional[float] = None,
                 min_speed_ratio: Optional[float] = None,
                 mode: str = "standard"):
        """
        初始化时间拉伸策略
        
        Args:
            tts_engine: TTS引擎实例
            max_speed_ratio: 最大语速比例，覆盖默认设置
            min_speed_ratio: 最小语速比例，覆盖默认设置
            mode: 变速模式 ("standard"=标准, "high_quality"=高质量, "ultra_wide"=超宽)
        """
        super().__init__(tts_engine)
        self.logger = get_logger()
        
        # 根据模式选择变速范围
        if max_speed_ratio is None and min_speed_ratio is None:
            if mode == "high_quality":
                self.max_speed_ratio = STRATEGY.HIGH_QUALITY_MAX_SPEED
                self.min_speed_ratio = STRATEGY.HIGH_QUALITY_MIN_SPEED
            elif mode == "ultra_wide":
                self.max_speed_ratio = STRATEGY.ULTRA_WIDE_MAX_SPEED
                self.min_speed_ratio = STRATEGY.ULTRA_WIDE_MIN_SPEED
            else:  # standard
                self.max_speed_ratio = STRATEGY.MAX_SPEED_RATIO
                self.min_speed_ratio = STRATEGY.MIN_SPEED_RATIO
        else:
            # 使用用户自定义参数
            self.max_speed_ratio = max_speed_ratio or STRATEGY.MAX_SPEED_RATIO
            self.min_speed_ratio = min_speed_ratio or STRATEGY.MIN_SPEED_RATIO
    
    def _apply_atempo_filter(self, audio_data: np.ndarray, sampling_rate: int, target_duration: float) -> np.ndarray:
        """
        使用FFmpeg的atempo滤镜调整音频播放速率，确保精确匹配目标时长
        
        Args:
            audio_data: 原始音频数据
            sampling_rate: 采样率
            target_duration: 目标时长（秒）
            
        Returns:
            精确匹配目标时长的音频数据
        """            
        source_duration = len(audio_data) / sampling_rate
        if source_duration <= 0:
            return audio_data
            
        # 计算变速比例
        original_rate = source_duration / target_duration
        
        # 限制变速范围
        rate = np.clip(original_rate, self.min_speed_ratio, self.max_speed_ratio)
        
        if rate != original_rate:
            self.logger.warning(f"变速比例超出限制范围，已调整: {original_rate:.3f} → {rate:.3f} ")
        
        if rate <= 1.0:
            # 实际时长小于等于目标时长：直接填充静音
            target_samples = int(target_duration * sampling_rate)
            return self._adjust_length_precisely(audio_data, target_samples)
            
        # 实际时长大于目标时长：使用FFmpeg压缩音频
        try:
            import io
            import scipy.io.wavfile as wav
            
            # 使用ffmpeg-python的内存管道
            input_buffer = io.BytesIO()
            wav.write(input_buffer, sampling_rate, (audio_data * 32767).astype(np.int16))
            input_buffer.seek(0)
            
            # 使用ffmpeg-python同步处理音频
            output_data, _ = (
                ffmpeg
                .input('pipe:', format='wav')
                .filter('atempo', rate)
                .output('pipe:', format='wav', 
                       ar=sampling_rate, 
                       ac=1, 
                       sample_fmt='s16',
                       loglevel='error')
                .overwrite_output()
                .run(input=input_buffer.getvalue(), capture_stdout=True, capture_stderr=True)
            )
            
            if not output_data:
                raise ValueError("FFmpeg输出为空")
            
            # 读取处理后的音频
            output_buffer = io.BytesIO(output_data)
            _, processed_audio = wav.read(output_buffer)
            
            if processed_audio is None or len(processed_audio) == 0:
                raise ValueError("FFmpeg未能生成有效音频数据")
            
            processed_audio = processed_audio.astype(np.float32) / 32767.0
            
            # # 验证并精确调整时长
            # actual_duration = len(processed_audio) / sampling_rate
            # duration_diff = abs(actual_duration - target_duration)
            
            # if duration_diff > 0.01:  # 10ms误差容限
            #     self.logger.info(f"FFmpeg变速后时长微调: {actual_duration:.3f}s -> {target_duration:.3f}s")
            #     target_samples = int(target_duration * sampling_rate)
            #     return self._adjust_length_precisely(processed_audio, target_samples)
            
            return processed_audio
            
        except Exception as e:
            error_msg = str(e)
            if hasattr(e, 'stderr') and e.stderr:
                error_msg = e.stderr.decode()
            self.logger.error(f"FFmpeg处理失败: {error_msg}")
            raise RuntimeError(f"FFmpeg处理失败: {error_msg}") from e
    
    def _adjust_length_precisely(self, audio_data: np.ndarray, target_samples: int) -> np.ndarray:
        """
        精确调整音频长度到目标样本数
        
        Args:
            audio_data: 原始音频数据
            target_samples: 目标样本数
            
        Returns:
            精确匹配长度的音频数据
        """
        current_samples = len(audio_data)
        
        if current_samples == target_samples:
            return audio_data
        elif current_samples > target_samples:
            # 截断到精确长度
            self.logger.warning(f"音频长度超过目标长度，将被截断: {current_samples} → {target_samples} 样本")
            return audio_data[:target_samples]
        else:
            # 填充静音到精确长度
            padding_samples = target_samples - current_samples
            padding = np.zeros(padding_samples, dtype=np.float32)
            return np.concatenate([audio_data, padding])
    
    
    @staticmethod
    def name() -> str:
        """策略名称"""
        return "stretch"

    @staticmethod
    def description() -> str:
        """策略描述"""
        return "时间拉伸策略：通过改变语速来精确匹配字幕时长（支持0.25-4.0倍速）"

    def synthesize_one(self, entry: SRTEntry, **kwargs) -> Dict[str, Any]:
        """合成单条字幕并进行时长匹配（由基类并发调度）"""
        voice_reference = kwargs.get('voice_reference')
        if not voice_reference:
            raise ValueError("必须提供参考语音文件路径 (voice_reference)")

        audio_data, sampling_rate = self.tts_engine.synthesize(
            text=entry.text,
            **kwargs
        )

        if STRATEGY.ENABLE_SAVE_ENTRY_WAVFILE:
            import scipy.io.wavfile as wav_test
            import os
            test_output_dir = "/tmp/dubbing_tests"
            os.makedirs(test_output_dir, exist_ok=True)
            test_filename = os.path.join(test_output_dir, f"original_entry_{entry.index}.wav")
            wav_test.write(test_filename, sampling_rate, (audio_data * 32767).astype(np.int16))
            self.logger.info(f"调试: 原始音频已保存到 {test_filename}")

        buffer_ratio = 0.005
        buffer_duration = max(entry.duration * buffer_ratio, 10)
        buffer_duration = min(buffer_duration, 50)
        target_duration = max((entry.duration - buffer_duration) / 1000.0, 0.1)
        processed_audio = self._apply_atempo_filter(audio_data, sampling_rate, target_duration)
        target_samples = int(entry.duration * sampling_rate / 1000.0)
        result_audio = self._adjust_length_precisely(processed_audio, target_samples)

        if STRATEGY.ENABLE_SAVE_ENTRY_WAVFILE:
            import scipy.io.wavfile as wav_test
            import os
            test_output_dir = "/tmp/dubbing_tests"
            os.makedirs(test_output_dir, exist_ok=True)
            test_filename = os.path.join(test_output_dir, f"stretch_entry_{entry.index}.wav")
            wav_test.write(test_filename, sampling_rate, (result_audio * 32767).astype(np.int16))
            self.logger.info(f"调试: 处理后音频已保存到 {test_filename}")

        return {
            'audio_data': result_audio,
            'start_time': entry.start_time,
            'end_time': entry.end_time,
            'text': entry.text,
            'index': entry.index,
            'duration': entry.duration
        }
