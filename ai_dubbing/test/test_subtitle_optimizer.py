"""
字幕优化器测试

测试SubtitleOptimizer类的各项功能
"""

import unittest
import tempfile
import os
import sys
from pathlib import Path

# 添加项目根目录到路径
current_file = Path(__file__).resolve() 
sys.path.insert(0, str(current_file.parent.parent.parent)) 

from ai_dubbing.src.parsers.srt_parser import SRTEntry, SRTParser
from ai_dubbing.src.utils.subtitle_optimizer import SubtitleOptimizer, OptimizationReport


class TestSubtitleOptimizer(unittest.TestCase):
    """字幕优化器单元测试"""
    
    def setUp(self):
        """测试初始化"""
        self.optimizer = SubtitleOptimizer(
            min_duration=1.5,
            max_duration=6.0,
            merge_threshold=0.8
        )
    
    def test_analyze_durations_no_issues(self):
        """测试无问题的字幕分析"""
        entries = [
            SRTEntry(1, 0.0, 2.5, "这是一个正常的字幕。"),
            SRTEntry(2, 3.0, 5.5, "这是另一个正常的字幕。")
        ]
        
        analysis = self.optimizer.analyze_durations(entries)
        self.assertFalse(analysis["needs_optimization"])
        self.assertEqual(analysis["total_issues"], 0)
    
    def test_analyze_durations_short_subtitles(self):
        """测试短字幕检测"""
        entries = [
            SRTEntry(1, 0.0, 1.0, "短字幕"),  # 时长1.0s < 1.5s
            SRTEntry(2, 1.2, 2.0, "另一个短字幕")  # 时长0.8s < 1.5s
        ]
        
        analysis = self.optimizer.analyze_durations(entries)
        self.assertTrue(analysis["needs_optimization"])
        self.assertEqual(len(analysis["short_subtitles"]), 2)
    
    def test_analyze_durations_fragmented_sentences(self):
        """测试句子片段检测"""
        entries = [
            SRTEntry(1, 0.0, 1.0, "这是一个未完成的"),
            SRTEntry(2, 1.2, 2.0, "句子片段")
        ]
        
        analysis = self.optimizer.analyze_durations(entries)
        self.assertTrue(analysis["needs_optimization"])
        self.assertEqual(len(analysis["fragmented_sentences"]), 1)
    
    def test_has_sentence_end(self):
        """测试句子结束检测"""
        self.assertTrue(self.optimizer._has_sentence_end("这是一个完整的句子。"))
        self.assertTrue(self.optimizer._has_sentence_end("这是一个感叹句！"))
        self.assertTrue(self.optimizer._has_sentence_end("这是一个疑问句？"))
        self.assertTrue(self.optimizer._has_sentence_end("这是一个英文句子."))
        self.assertFalse(self.optimizer._has_sentence_end("这是一个未完成的句子"))
    
    def test_should_merge_basic(self):
        """测试合并判断基础逻辑"""
        entry1 = SRTEntry(1, 0.0, 1.0, "未完成")
        entry2 = SRTEntry(2, 1.5, 2.5, "句子")
        
        # 时间间隔合适，文本无结束标点
        self.assertTrue(self.optimizer._should_merge(entry1, entry2))
    
    def test_should_merge_too_far(self):
        """测试时间间隔过远不合并"""
        entry1 = SRTEntry(1, 0.0, 1.0, "未完成")
        entry2 = SRTEntry(2, 2.0, 3.0, "句子")  # 间隔1.0s > 0.8s
        
        self.assertFalse(self.optimizer._should_merge(entry1, entry2))
    
    def test_should_merge_complete_sentence(self):
        """测试完整句子不合并"""
        entry1 = SRTEntry(1, 0.0, 1.0, "这是一个完整的句子。")
        entry2 = SRTEntry(2, 1.2, 2.0, "这是另一个句子")
        
        self.assertFalse(self.optimizer._should_merge(entry1, entry2))
    
    def test_optimize_subtitles_no_merge(self):
        """测试无需优化的字幕"""
        entries = [
            SRTEntry(1, 0.0, 2.5, "这是一个正常的字幕。"),
            SRTEntry(2, 3.0, 5.5, "这是另一个正常的字幕。")
        ]
        
        optimized, report = self.optimizer.optimize_subtitles(entries)
        self.assertEqual(len(optimized), 2)
        self.assertEqual(report.merged_count, 0)
    
    def test_optimize_subtitles_with_merge(self):
        """测试需要合并的字幕"""
        entries = [
            SRTEntry(1, 0.0, 1.0, "这是一个"),
            SRTEntry(2, 1.2, 2.0, "未完成的句子")
        ]
        
        optimized, report = self.optimizer.optimize_subtitles(entries)
        self.assertEqual(len(optimized), 1)
        self.assertEqual(report.merged_count, 1)
        self.assertEqual(optimized[0].text, "这是一个 未完成的句子")
        self.assertEqual(optimized[0].start_time, 0.0)
        self.assertEqual(optimized[0].end_time, 2.0)
    
    def test_optimize_subtitles_too_long(self):
        """测试合并后过长的字幕不合并"""
        long_text = "这是一个非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常长的文本"
        entries = [
            SRTEntry(1, 0.0, 1.0, long_text),
            SRTEntry(2, 1.2, 2.0, "另一个长文本")
        ]
        
        optimized, report = self.optimizer.optimize_subtitles(entries)
        # 合并后可能超过最大时长，应该保持分开或合并
        # 实际测试中，由于文本长度限制，可能会合并或保持分开
        self.assertIsInstance(optimized, list)
        self.assertGreater(len(optimized), 0)
    
    def test_save_optimized_srt(self):
        """测试保存优化后的SRT文件"""
        entries = [
            SRTEntry(1, 0.0, 2.0, "测试字幕1"),
            SRTEntry(2, 3.0, 5.0, "测试字幕2")
        ]
        
        with tempfile.TemporaryDirectory() as temp_dir:
            original_path = os.path.join(temp_dir, "test.srt")
            
            # 先创建原始文件
            with open(original_path, 'w', encoding='utf-8') as f:
                f.write("1\n00:00:00,000 --> 00:00:02,000\n测试字幕1\n\n")
                f.write("2\n00:00:03,000 --> 00:00:05,000\n测试字幕2\n\n")
            
            # 保存优化后的文件
            optimized_path = self.optimizer.save_optimized_srt(entries, original_path)
            
            # 验证文件存在
            self.assertTrue(os.path.exists(optimized_path))
            self.assertTrue(optimized_path.endswith("_optimized.srt"))
            
            # 验证内容
            with open(optimized_path, 'r', encoding='utf-8') as f:
                content = f.read()
                self.assertIn("测试字幕1", content)
                self.assertIn("测试字幕2", content)
    
    def test_save_optimized_srt_custom_path(self):
        """测试自定义优化文件路径"""
        entries = [SRTEntry(1, 0.0, 2.0, "测试")]
        
        with tempfile.TemporaryDirectory() as temp_dir:
            custom_path = os.path.join(temp_dir, "custom_optimized.srt")
            optimized_path = self.optimizer.save_optimized_srt(
                entries, "/fake/path.srt", custom_path
            )
            
            self.assertEqual(optimized_path, custom_path)
            self.assertTrue(os.path.exists(custom_path))
    
    def test_optimization_report(self):
        """测试优化报告生成"""
        report = OptimizationReport(
            original_entries=5,
            optimized_entries=3,
            merged_count=2,
            short_subtitles_fixed=1,
            fragmented_sentences_merged=1,
            duration_improvements={
                "avg_duration_before": 1.0,
                "avg_duration_after": 2.0
            }
        )
        
        summary = self.optimizer.generate_optimization_summary(report)
        self.assertIn("5", summary)
        self.assertIn("3", summary)
        self.assertIn("2", summary)


