import unittest
import sys
import tempfile
import os
from pathlib import Path

# Add project root to path
current_file = Path(__file__).resolve()
sys.path.insert(0, str(current_file.parent.parent.parent))

from ai_dubbing.src.parsers.txt_parser import TXTParser
from ai_dubbing.src.optimizer.subtitle_optimizer import SRTEntry


class TestTXTParser(unittest.TestCase):
    """Tests for TXTParser"""

    def setUp(self):
        """Set up the test case"""
        self.parser_en = TXTParser(language="en")
        self.parser_zh = TXTParser(language="zh")

    def test_parse_basic_english_text(self):
        """Test parsing basic English text"""
        test_content = "Hello world. This is a test. How are you?"
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            f.write(test_content)
            temp_file = f.name
        
        try:
            entries = self.parser_en.parse_file(temp_file)
            
            # Should have 3 sentences
            self.assertEqual(len(entries), 3)
            
            # Check first entry
            self.assertIsInstance(entries[0], SRTEntry)
            self.assertEqual(entries[0].index, 1)
            self.assertEqual(entries[0].text, "Hello world.")
            self.assertEqual(entries[0].start_time, 0.0)
            self.assertEqual(entries[0].end_time, 0.0)
            
            # Check second entry
            self.assertEqual(entries[1].index, 2)
            self.assertEqual(entries[1].text, "This is a test.")
            
            # Check third entry
            self.assertEqual(entries[2].index, 3)
            self.assertEqual(entries[2].text, "How are you?")
            
        finally:
            os.unlink(temp_file)

    def test_parse_chinese_text(self):
        """Test parsing Chinese text"""
        test_content = "你好世界。这是一个测试。你好吗？"
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            f.write(test_content)
            temp_file = f.name
        
        try:
            entries = self.parser_zh.parse_file(temp_file)
            
            # Should have 3 sentences
            self.assertEqual(len(entries), 3)
            
            # Check entries
            self.assertEqual(entries[0].text, "你好世界。")
            self.assertEqual(entries[1].text, "这是一个测试。")
            self.assertEqual(entries[2].text, "你好吗？")
            
        finally:
            os.unlink(temp_file)

    def test_parse_empty_file(self):
        """Test parsing empty file"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            temp_file = f.name
        
        try:
            entries = self.parser_en.parse_file(temp_file)
            self.assertEqual(len(entries), 0)
            
        finally:
            os.unlink(temp_file)

    def test_parse_file_with_newlines(self):
        """Test parsing file with newlines and whitespace"""
        test_content = "First sentence.\n\nSecond sentence.   \n\n\nThird sentence."
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            f.write(test_content)
            temp_file = f.name
        
        try:
            entries = self.parser_en.parse_file(temp_file)
            
            # Should have 3 sentences
            self.assertEqual(len(entries), 3)
            
            # Check that newlines are replaced with spaces and whitespace is trimmed
            self.assertEqual(entries[0].text, "First sentence.")
            self.assertEqual(entries[1].text, "Second sentence.")
            self.assertEqual(entries[2].text, "Third sentence.")
            
        finally:
            os.unlink(temp_file)

    def test_parse_file_with_only_whitespace(self):
        """Test parsing file with only whitespace"""
        test_content = "   \n\n   \t\t   \n   "
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            f.write(test_content)
            temp_file = f.name
        
        try:
            entries = self.parser_en.parse_file(temp_file)
            self.assertEqual(len(entries), 0)
            
        finally:
            os.unlink(temp_file)

    def test_parse_file_with_mixed_languages(self):
        """Test parsing file with mixed languages"""
        test_content = "Hello world. 你好世界。This is English. 这是中文。"
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            f.write(test_content)
            temp_file = f.name
        
        try:
            # Test with English parser
            entries_en = self.parser_en.parse_file(temp_file)
            self.assertGreater(len(entries_en), 0)
            
            # Test with Chinese parser
            entries_zh = self.parser_zh.parse_file(temp_file)
            self.assertGreater(len(entries_zh), 0)
            
            # Results might be different due to different sentence segmentation
            # Both should produce valid entries
            for entry in entries_en + entries_zh:
                self.assertIsInstance(entry, SRTEntry)
                self.assertGreater(len(entry.text.strip()), 0)
                self.assertEqual(entry.start_time, 0.0)
                self.assertEqual(entry.end_time, 0.0)
            
        finally:
            os.unlink(temp_file)

    def test_parse_file_with_long_text(self):
        """Test parsing file with long text"""
        # Create a long text with multiple paragraphs
        sentences = []
        for i in range(50):
            sentences.append(f"This is sentence number {i+1}. It contains some text to make it longer.")
        
        test_content = " ".join(sentences)
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            f.write(test_content)
            temp_file = f.name
        
        try:
            entries = self.parser_en.parse_file(temp_file)
            
            # Should have multiple entries
            self.assertGreater(len(entries), 0)
            
            # All entries should be valid
            for i, entry in enumerate(entries):
                self.assertIsInstance(entry, SRTEntry)
                self.assertEqual(entry.index, i + 1)
                self.assertGreater(len(entry.text.strip()), 0)
                self.assertEqual(entry.start_time, 0.0)
                self.assertEqual(entry.end_time, 0.0)
            
        finally:
            os.unlink(temp_file)

    def test_parse_nonexistent_file(self):
        """Test parsing nonexistent file"""
        with self.assertRaises(FileNotFoundError):
            self.parser_en.parse_file("nonexistent_file.txt")

    def test_parse_file_with_unicode_characters(self):
        """Test parsing file with Unicode characters"""
        test_content = "Hello 🌍 world! This is a test with emojis 🎉 and special chars: ñáéíóú."
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            f.write(test_content)
            temp_file = f.name
        
        try:
            entries = self.parser_en.parse_file(temp_file)
            
            # Should have 2 sentences
            self.assertEqual(len(entries), 2)
            
            # Check that Unicode characters are preserved
            self.assertEqual(entries[0].text, "Hello 🌍 world!")
            self.assertEqual(entries[1].text, "This is a test with emojis 🎉 and special chars: ñáéíóú.")
            
        finally:
            os.unlink(temp_file)

    def test_srt_entry_properties(self):
        """Test that SRTEntry properties work correctly"""
        test_content = "First sentence. Second sentence."
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            f.write(test_content)
            temp_file = f.name
        
        try:
            entries = self.parser_en.parse_file(temp_file)
            
            # Test duration property (should be 0 since start_time and end_time are both 0)
            for entry in entries:
                self.assertEqual(entry.duration, 0)
            
        finally:
            os.unlink(temp_file)

    def test_user_example_text(self):
        test_content = (
            "梅长苏的经典台词有很多，其中一些包括："
            "\"林殊虽死，属于林殊的责任不能死\"强调了责任与担当；"
            "\"那又怎样！我毕竟是林殊，是赤焰军的少帅林殊！\"表达了他身份的回归与不屈；"
            "\"我的存在，以前没有为她带来过幸福，起码以后也不要成为她的不幸\"展现了他的深情与守护；"
            "以及\"不是还有我吗，那些阴暗沾满鲜血的事，就让我来做\"突出他甘愿背负一切的决心。"
        )
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            f.write(test_content)
            temp_file = f.name
        
        try:
            entries = self.parser_zh.parse_file(temp_file)
            self.assertEqual(len(entries), 3)
            # Test duration property (should be 0 since start_time and end_time are both 0)
            for entry in entries:
                self.assertEqual(entry.duration, 0)
            
        finally:
            os.unlink(temp_file)


if __name__ == '__main__':
    unittest.main()
