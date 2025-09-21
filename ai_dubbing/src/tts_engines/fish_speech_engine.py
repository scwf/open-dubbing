import inspect
import traceback
from typing import Tuple, Dict, Any, Optional
import numpy as np
import torch
from pathlib import Path
from .base_engine import BaseTTSEngine
from ai_dubbing.src.logger import get_logger
from ai_dubbing.src.config import FishSpeechConfig

logger = get_logger()

class FishSpeechEngine(BaseTTSEngine):
    """Fish Speech引擎的实现 - 基于Fish Speech的语音克隆功能"""

    def __init__(self):
        """
        初始化Fish Speech引擎。
        """
        # 动态导入Fish Speech组件
        try:
            from fish_speech.inference_engine import TTSInferenceEngine
            from fish_speech.models.text2semantic.inference import launch_thread_safe_queue
            from fish_speech.models.dac.inference import load_model as load_decoder_model
        except ImportError as e:
            logger.error("请先安装 fish-speech: pip install -e .")
            raise ImportError("请先安装 fish-speech: pip install -e .") from e

        # 使用配置系统
        init_kwargs = FishSpeechConfig.get_init_kwargs()
        
        # 设置设备类型（自动检测）
        if init_kwargs["device"] is None:
            init_kwargs["device"] = "cuda" if torch.cuda.is_available() else "cpu"
        
        # 设置精度类型（自动检测）
        if init_kwargs["precision"] is None:
            init_kwargs["precision"] = torch.bfloat16 if torch.cuda.is_available() else torch.float32
        
        # 过滤掉值为None的参数
        init_kwargs = {k: v for k, v in init_kwargs.items() if v is not None}
        
        logger.step("加载Fish Speech模型...")
        
        # 检查模型路径是否存在
        llama_path = init_kwargs["llama_checkpoint_path"]
        decoder_path = init_kwargs["decoder_checkpoint_path"]
        
        logger.info(f"LLM路径: {llama_path}")
        logger.info(f"Decoder路径: {decoder_path}")
        
        if not Path(llama_path).exists():
            logger.error(f"LLM路径不存在: {llama_path}")
            raise FileNotFoundError(f"Fish Speech LLM路径不存在: {llama_path}")
        
        if not Path(decoder_path).exists():
            logger.error(f"Decoder路径不存在: {decoder_path}")
            raise FileNotFoundError(f"Fish Speech Decoder路径不存在: {decoder_path}")
        
        try:
            # 初始化LLM队列
            self.llama_queue = launch_thread_safe_queue(
                checkpoint_path=llama_path,
                device=init_kwargs["device"],
                precision=init_kwargs["precision"],
                compile=init_kwargs["compile"],
            )
            
            # 初始化解码器
            self.decoder_model = load_decoder_model(
                config_name="modded_dac_vq",
                checkpoint_path=decoder_path,
                device=init_kwargs["device"],
            )
            
            # 创建推理引擎
            self.engine = TTSInferenceEngine(
                llama_queue=self.llama_queue,
                decoder_model=self.decoder_model,
                precision=init_kwargs["precision"],
                compile=init_kwargs["compile"],
            )
            
            logger.success("模型加载成功")
            
        except Exception as e:
            logger.error(f"模型加载失败: {e}")
            raise RuntimeError(f"加载Fish Speech模型失败: {e}")

    def cleanup(self):
        """清理GPU资源，释放模型内存"""
        try:
            # 清理模型引用
            if hasattr(self, 'engine'):
                del self.engine
            if hasattr(self, 'decoder_model'):
                del self.decoder_model
            if hasattr(self, 'llama_queue'):
                # 尝试关闭线程安全队列
                if hasattr(self.llama_queue, 'close'):
                    self.llama_queue.close()
                del self.llama_queue
            
            # 强制清理CUDA缓存
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                torch.cuda.synchronize()
            
            logger.info("Fish Speech引擎GPU资源已清理")
            
        except Exception as e:
            logger.warning(f"清理Fish Speech引擎资源时发生错误: {e}")

    def __del__(self):
        """析构函数，确保资源被释放"""
        self.cleanup()

    def synthesize(self, text: str, **kwargs) -> Tuple[np.ndarray, int]:
        """
        使用Fish Speech进行语音合成（语音克隆）
        
        :param text: 需要合成的文本
        :param kwargs: 其他参数，包括参考音频和文本
        :return: 音频数据和采样率的元组
        """
        # 获取参考音频配置
        voice_files = kwargs.get('voice_files', [])
        prompt_texts = kwargs.get('prompt_texts', [])
        
        # 读取所有参考音频
        reference_audios = []
        for audio_path, ref_text in zip(voice_files, prompt_texts):
            try:
                with open(audio_path, "rb") as f:
                    audio_bytes = f.read()
                reference_audios.append((audio_bytes, ref_text))
            except Exception as e:
                raise RuntimeError(f"读取参考音频失败 {audio_path}: {e}")
        
        logger.info(f"使用 {len(reference_audios)} 个参考音频进行语音合成")

        # 构建Fish Speech请求
        try:
            from fish_speech.utils.schema import ServeTTSRequest, ServeReferenceAudio
            
            # 使用配置系统的默认参数，并允许用户覆盖
            default_params = FishSpeechConfig.get_inference_kwargs()
            
            # 合并用户提供的参数
            final_params = default_params.copy()
            final_params.update({
                "max_new_tokens": kwargs.get("max_new_tokens", default_params["max_new_tokens"]),
                "chunk_length": kwargs.get("chunk_length", default_params["chunk_length"]),
                "top_p": kwargs.get("top_p", default_params["top_p"]),
                "repetition_penalty": kwargs.get("repetition_penalty", default_params["repetition_penalty"]),
                "temperature": kwargs.get("temperature", default_params["temperature"]),
                "format": kwargs.get("format", "wav"),
                "seed": kwargs.get("seed", default_params["seed"]),
                "use_memory_cache": kwargs.get("use_memory_cache", default_params["use_memory_cache"]),
            })

            # 为每个参考音频创建ServeReferenceAudio对象
            references = [
                ServeReferenceAudio(
                    audio=audio_bytes,
                    text=ref_text
                )
                for audio_bytes, ref_text in reference_audios
            ]
            
            request = ServeTTSRequest(
                text=text,
                references=references,
                max_new_tokens=final_params["max_new_tokens"],
                chunk_length=final_params["chunk_length"],
                top_p=final_params["top_p"],
                repetition_penalty=final_params["repetition_penalty"],
                temperature=final_params["temperature"],
                format=final_params["format"],
                seed=final_params["seed"],
                use_memory_cache=final_params["use_memory_cache"]
            )
            
            # 执行推理
            logger.debug(f"请求参数: {final_params}")
            results = list(self.engine.inference(request))
            
            if not results:
                raise RuntimeError("Fish Speech合成失败，未返回任何结果")
                
            final_result = results[-1]
                        
            if final_result.code == "final":
                sample_rate, audio_data = final_result.audio
                
                # 调试音频数据信息
                logger.info(f"原始音频数据类型: {audio_data.dtype}")
                logger.info(f"采样率: {sample_rate}")
                
                # 检查是否全静音
                if np.abs(audio_data).max() < 0.01:
                    logger.warning(f"返回的音频数据振幅过小: max={np.abs(audio_data).max():.6f}")
                
                # 确保音频数据是float32格式，保持Fish Speech的原生格式
                if audio_data.dtype != np.float32:
                    audio_data = audio_data.astype(np.float32)
                
                # 返回Fish Speech原生采样率和音频数据，避免重采样导致的音调和速度问题
                return audio_data, sample_rate
            else:
                raise RuntimeError(f"Fish Speech合成失败: {final_result.error}")
                
        except ImportError as e:
            logger.error(f"Fish Speech schema导入失败: {str(e)}")
            logger.error(f"完整错误堆栈:\n{traceback.format_exc()}")
            raise RuntimeError(f"Fish Speech schema导入失败: {e}") from e
        except Exception as e:
            logger.error(f"Fish Speech合成过程中出错: {str(e)}")
            logger.error(f"完整错误堆栈:\n{traceback.format_exc()}")
            raise RuntimeError(f"Fish Speech合成过程中出错: {e}") from e


    @staticmethod
    def get_default_params() -> Dict[str, Any]:
        """获取Fish Speech的默认参数"""
        return FishSpeechConfig.get_inference_kwargs()

    @staticmethod
    def get_high_quality_params() -> Dict[str, Any]:
        """获取高质量参数 - 使用原始示例配置"""
        return {
            "temperature": 0.2,  # 匹配原始示例
            "top_p": 0.6,  # 匹配原始示例
            "repetition_penalty": 1.4,  # 高质量模式的重复惩罚
            "chunk_length": 100,  # 匹配原始示例
            "max_new_tokens": 800,  # 高质量模式稍低的token限制
            "seed": 42,
            "use_memory_cache": "on"
        }

    @staticmethod
    def get_balanced_params() -> Dict[str, Any]:
        """获取平衡参数"""
        return {
            "temperature": 0.5,
            "top_p": 0.7,
            "repetition_penalty": 1.1,
            "chunk_length": 150,
            "max_new_tokens": 1000,
            "seed": 42,
            "use_memory_cache": "on"
        }

    @staticmethod
    def get_diverse_params() -> Dict[str, Any]:
        """获取多样性参数"""
        return {
            "temperature": 0.8,
            "top_p": 0.8,
            "repetition_penalty": 1.0,
            "chunk_length": 200,
            "max_new_tokens": 1024,
            "seed": 42,
            "use_memory_cache": "on"
        }

    @staticmethod
    def get_natural_params() -> Dict[str, Any]:
        """获取自然语音参数 - 使用原始示例配置"""
        return {
            "temperature": 0.2,  # 匹配原始示例
            "top_p": 0.6,  # 匹配原始示例
            "repetition_penalty": 1.1,  # 匹配原始示例
            "chunk_length": 100,  # 匹配原始示例
            "max_new_tokens": 1024,  # 匹配原始示例
            "seed": 42,
            "use_memory_cache": "on"
        }