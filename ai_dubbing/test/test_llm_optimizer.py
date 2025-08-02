"""
LLM字幕优化器测试

测试LLMContextOptimizer类的各项功能
"""

import unittest
import tempfile
import os
import sys
from pathlib import Path

# 添加项目根目录到路径
current_file = Path(__file__).resolve()
sys.path.insert(0, str(current_file.parent.parent.parent))

from ai_dubbing.src.parsers.srt_parser import SRTEntry
from ai_dubbing.src.utils.subtitle_optimizer import LLMContextOptimizer


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
        
        # 中文字符数量 * 0.15秒
        chinese_chars = len(text)  # 每个字符都算
        expected_duration = chinese_chars * 0.15
        
        self.assertAlmostEqual(min_duration, expected_duration, places=2)
        self.assertEqual(lang_type, 'chinese')

    def test_calculate_minimum_duration_english(self):
        """测试英文单词最小时间计算"""
        text = "This is a test subtitle for density calculation"
        min_duration, lang_type = self.optimizer.calculate_minimum_duration(text)
        
        # 英文单词数量 * 0.3秒
        english_words = 8  # 8个英文单词
        expected_duration = english_words * 0.3
        
        self.assertAlmostEqual(min_duration, expected_duration, places=2)
        self.assertEqual(lang_type, 'english')

    def test_calculate_minimum_duration_mixed(self):
        """测试中英文混合最小时间计算"""
        text = "这是一个test混合的字幕subtitle"
        min_duration, lang_type = self.optimizer.calculate_minimum_duration(text)
        
        expected_duration = 9 * 0.15 + 2 * 0.3
        self.assertEqual(lang_type, 'mixed_cn9_en2')
        self.assertAlmostEqual(min_duration, expected_duration, places=2)
    
    def test_identify_high_density_contexts(self):
        """测试高密度字幕识别（基于最小时间阈值）"""
        entries = [
            SRTEntry(1, 0.0, 2.0, "正常字幕"),  # 4中文字符 * 0.15 = 0.6秒，实际2秒，充足
            SRTEntry(2, 2.5, 3.0, "高密度字幕"),  # 5中文字符 * 0.15 = 0.75秒，实际0.5秒，不足
            SRTEntry(3, 3.5, 5.0, "正常字幕"),  # 4中文字符 * 0.15 = 0.6秒，实际1.5秒，充足
        ]
        
        contexts = self.optimizer.identify_high_density_contexts(entries)
        
        # 应该识别到第2条字幕
        self.assertEqual(len(contexts), 1)
        self.assertEqual(contexts[0]['index'], 1)  # 索引1是第2条
        self.assertEqual(contexts[0]['min_required_duration'], 0.75)  # 5字符 * 0.15秒/字符
    
    def test_no_high_density_subtitles(self):
        """测试无高密度字幕的情况"""
        entries = [
            SRTEntry(1, 0.0, 3.0, "正常字幕"),
            SRTEntry(2, 3.5, 6.0, "正常字幕"),
        ]
        
        contexts = self.optimizer.identify_high_density_contexts(entries)
        
        # 不应该识别到任何高密度字幕
        self.assertEqual(len(contexts), 0)
    
    def test_context_boundary_conditions(self):
        """测试边界条件：第一条和最后一条字幕"""
        entries = [
            SRTEntry(1, 0.0, 0.5, "高密度首条"),  # 5字符 * 0.15 = 0.75秒，实际0.5秒，不足
            SRTEntry(2, 1.0, 2.0, "正常字幕"),   # 4字符 * 0.15 = 0.6秒，实际1秒，充足
            SRTEntry(3, 2.5, 3.0, "高密度末条"),  # 5字符 * 0.15 = 0.75秒，实际0.5秒，不足
        ]
        
        contexts = self.optimizer.identify_high_density_contexts(entries)
        
        self.assertEqual(len(contexts), 2)
        
        # 第一条字幕上下文
        self.assertEqual(contexts[0]['index'], 0)
        self.assertIsNone(contexts[0]['prev'])
        self.assertIsNotNone(contexts[0]['next'])
        
        # 最后一条字幕上下文
        self.assertEqual(contexts[1]['index'], 2)
        self.assertIsNotNone(contexts[1]['prev'])
        self.assertIsNone(contexts[1]['next'])
    
    def test_empty_entries(self):
        """测试空条目处理"""
        entries = []
        optimized, report = self.optimizer.optimize_subtitles(entries)
        
        self.assertEqual(len(optimized), 0)
        self.assertEqual(report.original_entries, 0)
        self.assertEqual(report.optimized_entries, 0)
        self.assertEqual(report.merged_count, 0)
    
    def test_single_entry(self):
        """测试单条字幕"""
        entries = [SRTEntry(1, 0.0, 2.0, "单条字幕")]
        optimized, report = self.optimizer.optimize_subtitles(entries)
        
        self.assertEqual(len(optimized), 1)
        self.assertEqual(report.original_entries, 1)
        self.assertEqual(report.optimized_entries, 1)
        self.assertEqual(report.merged_count, 0)
    
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
        self.assertEqual(report.merged_count, 0)


