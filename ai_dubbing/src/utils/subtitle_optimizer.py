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
    simplified_count: int
    decisions: List[Dict[str, Any]]


class LLMContextOptimizer:
    """LLM上下文感知字幕优化器"""
    
    def __init__(self, 
                 api_key: Optional[str] = None,
                 model: str = "deepseek-chat",
                 base_url: str = "https://api.deepseek.com",
                 chinese_char_min_time: float = 0.13,    # 每个中文字最小时间(秒)
                 english_word_min_time: float = 0.25):     # 每个英文单词最小时间(秒)
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
                    'current': entry,
                    'min_required_duration': min_duration,
                    'shortage_ratio': min_duration / entry.duration if entry.duration > 0 else float('inf'),
                    'lang_type': lang_type,
                    'text': entry.text,
                    'all_entries': entries  # 用于获取上下文
                })
        
        return contexts
    
    def _build_simplification_prompt(self, context: Dict[str, Any]) -> str:
        """构建LLM文本简化提示词"""
        current = context['current']
        min_required = context['min_required_duration']
        
        # 获取上下文（前3条和后3条）
        entries = context['all_entries']
        current_idx = context['index']
        
        # 计算上下文范围
        start_idx = max(0, current_idx - 3)
        end_idx = min(len(entries), current_idx + 4)
        
        context_entries = []
        for i in range(start_idx, end_idx):
            entry = entries[i]
            position = "当前" if i == current_idx else f"前{current_idx-i}" if i < current_idx else f"后{i-current_idx}"
            context_entries.append({
                'position': position,
                'text': entry.text,
                'index': i + 1
            })
        
        context_text = ""
        for entry in context_entries:
            marker = "【需要简化】" if entry['index'] == current_idx + 1 else ""
            context_text += f"字幕{entry['index']} ({entry['position']}){marker}: {entry['text']}\n"
        
        return f"""
        你是字幕文本简化专家，请对指定的字幕进行智能简化。

        ## 任务说明
        当前需要简化的字幕文本时长不足，需要简化文本使其朗读时长能够达到最小时长要求。

        ## 上下文信息
        {context_text}

        ## 需要简化的字幕
        - 原始文本："{current.text}"
        - 当前时长：{current.duration:.2f}秒
        - 需要达到的最小时长：{min_required:.2f}秒

        ## 简化要求
        1. 使用更简洁的表达方式，使得简化后文本汉字数量小于原始文本汉字数量
        2. 保持核心语义不变，去除冗余词汇
        3. 与上下文保持语义连贯
        4. 尽量保持语言的自然流畅

        ## 回复格式
        SIMPLIFIED_TEXT: [简化后的文本]
        REASON: [简要说明简化策略]
        """
    
    def _get_llm_simplification(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """获取LLM文本简化结果"""
        if not self.client:
            return {'action': 'NO_CHANGE', 'reason': 'LLM未配置', 'original_text': context['current'].text}
        
        prompt = self._build_simplification_prompt(context)
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                stream=False
            )
            
            result = response.choices[0].message.content.strip()
            
            # 解析LLM响应
            lines = result.split('\n')
            simplified_text = context['current'].text
            reason = 'LLM未返回有效简化文本'
            
            for line in lines:
                if line.startswith('SIMPLIFIED_TEXT:'):
                    simplified_text = line.split(':', 1)[1].strip().strip('"')
                elif line.startswith('REASON:'):
                    reason = line.split(':', 1)[1].strip()
            
            return {
                'action': 'SIMPLIFY',
                'reason': reason,
                'original_text': context['current'].text,
                'simplified_text': simplified_text,
                'context': context
            }
            
        except Exception as e:
            self.logger.error(f"LLM简化失败: {e}")
            return {'action': 'NO_CHANGE', 'reason': str(e), 'original_text': context['current'].text}
    
    def optimize_subtitles(self, entries) -> tuple[list, OptimizationReport]:
        """
        使用LLM优化字幕（文本简化版）
        
        Args:
            entries: 字幕条目列表
            
        Returns:
            优化后的字幕条目列表和优化报告
        """
        if not entries:
            return entries, OptimizationReport(len(entries), len(entries), 0, [])
        
        if not self.client:
            self.logger.info("LLM未配置，跳过优化")
            return entries, OptimizationReport(len(entries), len(entries), 0, [])
        
        self.logger.step("开始LLM字幕文本简化优化")
        
        # 1. 识别时长不足的字幕
        contexts = self.identify_high_density_contexts(entries)
        
        if not contexts:
            self.logger.info("未发现时长不足的字幕，无需优化")
            return entries, OptimizationReport(len(entries), len(entries), 0, [])
        
        self.logger.info(f"发现{len(contexts)}个时长不足的字幕")
        
        # 2. LLM文本简化
        decisions = []
        for context in contexts:
            decision = self._get_llm_simplification(context)
            decisions.append(decision)
        
        # 3. 执行文本简化
        optimized = self._execute_simplifications(entries, decisions)
        
        # 4. 生成报告
        simplified_count = len([d for d in decisions if d['action'] == 'SIMPLIFY'])
        report = OptimizationReport(
            original_entries=len(entries),
            optimized_entries=len(optimized),
            simplified_count=simplified_count,
            decisions=decisions
        )
        
        self.logger.success(f"LLM优化完成：简化{report.simplified_count}个字幕")
        return optimized, report
    
    def _execute_simplifications(self, entries: list, decisions: List[Dict[str, Any]]) -> list:
        """执行LLM文本简化决策"""
        if not decisions:
            return entries
        
        optimized = [entry for entry in entries]  # 创建副本
        
        # 延迟导入避免循环导入
        from ai_dubbing.src.parsers.srt_parser import SRTEntry
        
        for decision in decisions:
            action = decision['action']
            if action != 'SIMPLIFY':
                continue
                
            idx = decision['context']['index']
            if idx >= len(optimized):
                continue
            
            original_entry = optimized[idx]
            simplified_text = decision['simplified_text']
            
            # 创建新的简化字幕条目
            simplified_entry = SRTEntry(
                index=original_entry.index,
                start_time=original_entry.start_time,
                end_time=original_entry.end_time,
                text=simplified_text
            )
            
            optimized[idx] = simplified_entry
            self.logger.info(f"简化字幕{idx+1}: '{original_entry.text}' → '{simplified_text}'")
        
        return optimized
    
    
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