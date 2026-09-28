import os
import traceback
from pathlib import Path
from typing import Tuple, Dict, Any
import numpy as np
import torch
from .base_engine import BaseTTSEngine
from ai_dubbing.src.config import IndexTTS25Config, AUDIO
from ai_dubbing.src.logger import get_logger
from ai_dubbing.src.utils import normalize_audio_data

logger = get_logger()

try:
    from indextts.infer_v2_5 import IndexTTS2 as IndexTTS25
except ImportError:
    IndexTTS25 = None


class IndexTTS25Engine(BaseTTSEngine):
    """IndexTTS-2.5 引擎。

    与 IndexTTS-2 并列，使用独立权重和 infer_v2_5 接口。
    """

    def __init__(self):
        if IndexTTS25 is None:
            raise ImportError(
                "IndexTTS-2.5 未安装。请在仓库根目录执行 ./install-index-tts25.sh，"
                "然后使用 conda 环境 index-tts25 启动。"
            )

        init_kwargs = {k: v for k, v in IndexTTS25Config.get_init_kwargs().items() if v is not None}
        model_dir = init_kwargs["model_dir"]
        # infer_v2_5 导入时会把 HF_HUB_CACHE 指到 ./checkpoints/hf_cache。
        # 辅助模型实际落在本次 model_dir 下，避免写到仓库根的 checkpoints/。
        os.environ["HF_HUB_CACHE"] = str(Path(model_dir) / "hf_cache")

        logger.step("加载 IndexTTS-2.5 模型...")
        try:
            self.tts_model = IndexTTS25(**init_kwargs)
            logger.success(f"IndexTTS-2.5 模型加载成功: {init_kwargs}")
        except Exception as e:
            logger.error(f"IndexTTS-2.5 模型加载失败: {e}")
            raise RuntimeError(f"加载 IndexTTS-2.5 模型失败: {e}") from e

    def cleanup(self):
        try:
            if hasattr(self, "tts_model"):
                del self.tts_model
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                torch.cuda.synchronize()
            logger.info("IndexTTS-2.5 引擎 GPU 资源已清理")
        except Exception as e:
            logger.warning(f"IndexTTS-2.5 引擎清理时发生错误: {e}")

    def synthesize(self, text: str, **kwargs) -> Tuple[np.ndarray, int]:
        spk_audio_prompt = kwargs.get("voice_reference")
        if not spk_audio_prompt:
            raise ValueError("必须提供参考语音文件路径 (voice_reference)")

        inference_kwargs = IndexTTS25Config.get_inference_kwargs()
        self._map_emotion_parameters(kwargs, inference_kwargs)
        inference_kwargs["spk_audio_prompt"] = spk_audio_prompt
        inference_kwargs["text"] = text
        inference_kwargs["output_path"] = None
        inference_kwargs["verbose"] = False
        inference_kwargs["lang"] = self._resolve_lang(kwargs.get("language"))

        if "duration_factor" in kwargs and kwargs["duration_factor"] is not None:
            inference_kwargs["duration_factor"] = float(kwargs["duration_factor"])

        logger.debug(f"IndexTTS-2.5 推理参数: {inference_kwargs}")

        try:
            result = self.tts_model.infer(**inference_kwargs)
            if not result or not isinstance(result, tuple) or len(result) != 2:
                raise RuntimeError("IndexTTS-2.5 未返回音频数据")

            sampling_rate, audio_data_int16 = result
            audio_data_float32 = normalize_audio_data(audio_data_int16)

            if sampling_rate != AUDIO.DEFAULT_SAMPLE_RATE:
                try:
                    import librosa
                    audio_data_float32 = librosa.resample(
                        audio_data_float32,
                        orig_sr=sampling_rate,
                        target_sr=AUDIO.DEFAULT_SAMPLE_RATE,
                    )
                    sampling_rate = AUDIO.DEFAULT_SAMPLE_RATE
                except ImportError:
                    logger.warning("librosa 未安装，跳过重采样，可能导致播放速度异常")

            if audio_data_float32.size == 0:
                raise RuntimeError("IndexTTS-2.5 合成结果为空")

            logger.debug(
                f"IndexTTS-2.5 合成完成，音频长度: {len(audio_data_float32) / sampling_rate:.2f}秒"
            )
            return audio_data_float32, sampling_rate
        except Exception as e:
            logger.error(f"IndexTTS-2.5 推理失败: {str(e)}")
            logger.error(f"完整错误堆栈:\n{traceback.format_exc()}")
            raise RuntimeError(f"IndexTTS-2.5 推理失败: {e}") from e

    def _resolve_lang(self, language: Any) -> str:
        requested = "" if language is None else str(language).strip()
        mapped = IndexTTS25Config.map_language(requested or None)
        known = (
            requested.lower() in IndexTTS25Config.LANG_BY_CODE
            or requested.upper() in IndexTTS25Config.LANG_BY_CODE.values()
        )
        if requested and not known:
            logger.warning(f"IndexTTS-2.5 不支持语言 '{language}'，已按 ZH 合成")
        return mapped

    def _map_emotion_parameters(self, input_kwargs: Dict[str, Any], inference_kwargs: Dict[str, Any]):
        if input_kwargs.get("emotion_audio_file"):
            inference_kwargs["emo_audio_prompt"] = input_kwargs["emotion_audio_file"]
            logger.info(f"使用情感音频引导: {input_kwargs['emotion_audio_file']}")

        emotion_vector = input_kwargs.get("emotion_vector")
        if emotion_vector:
            if isinstance(emotion_vector, (list, tuple)) and len(emotion_vector) == 8:
                inference_kwargs["emo_vector"] = list(emotion_vector)
                logger.info(f"使用情感向量控制: {emotion_vector}")
            else:
                logger.warning(f"情感向量格式错误，应为 8 个浮点数的列表，收到: {emotion_vector}")

        if input_kwargs.get("emotion_text"):
            inference_kwargs["emo_text"] = input_kwargs["emotion_text"]
            inference_kwargs["use_emo_text"] = True
            logger.info(f"使用情感文本描述: {input_kwargs['emotion_text']}")
        elif input_kwargs.get("auto_emotion", False):
            inference_kwargs["use_emo_text"] = True
            logger.info("启用自动情感检测模式")

        if inference_kwargs.get("use_emo_text") and not IndexTTS25Config.USE_QWEN_EMO:
            raise RuntimeError(
                "IndexTTS-2.5 的文本情感需要在初始化时打开 use_qwen_emo。"
            )

        if "emotion_alpha" in input_kwargs:
            alpha = float(input_kwargs["emotion_alpha"])
            if 0.0 <= alpha <= 1.0:
                inference_kwargs["emo_alpha"] = alpha
                logger.info(f"设置情感强度: {alpha}")
            else:
                logger.warning(f"情感强度超出范围 [0.0, 1.0]，收到: {alpha}")

        if "use_random" in input_kwargs:
            inference_kwargs["use_random"] = bool(input_kwargs["use_random"])

    def get_engine_info(self) -> Dict[str, Any]:
        return {
            "name": "IndexTTS-2.5",
            "version": "2.5",
            "description": "IndexTTS-2.5 - 更快的多语种零样本语音合成，保留 IndexTTS-2 供对照",
            "features": [
                "零样本声音克隆",
                "情感音色分离控制",
                "语速控制",
                "中英日西阿多语种",
            ],
        }
