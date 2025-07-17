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

def get_tts_engine(engine_name: str) -> 'BaseTTSEngine':
    """
    TTS引擎工厂函数。

    :param engine_name: 要实例化的引擎名称。
    :return: TTS引擎的实例。
    """
    engine_class = TTS_ENGINES.get(engine_name)
    if not engine_class:
        raise ValueError(f"未找到名为 '{engine_name}' 的TTS引擎。可用引擎: {list(TTS_ENGINES.keys())}")
    
    # mypy需要明确知道这里返回的是BaseTTSEngine的子类实例
    engine_instance: 'BaseTTSEngine' = engine_class()
    return engine_instance 