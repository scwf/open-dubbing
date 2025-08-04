"""
LLM驱动的字幕优化器（增强版）

基于大语言模型的上下文感知字幕优化系统，集成智能时间借用功能
先时间借用优化，后LLM文本简化
"""

import re
from typing import List, Dict, Any, Optional, NamedTuple
from pathlib import Path
from ai_dubbing.src.logger import get_logger
from openai import OpenAI


class SRTEntry(NamedTuple):
    """SRT条目数据结构"""
    index: int
    start_time: int  # 毫秒
    end_time: int    # 毫秒
    text: str
    
    @property
    def duration(self) -> int:
        """获取持续时间（毫秒）"""
        return self.end_time - self.start_time


class SubtitleTimingConstants:
    """字幕时间计算常量"""
    CHINESE_CHAR_TIME = 130  # 每个中文字符的默认朗读时间（毫秒）- 约0.13秒
    ENGLISH_WORD_TIME = 250  # 每个英文单词的默认朗读时间（毫秒）- 约0.25秒


class OptimizationReport(NamedTuple):
    """优化报告数据结构"""
    original_entries: int
    optimized_entries: int
    simplified_count: int
    time_borrowed_count: int
    decisions: List[Dict[str, Any]]


class TimeBorrowOptimizer:
    """时间借用优化器"""
    
    def __init__(self, 
                 min_gap_threshold: int = 300,
                 borrow_ratio: float = 0.5,
                 extra_buffer: int = 200,
                 chinese_char_time: int = None,
                 english_word_time: int = None):
        """
        初始化时间借用优化器
        
        Args:
            min_gap_threshold: 最小保护空隙（毫秒）
            borrow_ratio: 借用比例（0.1-0.8）
            extra_buffer: 额外缓冲时间（毫秒）
            chinese_char_time: 每个中文字符的朗读时间（毫秒），默认为SubtitleTimingConstants.CHINESE_CHAR_TIME
            english_word_time: 每个英文单词的朗读时间（毫秒），默认为SubtitleTimingConstants.ENGLISH_WORD_TIME
        """
        self.min_gap_threshold = min_gap_threshold
        self.borrow_ratio = borrow_ratio
        self.extra_buffer = extra_buffer
        self.chinese_char_time = chinese_char_time or SubtitleTimingConstants.CHINESE_CHAR_TIME
        self.english_word_time = english_word_time or SubtitleTimingConstants.ENGLISH_WORD_TIME
        self.logger = get_logger()
    
    def calculate_needed_extension(self, text: str, current_duration: int) -> int:
        """计算需要延长的时间"""
        min_required = self._calculate_minimum_duration(text)
        needed = max(0, min_required - current_duration)
        return needed
    
    def _calculate_minimum_duration(self, text: str) -> int:
        """基于字符密度计算最小所需时长"""
        chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
        english_words = len(re.findall(r'[a-zA-Z]+', text))
        
        chinese_duration = chinese_chars * self.chinese_char_time
        english_duration = english_words * self.english_word_time
        
        return chinese_duration + english_duration
    
    def can_borrow_time(self, prev_gap: int, next_gap: int) -> tuple[bool, int, int]:
        """
        判断是否可以借用时间
        
        Returns:
            (是否可以借用, 可前向借用时间, 可后向借用时间)
        """
        front_available = max(0, prev_gap - self.min_gap_threshold)
        back_available = max(0, next_gap - self.min_gap_threshold)
        
        front_borrow = int(front_available * self.borrow_ratio)
        back_borrow = int(back_available * self.borrow_ratio)
        
        total_available = front_borrow + back_borrow
        
        return (total_available > 0, front_borrow, back_borrow)
    
    def adjust_timing(self, entry: SRTEntry, front_borrow: int, back_borrow: int) -> SRTEntry:
        """调整字幕时间"""
        new_start = max(0, entry.start_time - front_borrow)
        new_end = entry.end_time + back_borrow
        
        return SRTEntry(
            index=entry.index,
            start_time=new_start,
            end_time=new_end,
            text=entry.text
        )
    
    def optimize_with_time_borrowing(self, entries: List[SRTEntry]) -> tuple[List[SRTEntry], List[Dict[str, Any]]]:
        """使用时间借用优化字幕"""
        if not entries:
            return entries, []
        
        optimized = []
        decisions = []
        
        for i, entry in enumerate(entries):
            # 计算需要延长时间
            needed_time = self.calculate_needed_extension(entry.text, entry.duration)
            
            if needed_time <= 0:
                optimized.append(entry)
                decisions.append({
                    'index': i,
                    'action': 'NO_CHANGE',
                    'reason': '时长充足',
                    'time_added': 0
                })
                continue
            
            # 计算前后空隙
            prev_gap = entry.start_time - (entries[i-1].end_time if i > 0 else 0)
            next_gap = (entries[i+1].start_time if i < len(entries) - 1 else entry.end_time + 1) - entry.end_time
            
            # 尝试借用时间
            can_borrow, front_borrow, back_borrow = self.can_borrow_time(prev_gap, next_gap)
            total_borrowed = front_borrow + back_borrow
            
            total_needed = needed_time + self.extra_buffer
            if total_borrowed >= total_needed:
                # 时间借用成功，按比例分配借用时间
                ratio = min(1.0, total_needed / total_borrowed)
                actual_front = int(front_borrow * ratio)
                actual_back = int(back_borrow * ratio)
                
                adjusted_entry = self.adjust_timing(entry, actual_front, actual_back)
                optimized.append(adjusted_entry)
                
                decisions.append({
                    'index': i,
                    'action': 'TIME_BORROW',
                    'time_added': actual_front + actual_back,
                    'front_borrow': actual_front,
                    'back_borrow': actual_back,
                    'reason': '时间借用成功',
                    'buffer_added': self.extra_buffer
                })
            else:
                # 时间借用不足，标记给LLM处理
                optimized.append(entry)
                decisions.append({
                    'index': i,
                    'action': 'NEED_LLM',
                    'time_added': total_borrowed,
                    'reason': '时间借用不足，需要LLM优化',
                    'min_required': self._calculate_minimum_duration(entry.text),
                    'current_duration': entry.duration
                })
        
        return optimized, decisions


