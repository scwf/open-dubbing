"""
SRT字幕文件解析器

提供SRT文件的解析功能，支持时间戳转换和文本提取。
"""

import re
from typing import List, NamedTuple, Optional
from pathlib import Path
from ai_dubbing.src.logger import get_logger
from ai_dubbing.src.optimizer.subtitle_optimizer import SRTEntry

class SRTParser:
    """SRT文件解析器"""

    # SRT时间戳格式：HH:MM:SS,mmm
    TIME_PATTERN = re.compile(
        r'(\d{2}):(\d{2}):(\d{2}),(\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2}),(\d{3})'
    )

    def __init__(self):
        self.entries: List[SRTEntry] = []

    @staticmethod
    def time_to_milliseconds(hours: int, minutes: int, seconds: int, milliseconds: int) -> int:
        """
        将时间转换为毫秒数

        Args:
            hours: 小时
            minutes: 分钟
            seconds: 秒
            milliseconds: 毫秒

        Returns:
            总毫秒数（整数）
        """
        return hours * 3600000 + minutes * 60000 + seconds * 1000 + milliseconds

    @staticmethod
    def milliseconds_to_time(total_milliseconds: int) -> str:
        """
        将毫秒数转换为SRT时间格式

        Args:
            total_milliseconds: 总毫秒数

        Returns:
            SRT格式时间字符串 (HH:MM:SS,mmm)
        """
        hours = total_milliseconds // 3600000
        minutes = (total_milliseconds % 3600000) // 60000
        seconds = (total_milliseconds % 60000) // 1000
        milliseconds = total_milliseconds % 1000
        return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"


    def parse_content(self, content: str) -> List[SRTEntry]:
        """
        解析SRT内容字符串

        Args:
            content: SRT文件内容

        Returns:
            SRT条目列表

        Raises:
            ValueError: 内容格式错误
        """
        logger = get_logger()
        logger.step("解析SRT内容结构")

        entries = []
        # 按空行分割SRT条目
        blocks = content.strip().split('\n\n')
        logger.debug(f"发现 {len(blocks)} 个字幕块")

        for block in blocks:
            if not block.strip():
                continue

            lines = block.strip().split('\n')

            if not lines:
                continue

            # 寻找时间戳行以确定结构
            time_line_index = -1
            for i, line in enumerate(lines):
                if "-->" in line:
                    time_line_index = i
                    break

            # 如果没有时间戳，则不是有效的SRT条目
            if time_line_index == -1:
                continue

            # 序号应该在时间戳行的正上方
            if time_line_index == 0:
                continue # 缺少序号

            index_line = lines[time_line_index - 1]

            # 文本内容在时间戳之后
            text_lines = lines[time_line_index + 1:]

            if not text_lines or not "".join(text_lines).strip():
                continue # 缺少文本内容

            try:
                index = int(index_line)
                time_line = lines[time_line_index]
                time_match = self.TIME_PATTERN.match(time_line)

                if not time_match:
                    continue

                start_time = self.time_to_milliseconds(
                    int(time_match.group(1)), int(time_match.group(2)),
                    int(time_match.group(3)), int(time_match.group(4))
                )
                end_time = self.time_to_milliseconds(
                    int(time_match.group(5)), int(time_match.group(6)),
                    int(time_match.group(7)), int(time_match.group(8))
                )

                text = '\n'.join(text_lines).strip()

                entry = SRTEntry(
                    index=index,
                    start_time=start_time,
                    end_time=end_time,
                    text=text
                )
                entries.append(entry)

            except (ValueError, IndexError) as e:
                logger.warning(f"解析SRT条目失败: {block[:50]}... 错误: {e}")
                continue

        self.entries = entries
        logger.success(f"SRT解析完成，共 {len(self.entries)} 个有效条目")
        return self.entries

    def parse_file(self, file_path: str) -> List[SRTEntry]:
        """
        解析SRT文件

        Args:
            file_path: SRT文件路径

        Returns:
            SRT条目列表

        Raises:
            FileNotFoundError: 文件不存在
            ValueError: 文件格式错误
        """
        logger = get_logger()
        logger.step(f"读取SRT文件: {file_path}")

        srt_file = Path(file_path)
        if not srt_file.exists():
            raise FileNotFoundError(f"SRT文件不存在: {file_path}")

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                logger.debug(f"文件读取成功，大小: {len(content)} 字符")
        except UnicodeDecodeError:
            logger.debug("UTF-8解码失败，尝试GBK编码")
            # 尝试其他编码
            with open(file_path, 'r', encoding='gbk') as f:
                content = f.read()
                logger.debug(f"GBK解码成功，大小: {len(content)} 字符")

        entries = self.parse_content(content)

        logger.success(f"SRT解析完成，共 {len(self.entries)} 个有效条目")
        return entries

    def validate_entries(self, entries: List[SRTEntry]) -> bool:
        """
        验证SRT条目的合理性

        Args:
            entries: SRT条目列表

        Returns:
            验证是否通过
        """
        if not entries:
            return False

        for i, entry in enumerate(entries):
            # 检查基本数据有效性
            if entry.start_time < 0 or entry.end_time < 0:
                return False
            if entry.start_time >= entry.end_time:
                return False
            if not entry.text.strip():
                return False

            # 检查时间重叠（警告）
            if i > 0 and entry.start_time < entries[i-1].end_time:
                logger = get_logger()
                logger.warning(f"条目 {entry.index} 与前一条目时间重叠")

        return True
