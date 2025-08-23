from abc import ABC, abstractmethod
import numpy as np
from typing import Tuple, Dict, Any

class BaseTTSEngine(ABC):
    """TTS引擎的抽象基类"""

    @abstractmethod
    def __init__(self):
        """
        初始化引擎。
        :param config: 引擎所需的特定配置字典。
        """
        pass

    @abstractmethod
    def synthesize(self, text: str, **kwargs) -> Tuple[np.ndarray, int]:
        """
        将文本合成为音频。

        :param text: 需要合成的文本。
        :param kwargs: 引擎特定的其他参数 (例如参考音频, 语速等)。
        :return: 一个元组，包含音频数据 (NumPy array) 和采样率 (int)。
        """
        pass

    def cleanup(self):
        """
        清理引擎资源。
        子类应该重写此方法来释放GPU内存等资源。
        """
        pass

