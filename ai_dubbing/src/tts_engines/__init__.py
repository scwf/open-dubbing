from __future__ import annotations
from typing import Dict, Type, Any

from .base_engine import BaseTTSEngine
from .index_tts_engine import IndexTTSEngine
# 当你添加新引擎时，在这里导入
from .f5_tts_engine import F5TTSEngine
from .cosy_voice_engine import CosyVoiceEngine
from .fish_speech_engine import FishSpeechEngine

# 引擎注册表
TTS_ENGINES: Dict[str, Type['BaseTTSEngine']] = {
    "index_tts": IndexTTSEngine,
    "f5_tts": F5TTSEngine,
    "cosy_voice": CosyVoiceEngine,
    "fish_speech": FishSpeechEngine,
}

# 引擎实例缓存，实现单例模式
_engine_instances: Dict[str, 'BaseTTSEngine'] = {}

def get_tts_engine(engine_name: str) -> 'BaseTTSEngine':
    """
    TTS引擎工厂函数（单例模式）。
    
    每个引擎类型只会创建一次实例，后续调用返回同一个实例。
    这样可以避免重复加载模型到GPU，解决内存泄漏问题。

    :param engine_name: 要实例化的引擎名称。
    :return: TTS引擎的实例。
    """
    # 如果已经有缓存的实例，直接返回
    if engine_name in _engine_instances:
        return _engine_instances[engine_name]
    
    engine_class = TTS_ENGINES.get(engine_name)
    if not engine_class:
        raise ValueError(f"未找到名为 '{engine_name}' 的TTS引擎。可用引擎: {list(TTS_ENGINES.keys())}")
    
    # 创建新实例并缓存
    engine_instance: 'BaseTTSEngine' = engine_class()
    _engine_instances[engine_name] = engine_instance
    return engine_instance

def cleanup_all_engines():
    """清理所有缓存的引擎实例"""
    for engine_name, engine_instance in _engine_instances.items():
        try:
            engine_instance.cleanup()
        except Exception as e:
            print(f"清理引擎 {engine_name} 时发生错误: {e}")
    
    _engine_instances.clear()

def cleanup_engine(engine_name: str):
    """清理指定的引擎实例"""
    if engine_name in _engine_instances:
        try:
            _engine_instances[engine_name].cleanup()
        except Exception as e:
            print(f"清理引擎 {engine_name} 时发生错误: {e}")
        finally:
            del _engine_instances[engine_name] 