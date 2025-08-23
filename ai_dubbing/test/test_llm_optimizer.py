"""
LLM字幕优化器测试

测试LLMContextOptimizer类的各项功能
"""

import unittest
import tempfile
import os
import sys
from pathlib import Path
from typing import List, Tuple, Dict, Any
from dataclasses import dataclass

# 添加项目根目录到路径
current_file = Path(__file__).resolve()
sys.path.insert(0, str(current_file.parent.parent.parent))

from ai_dubbing.src.parsers.srt_parser import SRTEntry
from ai_dubbing.src.optimizer.subtitle_optimizer import LLMContextOptimizer, TimeBorrowOptimizer


@dataclass
class TestConstants:
    """测试常量配置类"""
    # 时间常量 (与dubbing.conf.example保持一致)
    CHINESE_CHAR_MIN_TIME: int = 150  # 中文字符最小时间 (ms)
    ENGLISH_WORD_MIN_TIME: int = 250  # 英文单词最小时间 (ms)
    
    # 测试字符串
    CHINESE_TEST_TEXT: str = "这是一个测试中文字符密度的字幕"
    ENGLISH_TEST_TEXT: str = "This is a test subtitle for density calculation"
    MIXED_TEST_TEXT: str = "这是一个test混合的字幕subtitle"
    
    # 预期的字符/单词数量
    EXPECTED_CHINESE_CHARS: int = 16  # CHINESE_TEST_TEXT中的字符数
    EXPECTED_ENGLISH_WORDS: int = 8   # ENGLISH_TEST_TEXT中的单词数
    EXPECTED_MIXED_CN_CHARS: int = 9  # MIXED_TEST_TEXT中的中文字符数
    EXPECTED_MIXED_EN_WORDS: int = 2  # MIXED_TEST_TEXT中的英文单词数
    
    # 边界测试值
    MIN_GAP_THRESHOLD: int = 200  # 最小保护空隙 (ms)
    BORROW_RATIO: float = 1.0     # 借用比例
    EXTRA_BUFFER: int = 200       # 额外缓冲时间 (ms)


class TestDataManager:
    """测试数据管理器"""
    
    def __init__(self):
        self.test_data_dir = Path(__file__).parent / "test_data"
        self.sample_files = {
            "sample1": self.test_data_dir / "sample1.srt",
            "sample2": self.test_data_dir / "sample2.srt", 
            "sample3": self.test_data_dir / "sample3.srt",
            "sample2_optimized": self.test_data_dir / "sample2_llm_optimized.srt"
        }
    
    def get_sample_path(self, sample_name: str) -> Path:
        """获取样本文件路径"""
        if sample_name not in self.sample_files:
            raise ValueError(f"Unknown sample file: {sample_name}")
        return self.sample_files[sample_name]
    
    def verify_sample_exists(self, sample_name: str) -> bool:
        """验证样本文件是否存在"""
        return self.get_sample_path(sample_name).exists()
    
    def load_sample_entries(self, sample_name: str) -> List[SRTEntry]:
        """加载样本文件的字幕条目"""
        from ai_dubbing.src.parsers.srt_parser import SRTParser
        
        sample_path = self.get_sample_path(sample_name)
        if not sample_path.exists():
            raise FileNotFoundError(f"Sample file not found: {sample_path}")
        
        parser = SRTParser()
        return parser.parse_file(str(sample_path))


class BaseOptimizerTest(unittest.TestCase):
    """优化器测试基类"""
    
    def setUp(self):
        """测试初始化"""
        self.constants = TestConstants()
        self.data_manager = TestDataManager()
        self.temp_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        """清理测试文件"""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def create_test_entries(self, texts_and_times: List[Tuple[str, float, float]]) -> List[SRTEntry]:
        """创建测试用的字幕条目"""
        return [
            SRTEntry(i + 1, start, end, text)
            for i, (text, start, end) in enumerate(texts_and_times)
        ]
    
    def assert_duration_calculation(
        self, 
        text: str, 
        expected_duration: int, 
        expected_lang_type: str,
        optimizer: LLMContextOptimizer
    ):
        """断言时长计算结果"""
        min_duration, lang_type = optimizer.calculate_minimum_duration(text)
        self.assertAlmostEqual(min_duration, expected_duration, places=2)
        self.assertEqual(lang_type, expected_lang_type)


