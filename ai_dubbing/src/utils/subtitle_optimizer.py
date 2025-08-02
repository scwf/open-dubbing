"""
字幕优化器

提供SRT字幕文件的优化功能，包括时长分析和语义合并。
自动优化字幕时长，确保TTS合成质量。
"""

import re
from typing import List, Dict, Any, Optional, NamedTuple
from pathlib import Path
from ai_dubbing.src.logger import get_logger


class OptimizationReport(NamedTuple):
    """优化报告数据结构"""
    original_entries: int
    optimized_entries: int
    merged_count: int
    short_subtitles_fixed: int
    fragmented_sentences_merged: int
    duration_improvements: Dict[str, Any]


class SubtitleOptimizer:
    """字幕优化器类"""
    
    def __init__(self, min_duration: float = 1.5, max_duration: float = 6.0, 
                 merge_threshold: float = 0.8):
        """
        初始化字幕优化器
        
        Args:
            min_duration: 最小字幕时长（秒）
            max_duration: 最大字幕时长（秒）
            merge_threshold: 合并阈值（秒），字幕间隔小于此值考虑合并
        """
        self.min_duration = min_duration
        self.max_duration = max_duration
        self.merge_threshold = merge_threshold
        self.logger = get_logger()
    
    def analyze_durations(self, entries) -> Dict[str, Any]:
        """分析字幕时长并识别优化需求"""
        if not entries:
            return {"needs_optimization": False, "issues": []}
        
        issues = []
        short_subtitles = []
        fragmented_sentences = []
        
        for i, entry in enumerate(entries):
            duration = entry.duration
            text = entry.text.strip()
            
            # 检查时长过短
            if duration < self.min_duration:
                short_subtitles.append({
                    "index": i,
                    "duration": duration,
                    "text": text[:50] + "..." if len(text) > 50 else text
                })
                issues.append("short_duration")
            
            # 检查句子完整性
            if not self._has_sentence_end(text):
                # 检查是否可以与下一条合并
                if i < len(entries) - 1:
                    next_entry = entries[i + 1]
                    time_gap = next_entry.start_time - entry.end_time
                    if time_gap <= self.merge_threshold:
                        fragmented_sentences.append({
                            "index": i,
                            "text": text,
                            "next_text": next_entry.text,
                            "gap": time_gap
                        })
                        issues.append("fragmented_sentence")
        
        return {
            "needs_optimization": len(issues) > 0,
            "short_subtitles": short_subtitles,
            "fragmented_sentences": fragmented_sentences,
            "total_issues": len(issues)
        }
    
    def _has_sentence_end(self, text: str) -> bool:
        """检查文本是否有句子结束标点"""
        sentence_endings = ['。', '！', '？', '.', '!', '?', '...', '⋯']
        return any(text.strip().endswith(ending) for ending in sentence_endings)
    
    def _should_merge(self, entry1, entry2) -> bool:
        """判断两个字幕是否应该合并"""
        # 检查时间间隔
        time_gap = entry2.start_time - entry1.end_time
        if time_gap > self.merge_threshold:
            return False
        
        # 检查文本语义连贯性
        text1 = entry1.text.strip()
        text2 = entry2.text.strip()
        
        # 如果第一条有句子结束标点，不合并
        if self._has_sentence_end(text1):
            return False
        
        # 如果第二条以小写字母或连接词开头，合并
        connecting_words = ['而且', '但是', '因为', '所以', '然后', '接着', '但是']
        if any(text2.startswith(word) for word in connecting_words):
            return True
        
        # 检查是否是同一句话的延续
        combined_text = text1 + text2
        if len(combined_text) < 100:  # 合并后不会太长
            return True
        
        return False
    
    def optimize_subtitles(self, entries) -> tuple[list, OptimizationReport]:
        """
        优化字幕文件
        
        Args:
            entries: 原始字幕条目列表
            
        Returns:
            优化后的字幕条目列表和优化报告
        """
        if not entries:
            return entries, OptimizationReport(0, 0, 0, 0, 0, {})
        
        self.logger.step("开始字幕优化分析")
        
        # 分析优化需求
        analysis = self.analyze_durations(entries)
        
        if not analysis["needs_optimization"]:
            self.logger.info("字幕无需优化")
            return entries, OptimizationReport(
                len(entries), len(entries), 0, 0, 0, {}
            )
        
        self.logger.info(f"发现 {analysis['total_issues']} 个优化需求")
        
        # 执行优化
        optimized_entries = self._merge_entries(entries)
        
        # 生成优化报告
        report = OptimizationReport(
            original_entries=len(entries),
            optimized_entries=len(optimized_entries),
            merged_count=len(entries) - len(optimized_entries),
            short_subtitles_fixed=len(analysis["short_subtitles"]),
            fragmented_sentences_merged=len(analysis["fragmented_sentences"]),
            duration_improvements={
                "avg_duration_before": sum(e.duration for e in entries) / len(entries),
                "avg_duration_after": sum(e.duration for e in optimized_entries) / len(optimized_entries),
                "min_duration_before": min(e.duration for e in entries),
                "min_duration_after": max(self.min_duration, min(e.duration for e in optimized_entries))
            }
        )
        
        self.logger.success(f"字幕优化完成：{report.merged_count} 个字幕已合并")
        return optimized_entries, report
    
    def _merge_entries(self, entries: list) -> list:
        """合并字幕条目"""
        if len(entries) <= 1:
            return entries
        
        # 延迟导入避免循环导入
        from ai_dubbing.src.parsers.srt_parser import SRTEntry
        
        merged = []
        i = 0
        
        while i < len(entries):
            current = entries[i]
            
            # 检查是否可以与下一条合并
            if i < len(entries) - 1 and self._should_merge(current, entries[i + 1]):
                next_entry = entries[i + 1]
                
                # 创建合并后的条目
                merged_entry = SRTEntry(
                    index=len(merged) + 1,
                    start_time=current.start_time,
                    end_time=next_entry.end_time,
                    text=current.text.strip() + " " + next_entry.text.strip()
                )
                
                # 检查合并后时长是否合理
                if merged_entry.duration <= self.max_duration:
                    merged.append(merged_entry)
                    i += 2
                    self.logger.debug(f"合并字幕 {current.index} 和 {next_entry.index}")
                else:
                    # 合并后太长，保持原样
                    merged.append(SRTEntry(
                        index=len(merged) + 1,
                        start_time=current.start_time,
                        end_time=current.end_time,
                        text=current.text
                    ))
                    i += 1
            else:
                # 不需要合并，保持原样
                merged.append(SRTEntry(
                    index=len(merged) + 1,
                    start_time=current.start_time,
                    end_time=current.end_time,
                    text=current.text
                ))
                i += 1
        
        return merged
    
    def save_optimized_srt(self, optimized_entries: list, 
                          original_path: str, 
                          custom_output: Optional[str] = None) -> str:
        """
        保存优化后的字幕文件
        
        Args:
            optimized_entries: 优化后的字幕条目
            original_path: 原始文件路径
            custom_output: 自定义输出路径（可选）
            
        Returns:
            优化文件的保存路径
        """
        # 延迟导入避免循环导入
        from ai_dubbing.src.parsers.srt_parser import SRTParser
        
        if custom_output:
            output_path = Path(custom_output)
        else:
            # 自动生成优化文件名
            original_file = Path(original_path)
            output_path = original_file.with_suffix('')
            output_path = output_path.parent / f"{output_path.name}_optimized.srt"
        
        # 确保输出目录存在
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 写入优化后的SRT文件
        with open(output_path, 'w', encoding='utf-8') as f:
            for entry in optimized_entries:
                # 格式化为SRT格式
                start_time_str = SRTParser.seconds_to_time(entry.start_time)
                end_time_str = SRTParser.seconds_to_time(entry.end_time)
                
                f.write(f"{entry.index}\n")
                f.write(f"{start_time_str} --> {end_time_str}\n")
                f.write(f"{entry.text}\n\n")
        
        self.logger.success(f"优化字幕已保存: {output_path}")
        return str(output_path)
    
    def generate_optimization_summary(self, report: OptimizationReport) -> str:
        """生成优化摘要"""
        if report.merged_count == 0:
            return "字幕无需优化"
        
        summary = f"""
            字幕优化摘要:
            - 原始条目: {report.original_entries}
            - 优化后条目: {report.optimized_entries}
            - 合并条目数: {report.merged_count}
            - 修复短字幕: {report.short_subtitles_fixed}
            - 合并句子片段: {report.fragmented_sentences_merged}
            - 平均时长改进: {report.duration_improvements.get('avg_duration_before', 0):.2f}s → {report.duration_improvements.get('avg_duration_after', 0):.2f}s
        """.strip()
        
        return summary