class LLMContextOptimizer:
    """LLM上下文感知字幕优化器（集成时间借用）"""
    
    def __init__(self, 
                 api_key: Optional[str] = None,
                 model: str = "deepseek-chat",
                 base_url: str = "https://api.deepseek.com",
                 chinese_char_min_time: int = None,
                 english_word_min_time: int = None,
                 min_gap_threshold: int = 300,
                 borrow_ratio: float = 0.5,
                 extra_buffer: int = 200):
        """
        初始化LLM优化器（集成时间借用）
        
        Args:
            api_key: DeepSeek API密钥
            model: LLM模型名称
            base_url: API基础URL
            chinese_char_min_time: 每个中文字最小时间(毫秒)，默认为SubtitleTimingConstants.CHINESE_CHAR_TIME
            english_word_min_time: 每个英文单词最小时间(毫秒)，默认为SubtitleTimingConstants.ENGLISH_WORD_TIME
            min_gap_threshold: 最小保护空隙（毫秒）
            borrow_ratio: 借用比例（0.1-0.8）
            extra_buffer: 额外缓冲时间（毫秒）
        """
        self.api_key = api_key
        self.model = model
        self.base_url = base_url
        self.chinese_char_min_time = chinese_char_min_time or SubtitleTimingConstants.CHINESE_CHAR_TIME
        self.english_word_min_time = english_word_min_time or SubtitleTimingConstants.ENGLISH_WORD_TIME
        self.logger = get_logger()
        
        # 初始化时间借用优化器
        self.time_borrower = TimeBorrowOptimizer(
            min_gap_threshold=min_gap_threshold,
            borrow_ratio=borrow_ratio,
            extra_buffer=extra_buffer,
            chinese_char_time=self.chinese_char_min_time,
            english_word_time=self.english_word_min_time
        )
        
        if api_key:
            self.client = OpenAI(api_key=api_key, base_url=base_url)
        else:
            self.client = None
            self.logger.warning("LLM优化器未配置，将跳过文本简化")
    
    def calculate_minimum_duration(self, text: str) -> tuple[int, str]:
        """基于最小时间阈值计算字幕的最小所需时长"""
        chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
        english_words = len(re.findall(r'[a-zA-Z]+', text))
        
        chinese_duration = int(chinese_chars * self.chinese_char_min_time)
        english_duration = int(english_words * self.english_word_min_time)
        min_duration = chinese_duration + english_duration
        
        if chinese_chars > 0 and english_words > 0:
            lang_type = f'mixed_cn{chinese_chars}_en{english_words}'
        elif chinese_chars > 0:
            lang_type = 'chinese'
        elif english_words > 0:
            lang_type = 'english'
        else:
            lang_type = 'unknown'
            
        return min_duration, lang_type
    
    def optimize_subtitles(self, entries: List[SRTEntry]) -> tuple[List[SRTEntry], OptimizationReport]:
        """
        智能字幕优化（时间借用 + LLM文本简化）
        
        Args:
            entries: 字幕条目列表
            
        Returns:
            优化后的字幕条目列表和优化报告
        """
        if not entries:
            return entries, OptimizationReport(len(entries), len(entries), 0, 0, [])
        
        self.logger.step("开始智能字幕优化（时间借用 + LLM简化）")
        
        # 1. 时间借用优化
        self.logger.step("开始时间借用优化")
        time_optimized, time_decisions = self.time_borrower.optimize_with_time_borrowing(entries)
        
        # 统计时间借用结果
        time_borrowed_count = len([d for d in time_decisions if d['action'] == 'TIME_BORROW'])
        need_llm_indices = [d['index'] for d in time_decisions if d['action'] == 'NEED_LLM']
        
        self.logger.info(f"时间借用成功: {time_borrowed_count}条字幕")
        self.logger.info(f"需要LLM优化: {len(need_llm_indices)}条字幕")
        
        # 2. 如果需要LLM优化
        llm_optimized = time_optimized
        llm_decisions = []
        
        if need_llm_indices and self.client:
            self.logger.step("开始LLM文本简化优化")
            
            # 创建需要LLM优化的上下文
            llm_contexts = []
            for idx in need_llm_indices:
                decision = next(d for d in time_decisions if d['index'] == idx)
                entry = time_optimized[idx]
                
                llm_contexts.append({
                    'index': idx,
                    'current': entry,
                    'min_required_duration': decision['min_required'],
                    'shortage_ratio': decision['min_required'] / entry.duration,
                    'text': entry.text,
                    'all_entries': time_optimized
                })
            
            # LLM文本简化
            for context in llm_contexts:
                llm_decision = self._get_llm_simplification(context)
                llm_decisions.append(llm_decision)
            
            # 执行LLM简化
            llm_optimized = self._execute_simplifications(time_optimized, llm_decisions)
        
        # 3. 生成最终报告
        simplified_count = len([d for d in llm_decisions if d['action'] == 'SIMPLIFY'])
        
        # 合并所有决策
        all_decisions = []
        for d in time_decisions:
            if d['action'] == 'NEED_LLM':
                # 找到对应的LLM决策
                llm_d = next((ld for ld in llm_decisions if ld.get('context', {}).get('index') == d['index']), None)
                if llm_d:
                    all_decisions.append(llm_d)
                else:
                    all_decisions.append(d)
            else:
                all_decisions.append(d)
        
        # 最终验证：检查还有多少字幕时长不足
        short_duration_count = 0
        short_duration_details = []
        
        for entry in llm_optimized:
            min_duration, _ = self.calculate_minimum_duration(entry.text)
            if entry.duration < min_duration:
                short_duration_count += 1
                short_duration_details.append({
                    'index': entry.index,
                    'text': entry.text,
                    'current_duration': entry.duration,
                    'min_required': min_duration,
                    'shortage': min_duration - entry.duration
                })
        
        if short_duration_count > 0:
            self.logger.warning(f"⚠️ 仍有 {short_duration_count} 条字幕时长不足最小时长")
            for detail in short_duration_details[:5]:  # 只显示前5条
                self.logger.warning(
                    f"字幕{detail['index']}: 当前{detail['current_duration']}ms, "
                    f"需要{detail['min_required']}ms, 缺少{detail['shortage']}ms"
                )
        else:
            self.logger.success("✅ 所有字幕时长均满足最小时长要求")
        
        report = OptimizationReport(
            original_entries=len(entries),
            optimized_entries=len(llm_optimized),
            simplified_count=simplified_count,
            time_borrowed_count=time_borrowed_count,
            decisions=all_decisions
        )
        
        self.logger.success(
            f"优化完成：时间借用{time_borrowed_count}条，LLM简化{simplified_count}条，"
            f"时长不足{short_duration_count}条"
        )
        return llm_optimized, report
    
    def _get_llm_simplification(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """获取LLM文本简化结果（保持原有逻辑）"""
        if not self.client:
            return {'action': 'NO_CHANGE', 'reason': 'LLM未配置', 'original_text': context['current'].text}
        
        current = context['current']
        min_required = context['min_required_duration']
        
        # 获取上下文
        entries = context['all_entries']
        current_idx = context['index']
        
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
        
        prompt = f"""
        你是字幕文本简化专家，请对指定的字幕进行智能简化。

        ## 任务说明
        当前需要简化的字幕文本时长不足，需要简化文本使其朗读时长能够达到最小时长要求。

        ## 上下文信息
        {context_text}

        ## 需要简化的字幕
        - 原始文本："{current.text}"
        - 当前时长：{current.duration}毫秒
        - 需要达到的最小时长：{min_required}毫秒

        ## 简化要求
        1. 使用更简洁的表达方式，使得简化后文本汉字数量小于原始文本汉字数量
        2. 保持核心语义不变，去除冗余词汇
        3. 与上下文保持语义连贯
        4. 尽量保持语言的自然流畅

        ## 回复格式
        SIMPLIFIED_TEXT: [简化后的文本]
        REASON: [简要说明简化策略]
        """
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                stream=False
            )
            
            result = response.choices[0].message.content.strip()
            
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
    
    def _execute_simplifications(self, entries: List[SRTEntry], decisions: List[Dict[str, Any]]) -> List[SRTEntry]:
        """执行LLM文本简化决策"""
        if not decisions:
            return entries
        
        optimized = [entry for entry in entries]
        
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
    
    def save_optimized_srt(self, optimized_entries: List[SRTEntry], 
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
                start_time_str = SRTParser.milliseconds_to_time(new_entry.start_time)
                end_time_str = SRTParser.milliseconds_to_time(new_entry.end_time)
                
                f.write(f"{new_entry.index}\n")
                f.write(f"{start_time_str} --> {end_time_str}\n")
                f.write(f"{new_entry.text}\n\n")
        
        self.logger.success(f"智能优化字幕已保存: {output_path}")
        return str(output_path)