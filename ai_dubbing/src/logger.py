"""
日志系统

提供结构化的日志输出，支持不同级别的日志记录和进度显示。
"""

import logging
import sys
from typing import Optional
from datetime import datetime

# 直接导入colorama，简化代码
import colorama
from colorama import Fore, Style
colorama.init(autoreset=True)


class SRTDubbingLogger:
    """SRT配音专用日志器"""
    
    def __init__(self, name: str = "srt_dubbing", log_level: str = "INFO"):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(getattr(logging, log_level.upper()))
        
        # 避免重复添加handler
        if not self.logger.handlers:
            self._setup_handler()
    
    def _setup_handler(self) -> None:
        """设置日志处理器"""
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(logging.DEBUG)
        
        # 不使用默认的格式化器，我们会自定义输出
        handler.setFormatter(logging.Formatter('%(message)s'))
        self.logger.addHandler(handler)
    
    def _format_message(self, level: str, message: str) -> str:
        """格式化日志消息"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        # 根据级别选择颜色
        color_map = {
            "INFO": Fore.CYAN,
            "SUCCESS": Fore.GREEN, 
            "WARNING": Fore.YELLOW,
            "ERROR": Fore.RED,
            "DEBUG": Fore.MAGENTA,
            "STEP": Fore.CYAN
        }
        
        color = color_map.get(level, "")
        
        if level == "STEP":
            return f"{color}🔄 [{timestamp}] {message}{Style.RESET_ALL}"
        elif level == "SUCCESS":
            return f"{color}✅ [{timestamp}] {message}{Style.RESET_ALL}"
        elif level == "WARNING":
            return f"{color}⚠️  [{timestamp}] {message}{Style.RESET_ALL}"
        elif level == "ERROR":
            return f"{color}❌ [{timestamp}] {message}{Style.RESET_ALL}"
        else:
            return f"{color}[{timestamp}] {message}{Style.RESET_ALL}"
    
    def info(self, message: str) -> None:
        """信息日志"""
        formatted = self._format_message("INFO", message)
        self.logger.info(formatted)
    
    def success(self, message: str) -> None:
        """成功日志"""
        formatted = self._format_message("SUCCESS", message)
        self.logger.info(formatted)
    
    def warning(self, message: str) -> None:
        """警告日志"""
        formatted = self._format_message("WARNING", message)
        self.logger.warning(formatted)
    
    def error(self, message: str) -> None:
        """错误日志"""
        formatted = self._format_message("ERROR", message)
        self.logger.error(formatted)
    
    def debug(self, message: str) -> None:
        """调试日志"""
        formatted = self._format_message("DEBUG", message)
        self.logger.debug(formatted)
    
    def step(self, message: str) -> None:
        """步骤日志"""
        formatted = self._format_message("STEP", message)
        self.logger.info(formatted)


class ProcessLogger:
    """进程日志记录器，专门用于记录处理进度"""
    
    def __init__(self, process_name: str):
        self.process_name = process_name
        self.logger = get_logger()
    
    def start(self, message: str = "") -> None:
        """开始处理"""
        full_message = f"{self.process_name}开始"
        if message:
            full_message += f": {message}"
        self.logger.step(full_message)
    
    def step(self, step_name: str) -> None:
        """处理步骤"""
        self.logger.step(f"{self.process_name} - {step_name}")
    
    def progress(self, current: int, total: int, item_description: str = ""):
        """进度更新"""
        percentage = (current / total) * 100 if total > 0 else 0
        
        if item_description:
            message = f"{self.process_name} {current}/{total} ({percentage:.1f}%): {item_description}"
        else:
            message = f"{self.process_name} {current}/{total} ({percentage:.1f}%)"
        
        self.logger.info(message)
    
    def complete(self, message: str = "") -> None:
        """完成处理"""
        full_message = f"{self.process_name}完成"
        if message:
            full_message += f": {message}"
        self.logger.success(full_message)


def setup_logging(level: str = "INFO") -> SRTDubbingLogger:
    """
    设置日志系统
    
    Args:
        level: 日志级别
        
    Returns:
        配置好的日志器
    """
    logger = SRTDubbingLogger("srt_dubbing", level)
    return logger


def create_process_logger(process_name: str) -> ProcessLogger:
    """
    创建进程日志器
    
    Args:
        process_name: 进程名称
        
    Returns:
        进程日志器实例
    """
    return ProcessLogger(process_name)


# 全局日志器实例
_global_logger: Optional[SRTDubbingLogger] = None


def get_logger(name: str = "srt_dubbing", log_level: str = "INFO") -> SRTDubbingLogger:
    """获取日志器实例"""
    global _global_logger
    if _global_logger is None:
        _global_logger = SRTDubbingLogger(name, log_level)
    return _global_logger 