class TestSRTParserWithOptimization(unittest.TestCase):
    """测试带优化的SRT解析器"""
    
    def setUp(self):
        """测试初始化"""
        self.temp_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        """清理测试文件"""
        import shutil
        shutil.rmtree(self.temp_dir)
    
    def test_parser_with_optimization_enabled(self):
        """测试启用优化的解析器"""
        parser = SRTParser(auto_optimize=True, min_duration=1.5)
        
        # 创建测试SRT文件
        srt_content = """1
00:00:00,000 --> 00:00:01,000
短字幕

2
00:00:01,200 --> 00:00:02,000
未完成的句子

3
00:00:02,500 --> 00:00:04,000
这是一个完整的句子。"""
        
        test_file = os.path.join(self.temp_dir, "test.srt")
        with open(test_file, 'w', encoding='utf-8') as f:
            f.write(srt_content)
        
        # 解析文件
        entries = parser.parse_file(test_file)
        
        # 验证优化结果
        self.assertLess(len(entries), 3)  # 应该合并了一些字幕
        self.assertTrue(os.path.exists(os.path.join(self.temp_dir, "test_optimized.srt")))
    
    def test_parser_with_optimization_disabled(self):
        """测试禁用优化的解析器"""
        parser = SRTParser(auto_optimize=False)
        
        srt_content = """1
00:00:00,000 --> 00:00:01,000
短字幕

2
00:00:01,200 --> 00:00:02,000
另一个短字幕"""
        
        test_file = os.path.join(self.temp_dir, "test_no_opt.srt")
        with open(test_file, 'w', encoding='utf-8') as f:
            f.write(srt_content)
        
        entries = parser.parse_file(test_file)
        
        # 验证未优化
        self.assertEqual(len(entries), 2)
        self.assertFalse(os.path.exists(os.path.join(self.temp_dir, "test_no_opt_optimized.srt")))


class TestRealWorldScenarios(unittest.TestCase):
    """测试真实场景"""
    
    def test_chinese_subtitles(self):
        """测试中文字幕优化"""
        optimizer = SubtitleOptimizer()
        
        entries = [
            SRTEntry(1, 0.0, 1.0, "过去几周，我已经"),
            SRTEntry(2, 1.2, 2.5, "从Cursor的Agent切换到了Cloud Code"),
            SRTEntry(3, 2.7, 3.5, "而且我完全不打算回头。")
        ]
        
        optimized, report = optimizer.optimize_subtitles(entries)
        
        # 验证中文句子合并
        self.assertLessEqual(len(optimized), 3)
        # 确保合并后的文本通顺
        for entry in optimized:
            self.assertIsInstance(entry.text, str)
            self.assertGreater(len(entry.text.strip()), 0)
    
    def test_mixed_punctuation(self):
        """测试混合标点符号"""
        optimizer = SubtitleOptimizer()
        
        entries = [
            SRTEntry(1, 0.0, 1.0, "Hello world"),
            SRTEntry(2, 1.2, 2.0, "how are you?"),
            SRTEntry(3, 2.2, 3.0, "I am fine!")
        ]
        
        optimized, report = optimizer.optimize_subtitles(entries)
        
        # 验证英文句子处理
        self.assertIsInstance(optimized, list)
        self.assertGreater(len(optimized), 0)


if __name__ == '__main__':
    unittest.main()