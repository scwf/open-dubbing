"""
LLM字幕优化器测试

测试LLMContextOptimizer类的各项功能
"""

import unittest
import tempfile
import os
from pathlib import Path

from ..parsers.srt_parser import SRTEntry
from ..optimizer.subtitle_optimizer import (
    LLMContextOptimizer,
    TimeBorrowOptimizer,
    SubtitleTimingConstants,
)


class TestLLMContextOptimizer(unittest.TestCase):
    """LLM字幕优化器单元测试"""
    
    def setUp(self):
        """测试初始化"""
        self.optimizer = LLMContextOptimizer()  # 无需API密钥，模拟测试
        self.temp_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        """清理测试文件"""
        import shutil
        shutil.rmtree(self.temp_dir)
    
    def test_calculate_minimum_duration_chinese(self):
        """测试中文字符最小时间计算"""
        text = "这是一个测试中文字符密度的字幕"
        min_duration, lang_type = self.optimizer.calculate_minimum_duration(text)
        
        # 中文字符数量 * 单字时长
        chinese_chars = len(text)
        expected_duration = chinese_chars * SubtitleTimingConstants.CHINESE_CHAR_TIME
        
        self.assertAlmostEqual(min_duration, expected_duration, places=2)
        self.assertEqual(lang_type, 'chinese')

    def test_calculate_minimum_duration_english(self):
        """测试英文单词最小时间计算"""
        text = "This is a test subtitle for density calculation"
        min_duration, lang_type = self.optimizer.calculate_minimum_duration(text)
        
        # 英文单词数量 * 单词时长
        english_words = 8
        expected_duration = english_words * SubtitleTimingConstants.ENGLISH_WORD_TIME
        
        self.assertAlmostEqual(min_duration, expected_duration, places=2)
        self.assertEqual(lang_type, 'english')

    def test_calculate_minimum_duration_mixed(self):
        """测试中英文混合最小时间计算"""
        text = "这是一个test混合的字幕subtitle"
        min_duration, lang_type = self.optimizer.calculate_minimum_duration(text)
        
        expected_duration = (
            9 * SubtitleTimingConstants.CHINESE_CHAR_TIME +
            2 * SubtitleTimingConstants.ENGLISH_WORD_TIME
        )
        self.assertEqual(lang_type, 'mixed_cn9_en2')
        self.assertAlmostEqual(min_duration, expected_duration, places=2)
    
    def test_calculate_minimum_duration(self):
        """测试最小时间计算"""
        # 中文字符测试
        text = "正常字幕"
        min_duration, lang_type = self.optimizer.calculate_minimum_duration(text)
        expected = len(text) * SubtitleTimingConstants.CHINESE_CHAR_TIME
        self.assertAlmostEqual(min_duration, expected, places=2)
        self.assertEqual(lang_type, 'chinese')
        
        # 英文单词测试
        text = "This is test"
        min_duration, lang_type = self.optimizer.calculate_minimum_duration(text)
        expected = 3 * SubtitleTimingConstants.ENGLISH_WORD_TIME
        self.assertAlmostEqual(min_duration, expected, places=2)
        self.assertEqual(lang_type, 'english')
    
    def test_empty_entries(self):
        """测试空条目处理"""
        entries = []
        optimized, report = self.optimizer.optimize_subtitles(entries)
        
        self.assertEqual(len(optimized), 0)
        self.assertEqual(report.original_entries, 0)
        self.assertEqual(report.optimized_entries, 0)
        self.assertEqual(report.simplified_count, 0)
    
    def test_single_entry(self):
        """测试单条字幕"""
        entries = [SRTEntry(1, 0.0, 2.0, "单条字幕")]
        optimized, report = self.optimizer.optimize_subtitles(entries)
        
        self.assertEqual(len(optimized), 1)
        self.assertEqual(report.original_entries, 1)
        self.assertEqual(report.optimized_entries, 1)
        self.assertEqual(report.simplified_count, 0)
    
    def test_no_llm_config(self):
        """测试无API密钥的情况"""
        optimizer = LLMContextOptimizer(api_key=None)
        entries = [
            SRTEntry(1, 0.0, 0.5, "高密度字幕"),
            SRTEntry(2, 1.0, 2.0, "正常字幕"),
        ]
        
        optimized, report = optimizer.optimize_subtitles(entries)
        
        # 应该跳过优化
        self.assertEqual(len(optimized), 2)
        self.assertEqual(report.original_entries, 2)
        self.assertEqual(report.optimized_entries, 2)
        self.assertEqual(report.simplified_count, 0)


