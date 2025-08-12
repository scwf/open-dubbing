import inspect
from typing import Tuple
import numpy as np
from .base_engine import BaseTTSEngine
from ..logger import get_logger
from ..config import F5TTSConfig, AUDIO
import torch

# 动态导入F5TTS，如果不存在则给出友好提示
try:
    from f5_tts.api import F5TTS
except ImportError:
    F5TTS = None

logger = get_logger()

class F5TTSEngine(BaseTTSEngine):
    """F5TTS引擎的实现 (遵循F5TTS_infer.md)"""

    def __init__(self):
        """
        初始化F5TTS引擎。
        注意：'config' 参数在此实现中被忽略，配置直接从config模块获取。
        """
        if F5TTS is None:
            raise ImportError("F5TTS未安装，请执行 `pip install f5-tts` 进行安装。")

        logger.step("加载F5TTS模型...")
        try:
            # 直接从配置模块获取初始化参数
            init_kwargs = F5TTSConfig.get_init_kwargs()
            # 过滤掉值为None的参数
            init_kwargs = {k: v for k, v in init_kwargs.items() if v is not None}

            logger.debug(f"F5TTS初始化参数: {init_kwargs}")
            self.tts_model = F5TTS(**init_kwargs)

            # 使用内省机制，获取底层模型真正支持的参数列表
            infer_signature = inspect.signature(self.tts_model.infer)
            self.valid_infer_params = set(infer_signature.parameters.keys())
            
            logger.success("模型加载成功")

        except Exception as e:
            logger.error(f"模型加载失败: {e}")
            raise RuntimeError(f"加载F5TTS模型失败: {e}")

    def synthesize(self, text: str, **kwargs) -> Tuple[np.ndarray, int]:
        voice_reference = kwargs.pop('voice_reference')
        if not voice_reference:
            raise ValueError("必须提供参考语音文件路径 (voice_reference)")

        # 优先从kwargs中获取参考文本(prompt_text)，如果未提供，再尝试自动转录
        ref_text = kwargs.pop("ref_text")
        if not ref_text:
            raise ValueError("F5TTS引擎的 `synthesize` 方法需要 'ref_text' 参数。") 

        # 优雅地过滤出底层模型支持的参数
        infer_kwargs = {
            key: value for key, value in kwargs.items() 
            if key in self.valid_infer_params
        }

        wav, sr, _ = self.tts_model.infer(
            ref_file=voice_reference,
            ref_text=ref_text,
            gen_text=text,
            **infer_kwargs
        )

        # F5TTS返回的是torch.Tensor，需要转换为numpy array
        if isinstance(wav, torch.Tensor):
            wav = wav.cpu().numpy()

        if wav is None:
            raise RuntimeError("TTS引擎返回了空的音频数据。")

        # 标准化采样率为系统默认采样率（与Fish Speech保持一致）
        if sr != AUDIO.DEFAULT_SAMPLE_RATE:
            try:
                import librosa
                wav = librosa.resample(wav.astype(np.float32), orig_sr=sr, target_sr=AUDIO.DEFAULT_SAMPLE_RATE)
                sr = AUDIO.DEFAULT_SAMPLE_RATE
            except ImportError:
                logger.warning("librosa未安装，跳过重采样，可能导致播放速度异常")
        
        return wav.astype(np.float32), sr

