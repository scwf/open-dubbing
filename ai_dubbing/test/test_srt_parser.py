import unittest
import sys
from pathlib import Path

# Add project root to path
current_file = Path(__file__).resolve()
sys.path.insert(0, str(current_file.parent.parent.parent))

from ai_dubbing.src.parsers.srt_parser import SRTParser

class TestSRTParser(unittest.TestCase):
    """Tests for SRTParser"""

    def setUp(self):
        """Set up the test case"""
        self.parser = SRTParser()

    def test_parse_srt_with_missing_text(self):
        """
        Test parsing of an SRT file where an entry is missing its text.
        The parser should handle this gracefully and not merge entries.
        """
        srt_content = """
1
00:00:01,000 --> 00:00:02,000
First subtitle

2
00:00:03,000 --> 00:00:04,000

3
00:00:05,000 --> 00:00:06,000
Third subtitle
"""

        entries = self.parser.parse_content(srt_content)

        # The second entry is invalid (missing text), so it should be skipped.
        # The parser should not read "3" as the text for the second entry.
        self.assertEqual(len(entries), 2, "Parser should skip entries with missing text")
        self.assertEqual(entries[0].text, "First subtitle")
        self.assertEqual(entries[1].text, "Third subtitle")
        self.assertEqual(entries[1].index, 3)

if __name__ == '__main__':
    unittest.main()
