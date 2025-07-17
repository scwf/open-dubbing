import inspect
from typing import Tuple, Dict, Any, Optional
import numpy as np
from .base_engine import BaseTTSEngine
from ai_dubbing.src.config import IndexTTSConfig, AUDIO
from ai_dubbing.src.logger import get_logger
from ai_dubbing.src.utils import normalize_audio_data

# 动态导入IndexTTS，如果不存在则给出友好提示
try:
    from indextts.infer import IndexTTS
except ImportError:
    IndexTTS = None

logger = get_logger()

class IndexTTSEngine(BaseTTSEngine):
    """IndexTTS引擎的实现"""

    def __init__(self):
        """
        初始化IndexTTS引擎。
        
        :param config: 引擎配置，需要包含 'model_dir' 和可选的 'cfg_path'。
        """
        if IndexTTS is None:
            raise ImportError("IndexTTS未安装。")
            
        # 直接从配置模块获取初始化参数
        init_kwargs = IndexTTSConfig.get_init_kwargs()
        # 过滤掉值为None的参数
        init_kwargs = {k: v for k, v in init_kwargs.items() if v is not None}
        logger.step("加载IndexTTS模型...")
        try:
            self.tts_model = IndexTTS(**init_kwargs)
            # 使用内省机制，获取底层模型真正支持的参数列表
            infer_signature = inspect.signature(self.tts_model.infer)
            self.valid_infer_params = set(infer_signature.parameters.keys())
            
            logger.success(f"IndexTTS模型加载成功: {init_kwargs}")
        except Exception as e:
            logger.error(f"IndexTTS模型加载失败: {e}")
            raise RuntimeError(f"加载IndexTTS模型失败: {e}")

    def synthesize(self, text: str, **kwargs) -> Tuple[np.ndarray, int]:
        voice_reference = kwargs.get('voice_reference')
        if not voice_reference:
            raise ValueError("必须提供参考语音文件路径 (voice_reference)")

        # 优雅地过滤出底层模型支持的参数，而不是手动pop
        filtered_kwargs = {
            key: value for key, value in kwargs.items() 
            if key in self.valid_infer_params
        }

        sampling_rate, audio_data_int16 = self.tts_model.infer(
            text=text, audio_prompt=voice_reference, output_path=None, **filtered_kwargs
        )
        
        # 将int16格式的音频数据规范化到 [-1, 1] 的float32格式
        audio_data_float32 = normalize_audio_data(audio_data_int16)
        
        # 标准化采样率为系统默认采样率（与Fish Speech保持一致）
        if sampling_rate != AUDIO.DEFAULT_SAMPLE_RATE:
            try:
                import librosa
                audio_data_float32 = librosa.resample(audio_data_float32, orig_sr=sampling_rate, target_sr=AUDIO.DEFAULT_SAMPLE_RATE)
                sampling_rate = AUDIO.DEFAULT_SAMPLE_RATE
            except ImportError:
                logger.warning("librosa未安装，跳过重采样，可能导致播放速度异常")
        
        return audio_data_float32, sampling_rate

