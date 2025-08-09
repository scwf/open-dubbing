"""
策略抽象基类
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import List, Dict, Any
import time
import random

from ai_dubbing.src.tts_engines.base_engine import BaseTTSEngine
from ai_dubbing.src.parsers.srt_parser import SRTEntry
from ai_dubbing.src.logger import get_logger, create_process_logger
from ai_dubbing.src.config import LOG

class TimeSyncStrategy(ABC):
    """时间同步策略抽象基类"""
    
    def __init__(self, tts_engine: 'BaseTTSEngine'):
        """
        初始化策略。
        
        Args:
            tts_engine: 一个遵循BaseTTSEngine接口的TTS引擎实例。
        """
        self.tts_engine = tts_engine
    
    @staticmethod
    @abstractmethod
    def name() -> str:
        """策略名称"""
        pass
    
    @staticmethod
    @abstractmethod
    def description() -> str:
        """策略描述"""
        pass
    
    @abstractmethod
    def synthesize_one(self, entry: SRTEntry, **kwargs) -> Dict[str, Any]:
        """合成单条字幕的音频片段，由具体策略实现"""
        raise NotImplementedError

    def process_entries(self, entries: List[SRTEntry], **kwargs) -> List[Dict[str, Any]]:
        """通用处理管线：串行合成，保证顺序，带重试与进度日志

        说明：GPU推理为计算密集任务，且多数TTS引擎内部已串行/非线程安全，
        因此默认采用串行执行，避免线程池对GPU的争用与上下文切换开销。
        可通过上层批处理或引擎自身队列优化吞吐。
        """
        logger = get_logger()
        if not entries:
            return []

        max_concurrency = int(kwargs.get('max_concurrency', 8))
        max_retries = int(kwargs.get('max_retries', 2))
        # 过滤掉并发控制相关参数，避免传递给底层引擎
        filtered_kwargs = {k: v for k, v in kwargs.items() if k not in {'max_concurrency', 'max_retries'}}

        process_logger = create_process_logger(f"{self.name()} 策略音频生成")
        process_logger.start(f"处理 {len(entries)} 个字幕条目")
        if max_concurrency and max_concurrency > 1:
            logger.warning(
                f"检测到 max_concurrency={max_concurrency}，已强制按串行方式执行以避免GPU争用。"
            )

        def call_with_retry(entry_idx: int, entry_obj: SRTEntry) -> Dict[str, Any]:
            for attempt in range(max_retries + 1):
                try:
                    return self.synthesize_one(entry_obj, **filtered_kwargs)
                except Exception as exc:
                    if attempt < max_retries:
                        backoff = min(2 ** attempt, 8) + random.uniform(0, 0.5)
                        logger.warning(
                            f"条目 {entry_obj.index} 合成失败，重试 {attempt+1}/{max_retries}，{exc}，{backoff:.1f}s 后重试"
                        )
                        time.sleep(backoff)
                    else:
                        raise

        results: List[Dict[str, Any]] = [None] * len(entries)
        completed = 0
        process_logger.progress(0, len(entries), "开始合成")
        start_ts = time.time()

        for i, entry in enumerate(entries):
            try:
                seg = call_with_retry(i, entry)
                results[i] = seg
            except Exception as e:
                logger.error(f"条目 {entry.index} 处理失败: {e}")
                raise
            completed += 1
            text_preview = entry.text[:LOG.PROGRESS_TEXT_PREVIEW_LENGTH] + "..." \
                if len(entry.text) > LOG.PROGRESS_TEXT_PREVIEW_LENGTH else entry.text
            process_logger.progress(completed, len(entries), f"条目 {entry.index}: {text_preview}")

        elapsed = time.time() - start_ts
        process_logger.complete(f"生成 {len(results)} 个音频片段（耗时 {elapsed:.2f}s）")
        return results