class TestLLMContextOptimizer(BaseOptimizerTest):
    """LLM字幕优化器单元测试"""
    
    def setUp(self):
        """测试初始化"""
        super().setUp()
        self.optimizer = LLMContextOptimizer()  # 无需API密钥，模拟测试
    
    def test_calculate_minimum_duration_chinese(self):
        """测试中文字符最小时间计算"""
        expected_duration = (
            self.constants.EXPECTED_CHINESE_CHARS * 
            self.constants.CHINESE_CHAR_MIN_TIME
        )
        
        self.assert_duration_calculation(
            self.constants.CHINESE_TEST_TEXT,
            expected_duration,
            'chinese',
            self.optimizer
        )

    def test_calculate_minimum_duration_english(self):
        """测试英文单词最小时间计算"""
        expected_duration = (
            self.constants.EXPECTED_ENGLISH_WORDS * 
            self.constants.ENGLISH_WORD_MIN_TIME
        )
        
        self.assert_duration_calculation(
            self.constants.ENGLISH_TEST_TEXT,
            expected_duration,
            'english',
            self.optimizer
        )

    def test_calculate_minimum_duration_mixed(self):
        """测试中英文混合最小时间计算"""
        expected_duration = (
            self.constants.EXPECTED_MIXED_CN_CHARS * self.constants.CHINESE_CHAR_MIN_TIME +
            self.constants.EXPECTED_MIXED_EN_WORDS * self.constants.ENGLISH_WORD_MIN_TIME
        )
        expected_lang_type = (
            f'mixed_cn{self.constants.EXPECTED_MIXED_CN_CHARS}_'
            f'en{self.constants.EXPECTED_MIXED_EN_WORDS}'
        )
        
        self.assert_duration_calculation(
            self.constants.MIXED_TEST_TEXT,
            expected_duration,
            expected_lang_type,
            self.optimizer
        )
    
    def test_calculate_minimum_duration_basic_cases(self):
        """测试基本时间计算案例"""
        test_cases = [
            ("正常字幕", 4 * self.constants.CHINESE_CHAR_MIN_TIME, 'chinese'),
            ("This is test", 3 * self.constants.ENGLISH_WORD_MIN_TIME, 'english'),
        ]
        
        for text, expected_duration, expected_lang_type in test_cases:
            with self.subTest(text=text):
                self.assert_duration_calculation(
                    text, expected_duration, expected_lang_type, self.optimizer
                )
    
    def test_empty_entries_handling(self):
        """测试空条目处理"""
        entries = []
        optimized, report = self.optimizer.optimize_subtitles(entries)
        
        self.assertEqual(len(optimized), 0)
        self.assertEqual(report.original_entries, 0)
        self.assertEqual(report.optimized_entries, 0)
        self.assertEqual(report.simplified_count, 0)
    
    def test_single_entry_processing(self):
        """测试单条字幕处理"""
        entries = [SRTEntry(1, 0.0, 2.0, "单条字幕")]
        optimized, report = self.optimizer.optimize_subtitles(entries)
        
        self.assertEqual(len(optimized), 1)
        self.assertEqual(report.original_entries, 1)
        self.assertEqual(report.optimized_entries, 1)
        self.assertEqual(report.simplified_count, 0)
    
    def test_no_api_key_configuration(self):
        """测试无API密钥的情况"""
        optimizer = LLMContextOptimizer(api_key=None)
        entries = self.create_test_entries([
            ("高密度字幕", 0.0, 0.5),
            ("正常字幕", 1.0, 2.0),
        ])
        
        optimized, report = optimizer.optimize_subtitles(entries)
        
        # 应该跳过优化，保持原始条目
        self.assertEqual(len(optimized), 2)
        self.assertEqual(report.original_entries, 2)
        self.assertEqual(report.optimized_entries, 2)
        self.assertEqual(report.simplified_count, 0)


