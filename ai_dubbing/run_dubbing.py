#!/usr/bin/env python3
"""
通过命令行参数运行的 SRT/TXT 配音工具。
"""

import argparse
import logging
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
from ai_dubbing.src.parsers import SRTParser, TXTParser
from ai_dubbing.src.strategies import get_strategy, list_available_strategies
from ai_dubbing.src.tts_engines import get_tts_engine, TTS_ENGINES
from ai_dubbing.src.audio_processor import AudioProcessor
from ai_dubbing.src.logger import setup_logging, create_process_logger, get_logger

# 初始化项目环境
setup_project_path()

DEFAULT_VOICE_FILE = str(project_root / "refer_voice" / "mcs.mp3")
DEFAULT_PROMPT_TEXT = (
    "很多人可能觉得，这不简单吗？把我们现有的函数或者API接口直接开放给智能体不就行了？"
    "但事实证明，这条路往往走不通。为什么呢？因为我们必须明白一个核心前提："
    "智能体“看见”和“使用”工具的方式，和我们人类开发者是完全不同的。"
)
DEFAULT_LANGUAGE = "zh"
DEFAULT_TTS_ENGINE = "index_tts2"
DEFAULT_TTS_MAX_RETRIES = 2
DEFAULT_EMOTION_TEXT = "平静"
DEFAULT_EMOTION_ALPHA = 0.5


def configure_external_loggers() -> None:
    """Lower noisy third-party debug loggers without muting normal app logs."""
    noisy_loggers = [
        "urllib3",
        "requests",
        "modelscope",
        "modelscope.hub",
        "numba",
        "numba.core",
        "numba.core.byteflow",
        "numba.core.interpreter",
        "numba.core.ssa",
    ]
    for name in noisy_loggers:
        logger = logging.getLogger(name)
        logger.setLevel(logging.INFO)

def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description="基于命令行参数的 SRT/TXT 配音工具",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--input-file",
        required=True,
        help="输入文件路径（SRT 或 TXT）",
    )
    parser.add_argument(
        "--voice-files",
        nargs="+",
        default=[DEFAULT_VOICE_FILE],
        help="一个或多个参考音频路径，多个值用空格分隔",
    )
    parser.add_argument(
        "--prompt-texts",
        nargs="+",
        default=[DEFAULT_PROMPT_TEXT],
        help="与参考音频一一对应的文本，包含空格时请用引号包裹",
    )
    parser.add_argument(
        "--output-file",
        required=True,
        help="输出音频文件路径",
    )
    parser.add_argument(
        "--tts-engine",
        default=DEFAULT_TTS_ENGINE,
        choices=sorted(TTS_ENGINES.keys()),
        help="TTS 引擎",
    )
    parser.add_argument(
        "--strategy",
        choices=list_available_strategies(),
        help="时间同步策略；未传时自动按输入类型选择（SRT=stretch，TXT=basic）",
    )
    parser.add_argument(
        "--emotion-text",
        default=DEFAULT_EMOTION_TEXT,
        help="IndexTTS2 文本情感描述",
    )
    parser.add_argument(
        "--emotion-alpha",
        type=float,
        default=DEFAULT_EMOTION_ALPHA,
        help="情感强度，范围 0.0-1.0",
    )

    args = parser.parse_args()
    validate_args(parser, args)
    return args

def validate_args(parser, args):
    """校验命令行参数"""
    if len(args.voice_files) != len(args.prompt_texts):
        parser.error(
            f"--voice-files ({len(args.voice_files)}) 和 --prompt-texts ({len(args.prompt_texts)}) 的数量必须一致"
        )

    if not (0.0 <= args.emotion_alpha <= 1.0):
        parser.error("--emotion-alpha 必须在 0.0 到 1.0 之间")

def determine_strategy(input_file, explicit_strategy):
    """根据输入文件类型决定默认策略。"""
    if explicit_strategy:
        return explicit_strategy
    return "basic" if Path(input_file).suffix.lower() == ".txt" else "stretch"

def get_emotion_config(args):
    """从命令行参数构建 IndexTTS2 文本情感配置"""
    return {
        "emotion_text": args.emotion_text.strip(),
        "emotion_alpha": args.emotion_alpha,
    }

def main():
    """主函数：完全遵循cli.py的精确结构和逻辑"""
    args = parse_args()
    configure_external_loggers()
    
    input_file = args.input_file
    output_file = args.output_file
    tts_engine_name = args.tts_engine
    strategy_name = determine_strategy(input_file, args.strategy)
    lang = DEFAULT_LANGUAGE
    tts_max_retries = DEFAULT_TTS_MAX_RETRIES
    voice_files = args.voice_files
    prompt_texts = args.prompt_texts
    
    # --- 初始化 ---
    start_time = time.time()
    setup_logging("INFO")
    
    # 创建logger
    logger = get_logger()
    
    # 获取情感控制配置（仅当使用IndexTTS2时）
    emotion_config = {}
    if tts_engine_name == 'index_tts2':
        emotion_config = get_emotion_config(args)
        if emotion_config:
            logger.info(f"IndexTTS2情感控制配置: {emotion_config}")
    
    # 打印每一对参考音频和文本配置
    logger.info(f"配置了 {len(voice_files)} 对参考音频和文本:")
    for i, (voice_file, prompt_text) in enumerate(zip(voice_files, prompt_texts), 1):
        logger.info(f"  {i}. 音频: {voice_file}")
        logger.info(f"     文本: {prompt_text}")
    
    process_logger = create_process_logger("命令行配音任务")
    
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
    sys.exit(main())
