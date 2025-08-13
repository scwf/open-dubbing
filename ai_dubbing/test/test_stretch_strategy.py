import numpy as np
import pytest
import ffmpeg
import sys
from pathlib import Path
import types

# 添加项目根目录到路径并伪造torch依赖
sys.modules['torch'] = types.ModuleType('torch')
current_file = Path(__file__).resolve()
sys.path.insert(0, str(current_file.parent.parent.parent))

from ai_dubbing.src.strategies.stretch_strategy import StretchStrategy
from ai_dubbing.src.tts_engines.base_engine import BaseTTSEngine


class DummyTTSEngine(BaseTTSEngine):
    def __init__(self):
        pass

    def synthesize(self, text: str, **kwargs):
        return np.zeros(1, dtype=np.float32), 16000


@pytest.fixture
def strategy():
    return StretchStrategy(tts_engine=DummyTTSEngine())


def test_run_ffmpeg_atempo_success(strategy):
    audio = np.random.rand(16000).astype(np.float32) * 2 - 1
    output = strategy._run_ffmpeg_atempo(audio, 16000, 1.5)
    assert isinstance(output, bytes)
    assert len(output) > 0


def test_run_ffmpeg_atempo_failure(monkeypatch, strategy):
    def fake_input(*args, **kwargs):
        raise Exception("ffmpeg failure")

    monkeypatch.setattr(ffmpeg, "input", fake_input)

    audio = np.zeros(16000, dtype=np.float32)
    with pytest.raises(RuntimeError):
        strategy._run_ffmpeg_atempo(audio, 16000, 1.5)


def test_post_process_audio_success(strategy):
    audio = np.random.rand(16000).astype(np.float32) * 2 - 1
    output = strategy._run_ffmpeg_atempo(audio, 16000, 1.5)
    processed = strategy._post_process_audio(output, 16000)
    assert processed.dtype == np.float32
    assert len(processed) > 0


def test_post_process_audio_failure(strategy):
    with pytest.raises(RuntimeError):
        strategy._post_process_audio(b"invalid", 16000)
