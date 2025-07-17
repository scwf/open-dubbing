
import pysbd
from typing import List

from ai_dubbing.src.parsers.srt_parser import SRTEntry

class TXTParser:
    """
    用于解析纯文本 (.txt) 文件的解析器。

    该解析器将文本文件内容读取，并按句子进行切分，
    将每个句子转换为与 SRTEntry 兼容的格式，以便后续处理。
    """

    def __init__(self, language: str = "en"):
        """
        初始化 TXTParser。

        Args:
            language (str): 用于句子边界检测的语言代码 (例如: "en", "zh")。
        """
        self.language = language
        self.segmenter = pysbd.Segmenter(language=self.language, clean=False)

    def parse_file(self, file_path: str) -> List[SRTEntry]:
        """
        解析指定的 .txt 文件。

        Args:
            file_path (str): .txt 文件的路径。

        Returns:
            List[SRTEntry]: 解析后的条目列表。
        """
        with open(file_path, 'r', encoding='utf-8') as f:
            text = f.read()
        
        sentences = self.segmenter.segment(text)
        
        entries = []
        for i, sentence in enumerate(sentences):
            # 移除句子中可能存在的换行符，并清理首尾空格
            cleaned_sentence = sentence.replace('\n', ' ').strip()
            if cleaned_sentence:
                entry = SRTEntry(
                    index=i + 1,
                    text=cleaned_sentence,
                    # TXT 文件没有时间信息，按用户建议设为0
                    start_time=0.0,
                    end_time=0.0
                )
                entries.append(entry)
        
        return entries 