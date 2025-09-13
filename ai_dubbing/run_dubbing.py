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
from ai_dubbing.src.logger import setup_logging, create_process_logger, get_logger

# 初始化项目环境
setup_project_path()

def load_config(config_file=str(current_file.parent)+"/dubbing.conf"):
    """加载配置文件，返回配置字典"""
    if not os.path.exists(config_file):
        # 创建简单logger用于配置文件不存在的错误
        setup_logging("INFO")
        logger = get_logger()
        logger.error(f"配置文件 {config_file} 不存在")
        logger.info("请复制 dubbing.conf.example 为 dubbing.conf 并根据实际需求修改参数")
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

def parse_quoted_list(text):
    """
    解析带引号的逗号分隔列表
    例如: '"文本1", "文本2", "文本3"' -> ['文本1', '文本2', '文本3']
    也支持不带引号的简单列表: 'file1.wav, file2.wav' -> ['file1.wav', 'file2.wav']
    """
    if not text or not text.strip():
        return []
    
    import re
    # 匹配带引号的字符串或不带引号的简单字符串
    pattern = r'"([^"]*?)"|([^,]+)'
    matches = re.findall(pattern, text)
    
    result = []
    for quoted, unquoted in matches:
        if quoted:  # 带引号的字符串
            result.append(quoted)
        elif unquoted.strip():  # 不带引号的字符串，去掉前后空白
            result.append(unquoted.strip())
    
    return result

def get_multi_voice_config(config):
    """
    获取多对参考音频配置
    
    Returns:
        tuple: (voice_files_list, prompt_texts_list)
    """
    voice_files_str = get_config_value(config, '基本配置', 'voice_files', None)
    prompt_texts_str = get_config_value(config, '基本配置', 'prompt_texts', None)
    
    if not voice_files_str or not prompt_texts_str:
        raise ValueError("必须同时配置 voice_files 和 prompt_texts")
    
    # 解析配置
    voice_files = parse_quoted_list(voice_files_str)
    prompt_texts = parse_quoted_list(prompt_texts_str)
    
    if not voice_files or not prompt_texts:
        raise ValueError("voice_files 和 prompt_texts 不能为空")
    
    if len(voice_files) != len(prompt_texts):
        raise ValueError(f"voice_files ({len(voice_files)}) 和 prompt_texts ({len(prompt_texts)}) 的数量不匹配")
    
    return voice_files, prompt_texts

def get_emotion_config(config):
    """
    获取IndexTTS2情感控制配置
    
    Args:
        config: configparser.ConfigParser对象
    
    Returns:
        dict: 情感控制参数字典
    """
    SECTION_NAME = 'IndexTTS2情感控制'
    
    # 情感模式处理器映射
    mode_handlers = {
        'audio': _handle_audio_emotion,
        'vector': _handle_vector_emotion,
        'text': _handle_text_emotion,
        'auto': _handle_auto_emotion,
    }
    
    emotion_config = {}
    emotion_mode = get_config_value(config, SECTION_NAME, 'emotion_mode', 'auto')
    
    # 处理特定情感模式
    handler = mode_handlers.get(emotion_mode)
    if handler:
        emotion_config.update(handler(config, SECTION_NAME))
    
    # 添加通用参数
    emotion_config.update(_get_common_emotion_params(config, SECTION_NAME))
    
    return emotion_config

def _handle_audio_emotion(config, section_name):
    """处理音频引导模式"""
    emotion_audio_file = get_config_value(config, section_name, 'emotion_audio_file')
    return {'emotion_audio_file': emotion_audio_file.strip()} if emotion_audio_file and emotion_audio_file.strip() else {}

def _handle_vector_emotion(config, section_name):
    """处理情感向量模式"""
    emotion_vector_str = get_config_value(config, section_name, 'emotion_vector')
    if not emotion_vector_str or not emotion_vector_str.strip():
        return {}
    
    try:
        emotion_vector = [float(x.strip()) for x in emotion_vector_str.split(',')]
        if len(emotion_vector) == 8:
            return {'emotion_vector': emotion_vector}
        else:
            print(f"警告：情感向量必须包含8个数值，当前有{len(emotion_vector)}个")
    except ValueError as e:
        print(f"警告：情感向量格式错误: {e}")
    
    return {}

def _handle_text_emotion(config, section_name):
    """处理文本描述模式"""
    emotion_text = get_config_value(config, section_name, 'emotion_text')
    return {'emotion_text': emotion_text.strip()} if emotion_text and emotion_text.strip() else {}

def _handle_auto_emotion(config, section_name):
    """处理自动检测模式"""
    return {'auto_emotion': True}

def _get_common_emotion_params(config, section_name):
    """获取通用情感参数"""
    emotion_alpha = get_config_value(config, section_name, 'emotion_alpha', 0.8, float)
    
    # 验证情感强度范围
    if not (0.0 <= emotion_alpha <= 1.0):
        print(f"警告：情感强度超出范围[0.0, 1.0]，使用默认值0.8，当前值: {emotion_alpha}")
        emotion_alpha = 0.8
    
    return {
        'emotion_alpha': emotion_alpha,
        'use_random': get_config_value(config, section_name, 'use_random', False, bool)
    }

