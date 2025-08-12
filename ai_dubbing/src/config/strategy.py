from dataclasses import dataclass


@dataclass
class StrategyConfig:
    """策略相关配置"""
    # 时间拉伸策略 - 优化音质保护
    TIME_STRETCH_THRESHOLD: float = 0.05  # 变速阈值 (5%)
    TIME_DURATION_TOLERANCE: float = 0.1   # 时间偏差容忍度 (0.1秒)

    # 标准变速范围 - 放宽限制以支持更多场景
    MAX_SPEED_RATIO: float = 4.0    # 放宽到4.0倍速（FFmpeg atempo支持上限）
    MIN_SPEED_RATIO: float = 0.25   # 放宽到0.25倍速（FFmpeg atempo下限）

    # 高质量模式的变速范围 - 用于音质敏感场景
    HIGH_QUALITY_MAX_SPEED: float = 2.0
    HIGH_QUALITY_MIN_SPEED: float = 0.5

    # 超宽变速范围 - 用于极端场景（需用户显式设置）
    ULTRA_WIDE_MAX_SPEED: float = 10.0
    ULTRA_WIDE_MIN_SPEED: float = 0.1

    # 基础策略 - 保持不变
    SILENCE_THRESHOLD: float = 0.5
    BASIC_MAX_SPEED_RATIO: float = 1.2
    BASIC_MIN_SPEED_RATIO: float = 0.8

    # 调试功能开关
    ENABLE_SAVE_ENTRY_WAVFILE: bool = False  # 是否保存各个字幕条目的音频文件到临时目录


def create_strategy_config() -> StrategyConfig:
    """工厂函数: 创建策略配置实例"""
    return StrategyConfig()
