import inspect
import traceback
from typing import Tuple, Dict, Any
import numpy as np
import torch
from .base_engine import BaseTTSEngine
from ai_dubbing.src.logger import get_logger
from ai_dubbing.src.utils import normalize_audio_data
from ai_dubbing.src.config import CosyVoiceConfig, AUDIO

logger = get_logger()

class CosyVoiceEngine(BaseTTSEngine):
    """CosyVoice引擎的实现"""

    def __init__(self):
        """
        初始化CosyVoice引擎。
        
        :param config: 引擎配置
        """
        # 动态导入CosyVoice，如果不存在则给出友好提示
        from cosyvoice.cli.cosyvoice import AutoModel

        init_kwargs = CosyVoiceConfig.get_init_kwargs()
        # 对于 CosyVoice 3 仅需要保留 model_dir
        model_dir = init_kwargs.get("model_dir")
        if not model_dir:
            raise ValueError("CosyVoice的初始化必须在 .env 或配置中指定 model_dir (如 models/Fun-CosyVoice3-0.5B)")
        
        logger.step(f"加载CosyVoice模型 (model_dir={model_dir})...")
        try:
            self.tts_model = AutoModel(model_dir=model_dir)
            logger.success("模型加载成功!")

            # 使用内省机制，获取底层模型真正支持的参数列表
            infer_signature = inspect.signature(self.tts_model.inference_zero_shot)
            self.valid_infer_params = set(infer_signature.parameters.keys())
        except Exception as e:
            logger.error(f"模型加载失败: {e}")
            raise RuntimeError(f"加载CosyVoice模型失败: {e}")

    def cleanup(self):
        """清理GPU资源"""
        try:
            if hasattr(self, 'tts_model'):
                del self.tts_model
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                torch.cuda.synchronize()
            logger.info("CosyVoice引擎GPU资源已清理")
        except Exception as e:
            logger.warning(f"CosyVoice引擎清理时发生错误: {e}")

    def synthesize(self, text: str, **kwargs) -> Tuple[np.ndarray, int]:
        prompt_text = kwargs.get("prompt_text")
        if not prompt_text:
             raise ValueError("CosyVoice引擎的 `synthesize` 方法需要 'prompt_text' 参数。")

        voice_reference = kwargs.get('voice_reference')
        if not voice_reference:
            raise ValueError("必须提供参考语音文件路径 (voice_reference)")

        try:
            # CosyVoice 3 zero_shot 建议增加 system prompt
            if "<|endofprompt|>" not in prompt_text:
                prompt_text = f"You are a helpful assistant.<|endofprompt|>{prompt_text}"

            # 优雅地过滤出底层模型支持的、且非核心的参数
            filtered_kwargs = {
                key: value for key, value in kwargs.items() 
                if key in self.valid_infer_params
            }

            output_speech_list = []
            # CosyVoice 3 的推理接口第三个参数直接传递路径字符串即可
            for speech in self.tts_model.inference_zero_shot(text, prompt_text, voice_reference, stream=False):
                # 将输出的tensor移动到CPU并转换为numpy
                output_speech_list.append(speech['tts_speech'].cpu())
            
            if not output_speech_list:
                raise RuntimeError("CosyVoice 合成失败，未生成任何音频数据。")

            # 将分块的音频拼接起来
            full_audio_tensor = torch.cat(output_speech_list, dim=1)
            
            # 将 [1, N] 的 tensor 转换为 [N] 的 numpy 数组
            audio_data_numpy = full_audio_tensor.squeeze().numpy()
            
            # CosyVoice 输出的已经是 float32，无需像 IndexTTS 那样转换
            original_sr = self.tts_model.sample_rate
            
            # 标准化采样率为系统默认采样率（与Fish Speech保持一致）
            if original_sr != AUDIO.DEFAULT_SAMPLE_RATE:
                try:
                    import librosa
                    audio_data_numpy = librosa.resample(audio_data_numpy.astype(np.float32), orig_sr=original_sr, target_sr=AUDIO.DEFAULT_SAMPLE_RATE)
                    original_sr = AUDIO.DEFAULT_SAMPLE_RATE
                except ImportError:
                    logger.warning("librosa未安装，跳过重采样，可能导致播放速度异常")
            
            return audio_data_numpy, original_sr
            
        except Exception as e:
            logger.error(f"CosyVoice推理失败: {str(e)}")
            logger.error(f"完整错误堆栈:\n{traceback.format_exc()}")
            raise RuntimeError(f"CosyVoice推理失败: {e}") from e
