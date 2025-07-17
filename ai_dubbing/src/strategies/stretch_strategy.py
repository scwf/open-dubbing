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
import subprocess
import os
from typing import List, Dict, Any, Optional

from ai_dubbing.src.tts_engines.base_engine import BaseTTSEngine
from ai_dubbing.src.config import AUDIO, STRATEGY, LOG
from ai_dubbing.src.parsers.srt_parser import SRTEntry
from ai_dubbing.src.strategies.base_strategy import TimeSyncStrategy
from ai_dubbing.src.logger import get_logger, create_process_logger

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
        rate = source_duration / target_duration
        
        # 限制变速范围
        rate = np.clip(rate, self.min_speed_ratio, self.max_speed_ratio)
        
        if abs(rate - 1.0) <= STRATEGY.TIME_STRETCH_THRESHOLD:
            # 时长接近，直接调整长度
            target_samples = int(target_duration * sampling_rate)
            return self._adjust_length_precisely(audio_data, target_samples)
            
        # 使用内存管道避免临时文件
        try:
            import io
            import scipy.io.wavfile as wav
            
            # 创建内存中的WAV数据
            wav_buffer = io.BytesIO()
            wav.write(wav_buffer, sampling_rate, (audio_data * 32767).astype(np.int16))
            wav_buffer.seek(0)
            
            # 构建FFmpeg命令，使用管道
            cmd = [
                'ffmpeg', '-y',
                '-f', 'wav', '-i', 'pipe:0',  # 从stdin读取
                '-filter_complex', f'atempo={rate}',
                '-ar', str(sampling_rate),
                '-ac', '1',
                '-sample_fmt', 's16',
                '-f', 'wav', 'pipe:1'  # 输出到stdout
            ]
            
            # 执行FFmpeg命令
            result = subprocess.run(
                cmd, 
                input=wav_buffer.getvalue(),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True
            )
            
            # 从输出读取音频数据
            output_buffer = io.BytesIO(result.stdout)
            rate_out, processed_audio = wav.read(output_buffer)
            processed_audio = processed_audio.astype(np.float32) / 32767.0
            
            # 验证并精确调整时长
            actual_duration = len(processed_audio) / sampling_rate
            duration_diff = abs(actual_duration - target_duration)
            
            if duration_diff > 0.01:  # 10ms误差容限
                logger = get_logger()
                logger.debug(f"FFmpeg变速后时长微调: {actual_duration:.3f}s -> {target_duration:.3f}s")
                target_samples = int(target_duration * sampling_rate)
                return self._adjust_length_precisely(processed_audio, target_samples)
            
            return processed_audio
            
        except subprocess.CalledProcessError as e:
            logger = get_logger()
            logger.error(f"FFmpeg处理失败: {e.stderr.decode() if e.stderr else str(e)}")
            # 降级到精确长度调整
            target_samples = int(target_duration * sampling_rate)
            return self._adjust_length_precisely(audio_data, target_samples)
        except Exception as e:
            logger = get_logger()
            logger.error(f"音频处理失败: {e}")
            target_samples = int(target_duration * sampling_rate)
            return self._adjust_length_precisely(audio_data, target_samples)
    
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
            return audio_data[:target_samples]
        else:
            # 填充静音到精确长度
            padding_samples = target_samples - current_samples
            padding = np.zeros(padding_samples, dtype=np.float32)
            return np.concatenate([audio_data, padding])
    
    def _pad_with_silence(self, audio_data: np.ndarray, sampling_rate: int, target_duration: float) -> np.ndarray:
        """
        使用静音填充音频到目标时长
        
        Args:
            audio_data: 原始音频数据
            sampling_rate: 采样率
            target_duration: 目标时长（秒）
            
        Returns:
            填充后的音频数据
        """
        source_duration = len(audio_data) / sampling_rate
        if source_duration >= target_duration:
            return audio_data
            
        padding_duration = target_duration - source_duration
        padding_samples = int(padding_duration * sampling_rate)
        
        if padding_samples > 0:
            silence = np.zeros(padding_samples, dtype=np.float32)
            return np.concatenate([audio_data, silence])
        
        return audio_data
    
    @staticmethod
    def name() -> str:
        """策略名称"""
        return "stretch"

    @staticmethod
    def description() -> str:
        """策略描述"""
        return "时间拉伸策略：通过改变语速来精确匹配字幕时长（支持0.25-4.0倍速）"

    def process_entries(self, entries: List[SRTEntry], **kwargs) -> List[Dict[str, Any]]:
        """
        处理SRT条目，生成与字幕时长精确匹配的音频片段
        
        优化逻辑：
        1. 音频时长小于字幕时长：用静音拼接
        2. 音频时长大于字幕时长：使用FFmpeg的atempo滤镜调整播放速率
        
        Args:
            entries: SRT条目列表
            **kwargs: 可选参数
                - voice_reference: 参考语音文件路径
        
        Returns:
            音频片段信息列表
        """
        logger = get_logger()
        voice_reference = kwargs.get('voice_reference')
        if not voice_reference:
            raise ValueError("必须提供参考语音文件路径 (voice_reference)")
        
        audio_segments = []
        
        # 创建处理进度日志器
        process_logger = create_process_logger("时间拉伸策略音频生成")
        process_logger.start(f"处理 {len(entries)} 个字幕条目")
        
        for i, entry in enumerate(entries):
            try:
                # 始终显示进度，不仅仅在verbose模式下
                text_preview = entry.text[:LOG.PROGRESS_TEXT_PREVIEW_LENGTH] + "..." if len(entry.text) > LOG.PROGRESS_TEXT_PREVIEW_LENGTH else entry.text
                process_logger.progress(i + 1, len(entries), f"条目 {entry.index}: {text_preview}")
                
                # 1. 合成原始语音 - 使用注入的TTS引擎
                assert self.tts_engine is not None, "TTS引擎未被注入"
                audio_data, sampling_rate = self.tts_engine.synthesize(
                    text=entry.text,
                    **kwargs
                )
                
                # 2. 计算时长和变速比例
                source_duration = len(audio_data) / sampling_rate
                target_duration = entry.duration
                
                if target_duration == 0:
                    processed_audio = audio_data
                else:
                    # 3. 根据时长关系选择处理策略
                    if source_duration < target_duration:
                        # 音频时长小于字幕时长：用静音拼接
                        processed_audio = self._pad_with_silence(
                            audio_data, sampling_rate, target_duration
                        )
                        padding_duration = target_duration - source_duration
                        logger.debug(
                            f"条目 {entry.index} 音频偏短 {padding_duration:.2f}s，已用静音填充"
                        )
                    elif source_duration > target_duration:
                        # 音频时长大于字幕时长：使用FFmpeg atempo滤镜
                        processed_audio = self._apply_atempo_filter(
                            audio_data, sampling_rate, target_duration
                        )
                        logger.debug(
                            f"条目 {entry.index} 使用FFmpeg atempo滤镜调整播放速率"
                        )
                    else:
                        # 时长完全匹配
                        processed_audio = audio_data

                # 4. 创建音频片段
                segment = {
                    'audio_data': processed_audio,
                    'start_time': entry.start_time,
                    'end_time': entry.end_time,
                    'text': entry.text,
                    'index': entry.index,
                    'duration': entry.duration
                }
                audio_segments.append(segment)

            except Exception as e:
                logger.error(f"条目 {entry.index} 处理失败: {e}")
                # 后备方案：创建静音片段
                default_sr = AUDIO.DEFAULT_SAMPLE_RATE
                silence_data = np.zeros(int(entry.duration * default_sr), dtype=np.float32)
                segment = {
                    'audio_data': silence_data,
                    'start_time': entry.start_time,
                    'end_time': entry.end_time,
                    'text': entry.text,
                    'index': entry.index,
                    'duration': entry.duration
                }
                audio_segments.append(segment)
        
        process_logger.complete(f"生成 {len(audio_segments)} 个音频片段")
        return audio_segments

# 注册逻辑将移至 __init__.py 中，以更好地管理
# def _register_stretch_strategy():
#     """注册时间拉伸策略"""
#     from ai_dubbing.src.strategies import _strategy_registry
#     _strategy_registry['stretch'] = StretchStrategy

# # 在模块导入时自动注册
# _register_stretch_strategy() 