class TestLLMIntegration(unittest.TestCase):
    """LLM集成测试"""
    
    def setUp(self):
        """测试初始化"""
        self.test_data_dir = Path(__file__).parent / "test_data"
        self.target_srt = Path(__file__).parent.parent.parent / "input" / "target_language.srt"
        self.sample_srt = self.test_data_dir / "sample2.srt"
        
    def test_load_sample_srt(self):
        """测试从sample2.srt加载字幕数据"""
        from ..parsers.srt_parser import SRTParser
        
        # 验证文件存在
        self.assertTrue(self.sample_srt.exists(), "sample2.srt文件不存在")
        
        # 解析SRT文件
        parser = SRTParser()
        entries = parser.parse_file(str(self.sample_srt))
        
        # 验证解析结果
        self.assertGreater(len(entries), 0, "未能解析任何字幕条目")
        
        # 验证前几条字幕
        self.assertEqual(entries[0].text, "过去几周，我已经")
        self.assertEqual(entries[1].text, "从Cursor的Agent切换到了Cloud Code")
        self.assertEqual(entries[2].text, "而且我完全不打算回头。")
        
        # 验证时间格式
        self.assertEqual(entries[0].start_time, 0.0)
        self.assertEqual(entries[0].end_time, 1520)
        
    def test_duration_analysis_on_sample(self):
        """测试对样本字幕进行时长分析"""
        from ..parsers.srt_parser import SRTParser
        
        parser = SRTParser()
        entries = parser.parse_file(str(self.sample_srt))
        
        optimizer = LLMContextOptimizer()
        
        # 测试最小时间计算
        min_duration, lang_type = optimizer.calculate_minimum_duration(entries[0].text)
        self.assertEqual(lang_type, 'chinese')
        self.assertGreater(min_duration, 0)
        
    def test_save_optimized_srt_with_sample(self):
        """测试使用sample2.srt数据保存优化文件"""
        from ..parsers.srt_parser import SRTParser
        
        # 加载样本字幕
        parser = SRTParser()
        entries = parser.parse_file(str(self.sample_srt))
        
        # 使用LLM优化器
        optimizer = LLMContextOptimizer()
        optimized_entries, _ = optimizer.optimize_subtitles(entries)
        
        with tempfile.TemporaryDirectory():
            # 使用sample2.srt作为原始文件
            original_path = str(self.sample_srt)
            
            # 保存优化后的文件
            optimized_path = optimizer.save_optimized_srt(optimized_entries, original_path)
            
            # 验证文件存在
            self.assertTrue(os.path.exists(optimized_path))
            self.assertTrue(optimized_path.endswith("_llm_optimized.srt"))
            
            # 验证内容包含原始字幕
            with open(optimized_path, 'r', encoding='utf-8') as f:
                content = f.read()
                self.assertIn("过去几周，我已经", content)
                self.assertIn("从Cursor的Agent切换到了Cloud Code", content)

class TestTimeBorrowOptimizer(unittest.TestCase):
    """时间借用优化器单元测试"""
    
    def setUp(self):
        """测试初始化"""
        self.borrower = TimeBorrowOptimizer()
    
    def test_calculate_needed_extension(self):
        """测试需要延长时间的计算"""
        # 时间充足的字幕
        text = "正常字幕文本"
        current_duration = 2000
        needed = self.borrower.calculate_needed_extension(text, current_duration)
        self.assertEqual(needed, 0)
        
        # 时间不足的字幕
        text = "这是一个很长的字幕文本需要更多时间"
        current_duration = 1000
        needed = self.borrower.calculate_needed_extension(text, current_duration)
        self.assertGreater(needed, 0)
    
    def test_can_borrow_time(self):
        """测试时间借用判断"""
        # 空隙充足
        prev_gap = 1000
        next_gap = 1000
        can_borrow, front, back = self.borrower.can_borrow_time(prev_gap, next_gap)
        self.assertTrue(can_borrow)
        self.assertGreater(front + back, 0)
        
        # 空隙不足
        prev_gap = 100
        next_gap = 100
        can_borrow, front, back = self.borrower.can_borrow_time(prev_gap, next_gap)
        self.assertFalse(can_borrow)
        self.assertEqual(front + back, 0)
    
    def test_time_borrow_optimization(self):
        """测试时间借用优化"""
        entries = [
            SRTEntry(1, 0.0, 1.0, "短字幕"),  # 需要延长时间
            SRTEntry(2, 2.0, 4.0, "正常字幕"),  # 提供前方空隙
            SRTEntry(3, 5.0, 7.0, "正常字幕"),  # 提供后方空隙
        ]
        
        optimized, decisions = self.borrower.optimize_with_time_borrowing(entries)
        
        # 验证结果
        self.assertEqual(len(optimized), 3)
        self.assertEqual(len(decisions), 3)
        
        # 第一条应该被优化（时间借用或LLM标记）
        first_decision = decisions[0]
        self.assertIn(first_decision['action'], ['TIME_BORROW', 'NEED_LLM', 'NO_CHANGE'])
    
    def test_boundary_conditions(self):
        """测试边界条件处理"""
        # 单条字幕
        entries = [SRTEntry(1, 0.0, 1.0, "单条字幕")]
        optimized, decisions = self.borrower.optimize_with_time_borrowing(entries)
        self.assertEqual(len(optimized), 1)
        self.assertEqual(len(decisions), 1)
        
        # 第一条字幕（无前字幕）
        entries = [
            SRTEntry(1, 0.0, 0.5, "首条字幕"),
            SRTEntry(2, 2.0, 3.0, "第二条"),
        ]
        optimized, decisions = self.borrower.optimize_with_time_borrowing(entries)
        self.assertEqual(len(optimized), 2)
        
        # 最后一条字幕（无后字幕）
        entries = [
            SRTEntry(1, 0.0, 1.0, "第一条"),
            SRTEntry(2, 2.0, 2.5, "末条字幕"),
        ]
        optimized, decisions = self.borrower.optimize_with_time_borrowing(entries)
        self.assertEqual(len(optimized), 2)


if __name__ == '__main__':
    unittest.main()
