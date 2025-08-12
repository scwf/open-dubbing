#!/usr/bin/env python3
"""
字幕时长验证工具

专门用于检查字幕文件中每条字幕的时长是否满足基于字符数的最小时长要求。
"""

import sys
import argparse
from pathlib import Path
from typing import List, Dict, Any

from .parsers.srt_parser import SRTParser
from .optimizer.subtitle_optimizer import LLMContextOptimizer, SubtitleTimingConstants
from .logger import get_logger


class DurationValidator:
    """字幕时长验证器"""
    
    def __init__(self, 
                 chinese_char_time: float = SubtitleTimingConstants.CHINESE_CHAR_TIME,
                 english_word_time: float = SubtitleTimingConstants.ENGLISH_WORD_TIME):
        """
        初始化验证器
        
        Args:
            chinese_char_time: 每个中文字符的朗读时间（毫秒）
            english_word_time: 每个英文单词的朗读时间（毫秒）
        """
        self.chinese_char_time = chinese_char_time
        self.english_word_time = english_word_time
        self.logger = get_logger()
        
    def calculate_minimum_duration(self, text: str) -> float:
        """基于字符密度计算最小所需时长"""
        import re
        chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
        english_words = len(re.findall(r'[a-zA-Z]+', text))
        
        chinese_duration = chinese_chars * self.chinese_char_time
        english_duration = english_words * self.english_word_time
        
        return chinese_duration + english_duration
    
    def validate_srt_file(self, file_path: str, verbose: bool = True) -> Dict[str, Any]:
        """
        验证SRT字幕文件时长
        
        Args:
            file_path: SRT文件路径
            verbose: 是否显示详细信息
            
        Returns:
            验证结果统计
        """
        file_path = Path(file_path)
        if not file_path.exists():
            self.logger.error(f"文件不存在: {file_path}")
            return {'error': '文件不存在'}
        
        try:
            # 解析字幕文件
            parser = SRTParser()
            entries = parser.parse_file(str(file_path))
            
            if not entries:
                self.logger.warning("字幕文件为空或格式错误")
                return {'error': '文件解析失败'}
            
            # 验证每条字幕
            short_duration_entries = []
            total_entries = len(entries)
            
            for entry in entries:
                min_duration = self.calculate_minimum_duration(entry.text)
                current_duration = entry.duration
                
                if current_duration < min_duration:
                    short_duration_entries.append({
                        'index': entry.index,
                        'text': entry.text,
                        'current_duration': current_duration,
                        'min_required': min_duration,
                        'shortage': min_duration - current_duration,
                        'shortage_ratio': (min_duration - current_duration) / min_duration * 100
                    })
            
            # 生成报告
            short_count = len(short_duration_entries)
            
            report = {
                'total_entries': total_entries,
                'short_duration_count': short_count,
                'valid_percentage': (total_entries - short_count) / total_entries * 100,
                'short_entries': short_duration_entries
            }
            
            # 打印结果
            self.logger.info(f"📊 字幕时长验证报告")
            self.logger.info(f"总字幕条数: {total_entries}")
            self.logger.info(f"时长不足: {short_count}条 ({report['valid_percentage']:.1f}%有效)")
            
            if verbose and short_count > 0:
                self.logger.warning(f"\n📋 时长不足详情:")
                for entry in short_duration_entries[:10]:  # 最多显示10条
                    self.logger.warning(
                        f"字幕{entry['index']}: "
                        f"{entry['text']}, "
                        f"当前{entry['current_duration']:.2f}ms, "
                        f"需要{entry['min_required']:.2f}ms, "
                        f"缺少{entry['shortage']:.2f}ms "
                        f"({entry['shortage_ratio']:.1f}%)")
                
                if short_count > 10:
                    self.logger.info(f"... 还有 {short_count - 10} 条未显示")
            
            if short_count == 0:
                self.logger.success("✅ 所有字幕时长均满足要求")
            
            return report
            
        except Exception as e:
            self.logger.error(f"验证失败: {str(e)}")
            return {'error': str(e)}


def main():
    """命令行入口"""
    parser = argparse.ArgumentParser(description='验证字幕文件时长是否满足最小时长要求')
    parser.add_argument('file', help='SRT字幕文件路径')
    parser.add_argument('-v', '--verbose', action='store_true', help='显示详细信息', default=True)
    parser.add_argument('--chinese-time', type=float, default=SubtitleTimingConstants.CHINESE_CHAR_TIME,
                        help=f'中文字符朗读时间(毫秒)，默认{SubtitleTimingConstants.CHINESE_CHAR_TIME}')
    parser.add_argument('--english-time', type=float, default=SubtitleTimingConstants.ENGLISH_WORD_TIME,
                        help=f'英文单词朗读时间(毫秒)，默认{SubtitleTimingConstants.ENGLISH_WORD_TIME}')
    
    args = parser.parse_args()
    
    validator = DurationValidator(
        chinese_char_time=args.chinese_time,
        english_word_time=args.english_time
    )
    
    result = validator.validate_srt_file(args.file, verbose=args.verbose)
    
    if 'error' in result:
        return 1
    
    return 0 if result['short_duration_count'] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())