class TestLLMIntegration(unittest.TestCase):
    """LLM集成测试"""
    
    def setUp(self):
        """测试初始化"""
        self.test_data_dir = Path(__file__).parent / "test_data"
        self.sample_srt = self.test_data_dir / "sample2.srt"
        
    def test_load_sample_srt(self):
        """测试从sample2.srt加载字幕数据"""
        from ai_dubbing.src.parsers.srt_parser import SRTParser
        
        # 验证文件存在
        self.assertTrue(self.sample_srt.exists(), "sample2.srt文件不存在")
        
        # 解析SRT文件
        parser = SRTParser(auto_optimize=False)
        entries = parser.parse_file(str(self.sample_srt))
        
        # 验证解析结果
        self.assertGreater(len(entries), 0, "未能解析任何字幕条目")
        
        # 验证前几条字幕
        self.assertEqual(entries[0].text, "过去几周，我已经")
        self.assertEqual(entries[1].text, "从Cursor的Agent切换到了Cloud Code")
        self.assertEqual(entries[2].text, "而且我完全不打算回头。")
        
        # 验证时间格式
        self.assertEqual(entries[0].start_time, 0.0)
        self.assertEqual(entries[0].end_time, 1.52)
        
    def test_duration_analysis_on_sample(self):
        """测试对样本字幕进行时长分析"""
        from ai_dubbing.src.parsers.srt_parser import SRTParser
        
        parser = SRTParser(auto_optimize=False)
        entries = parser.parse_file(str(self.sample_srt))
        
        optimizer = LLMContextOptimizer()
        
        # 测试最小时间计算
        min_duration, lang_type = optimizer.calculate_minimum_duration(entries[0].text)
        self.assertEqual(lang_type, 'chinese')
        self.assertGreater(min_duration, 0)
        
        # 测试时长不足识别
        contexts = optimizer.identify_high_density_contexts(entries)
        
        # 打印分析结果用于调试
        print(f"\n【sample2.srt时长分析】")
        print(f"总字幕数: {len(entries)}")
        for i, entry in enumerate(entries[:5]):  # 只显示前5条
            min_duration, _ = optimizer.calculate_minimum_duration(entry.text)
            is_adequate, _, _ = optimizer.is_duration_adequate(entry.text, entry.duration)
            print(f"字幕{i+1}: '{entry.text}' -> 最小所需: {min_duration:.2f}秒, 实际: {entry.duration:.2f}秒, 充足: {is_adequate}")
        
        print(f"识别到的时长不足字幕: {len(contexts)}")
        
    def test_save_optimized_srt_with_sample(self):
        """测试使用sample2.srt数据保存优化文件"""
        from ai_dubbing.src.parsers.srt_parser import SRTParser
        
        # 加载样本字幕
        parser = SRTParser(auto_optimize=False)
        entries = parser.parse_file(str(self.sample_srt))
        
        # 使用LLM优化器
        optimizer = LLMContextOptimizer()
        optimized_entries, report = optimizer.optimize_subtitles(entries)
        
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


if __name__ == '__main__':
    unittest.main()