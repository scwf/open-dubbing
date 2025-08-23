"""
Configuration Manager

Handles loading, saving, and managing application configuration.
"""

import configparser
import logging
from pathlib import Path
from typing import Dict, Any, Optional, Union

from .config_models import DubbingConfig, BasicConfig, ConcurrencyConfig, SubtitleOptimizationConfig, TimeBorrowingConfig

logger = logging.getLogger(__name__)


class ConfigError(Exception):
    """配置相关错误"""
    pass


class ConfigManager:
    """配置管理器"""
    
    # 中文配置节名称映射
    SECTION_MAPPING = {
        "basic": "基本配置",
        "concurrency": "并发配置", 
        "subtitle_optimization": "字幕优化配置",
        "time_borrowing": "时间借用配置"
    }
    
    def __init__(self, config_file: Union[str, Path] = None):
        """
        初始化配置管理器
        
        Args:
            config_file: 配置文件路径，默认为 ai_dubbing/dubbing.conf
        """
        if config_file is None:
            config_file = Path("ai_dubbing/dubbing.conf")
        
        self.config_file = Path(config_file)
        self._config = configparser.ConfigParser()
        self._ensure_config_file_exists()
    
    def _ensure_config_file_exists(self) -> None:
        """确保配置文件存在"""
        if not self.config_file.exists():
            logger.warning(f"Config file {self.config_file} does not exist, will create with defaults")
            self.config_file.parent.mkdir(parents=True, exist_ok=True)
            self._create_default_config()
    
    def _create_default_config(self) -> None:
        """创建默认配置文件"""
        default_config = DubbingConfig()
        self.save_config(default_config)
        logger.info(f"Created default config file: {self.config_file}")
    
    def load_config(self) -> DubbingConfig:
        """
        加载配置
        
        Returns:
            DubbingConfig: 配置对象
            
        Raises:
            ConfigError: 配置加载失败
        """
        try:
            self._config.read(self.config_file, encoding="utf-8")
            
            config_data = self._parse_config_sections()
            return DubbingConfig.from_dict(config_data)
            
        except Exception as e:
            logger.error(f"Failed to load config from {self.config_file}: {e}")
            raise ConfigError(f"Failed to load configuration: {e}")
    
    def _parse_config_sections(self) -> Dict[str, Any]:
        """解析配置文件各节"""
        config_data = {}
        
        # 解析基本配置
        basic_section = self.SECTION_MAPPING["basic"]
        if self._config.has_section(basic_section):
            config_data["basic"] = {
                "voice_files": self._config.get(basic_section, "voice_files", fallback=""),
                "prompt_texts": self._config.get(basic_section, "prompt_texts", fallback=""),
                "tts_engine": self._config.get(basic_section, "tts_engine", fallback="fish_speech"),
                "strategy": self._config.get(basic_section, "strategy", fallback="stretch"),
                "language": self._config.get("高级配置", "language", fallback="zh"),
            }
        
        # 解析并发配置
        concurrency_section = self.SECTION_MAPPING["concurrency"]
        if self._config.has_section(concurrency_section):
            config_data["concurrency"] = {
                "tts_max_concurrency": self._config.getint(concurrency_section, "tts_max_concurrency", fallback=8),
                "tts_max_retries": self._config.getint(concurrency_section, "tts_max_retries", fallback=2),
            }
        
        # 解析字幕优化配置
        subtitle_section = self.SECTION_MAPPING["subtitle_optimization"]
        if self._config.has_section(subtitle_section):
            config_data["subtitle_optimization"] = {
                "llm_api_key": self._config.get(subtitle_section, "llm_api_key", fallback=""),
                "llm_model": self._config.get(subtitle_section, "llm_model", fallback=""),
                "base_url": self._config.get(subtitle_section, "base_url", fallback=""),
                "chinese_char_min_time": self._config.getint(subtitle_section, "chinese_char_min_time", fallback=150),
                "english_word_min_time": self._config.getint(subtitle_section, "english_word_min_time", fallback=250),
                "llm_max_concurrency": self._config.getint(subtitle_section, "llm_max_concurrency", fallback=50),
                "llm_max_retries": self._config.getint(subtitle_section, "llm_max_retries", fallback=3),
                "llm_timeout": self._config.getint(subtitle_section, "llm_timeout", fallback=60),
                "optimized_srt_output_file": self._config.get(subtitle_section, "optimized_srt_output_file", fallback=""),
            }
        
        # 解析时间借用配置
        time_section = self.SECTION_MAPPING["time_borrowing"]
        if self._config.has_section(time_section):
            config_data["time_borrowing"] = {
                "min_gap_threshold": self._config.getint(time_section, "min_gap_threshold", fallback=200),
                "borrow_ratio": self._config.getfloat(time_section, "borrow_ratio", fallback=1.0),
                "extra_buffer": self._config.getint(time_section, "extra_buffer", fallback=200),
            }
        
        return config_data
    
    def save_config(self, config: DubbingConfig) -> None:
        """
        保存配置
        
        Args:
            config: 配置对象
            
        Raises:
            ConfigError: 配置保存失败
        """
        try:
            self._config.clear()
            config_data = config.to_dict()
            
            # 保存各个配置节
            self._save_basic_config(config_data["basic"])
            self._save_concurrency_config(config_data["concurrency"])
            self._save_subtitle_optimization_config(config_data["subtitle_optimization"])
            self._save_time_borrowing_config(config_data["time_borrowing"])
            
            # 写入文件
            with open(self.config_file, "w", encoding="utf-8") as f:
                self._config.write(f)
            
            logger.info(f"Configuration saved to {self.config_file}")
            
        except Exception as e:
            logger.error(f"Failed to save config to {self.config_file}: {e}")
            raise ConfigError(f"Failed to save configuration: {e}")
    
    def _save_basic_config(self, basic_config: Dict[str, Any]) -> None:
        """保存基本配置"""
        section_name = self.SECTION_MAPPING["basic"]
        self._ensure_section(section_name)
        
        for key, value in basic_config.items():
            if key != "language":  # language 保存在高级配置节
                self._config.set(section_name, key, str(value))
        
        # 保存语言设置到高级配置节
        self._ensure_section("高级配置")
        self._config.set("高级配置", "language", basic_config.get("language", "zh"))
    
    def _save_concurrency_config(self, concurrency_config: Dict[str, Any]) -> None:
        """保存并发配置"""
        section_name = self.SECTION_MAPPING["concurrency"]
        self._ensure_section(section_name)
        
        for key, value in concurrency_config.items():
            self._config.set(section_name, key, str(value))
    
    def _save_subtitle_optimization_config(self, subtitle_config: Dict[str, Any]) -> None:
        """保存字幕优化配置"""
        section_name = self.SECTION_MAPPING["subtitle_optimization"]
        self._ensure_section(section_name)
        
        for key, value in subtitle_config.items():
            self._config.set(section_name, key, str(value))
    
    def _save_time_borrowing_config(self, time_config: Dict[str, Any]) -> None:
        """保存时间借用配置"""
        section_name = self.SECTION_MAPPING["time_borrowing"]
        self._ensure_section(section_name)
        
        for key, value in time_config.items():
            self._config.set(section_name, key, str(value))
    
    def _ensure_section(self, section_name: str) -> None:
        """确保配置节存在"""
        if not self._config.has_section(section_name):
            self._config.add_section(section_name)
    
    def update_config_from_dict(self, update_data: Dict[str, Any]) -> DubbingConfig:
        """
        从字典更新配置
        
        Args:
            update_data: 更新数据
            
        Returns:
            DubbingConfig: 更新后的配置对象
        """
        current_config = self.load_config()
        config_dict = current_config.to_dict()
        
        # 递归更新配置数据
        for section_key, section_data in update_data.items():
            if section_key in config_dict and isinstance(section_data, dict):
                config_dict[section_key].update(section_data)
        
        updated_config = DubbingConfig.from_dict(config_dict)
        self.save_config(updated_config)
        
        return updated_config
    
    def get_config_value(self, section: str, key: str, fallback: Any = None) -> Any:
        """
        获取单个配置值
        
        Args:
            section: 配置节名称
            key: 配置键名
            fallback: 默认值
            
        Returns:
            配置值
        """
        try:
            config = self.load_config()
            config_dict = config.to_dict()
            
            if section in config_dict and key in config_dict[section]:
                return config_dict[section][key]
            else:
                return fallback
                
        except Exception as e:
            logger.warning(f"Failed to get config value {section}.{key}: {e}")
            return fallback
    
    def set_config_value(self, section: str, key: str, value: Any) -> None:
        """
        设置单个配置值
        
        Args:
            section: 配置节名称
            key: 配置键名
            value: 配置值
        """
        update_data = {section: {key: value}}
        self.update_config_from_dict(update_data)
    
    def reset_to_defaults(self) -> DubbingConfig:
        """
        重置为默认配置
        
        Returns:
            DubbingConfig: 默认配置对象
        """
        default_config = DubbingConfig()
        self.save_config(default_config)
        logger.info("Configuration reset to defaults")
        return default_config