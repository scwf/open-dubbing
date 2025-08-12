"""
音频处理器

提供音频合成、合并、格式转换等功能，支持多种音频格式的输入输出。
"""

import numpy as np
from typing import List, Dict, Any, Optional, Union
from pathlib import Path
import soundfile as sf

from .config import AUDIO
from .utils.common_utils import create_directory_if_needed
from .logger import get_logger


class AudioProcessor:
    """音频处理器类"""
    
    def __init__(self):
        """
        初始化音频处理器
        
        音频处理器现在使用固定的标准采样率44.1kHz，所有TTS引擎已标准化输出
        """
        self.sample_rate = AUDIO.DEFAULT_SAMPLE_RATE  # 固定44.1kHz
        self.audio_segments: List[Dict[str, Any]] = []
    

    def merge_audio_segments(self, segments: List[Dict[str, Any]], 
                           strategy_name: str = "stretch") -> np.ndarray:
        """
        根据策略类型合并音频片段
        
        Args:
            segments: 音频片段列表，每个包含：
                - audio_data: 音频数据
                - start_time: 开始时间
                - end_time: 结束时间
            strategy_name: 策略名称 ("basic", "stretch")
        
        Returns:
            合并后的音频数据
        """
        if not segments:
            return np.array([])
        
        logger = get_logger()
        
        # 根据策略选择合并方式
        if strategy_name == "basic":
            logger.info(f"使用自然拼接模式进行音频合并 (策略: {strategy_name})")
            return self._natural_concatenation(segments)
        else:
            logger.info(f"使用时间同步模式进行音频合并 (策略: {strategy_name})")
            return self._time_synchronized_merge(segments)

    
    def _natural_concatenation(self, segments: List[Dict[str, Any]]) -> np.ndarray:
        """
        自然拼接模式：按字幕顺序连续拼接音频，忽略时间约束
        
        适用于basic策略，优先保证语音的自然流畅性
        
        Args:
            segments: 音频片段列表
            
        Returns:
            拼接后的音频数据
        """
        logger = get_logger()
        
        sorted_segments = sorted(segments, key=lambda x: x['index'])
        
        # 收集所有有效的音频数据
        audio_parts = []
        
        for segment in sorted_segments:
            audio_data = segment['audio_data']
            
            # 确保音频数据是numpy数组
            if not isinstance(audio_data, np.ndarray):
                audio_data = np.array(audio_data, dtype=np.float32)
            
            # 检查音频数据是否有效
            if len(audio_data) == 0:
                continue
            
            audio_parts.append(audio_data)
        
        if not audio_parts:
            logger.warning("没有有效的音频数据可供拼接")
            return np.array([])
        
        # 简单直接拼接所有音频片段
        merged_audio = np.concatenate(audio_parts)
        
        logger.success(f"自然拼接完成: {len(audio_parts)} 个片段，总时长 {len(merged_audio)/self.sample_rate:.2f}s")
        
        return merged_audio
    
    def _time_synchronized_merge(self, segments: List[Dict[str, Any]]) -> np.ndarray:
        """
        时间同步合并模式：严格按照字幕时间轴对齐音频片段
        
        简化后的逻辑：
        1. 使用字幕文件的总时长作为基准
        2. 严格按照字幕的start_time和end_time放置音频
        3. 音频片段已在前序处理中匹配字幕时长，无需额外处理
        
        Args:
            segments: 音频片段列表（已匹配字幕时长）
            
        Returns:
            合并后的音频数据，严格对齐字幕时间轴
        """
        logger = get_logger()
        
        if not segments:
            return np.array([])
        
        # 按开始时间排序
        sorted_segments = sorted(segments, key=lambda x: x['start_time'])
        
        # 计算准确的结束时间（基于字幕文件的时间轴）
        max_end_time_ms = max(seg['end_time'] for seg in sorted_segments)
        total_samples = int(max_end_time_ms * self.sample_rate // 1000)  # 使用整数运算避免浮点精度损失
        
        logger.debug("时间同步合并详情:")
        logger.debug(f"  字幕总时长: {max_end_time_ms / 1000:.2f}s")
        logger.debug(f"  总样本数: {total_samples}")
        
        # 创建固定大小的音频数组
        merged_audio = np.zeros(total_samples, dtype=np.float32)
        
        # 将每个音频片段精确放置到字幕时间轴（音频已匹配字幕时长）
        for i, segment in enumerate(sorted_segments):
            audio_data = segment['audio_data']
            
            # 确保音频数据是numpy数组
            if not isinstance(audio_data, np.ndarray):
                audio_data = np.array(audio_data, dtype=np.float32)
            
            # 检查音频数据是否有效
            if len(audio_data) == 0:
                logger.warning(f"片段 {i+1} (条目 {segment.get('index', '?')}) 音频数据为空")
                continue
            
            # 计算精确的时间位置
            start_sample = int(segment['start_time'] * self.sample_rate // 1000)
            end_sample = int(segment['end_time'] * self.sample_rate // 1000)
            target_length = end_sample - start_sample
            
            # 音频已在前序处理中匹配字幕时长，直接放置
            if target_length == len(audio_data):
                # 完美匹配，直接放置
                merged_audio[start_sample:end_sample] = audio_data
                logger.debug(f"    ✓ 已放置: {start_sample}-{end_sample} 样本")
            elif len(audio_data) <= target_length:
                # 音频较短或正好，放置后剩余部分为静音（已在前面处理过）
                actual_end = start_sample + len(audio_data)
                merged_audio[start_sample:actual_end] = audio_data
                logger.debug(f"    ✓ 已放置: {start_sample}-{actual_end} 样本")
            else:
                # 音频较长，截断到字幕时长（理论上不应发生，安全处理）
                merged_audio[start_sample:end_sample] = audio_data[:target_length]
                logger.warning(f"    ⚠ 音频被截断到字幕时长: {target_length} 样本")
        
        # 防止音频过载（混音时可能超过[-1,1]范围）
        max_val = np.max(np.abs(merged_audio))
        if max_val > AUDIO.MAX_AMPLITUDE:
            merged_audio = merged_audio / max_val
            logger.debug(f"音频归一化: 最大值 {max_val:.2f} -> {AUDIO.MAX_AMPLITUDE}")
        
        final_duration = len(merged_audio) / self.sample_rate
        logger.success(f"时间同步合并完成: 最终时长 {final_duration:.2f}s，与字幕时间轴完全对齐")
        
        return merged_audio

    
    
    def export_audio(self, audio_data: np.ndarray, 
                    output_path: str, format: str = "wav") -> bool:
        """
        导出音频文件
        
        Args:
            audio_data: 音频数据
            output_path: 输出路径
            format: 音频格式 (wav, mp3, flac等)
        
        Returns:
            导出是否成功
        """
        try:
            # 确保输出目录存在
            create_directory_if_needed(output_path)
            
            # 归一化音频数据到合适范围
            if len(audio_data) > 0:
                # 防止过载，限制在[-1, 1]范围内
                max_val = np.max(np.abs(audio_data))
                if max_val > AUDIO.MAX_AMPLITUDE:
                    audio_data = audio_data / max_val
            
            # 使用soundfile导出音频
            sf.write(output_path, audio_data, self.sample_rate, format=format.upper())
            
            logger = get_logger()
            logger.success(f"音频已导出到: {output_path}")
            return True
            
        except Exception as e:
            logger = get_logger()
            logger.error(f"导出音频失败: {e}")
            return False
    
    
    def get_audio_info(self, audio_data: np.ndarray) -> Dict[str, Any]:
        """
        获取音频信息
        
        Args:
            audio_data: 音频数据
        
        Returns:
            音频信息字典
        """
        if len(audio_data) == 0:
            return {'duration': 0, 'peak_level': 0, 'rms_level': 0}
        
        duration = len(audio_data) / self.sample_rate
        peak_level = np.max(np.abs(audio_data))
        rms_level = np.sqrt(np.mean(audio_data ** 2))
        
        return {
            'duration': duration,
            'peak_level': peak_level,
            'rms_level': rms_level,
            'sample_count': len(audio_data)
        } 

    def merge_audio_segments_with_gaps(self, 
                                      segments: List[Dict[str, Any]], 
                                      gap_duration: Optional[float] = None) -> List[Dict[str, Any]]:
        """
        在音频片段间添加间隔
        
        Args:
            segments: 音频片段列表
            gap_duration: 间隔时长（秒）
            
        Returns:
            处理后的音频片段列表
        """
        gap_duration = gap_duration or AUDIO.DEFAULT_GAP_DURATION
        
        if not segments:
            return []
        
        # 添加间隔的逻辑实现
        processed_segments = []
        for i, segment in enumerate(segments):
            processed_segments.append(segment)
            
            # 最后一个片段后不添加间隔
            if i < len(segments) - 1:
                gap_samples = int(gap_duration * self.sample_rate)
                gap_audio = np.zeros(gap_samples, dtype=np.float32)
                
                gap_segment = {
                    'audio_data': gap_audio,
                    'start_time': segment['end_time'],
                    'end_time': segment['end_time'] + gap_duration,
                    'text': '[间隔]',
                    'index': f"{segment['index']}_gap",
                    'duration': gap_duration
                }
                processed_segments.append(gap_segment)
        
        return processed_segments