class TestLLMIntegration(BaseOptimizerTest):
    """LLM集成测试"""
    
    def test_load_sample_data(self):
        """测试加载样本数据"""
        sample_name = "sample2"
        
        # 验证文件存在
        self.assertTrue(
            self.data_manager.verify_sample_exists(sample_name),
            f"{sample_name}.srt文件不存在"
        )
        
        # 加载并验证条目
        entries = self.data_manager.load_sample_entries(sample_name)
        self.assertGreater(len(entries), 0, "未能解析任何字幕条目")
        
        # 验证已知的前几条字幕内容
        expected_texts = [
            "过去几周，我已经",
            "从Cursor的Agent切换到了Cloud Code",
            "而且我完全不打算回头。"
        ]
        
        for i, expected_text in enumerate(expected_texts):
            with self.subTest(index=i):
                self.assertEqual(entries[i].text, expected_text)
        
        # 验证时间格式正确性
        self.assertEqual(entries[0].start_time, 0.0)
        self.assertEqual(entries[0].end_time, 1520)
        
    def test_duration_analysis_on_sample(self):
        """测试对样本字幕进行时长分析"""
        entries = self.data_manager.load_sample_entries("sample2")
        optimizer = LLMContextOptimizer()
        
        # 测试第一条字幕的最小时间计算
        min_duration, lang_type = optimizer.calculate_minimum_duration(entries[0].text)
        self.assertEqual(lang_type, 'chinese')
        self.assertGreater(min_duration, 0)
        
    def test_save_optimized_srt_with_sample(self):
        """测试使用样本数据保存优化文件"""
        entries = self.data_manager.load_sample_entries("sample2")
        optimizer = LLMContextOptimizer()
        optimized_entries, _ = optimizer.optimize_subtitles(entries)
        
        with tempfile.TemporaryDirectory() as temp_dir:
            original_path = str(self.data_manager.get_sample_path("sample2"))
            optimized_path = optimizer.save_optimized_srt(optimized_entries, original_path)
            
            # 验证文件存在并符合命名规范
            self.assertTrue(os.path.exists(optimized_path))
            self.assertTrue(optimized_path.endswith("_llm_optimized.srt"))
            
            # 验证内容包含原始字幕的文本
            with open(optimized_path, 'r', encoding='utf-8') as f:
                content = f.read()
                expected_texts = ["过去几周，我已经", "从Cursor的Agent切换到了Cloud Code"]
                for text in expected_texts:
                    self.assertIn(text, content)


class TestTimeBorrowOptimizer(BaseOptimizerTest):
    """时间借用优化器单元测试"""
    
    def setUp(self):
        """测试初始化"""
        super().setUp()
        self.borrower = TimeBorrowOptimizer(
            min_gap_threshold=self.constants.MIN_GAP_THRESHOLD,
            borrow_ratio=self.constants.BORROW_RATIO,
            extra_buffer=self.constants.EXTRA_BUFFER
        )
    
    def test_calculate_needed_extension(self):
        """测试需要延长时间的计算"""
        test_cases = [
            ("正常字幕文本", 2000, 0),  # 时间充足
            ("这是一个很长的字幕文本需要更多时间", 1000, ">0"),  # 时间不足
        ]
        
        for text, current_duration, expected in test_cases:
            with self.subTest(text=text):
                needed = self.borrower.calculate_needed_extension(text, current_duration)
                if expected == 0:
                    self.assertEqual(needed, 0)
                else:
                    self.assertGreater(needed, 0)
    
    def test_can_borrow_time_decisions(self):
        """测试时间借用判断逻辑"""
        test_scenarios = [
            (1000, 1000, True, ">0"),   # 空隙充足
            (100, 100, False, "=0"),    # 空隙不足
        ]
        
        for prev_gap, next_gap, expected_can_borrow, expected_time in test_scenarios:
            with self.subTest(prev_gap=prev_gap, next_gap=next_gap):
                can_borrow, front, back = self.borrower.can_borrow_time(prev_gap, next_gap)
                self.assertEqual(can_borrow, expected_can_borrow)
                
                if expected_time == ">0":
                    self.assertGreater(front + back, 0)
                else:
                    self.assertEqual(front + back, 0)
    
    def test_time_borrow_optimization_workflow(self):
        """测试时间借用优化流程"""
        entries = self.create_test_entries([
            ("短字幕", 0.0, 1.0),        # 需要延长时间
            ("正常字幕", 2.0, 4.0),      # 提供前方空隙  
            ("正常字幕", 5.0, 7.0),      # 提供后方空隙
        ])
        
        optimized, decisions = self.borrower.optimize_with_time_borrowing(entries)
        
        # 验证输出结构
        self.assertEqual(len(optimized), 3)
        self.assertEqual(len(decisions), 3)
        
        # 验证决策类型
        valid_actions = ['TIME_BORROW', 'NEED_LLM', 'NO_CHANGE']
        for decision in decisions:
            self.assertIn(decision['action'], valid_actions)
    
    def test_boundary_conditions_handling(self):
        """测试边界条件处理"""
        boundary_test_cases = [
            # (描述, 字幕条目数据)
            ("单条字幕", [("单条字幕", 0.0, 1.0)]),
            ("首条字幕无前置", [("首条字幕", 0.0, 0.5), ("第二条", 2.0, 3.0)]),
            ("末条字幕无后置", [("第一条", 0.0, 1.0), ("末条字幕", 2.0, 2.5)]),
        ]
        
        for description, entry_data in boundary_test_cases:
            with self.subTest(description=description):
                entries = self.create_test_entries(entry_data)
                optimized, decisions = self.borrower.optimize_with_time_borrowing(entries)
                
                # 确保输出结构正确
                self.assertEqual(len(optimized), len(entries))
                self.assertEqual(len(decisions), len(entries))
                
                # 确保没有抛出异常，且有有效的决策
                for decision in decisions:
                    self.assertIsInstance(decision, dict)
                    self.assertIn('action', decision)


