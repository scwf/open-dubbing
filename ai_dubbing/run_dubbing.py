#!/usr/bin/env python3
"""
基于配置文件的SRT配音工具

通过读取dubbing.conf配置文件来执行配音任务，完全遵循cli.py的结构和逻辑。
"""

import configparser
import os
import sys
import time
from pathlib import Path

# 获取项目根目录
current_file = Path(__file__).resolve()
project_root = current_file.parent.parent

# 添加到 sys.path（如果还没有的话）
project_root_str = str(project_root)
if project_root_str not in sys.path:
    sys.path.append(project_root_str)

# 使用绝对导入
from ai_dubbing.src.utils import setup_project_path
from ai_dubbing.src.config import PATH
from ai_dubbing.src.parsers import SRTParser, TXTParser
from ai_dubbing.src.strategies import get_strategy, list_available_strategies, get_strategy_description
from ai_dubbing.src.tts_engines import get_tts_engine, TTS_ENGINES
from ai_dubbing.src.audio_processor import AudioProcessor
from ai_dubbing.src.logger import setup_logging, create_process_logger

# 初始化项目环境
setup_project_path()

def load_config(config_file=str(current_file.parent)+"/dubbing.conf"):
    """加载配置文件，返回配置字典"""
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

def main():
    """主函数：完全遵循cli.py的精确结构和逻辑"""
    
    # 加载配置
    config = load_config()
    
    # 解析配置参数（映射到cli.py的参数）
    input_file = get_config_value(config, '基本配置', 'input_file')
    voice_file = get_config_value(config, '基本配置', 'voice_file')
    output_file = get_config_value(config, '基本配置', 'output_file', PATH.get_default_output_path())
    tts_engine = get_config_value(config, '基本配置', 'tts_engine', 'index_tts')
    strategy = get_config_value(config, '基本配置', 'strategy', 'stretch')
    lang = get_config_value(config, '高级配置', 'language', 'zh')
    prompt_text = get_config_value(config, '基本配置', 'prompt_text', None)
    
    # --- 初始化 ---
    start_time = time.time()
    setup_logging("INFO")
    
    process_logger = create_process_logger("配置文件配音任务")
    
    # --- 确定输入文件类型和解析器 ---
    file_extension = os.path.splitext(input_file)[1].lower()
    is_txt_mode = file_extension == '.txt'
    
    if not os.path.exists(input_file):
        print(f"错误: 输入文件不存在: {input_file}")
        return 1
    
    if not os.path.exists(voice_file):
        print(f"错误: 参考语音文件不存在: {voice_file}")
        return 1
    
    process_logger.start(f"输入: {input_file}, 引擎: {tts_engine}, 策略: {strategy}")

    # --- 1. 初始化TTS引擎 ---
    try:
        process_logger.step("初始化TTS引擎")
        tts_engine_instance = get_tts_engine(tts_engine)
        process_logger.logger.info(f"使用TTS引擎: {tts_engine}")
    except (ValueError, RuntimeError, ImportError) as e:
        process_logger.logger.error(f"TTS引擎初始化失败: {e}")
        return 1
        
    # --- 2. 解析文件 ---
    try:
        process_logger.step("解析输入文件")
        if is_txt_mode:
            process_logger.logger.info(f"检测到TXT文件输入，将按语言 '{lang}' 的规则进行解析。")
            parser_instance = TXTParser(language=lang)
        else:
            parser_instance = SRTParser()
        
        entries = parser_instance.parse_file(input_file)
        process_logger.logger.success(f"成功解析 {len(entries)} 个条目")
    except Exception as e:
        process_logger.logger.error(f"解析文件失败: {e}")
        return 1

    # --- 3. 初始化处理策略 ---
    strategy_name = strategy
    if is_txt_mode:
        if strategy_name != "basic":
            process_logger.logger.warning(f"TXT文件模式下仅支持 'basic' 策略，已自动切换。")
            strategy_name = "basic"
            
    try:
        process_logger.step("初始化处理策略")
        # 注入TTS引擎实例
        strategy = get_strategy(strategy_name, tts_engine=tts_engine_instance)
        process_logger.logger.info(f"使用策略: {strategy.name()} - {strategy.description()}")
    except ValueError as e:
        process_logger.logger.error(f"策略初始化失败: {e}")
        return 1

    # --- 4. 生成音频片段 ---
    try:
        process_logger.step("生成音频片段")
        
        # 将引擎特定的运行时参数传递给策略
        runtime_kwargs = {
            "prompt_text": prompt_text,
            "ref_text": prompt_text
        }
        
        audio_segments = strategy.process_entries(
            entries,
            voice_reference=voice_file,
            **runtime_kwargs
        )
        process_logger.logger.success(f"成功生成 {len(audio_segments)} 个音频片段")
    except Exception as e:
        process_logger.logger.error(f"音频生成失败: {e}")
        return 1
        
    # --- 5. 合并并导出音频 ---
    try:
        process_logger.step("合并音频片段")
        processor = AudioProcessor()
        merged_audio = processor.merge_audio_segments(
            audio_segments,
            strategy_name=strategy_name,
            truncate_on_overflow=False
        )
        
        process_logger.step("导出音频文件")
        if not processor.export_audio(merged_audio, output_file):
            process_logger.logger.error("音频导出失败")
            return 1
            
    except Exception as e:
        process_logger.logger.error(f"音频处理失败: {e}")
        import traceback
        process_logger.logger.debug("详细错误信息:")
        process_logger.logger.debug(traceback.format_exc())
        return 1
    
    end_time = time.time()
    processing_time = end_time - start_time
    process_logger.complete(f"配音文件已保存至: {output_file} (耗时: {processing_time:.2f}s)")
    return 0

if __name__ == "__main__":
    import sys
    sys.exit(main())