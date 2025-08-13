from dataclasses import dataclass


@dataclass
class AudioConfig:
    """音频相关配置"""
    # 音频处理常量 - 使用44.1kHz以匹配Fish Speech输出
    DEFAULT_SAMPLE_RATE: int = 44100
    DEFAULT_CHANNELS: int = 1
    AUDIO_NORMALIZATION_FACTOR: float = 32768.0  # int16 to float32 conversion

    # 音频合并配置
    DYNAMIC_BUFFER_SIZE: int = 1024
    MAX_AMPLITUDE: float = 1.0

    # 音频效果配置
    DEFAULT_FADE_DURATION: float = 0.1
    DEFAULT_GAP_DURATION: float = 0.1


def create_audio_config() -> AudioConfig:
    """工厂函数: 创建音频配置实例"""
    return AudioConfig()