class TestOptimizerConfiguration(BaseOptimizerTest):
    """优化器配置测试"""
    
    def test_llm_optimizer_custom_config(self):
        """测试LLM优化器自定义配置"""
        custom_config = {
            'chinese_char_min_time': 200,
            'english_word_min_time': 300,
            'max_retries': 5
        }
        
        optimizer = LLMContextOptimizer(**custom_config)
        
        # 验证配置是否正确应用
        min_duration, _ = optimizer.calculate_minimum_duration("测试")
        expected = 2 * 200  # 2个中文字符 * 200ms
        self.assertEqual(min_duration, expected)
    
    def test_time_borrow_optimizer_custom_config(self):
        """测试时间借用优化器自定义配置"""
        custom_config = {
            'min_gap_threshold': 300,
            'borrow_ratio': 0.8,
            'extra_buffer': 100
        }
        
        borrower = TimeBorrowOptimizer(**custom_config)
        
        # 验证配置通过行为反映
        can_borrow, _, _ = borrower.can_borrow_time(200, 200)  # 低于新阈值
        self.assertFalse(can_borrow)
        
        can_borrow, _, _ = borrower.can_borrow_time(400, 400)  # 高于新阈值
        self.assertTrue(can_borrow)


def create_test_suite() -> unittest.TestSuite:
    """创建测试套件"""
    test_suite = unittest.TestSuite()
    
    # 添加所有测试类
    test_classes = [
        TestLLMContextOptimizer,
        TestLLMIntegration,
        TestTimeBorrowOptimizer,
        TestOptimizerConfiguration
    ]
    
    for test_class in test_classes:
        tests = unittest.TestLoader().loadTestsFromTestCase(test_class)
        test_suite.addTests(tests)
    
    return test_suite


if __name__ == '__main__':
    # 可以选择运行特定测试或完整套件
    import argparse
    
    parser = argparse.ArgumentParser(description='运行LLM优化器测试')
    parser.add_argument('--verbose', '-v', action='store_true', help='详细输出')
    parser.add_argument('--class', '-c', dest='test_class', help='运行特定测试类')
    args = parser.parse_args()
    
    if args.test_class:
        # 运行特定测试类
        test_class = globals().get(args.test_class)
        if test_class and issubclass(test_class, unittest.TestCase):
            unittest.main(argv=[''], testRunner=unittest.TextTestRunner(
                verbosity=2 if args.verbose else 1
            ), defaultTest=args.test_class)
        else:
            print(f"错误：找不到测试类 '{args.test_class}'")
    else:
        # 运行完整测试套件
        runner = unittest.TextTestRunner(verbosity=2 if args.verbose else 1)
        runner.run(create_test_suite())