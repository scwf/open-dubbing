import inspect
from typing import Tuple, Dict, Any, Optional, List
import numpy as np
import torch
from .base_engine import BaseTTSEngine
from ai_dubbing.src.config import IndexTTS2Config, AUDIO
from ai_dubbing.src.logger import get_logger
from ai_dubbing.src.utils import normalize_audio_data

# 动态导入IndexTTS2，如果不存在则给出友好提示
try:
    from indextts.infer_v2 import IndexTTS2
except ImportError:
    IndexTTS2 = None

logger = get_logger()

class IndexTTS2Engine(BaseTTSEngine):
    """IndexTTS2引擎的实现
    
    支持IndexTTS2的所有新特性：
    - 零样本声音克隆
    - 情感音色分离控制
    - 精确时长控制
    - 多模态情感输入
    """

    def __init__(self):
        """
        初始化IndexTTS2引擎。
        """
        if IndexTTS2 is None:
            raise ImportError(
                "IndexTTS2未安装。请按照官方文档安装IndexTTS2：\n"
                "1. 克隆仓库：git clone https://github.com/index-tts/index-tts.git\n"
                "2. 安装依赖：cd index-tts && uv sync --all-extras\n"
                "3. 下载模型：hf download IndexTeam/IndexTTS-2 --local-dir=checkpoints"
            )
            
        # 直接从配置模块获取初始化参数
        init_kwargs = IndexTTS2Config.get_init_kwargs()
        # 过滤掉值为None的参数
        init_kwargs = {k: v for k, v in init_kwargs.items() if v is not None}
        
        logger.step("加载IndexTTS2模型...")
        try:
            self.tts_model = IndexTTS2(**init_kwargs)
            
            # 使用内省机制，获取底层模型真正支持的参数列表
            infer_signature = inspect.signature(self.tts_model.infer)
            self.valid_infer_params = set(infer_signature.parameters.keys())
            
            logger.success(f"IndexTTS2模型加载成功: {init_kwargs}")
            logger.info(f"支持的推理参数: {sorted(self.valid_infer_params)}")
        except Exception as e:
            logger.error(f"IndexTTS2模型加载失败: {e}")
            raise RuntimeError(f"加载IndexTTS2模型失败: {e}")

    def cleanup(self):
        """清理GPU资源"""
        try:
            if hasattr(self, 'tts_model'):
                del self.tts_model
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                torch.cuda.synchronize()
            logger.info("IndexTTS2引擎GPU资源已清理")
        except Exception as e:
            logger.warning(f"IndexTTS2引擎清理时发生错误: {e}")

    def synthesize(self, text: str, **kwargs) -> Tuple[np.ndarray, int]:
        """
        使用IndexTTS2合成语音
        
        支持的参数：
        - voice_reference: 音色参考音频文件路径 (必需)
        
        情感控制参数：
        - emotion_audio_file: 情感参考音频文件路径 (可选)
        - emotion_vector: 情感向量，8个浮点数的列表 [happy, angry, sad, afraid, disgusted, melancholic, surprised, calm] (可选)
        - emotion_text: 情感描述文本 (可选)
        - auto_emotion: 是否基于输入文本自动判断情感 (可选)
        - emotion_alpha: 情感强度，0.0-1.0之间 (可选，默认1.0)
        - use_random: 是否启用随机采样 (可选，默认False)
        
        Returns:
            Tuple[np.ndarray, int]: (音频数据, 采样率)
        """
        # 获取音色参考音频
        spk_audio_prompt = kwargs.get('voice_reference')
        if not spk_audio_prompt:
            raise ValueError("必须提供参考语音文件路径 (voice_reference)")

        # 合并默认推理参数和用户提供的参数
        inference_kwargs = IndexTTS2Config.get_inference_kwargs()
        
        # 情感控制参数映射
        self._map_emotion_parameters(kwargs, inference_kwargs)
        
        # 设置基础参数
        inference_kwargs['spk_audio_prompt'] = spk_audio_prompt
        inference_kwargs['text'] = text
        inference_kwargs['output_path'] = None  # 不保存文件，直接返回音频数据
        inference_kwargs['verbose'] = False  # 减少输出噪音
        
        # 优雅地过滤出底层模型支持的参数
        filtered_kwargs = {
            key: value for key, value in inference_kwargs.items() 
            if key in self.valid_infer_params
        }
        
        logger.debug(f"IndexTTS2推理参数: {filtered_kwargs}")
        
        try:
            # 调用IndexTTS2进行推理
            sampling_rate, audio_data_int16 = self.tts_model.infer(**filtered_kwargs)
            
            # 将int16格式的音频数据规范化到 [-1, 1] 的float32格式
            audio_data_float32 = normalize_audio_data(audio_data_int16)
            
            # 标准化采样率为系统默认采样率
            if sampling_rate != AUDIO.DEFAULT_SAMPLE_RATE:
                try:
                    import librosa
                    audio_data_float32 = librosa.resample(
                        audio_data_float32, 
                        orig_sr=sampling_rate, 
                        target_sr=AUDIO.DEFAULT_SAMPLE_RATE
                    )
                    sampling_rate = AUDIO.DEFAULT_SAMPLE_RATE
                    logger.debug(f"音频重采样至 {AUDIO.DEFAULT_SAMPLE_RATE}Hz")
                except ImportError:
                    logger.warning("librosa未安装，跳过重采样，可能导致播放速度异常")
            
            logger.debug(f"IndexTTS2合成完成，音频长度: {len(audio_data_float32)/sampling_rate:.2f}秒")
            return audio_data_float32, sampling_rate
            
        except Exception as e:
            logger.error(f"IndexTTS2推理失败: {e}")
            raise RuntimeError(f"IndexTTS2推理失败: {e}")

    def _map_emotion_parameters(self, input_kwargs: Dict[str, Any], inference_kwargs: Dict[str, Any]):
        """
        将输入的情感控制参数映射到IndexTTS2的API参数
        
        Args:
            input_kwargs: 输入的参数字典
            inference_kwargs: 要传递给IndexTTS2的参数字典
        """
        # 情感音频引导
        if 'emotion_audio_file' in input_kwargs and input_kwargs['emotion_audio_file']:
            inference_kwargs['emo_audio_prompt'] = input_kwargs['emotion_audio_file']
            logger.debug(f"使用情感音频引导: {input_kwargs['emotion_audio_file']}")
        
        # 情感向量控制
        if 'emotion_vector' in input_kwargs and input_kwargs['emotion_vector']:
            emotion_vector = input_kwargs['emotion_vector']
            if isinstance(emotion_vector, (list, tuple)) and len(emotion_vector) == 8:
                inference_kwargs['emo_vector'] = list(emotion_vector)
                logger.debug(f"使用情感向量控制: {emotion_vector}")
            else:
                logger.warning(f"情感向量格式错误，应为8个浮点数的列表，收到: {emotion_vector}")
        
        # 情感文本描述
        if 'emotion_text' in input_kwargs and input_kwargs['emotion_text']:
            inference_kwargs['emo_text'] = input_kwargs['emotion_text']
            inference_kwargs['use_emo_text'] = True
            logger.debug(f"使用情感文本描述: {input_kwargs['emotion_text']}")
        elif input_kwargs.get('auto_emotion', False):
            # 自动情感检测模式
            inference_kwargs['use_emo_text'] = True
            logger.debug("启用自动情感检测模式")
        
        # 情感强度控制
        if 'emotion_alpha' in input_kwargs:
            alpha = float(input_kwargs['emotion_alpha'])
            if 0.0 <= alpha <= 1.0:
                inference_kwargs['emo_alpha'] = alpha
                logger.debug(f"设置情感强度: {alpha}")
            else:
                logger.warning(f"情感强度超出范围[0.0, 1.0]，收到: {alpha}")
        
        # 随机采样控制
        if 'use_random' in input_kwargs:
            inference_kwargs['use_random'] = bool(input_kwargs['use_random'])
            logger.debug(f"随机采样: {inference_kwargs['use_random']}")

    def get_engine_info(self) -> Dict[str, Any]:
        """获取引擎信息"""
        return {
            "name": "IndexTTS2",
            "version": "2.0",
            "description": "IndexTTS2 - 支持情感表达和时长控制的零样本语音合成",
            "features": [
                "零样本声音克隆",
                "情感音色分离控制", 
                "精确时长控制",
                "多模态情感输入",
                "高质量语音合成"
            ],
            "supported_emotions": [
                "happy", "angry", "sad", "afraid", 
                "disgusted", "melancholic", "surprised", "calm"
            ],
            "emotion_control_modes": [
                "auto (自动检测)",
                "audio (音频引导)", 
                "vector (向量控制)",
                "text (文本描述)"
            ]
        }
