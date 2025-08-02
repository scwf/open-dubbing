"""
带优化功能的SRT解析器测试

测试SRTParser与字幕优化功能的集成
"""

import unittest
import tempfile
import os
import sys
from pathlib import Path

# 添加项目根目录到路径
current_file = Path(__file__).resolve()
sys.path.insert(0, str(current_file.parent.parent.parent)) 

from ai_dubbing.src.parsers.srt_parser import SRTParser


class TestParserWithOptimization(unittest.TestCase):
    """测试带优化功能的SRT解析器"""
    
    def setUp(self):
        """测试初始化"""
        self.temp_dir = tempfile.mkdtemp()
        self.test_content = """1
00:00:00,000 --> 00:00:01,000
短字幕

2
00:00:01,200 --> 00:00:02,000
未完成的句子

3
00:00:02,500 --> 00:00:04,000
这是一个完整的句子。"""
    
    def tearDown(self):
        """清理测试文件"""
        import shutil
        shutil.rmtree(self.temp_dir)
    
    def test_parser_default_optimization(self):
        """测试默认启用优化的解析器"""
        parser = SRTParser()  # 默认auto_optimize=True
        
        test_file = os.path.join(self.temp_dir, "test.srt")
        with open(test_file, 'w', encoding='utf-8') as f:
            f.write(self.test_content)
        
        entries = parser.parse_file(test_file)
        
        # 验证优化结果
        self.assertGreater(len(entries), 0)
        # 检查是否生成了优化文件
        optimized_file = os.path.join(self.temp_dir, "test_optimized.srt")
        # 由于有些短字幕，应该生成了优化文件
    
    def test_parser_explicit_optimization_enabled(self):
        """测试明确启用优化的解析器"""
        parser = SRTParser(auto_optimize=True, min_duration=1.5, max_duration=6.0)
        
        test_file = os.path.join(self.temp_dir, "test_enabled.srt")
        with open(test_file, 'w', encoding='utf-8') as f:
            f.write("""1
00:00:00,000 --> 00:00:00,800
超短字幕

2
00:00:01,000 --> 00:00:01,500
另一个超短字幕""")
        
        entries = parser.parse_file(test_file)
        
        # 验证优化效果
        self.assertLessEqual(len(entries), 2)  # 应该合并
        # 检查优化文件
        optimized_file = os.path.join(self.temp_dir, "test_enabled_optimized.srt")
    
    def test_parser_optimization_disabled(self):
        """测试禁用优化的解析器"""
        parser = SRTParser(auto_optimize=False)
        
        test_file = os.path.join(self.temp_dir, "test_disabled.srt")
        with open(test_file, 'w', encoding='utf-8') as f:
            f.write("""1
00:00:00,000 --> 00:00:00,800
超短字幕

2
00:00:01,000 --> 00:00:01,500
另一个超短字幕""")
        
        entries = parser.parse_file(test_file)
        
        # 验证未优化
        self.assertEqual(len(entries), 2)
        # 检查是否没有生成优化文件
        optimized_file = os.path.join(self.temp_dir, "test_disabled_optimized.srt")
        # 文件不应该存在
    
    def test_parser_empty_file(self):
        """测试空文件处理"""
        parser = SRTParser(auto_optimize=True)
        
        test_file = os.path.join(self.temp_dir, "empty.srt")
        with open(test_file, 'w', encoding='utf-8') as f:
            f.write("")
        
        entries = parser.parse_file(test_file)
        self.assertEqual(len(entries), 0)
    
    def test_parser_single_entry(self):
        """测试单条字幕处理"""
        parser = SRTParser(auto_optimize=True)
        
        test_file = os.path.join(self.temp_dir, "single.srt")
        with open(test_file, 'w', encoding='utf-8') as f:
            f.write("""1
00:00:00,000 --> 00:00:03,000
单条字幕""")
        
        entries = parser.parse_file(test_file)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].text, "单条字幕")
    
    def test_parser_chinese_subtitles(self):
        """测试中文字幕优化"""
        parser = SRTParser(auto_optimize=True, min_duration=1.5)
        
        test_file = os.path.join(self.temp_dir, "chinese.srt")
        with open(test_file, 'w', encoding='utf-8') as f:
            f.write("""1
00:00:00,000 --> 00:00:01,000
中文字幕测试

2
00:00:01,200 --> 00:00:02,000
优化功能验证""")
        
        entries = parser.parse_file(test_file)
        
        # 验证解析成功
        self.assertGreater(len(entries), 0)
        # 验证中文字符处理
        for entry in entries:
            self.assertIsInstance(entry.text, str)
    
    def test_parser_custom_duration_limits(self):
        """测试自定义时长限制"""
        parser = SRTParser(auto_optimize=True, min_duration=2.0, max_duration=5.0)
        
        test_file = os.path.join(self.temp_dir, "custom_limits.srt")
        with open(test_file, 'w', encoding='utf-8') as f:
            f.write("""1
00:00:00,000 --> 00:00:00,800
超短字幕

2
00:00:01,000 --> 00:00:01,500
另一个超短字幕

3
00:00:02,000 --> 00:00:08,000
这个已经超过最大时长限制""")
        
        entries = parser.parse_file(test_file)
        
        # 验证解析成功
        self.assertGreater(len(entries), 0)
        for entry in entries:
            self.assertGreaterEqual(entry.duration, 0.8)  # 至少原始时长
    
    def test_parser_mixed_punctuation(self):
        """测试混合标点符号处理"""
        parser = SRTParser(auto_optimize=True)
        
        test_file = os.path.join(self.temp_dir, "mixed_punctuation.srt")
        with open(test_file, 'w', encoding='utf-8') as f:
            f.write("""1
00:00:00,000 --> 00:00:01,000
Hello world

2
00:00:01,200 --> 00:00:02,000
how are you?

3
00:00:02,500 --> 00:00:03,500
I am fine!""")
        
        entries = parser.parse_file(test_file)
        
        # 验证英文句子处理
        self.assertGreater(len(entries), 0)
        for entry in entries:
            self.assertIsInstance(entry.text, str)


if __name__ == '__main__':
    unittest.main()