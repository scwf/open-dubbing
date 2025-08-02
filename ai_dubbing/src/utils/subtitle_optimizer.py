"""
LLM驱动的字幕优化器

基于大语言模型的上下文感知字幕优化系统
仅使用字符密度触发，LLM做智能合并决策
"""

import re
from typing import List, Dict, Any, Optional, NamedTuple
from pathlib import Path
from ai_dubbing.src.logger import get_logger
from openai import OpenAI


class SRTEntry(NamedTuple):
    """SRT条目数据结构"""
    index: int
    start_time: float  # 秒
    end_time: float    # 秒
    text: str
    
    @property
    def duration(self) -> float:
        """获取持续时间（秒）"""
        return self.end_time - self.start_time


class OptimizationReport(NamedTuple):
    """优化报告数据结构"""
    original_entries: int
    optimized_entries: int
    merged_count: int
    decisions: List[Dict[str, Any]]


class LLMContextOptimizer:
    """LLM上下文感知字幕优化器"""
    
    def __init__(self, 
                 api_key: Optional[str] = None,
                 model: str = "deepseek-chat",
                 base_url: str = "https://api.deepseek.com",
                 chinese_char_min_time: float = 0.15,    # 每个中文字最小时间(秒)
                 english_word_min_time: float = 0.3):     # 每个英文单词最小时间(秒)
        """
        初始化LLM优化器
        
        Args:
            api_key: DeepSeek API密钥
            model: LLM模型名称
            base_url: API基础URL
            chinese_char_min_time: 每个中文字最小时间(秒)
            english_word_min_time: 每个英文单词最小时间(秒)
        """
        self.api_key = api_key
        self.model = model
        self.base_url = base_url
        self.chinese_char_min_time = chinese_char_min_time
        self.english_word_min_time = english_word_min_time
        self.logger = get_logger()
        
        if api_key:
            self.client = OpenAI(api_key=api_key, base_url=base_url)
        else:
            self.client = None
            self.logger.warning("LLM优化器未配置，将跳过优化")

    def calculate_minimum_duration(self, text: str) -> tuple[float, str]:
        """
        基于最小时间阈值计算字幕的最小所需时长
        
        对于中英文混合的字幕，分别计算中文和英文部分的最短时长然后相加
        
        Args:
            text: 字幕文本
            
        Returns:
            (最小所需时长, 语言类型描述)
        """
        # 分别计算中文和英文部分
        chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
        english_words = len(re.findall(r'[a-zA-Z]+', text))
        
        # 分别计算最短时长并相加
        chinese_duration = chinese_chars * self.chinese_char_min_time
        english_duration = english_words * self.english_word_min_time
        min_duration = chinese_duration + english_duration
        
        # 生成语言类型描述
        if chinese_chars > 0 and english_words > 0:
            lang_type = f'mixed_cn{chinese_chars}_en{english_words}'
        elif chinese_chars > 0:
            lang_type = 'chinese'
        elif english_words > 0:
            lang_type = 'english'
        else:
            lang_type = 'unknown'
            
        return min_duration, lang_type

    def is_duration_adequate(self, text: str, duration: float) -> tuple[bool, float, str]:
        """
        判断字幕时长是否充足
        
        Args:
            text: 字幕文本
            duration: 实际时长
            
        Returns:
            (是否充足, 最小所需时长, 语言类型)
        """
        min_duration, lang_type = self.calculate_minimum_duration(text)
        is_adequate = duration >= min_duration
        return is_adequate, min_duration, lang_type
    
    def identify_high_density_contexts(self, entries: List[SRTEntry]) -> List[Dict[str, Any]]:
        """识别需要优化的字幕（基于最小时间阈值）"""
        contexts = []
        
        for i, entry in enumerate(entries):
            is_adequate, min_duration, lang_type = self.is_duration_adequate(entry.text, entry.duration)
            
            if not is_adequate:  # 时长不足，需要优化
                contexts.append({
                    'index': i,
                    'prev': entries[i-1] if i > 0 else None,
                    'current': entry,
                    'next': entries[i+1] if i < len(entries) - 1 else None,
                    'min_required_duration': min_duration,
                    'shortage_ratio': min_duration / entry.duration if entry.duration > 0 else float('inf'),
                    'lang_type': lang_type,
                    'text': entry.text
                })
        
        return contexts
    
    def _build_context_prompt(self, context: Dict[str, Any]) -> str:
        """构建LLM决策提示词"""
        prev = context['prev']
        current = context['current']
        next_entry = context['next']
        
        def format_entry(entry: SRTEntry, prefix: str):
            if not entry:
                return f"### {prefix}\n文本：无\n时长：0秒\n最小所需时长：0秒\n"
            
            is_adequate, min_duration, _ = self.is_duration_adequate(entry.text, entry.duration)
            
            return f"""### {prefix}
                文本："{entry.text}"
                实际时长：{entry.duration:.2f}秒
                最小所需时长：{min_duration:.2f}秒
                时长是否充足：{'是' if is_adequate else '否'}
                """
        
        # 计算合并场景
        merge_scenarios = []
        
        # 与前一条合并
        if prev:
            combined_text = prev.text + " " + current.text
            combined_duration = current.end_time - prev.start_time
            merge_scenarios.append({
                'type': 'MERGE_PREV',
                'text': combined_text,
                'duration': combined_duration,
                'min_duration': self.calculate_minimum_duration(combined_text)[0]
            })
        
        # 与后一条合并
        if next_entry:
            combined_text = current.text + " " + next_entry.text
            combined_duration = next_entry.end_time - current.start_time
            merge_scenarios.append({
                'type': 'MERGE_NEXT',
                'text': combined_text,
                'duration': combined_duration,
                'min_duration': self.calculate_minimum_duration(combined_text)[0]
            })
        
        # 三条合并
        if prev and next_entry:
            combined_text = prev.text + " " + current.text + " " + next_entry.text
            combined_duration = next_entry.end_time - prev.start_time
            merge_scenarios.append({
                'type': 'MERGE_BOTH',
                'text': combined_text,
                'duration': combined_duration,
                'min_duration': self.calculate_minimum_duration(combined_text)[0]
            })
        
        scenarios_text = ""
        for scenario in merge_scenarios:
            scenarios_text += f"""
                {scenario['type']}:
                合并后文本："{scenario['text']}"
                合并后时长：{scenario['duration']:.2f}秒
                合并后最小所需时长：{scenario['min_duration']:.2f}秒
                """
        
        return f"""
            你是字幕优化专家，请基于时长合理性分析决定最佳合并策略。
            ## 当前分析场景
            高密度字幕位于中间，需要与前后字幕优化。

            {format_entry(prev, '字幕A（前一条）')}
            {format_entry(current, '字幕B（当前字幕，时长不足）')}
            {format_entry(next_entry, '字幕C（后一条）')}

            ## 合并选项{scenarios_text}

            ## 决策标准
            1. 语义连贯性：合并后是否有明显的语义断层和生硬感
            2. 时长合理性：合并后时长应大于或等于最小所需要求，且不能过长（不超过5秒）

            ## 回复格式
            DECISION: [MERGE_PREV/MERGE_NEXT/NO_MERGE/MERGE_BOTH]
            REASON: [简短理由]
            """
    
    def _get_llm_decision(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """获取LLM合并决策"""
        if not self.client:
            return {'action': 'NO_MERGE', 'reason': 'LLM未配置'}
        
        prompt = self._build_context_prompt(context)
        print(prompt)
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                stream=False
            )
            
            result = response.choices[0].message.content.strip()
            print("--------------------------------")
            print(result)
            # 解析LLM响应
            lines = result.split('\n')
            decision = 'NO_MERGE'
            reason = 'LLM未返回有效决策'
            
            for line in lines:
                if line.startswith('DECISION:'):
                    decision = line.split(':', 1)[1].strip()
                elif line.startswith('REASON:'):
                    reason = line.split(':', 1)[1].strip()
            
            return {
                'action': decision,
                'reason': reason,
                'context': context
            }
            
        except Exception as e:
            self.logger.error(f"LLM决策失败: {e}")
            return {'action': 'NO_MERGE', 'reason': str(e)}
    
    def optimize_subtitles(self, entries) -> tuple[list, OptimizationReport]:
        """
        使用LLM优化字幕
        
        Args:
            entries: 字幕条目列表
            
        Returns:
            优化后的字幕条目列表和优化报告
        """
        if not entries or len(entries) < 2:
            return entries, OptimizationReport(len(entries), len(entries), 0, [])
        
        if not self.client:
            self.logger.info("LLM未配置，跳过优化")
            return entries, OptimizationReport(len(entries), len(entries), 0, [])
        
        self.logger.step("开始LLM字幕优化")
        
        # 1. 识别高密度字幕
        contexts = self.identify_high_density_contexts(entries)
        
        if not contexts:
            self.logger.info("未发现高密度字幕，无需优化")
            return entries, OptimizationReport(len(entries), len(entries), 0, [])
        
        self.logger.info(f"发现{len(contexts)}个高密度字幕")
        
        # 2. LLM决策
        decisions = []
        for context in contexts:
            decision = self._get_llm_decision(context)
            decisions.append(decision)
        
        # 3. 执行合并决策
        optimized = self._execute_decisions(entries, decisions)
        
        # 4. 生成报告
        report = OptimizationReport(
            original_entries=len(entries),
            optimized_entries=len(optimized),
            merged_count=len(entries) - len(optimized),
            decisions=decisions
        )
        
        self.logger.success(f"LLM优化完成：合并{report.merged_count}个字幕")
        return optimized, report
    
    def _execute_decisions(self, entries: list, decisions: List[Dict[str, Any]]) -> list:
        """执行LLM合并决策"""
        if not decisions:
            return entries
        
        # 从后向前执行，避免索引偏移
        decisions.sort(key=lambda x: x['context']['index'], reverse=True)
        
        optimized = entries.copy()
        
        # 延迟导入避免循环导入
        from ai_dubbing.src.parsers.srt_parser import SRTEntry
        
        for decision in decisions:
            action = decision['action']
            idx = decision['context']['index']
            
            if idx >= len(optimized):
                continue
            
            if action == "MERGE_PREV" and idx > 0:
                optimized = self._merge_entries(optimized, idx-1, idx, SRTEntry)
                
            elif action == "MERGE_NEXT" and idx < len(optimized) - 1:
                optimized = self._merge_entries(optimized, idx, idx+1, SRTEntry)
                
            elif action == "MERGE_BOTH" and 1 <= idx < len(optimized) - 1:
                optimized = self._merge_three_entries(optimized, idx-1, idx, idx+1, SRTEntry)
        
        return optimized
    
    def _merge_entries(self, entries: list, idx1: int, idx2: int, entry_class) -> list:
        """合并两个字幕条目"""
        if idx1 >= len(entries) or idx2 >= len(entries):
            return entries
        
        new_entry = entry_class(
            index=idx1 + 1,
            start_time=entries[idx1].start_time,
            end_time=entries[idx2].end_time,
            text=entries[idx1].text.strip() + " " + entries[idx2].text.strip()
        )
        
        return entries[:idx1] + [new_entry] + entries[idx2+1:]
    
    def _merge_three_entries(self, entries: list, idx1: int, idx2: int, idx3: int, entry_class) -> list:
        """合并三个字幕条目"""
        if max(idx1, idx2, idx3) >= len(entries):
            return entries
        
        new_entry = entry_class(
            index=idx1 + 1,
            start_time=entries[idx1].start_time,
            end_time=entries[idx3].end_time,
            text=" ".join([entries[idx1].text.strip(), entries[idx2].text.strip(), entries[idx3].text.strip()])
        )
        
        return entries[:idx1] + [new_entry] + entries[idx3+1:]
    
    def save_optimized_srt(self, optimized_entries: list, 
                          original_path: str, 
                          custom_output: Optional[str] = None) -> str:
        """保存优化后的字幕文件"""
        # 延迟导入避免循环导入
        from ai_dubbing.src.parsers.srt_parser import SRTParser
        
        if custom_output:
            output_path = Path(custom_output)
        else:
            original_file = Path(original_path)
            output_path = original_file.with_suffix('')
            output_path = output_path.parent / f"{output_path.name}_llm_optimized.srt"
        
        # 确保输出目录存在
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 写入优化后的SRT文件
        with open(output_path, 'w', encoding='utf-8') as f:
            for i, entry in enumerate(optimized_entries):
                # 重新编号
                new_entry = entry._replace(index=i+1)
                
                # 格式化为SRT格式
                start_time_str = SRTParser.seconds_to_time(new_entry.start_time)
                end_time_str = SRTParser.seconds_to_time(new_entry.end_time)
                
                f.write(f"{new_entry.index}\n")
                f.write(f"{start_time_str} --> {end_time_str}\n")
                f.write(f"{new_entry.text}\n\n")
        
        self.logger.success(f"LLM优化字幕已保存: {output_path}")
        return str(output_path)