"""
通用工具模块

提供项目中常用的工具函数和类
"""

import os
import sys
from pathlib import Path
from typing import Optional, Dict, Any, List, Union
import logging
import numpy as np

from ai_dubbing.src.config import CosyVoiceConfig, IndexTTSConfig, FishSpeechConfig, AUDIO


def setup_project_path():
    """
    设置项目路径，确保可以正确导入模块
    
    这个函数应该在每个需要导入项目模块的文件开头调用一次。
    """
    # 获取项目根目录 (index-tts)
    current_file = Path(__file__).resolve()
    project_root = current_file.parent.parent.parent  # ai_dubbing/src/utils/common_utils.py -> index-tts
    
    # 添加到 sys.path（如果还没有的话）
    project_root_str = str(project_root)
    if project_root_str not in sys.path:
        sys.path.append(project_root_str)

    # 仅当 CosyVoiceConfig.SOURCE_DIR 存在时才添加到 sys.path
    if os.path.exists(CosyVoiceConfig.SOURCE_DIR) and CosyVoiceConfig.SOURCE_DIR not in sys.path:
        sys.path.append(CosyVoiceConfig.SOURCE_DIR)
        sys.path.append(CosyVoiceConfig.SOURCE_DIR + "/third_party/Matcha-TTS")

    # 仅当 IndexTTSConfig.SOURCE_DIR 存在时才添加到 sys.path
    if os.path.exists(IndexTTSConfig.SOURCE_DIR) and IndexTTSConfig.SOURCE_DIR not in sys.path:
        sys.path.append(IndexTTSConfig.SOURCE_DIR)

    # 仅当 FishSpeechConfig.SOURCE_DIR 存在时才添加到 sys.path
    if os.path.exists(FishSpeechConfig.SOURCE_DIR) and FishSpeechConfig.SOURCE_DIR not in sys.path:
        sys.path.append(FishSpeechConfig.SOURCE_DIR)

    return project_root


def validate_file_exists(file_path: str, file_type: str = "文件") -> bool:
    """
    验证文件是否存在
    
    Args:
        file_path: 文件路径
        file_type: 文件类型描述（用于错误信息）
    
    Returns:
        bool: 文件是否存在
        
    Raises:
        FileNotFoundError: 文件不存在时抛出
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"{file_type}不存在: {file_path}")
    return True


def create_directory_if_needed(file_path: str) -> Path:
    """
    如果目录不存在则创建
    
    Args:
        file_path: 文件路径（将创建其父目录）
    
    Returns:
        Path: 父目录路径
    """
    output_dir = Path(file_path).parent
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def format_duration(seconds: float) -> str:
    """
    格式化时长显示
    
    Args:
        seconds: 秒数
    
    Returns:
        str: 格式化的时长字符串
    """
    if seconds < 60:
        return f"{seconds:.2f}s"
    elif seconds < 3600:
        minutes = seconds // 60
        secs = seconds % 60
        return f"{int(minutes)}m {secs:.1f}s"
    else:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        return f"{int(hours)}h {int(minutes)}m {secs:.1f}s"


def format_progress_text(text: str, max_length: int = 30) -> str:
    """
    格式化进度显示的文本
    
    Args:
        text: 原始文本
        max_length: 最大长度
    
    Returns:
        str: 截断并格式化的文本
    """
    if len(text) <= max_length:
        return text
    return text[:max_length-3] + "..."


class ProgressLogger:
    """简单的进度日志记录器"""
    
    def __init__(self, total_items: int, description: str = "处理"):
        self.total_items = total_items
        self.current_item = 0
        self.description = description
    
    def update(self, item_index: int, item_description: str = "") -> None:
        """更新进度"""
        self.current_item = item_index + 1
        progress = (self.current_item / self.total_items) * 100
        
        if item_description:
            item_desc = format_progress_text(item_description)
            print(f"{self.description} {self.current_item}/{self.total_items} ({progress:.1f}%): {item_desc}")
        else:
            print(f"{self.description} {self.current_item}/{self.total_items} ({progress:.1f}%)")
    
    def complete(self) -> None:
        """完成进度"""
        print(f"✓ {self.description}完成，共处理 {self.total_items} 项")


def normalize_audio_data(audio_data_int16, normalization_factor: Optional[float] = None):
    """
    规范化音频数据，将int16格式的音频数据转换为float32并归一化到[-1, 1]区间。
    
    ---------------------------------
    int16格式的音频数据取值范围是[-32768, 32767]，而float32格式的音频通常要求在[-1.0, 1.0]之间。
    因此，除以32768.0可以将int16的最大绝对值映射到1.0，实现幅度归一化，便于后续音频处理和播放。
    注意：虽然正方向最大值是32767，但通常采用32768.0作为归一化因子，保证对称性和兼容性。
    
    Args:
        audio_data_int16: int16格式的音频数据
        normalization_factor: 规范化因子（默认32768.0）
    
    Returns:
        numpy.ndarray: 规范化后的float32音频数据
    """
    if normalization_factor is None:
        normalization_factor = AUDIO.AUDIO_NORMALIZATION_FACTOR  # 默认32768.0

    # 归一化到[-1, 1]的float32
    return audio_data_int16.flatten().astype(np.float32) / normalization_factor


# 项目初始化函数
def initialize_project():
    """
    初始化项目环境
    
    Returns:
        Path: project_root_path
    """
    project_root = setup_project_path()
    return project_root