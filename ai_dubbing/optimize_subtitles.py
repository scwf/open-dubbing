#!/usr/bin/env python3
"""
字幕文件优化工具

使用LLM对字幕文件进行智能文本简化优化，确保字幕时长合理。
基于dubbing.conf配置文件进行参数设置，与run_dubbing.py保持一致。
"""

import os
import sys
import configparser
from pathlib import Path

# 获取项目根目录
current_file = Path(__file__).resolve()
ai_dubbing_root = current_file.parent

# 添加到 sys.path（如果还没有的话）
project_root_str = str(ai_dubbing_root.parent)
if project_root_str not in sys.path:
    sys.path.append(project_root_str)

from ai_dubbing.src.parsers.srt_parser import SRTParser
from ai_dubbing.src.optimizer.subtitle_optimizer import LLMContextOptimizer
from ai_dubbing.src.logger import get_logger

def load_config(config_file=str(current_file.parent / "dubbing.conf")):
    """加载配置文件"""
    if not os.path.exists(config_file):
        print(f"错误: 配置文件 {config_file} 不存在")
        print("请复制 dubbing.conf.example 为 dubbing.conf 并根据实际需求修改参数")
        sys.exit(1)
    
    config = configparser.ConfigParser()
    config.read(config_file, encoding='utf-8')
    return config

def get_config_value(config, section, key, default=None, value_type=str):
    """获取配置值，支持类型转换"""
    try:
        if value_type == bool:
            return config.getboolean(section, key)
        elif value_type == float:
            return config.getfloat(section, key)
        elif value_type == int:
            return config.getint(section, key)
        else:
            return config.get(section, key)
    except (configparser.NoSectionError, configparser.NoOptionError):
        return default

def load_config_from_file(config_file=None):
    """从配置文件加载LLM优化配置"""
    if not config_file:
        config_file = str(ai_dubbing_root / "dubbing.conf")
    
    config = load_config(config_file)
    
    # 从字幕优化配置部分读取参数
    llm_config = {
        'api_key': get_config_value(config, '字幕优化配置', 'llm_api_key'),
        'model': get_config_value(config, '字幕优化配置', 'llm_model', 'deepseek-chat'),
        'base_url': get_config_value(config, '字幕优化配置', 'base_url', 'https://api.deepseek.com'),
        'chinese_char_min_time': get_config_value(config, '字幕优化配置', 'chinese_char_min_time', 130, int),
        'english_word_min_time': get_config_value(config, '字幕优化配置', 'english_word_min_time', 250, int),
        'min_gap_threshold': get_config_value(config, '时间借用配置', 'min_gap_threshold', 300, int),
        'borrow_ratio': get_config_value(config, '时间借用配置', 'borrow_ratio', 0.5, float),
        'extra_buffer': get_config_value(config, '时间借用配置', 'extra_buffer', 200, int)
    }
    
    return llm_config

def optimize_srt_file(input_path: str, output_path: str = None, config: dict = None):
    """
    优化单个SRT字幕文件
    
    Args:
        input_path: 输入SRT文件路径
        output_path: 输出SRT文件路径（可选）
        config: LLM配置字典
    
    Returns:
        优化后的文件路径
    """
    logger = get_logger()
    
    if not os.path.exists(input_path):
        logger.error(f"输入文件不存在: {input_path}")
        return None
    
    try:
        # 加载字幕文件
        logger.step(f"加载字幕文件: {input_path}")
        parser = SRTParser()
        entries = parser.parse_file(input_path)
        
        if not entries:
            logger.warning("字幕文件为空或格式错误")
            return None
        
        logger.info(f"成功加载 {len(entries)} 个字幕条目")
        
        # 初始化LLM优化器
        if not config:
            config = load_config_from_file()
        
        if not config.get('api_key'):
            logger.error("未配置LLM API密钥，请在 dubbing.conf 文件中设置 llm_api_key")
            return None
        
        optimizer = LLMContextOptimizer(
            api_key=config['api_key'],
            model=config['model'],
            base_url=config['base_url'],
            chinese_char_min_time=config['chinese_char_min_time'],
            english_word_min_time=config['english_word_min_time'],
            min_gap_threshold=config['min_gap_threshold'],
            borrow_ratio=config['borrow_ratio'],
            extra_buffer=config['extra_buffer']
        )
        
        # 执行优化
        logger.step("开始LLM字幕优化")
        optimized_entries, report = optimizer.optimize_subtitles(entries)
        
        # 保存优化结果
        optimized_path = optimizer.save_optimized_srt(
            optimized_entries, 
            input_path, 
            output_path
        )
        
        # 打印优化报告
        logger.success("字幕优化完成！")
        logger.info(f"原始字幕数: {report.original_entries}")
        logger.info(f"优化后字幕数: {report.optimized_entries}")
        logger.info(f"简化字幕数: {report.simplified_count}")
        logger.info(f"优化后文件: {optimized_path}")
        
        return optimized_path
        
    except Exception:
        logger.exception("字幕优化失败")
        return None

def main():
    """主函数 - 完全从配置文件读取"""
    config = load_config()
    
    # 从配置文件读取输入文件
    input_file = get_config_value(config, '基本配置', 'input_file')
    if not input_file:
        print("错误: 请在 dubbing.conf 文件的 [基本配置] 部分设置 input_file")
        return 1
    
    # 从配置文件读取LLM配置
    llm_config = load_config_from_file()
    
    # 检查API密钥
    if not llm_config.get('api_key'):
        print("错误: 未配置LLM API密钥")
        print("请在 dubbing.conf 文件的 [字幕优化配置] 部分设置 llm_api_key")
        return 1
    
    # 从字幕优化配置读取输出文件（新键名优先，兼容旧键名）
    output_file = get_config_value(config, '字幕优化配置', 'optimized_srt_output_file')
    
    # 执行优化
    result = optimize_srt_file(input_file, output_file, llm_config)
    
    if result:
        print(f"\n✅ 字幕优化成功完成！")
        print(f"📁 优化后文件: {result}")
        return 0
    else:
        print("\n❌ 字幕优化失败")
        return 1

if __name__ == "__main__":
    sys.exit(main())