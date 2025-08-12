from importlib import import_module
from typing import Dict

from .base_engine import BaseTTSEngine

# 引擎路径映射，使用懒加载避免未安装依赖时导入失败
TTS_ENGINES: Dict[str, str] = {
    "index_tts": ".index_tts_engine.IndexTTSEngine",
    "f5_tts": ".f5_tts_engine.F5TTSEngine",
    "cosy_voice": ".cosy_voice_engine.CosyVoiceEngine",
    "fish_speech": ".fish_speech_engine.FishSpeechEngine",
}


def get_tts_engine(engine_name: str) -> BaseTTSEngine:
    """TTS引擎工厂函数，按需导入具体实现。"""
    path = TTS_ENGINES.get(engine_name)
    if not path:
        raise ValueError(
            f"未找到名为 '{engine_name}' 的TTS引擎。可用引擎: {list(TTS_ENGINES.keys())}"
        )
    module_path, class_name = path.rsplit(".", 1)
    module = import_module(module_path, package=__name__)
    engine_class = getattr(module, class_name)
    return engine_class()