def main():
    """主函数：完全遵循cli.py的精确结构和逻辑"""
    
    # 加载配置
    config = load_config()
    
    # 解析配置参数（映射到cli.py的参数）
    input_file = get_config_value(config, '基本配置', 'input_file')
    output_file = get_config_value(config, '基本配置', 'output_file', PATH.get_default_output_path())
    tts_engine_name = get_config_value(config, '基本配置', 'tts_engine', 'fish_speech')
    strategy_name = get_config_value(config, '基本配置', 'strategy', 'stretch')
    lang = get_config_value(config, '高级配置', 'language', 'zh')
    # 并发配置（供策略并行合成使用）
    tts_max_concurrency = get_config_value(config, '并发配置', 'tts_max_concurrency', 8, int)
    tts_max_retries = get_config_value(config, '并发配置', 'tts_max_retries', 2, int)
    
    # 解析多对参考音频配置
    voice_files, prompt_texts = get_multi_voice_config(config)
    
    # --- 初始化 ---
    start_time = time.time()
    setup_logging("INFO")
    
    # 创建logger
    logger = get_logger()
    
    # 获取情感控制配置（仅当使用IndexTTS2时）
    emotion_config = {}
    if tts_engine_name == 'index_tts2':
        emotion_config = get_emotion_config(config)
        if emotion_config:
            logger.info(f"IndexTTS2情感控制配置: {emotion_config}")
    
    # 打印每一对参考音频和文本配置
    logger.info(f"配置了 {len(voice_files)} 对参考音频和文本:")
    for i, (voice_file, prompt_text) in enumerate(zip(voice_files, prompt_texts), 1):
        logger.info(f"  {i}. 音频: {voice_file}")
        logger.info(f"     文本: {prompt_text}")
    
    process_logger = create_process_logger("配置文件配音任务")
    
    # --- 确定输入文件类型和解析器 ---
    file_extension = os.path.splitext(input_file)[1].lower()
    is_txt_mode = file_extension == '.txt'
    
    if not os.path.exists(input_file):
        logger.error(f"输入文件不存在: {input_file}")
        return 1
    
    allowed_exts = {'.wav', '.mp3'}
    for i, voice_file in enumerate(voice_files):
        if not os.path.exists(voice_file):
            logger.error(f"参考语音文件不存在: {voice_file}")
            return 1
        ext = Path(voice_file).suffix.lower()
        if ext not in allowed_exts:
            logger.error(f"参考语音文件格式不支持: {voice_file}，仅支持 wav/mp3")
            return 1
    
    process_logger.start(f"输入: {input_file}, 引擎: {tts_engine_name}, 策略: {strategy_name}, 参考音频: {len(voice_files)}个")

    # --- 1. 初始化TTS引擎 ---
    try:
        process_logger.step("初始化TTS引擎")
        tts_engine_instance = get_tts_engine(tts_engine_name)
        process_logger.logger.info(f"使用TTS引擎: {tts_engine_name}")
    except (ValueError, RuntimeError, ImportError):
        process_logger.logger.exception("TTS引擎初始化失败")
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
    except Exception:
        process_logger.logger.exception("解析文件失败")
        return 1

    # --- 3. 初始化处理策略 ---
    if is_txt_mode and strategy_name != "basic":
        process_logger.logger.warning("TXT文件模式下仅支持 'basic' 策略，已自动切换。")
        strategy_name = "basic"
    try:
        process_logger.step("初始化处理策略")
        # 注入TTS引擎实例
        strategy_instance = get_strategy(strategy_name, tts_engine=tts_engine_instance)
        process_logger.logger.info(f"使用策略: {strategy_instance.name()} - {strategy_instance.description()}")
    except ValueError:
        process_logger.logger.exception("策略初始化失败")
        return 1

    # --- 4. 生成音频片段 ---
    try:
        process_logger.step("生成音频片段")
        
        # 将引擎特定的运行时参数传递给策略
        runtime_kwargs = {
            "prompt_text": prompt_texts[0] if prompt_texts else None,  # 主要参考文本
            "ref_text": prompt_texts[0] if prompt_texts else None,     # 兼容性
            "voice_files": voice_files,        # 所有参考音频文件
            "prompt_texts": prompt_texts,      # 所有参考文本
            # 并发相关参数：由基础策略读取并控制
            "max_concurrency": tts_max_concurrency,
            "max_retries": tts_max_retries,
            # IndexTTS2情感控制参数
            **emotion_config
        }
        
        audio_segments = strategy_instance.process_entries(
            entries,
            voice_reference=voice_files[0],  # 主要参考音频
            **runtime_kwargs
        )
        process_logger.logger.success(f"成功生成 {len(audio_segments)} 个音频片段")
    except Exception:
        process_logger.logger.exception("音频生成失败")
        return 1
        
    # --- 5. 合并并导出音频 ---
    try:
        process_logger.step("合并音频片段")
        processor = AudioProcessor()
        merged_audio = processor.merge_audio_segments(
            audio_segments,
            strategy_name=strategy_name)
        
        process_logger.step("导出音频文件")
        if not processor.export_audio(merged_audio, output_file):
            process_logger.logger.error("音频导出失败")
            return 1
            
    except Exception:
        process_logger.logger.exception("音频处理失败")
        return 1
    
    end_time = time.time()
    processing_time = end_time - start_time
    process_logger.complete(f"配音文件已保存至: {output_file} (耗时: {processing_time:.2f}s)")
    return 0

if __name__ == "__main__":
    import sys
    sys.exit(main())