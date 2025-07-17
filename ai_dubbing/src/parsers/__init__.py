"""
统一解析器模块

提供SRT字幕文件和TXT文本文件的解析功能，支持统一的API接口。
"""

from .srt_parser import SRTParser, SRTEntry
from .txt_parser import TXTParser

__all__ = [
    "SRTParser",
    "SRTEntry", 
    "TXTParser"
]

# 便捷的工厂函数
def get_parser(file_path):
    """
    根据文件扩展名自动选择合适的解析器
    
    Args:
        file_path: 文件路径
        
    Returns:
        对应的解析器实例
        
    Raises:
        ValueError: 不支持的文件类型
    """
    from pathlib import Path
    
    ext = Path(file_path).suffix.lower()
    if ext == '.srt':
        return SRTParser()
    elif ext == '.txt':
        return TXTParser()
    else:
        raise ValueError(f"不支持的文件类型: {ext}")

# 快捷别名
ParserFactory = get_parser