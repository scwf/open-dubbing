"""
命令行接口

提供SRT配音工具的命令行访问接口，支持各种参数配置和批量处理。
"""

import argparse
import time

# 使用绝对导入
from ai_dubbing.src.utils.common_utils import setup_project_path
from ai_dubbing.src.config import PATH
from ai_dubbing.src.parsers import SRTParser, TXTParser
from ai_dubbing.src.strategies import get_strategy, list_available_strategies, get_strategy_description
from ai_dubbing.src.tts_engines import get_tts_engine, TTS_ENGINES
from ai_dubbing.src.audio_processor import AudioProcessor
from ai_dubbing.src.logger import setup_logging, create_process_logger

# 初始化项目环境
setup_project_path()


def main():
    """主函数：解析命令行参数并启动处理流程"""
    
    available_strategies = list_available_strategies()
    available_tts_engines = list(TTS_ENGINES.keys())
    
    parser = argparse.ArgumentParser(
        description="SRT及TXT字幕配音工具",
        formatter_class=argparse.RawTextHelpFormatter
    )
    
    # --- 核心参数 (输入文件) ---
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument("--srt", help="待处理的SRT字幕文件路径")
    input_group.add_argument("--txt", help="待处理的TXT纯文本文件路径")

    parser.add_argument("--voice", required=True, help="参考语音WAV文件路径")
    parser.add_argument("--output", default=PATH.get_default_output_path(), help=f"输出的音频文件路径 (默认: {PATH.get_default_output_path()})")
    
    # --- 策略与引擎选择 ---
    parser.add_argument(
        "--strategy",
        default="stretch",
        choices=available_strategies,
        help=(
            "选择使用的时间同步策略。\n"
            f"可选策略: {', '.join(available_strategies)}\n"
            # 动态生成策略描述
            + "\n".join([f"  - {s}: {get_strategy_description(s)}" for s in available_strategies])
            + "\n(默认: stretch)"
        )
    )
    parser.add_argument(
        "--tts-engine",
        default="index_tts",
        choices=available_tts_engines,
        help=f"选择使用的TTS引擎 (默认: index_tts)"
    )

    # --- 模型与配置 ---
    parser.add_argument("--lang", default="zh", help="[TXT模式] 指定文本语言 (例如: en, zh)")
    parser.add_argument("--prompt-text", help="[CosyVoice] 参考音频对应的文本")

    parser.add_argument("--ref-text", help="[F5TTS] 参考音频对应的文本")
    
    # --- 其他选项 ---
    
    args = parser.parse_args()
    
    # --- 初始化 ---
    start_time = time.time()
    logger = setup_logging("INFO")
    
    process_logger = create_process_logger("配音任务")
    
    # --- 确定输入文件类型和解析器 ---
    is_txt_mode = args.txt is not None
    input_file = args.txt if is_txt_mode else args.srt
    
    process_logger.start(f"输入: {input_file}, 引擎: {args.tts_engine}, 策略: {args.strategy}")

    # --- 1. 初始化TTS引擎 ---
    try:
        process_logger.step("初始化TTS引擎")
        tts_engine = get_tts_engine(args.tts_engine)
        logger.info(f"使用TTS引擎: {args.tts_engine}")
    except (ValueError, RuntimeError, ImportError) as e:
        logger.error(f"TTS引擎初始化失败: {e}")
        return 1
        
    # --- 2. 解析文件 ---
    try:
        process_logger.step("解析输入文件")
        if is_txt_mode:
            logger.info(f"检测到TXT文件输入，将按语言 '{args.lang}' 的规则进行解析。")
            parser_instance = TXTParser(language=args.lang)
        else:
            parser_instance = SRTParser()
        
        entries = parser_instance.parse_file(input_file)
        logger.success(f"成功解析 {len(entries)} 个条目")
    except Exception as e:
        logger.error(f"解析文件失败: {e}")
        return 1

    # --- 3. 初始化处理策略 ---
    strategy_name = args.strategy
    if is_txt_mode:
        if strategy_name != "basic":
            logger.warning(f"TXT文件模式下仅支持 'basic' 策略，已自动切换。")
            strategy_name = "basic"
            
    try:
        process_logger.step("初始化处理策略")
        # 注入TTS引擎实例
        strategy = get_strategy(strategy_name, tts_engine=tts_engine)
        logger.info(f"使用策略: {strategy.name()} - {strategy.description()}")
    except ValueError as e:
        logger.error(f"策略初始化失败: {e}")
        return 1

    # --- 4. 生成音频片段 ---
    try:
        process_logger.step("生成音频片段")
        
        # 将引擎特定的运行时参数传递给策略
        runtime_kwargs = {
            "prompt_text": args.prompt_text,
            "ref_text": args.prompt_text
        }
        
        audio_segments = strategy.process_entries(
            entries,
            voice_reference=args.voice,
            **runtime_kwargs
        )
        logger.success(f"成功生成 {len(audio_segments)} 个音频片段")
    except Exception as e:
        logger.error(f"音频生成失败: {e}")
        return 1
        
    # --- 5. 合并并导出音频 ---
    try:
        process_logger.step("合并音频片段")
        processor = AudioProcessor()
        merged_audio = processor.merge_audio_segments(
            audio_segments,
            strategy_name=args.strategy,
            truncate_on_overflow=False
        )
        
        process_logger.step("导出音频文件")
        if not processor.export_audio(merged_audio, args.output):
            logger.error("音频导出失败")
            return 1
            
    except Exception as e:
        logger.error(f"音频处理失败: {e}")
        import traceback
        logger.debug("详细错误信息:")
        logger.debug(traceback.format_exc())
        return 1
    
    end_time = time.time()
    processing_time = end_time - start_time
    process_logger.complete(f"配音文件已保存至: {args.output} (耗时: {processing_time:.2f}s)")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main()) 