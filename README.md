# AI配音工具

## 📖 项目介绍

AI配音工具是一个专业的AI语音克隆配音解决方案，通过先进的TTS模型将SRT字幕文件或TXT文本转换为高质量的配音音频。工具支持多种时间同步策略，能够精确匹配字幕时长，生成与视频完美同步的配音。

### 主要特性

- **🎯 精确同步**: 支持时间拉伸策略，确保配音与字幕时长完全匹配
- **🎨 高质量音频**: 基于Fish-speech\IndexTTS\CosyVoice\F5等模型，生成自然流畅的语音
- **⚙️ 灵活策略**: 提供基础策略和拉伸策略，适应不同需求
- **📊 实时监控**: 专业日志系统，实时显示处理进度和状态
- **🔧 易于使用**: 简洁的命令行接口，支持批量处理

## 🏗️ 项目架构

```
ai_dubbing/
├── src/
│   ├── __init__.py            # 模块初始化
│   ├── config.py              # 配置管理
│   ├── utils.py               # 工具函数
│   ├── logger.py              # 日志系统
│   ├── audio_processor.py     # 音频处理器
│   ├── cli.py                 # 命令行接口
│   ├── parsers/               # 统一解析器模块
│   │   ├── __init__.py        # 解析器导出
│   │   ├── srt_parser.py      # SRT解析器
│   │   └── txt_parser.py      # TXT解析器
│   └── strategies/            # 同步策略
│       ├── __init__.py        # 策略注册
│       ├── base_strategy.py   # 抽象基类
│       ├── basic_strategy.py  # 基础策略
│       └── stretch_strategy.py # 时间拉伸策略
│   └── tts_engines/           # TTS引擎
│       ├── __init__.py        # 引擎注册
│       ├── base_engine.py     # 抽象基类
│       ├── index_tts_engine.py # IndexTTS引擎
│       ├── f5_tts_engine.py   # F5-TTS引擎
│       ├── cosy_voice_engine.py # CosyVoice引擎
│       └── fish_speech_engine.py # Fish Speech引擎
└── README.md                  # 说明文档
```

## 🛠️ 环境配置

环境安装和配置请参考 [INSTALL.md](INSTALL.md) 文件。

## 📝 使用说明

支持两种使用方式：**配置文件方式**（推荐）和**命令行参数方式**。

### 方式一：配置文件方式（推荐）

#### 1. 创建配置文件
复制配置文件模板并修改：

```bash
cp ai_dubbing/dubbing.conf.example ai_dubbing/dubbing.conf
```

#### 2. 编辑配置文件
修改 `ai_dubbing/dubbing.conf` 中的参数：

```ini
# SRT配音工具配置文件
# 复制此文件并根据实际需求修改参数

[基本配置]
# 输入文件路径（SRT或TXT，必须指定）
input_file = subtitles/movie.srt

# 参考语音文件路径（WAV格式，必须指定）
voice_file = voices/narrator.wav

# 参考音频文本（使用fish_speech/cosy_voice/f5_tts时需要）
prompt_text = "这是参考音频讲的语音对应的文字"

# 输出音频文件路径（默认：output.wav）
output_file = output/movie_dubbed.wav

# TTS引擎选择：fish_speech, index_tts, f5_tts, cosy_voice
tts_engine = fish_speech

# 时间同步策略：stretch, basic
# 注意：TXT文件模式下系统会自动使用basic策略
strategy = basic

[高级配置]
# 语言设置：zh, en, ja, ko（TXT模式专用）
language = zh
```

#### 3. 运行配音
```bash
python ai_dubbing/run_dubbing.py
```

### 方式二：CLI命令行参数

#### 基础使用
默认使用 `index_tts` 引擎和 `stretch` 策略：

```bash
python -m ai_dubbing.src.cli \
  --srt input.srt \
  --voice reference.wav \
  --output result.wav
```

#### 完整示例

```bash
# 使用时间拉伸策略，精确匹配字幕时长 (使用默认的index_tts引擎)
python -m ai_dubbing.src.cli \
  --srt subtitles/movie.srt \
  --voice voices/narrator.wav \
  --output output/movie_dubbed.wav \
  --strategy stretch \
  --model-dir model-dir/index_tts

# 使用CosyVoice引擎 (需要提供参考文本)
python -m ai_dubbing.src.cli \
  --srt subtitles/movie.srt \
  --voice voices/speaker.wav \
  --output output/movie_cosy.wav \
  --tts-engine cosy_voice \
  --prompt-text "这是参考音频说的话。" \
  --fp16

# 使用Fish Speech引擎 (需要提供参考文本)
python -m ai_dubbing.src.cli \
  --srt subtitles/movie.srt \
  --voice voices/speaker.wav \
  --output output/movie_fish.wav \
  --tts-engine fish_speech \
  --prompt-text "这是参考音频说的话。"

# 使用基础策略，自然语音合成
python -m ai_dubbing.src.cli \
  --srt subtitles/movie.srt \
  --voice voices/narrator.wav \
  --output output/movie_natural.wav \
  --strategy basic
```

## 🔧 命令行参数

### 核心参数

| 参数 | 说明 | 示例 |
|------|------|------|
| `--srt` | SRT字幕文件路径 | `--srt input.srt` |
| `--voice` | 参考语音文件路径（WAV格式） | `--voice reference.wav` |
| `--output`| 输出音频文件路径 | `--output result.wav` |

### 策略与引擎

| 参数 | 默认值 | 说明 | 示例 |
|------|--------|------|------|
| `--strategy` | `stretch` | 时间同步策略 | `--strategy basic` |
| `--tts-engine` | `index_tts` | 选择TTS引擎。可用: `index_tts`, `f5_tts`, `cosy_voice`, `fish_speech` | `--tts-engine cosy_voice` |

### TTS引擎特定参数

| 参数 | 默认值 | 说明 | 示例 |
|------|--------|------|------|
| `--model-dir` | `model-dir/index_tts` | TTS模型目录 | `--model-dir /path/to/model` |
| `--cfg-path` | 自动检测 | 模型配置文件路径 | `--cfg-path config.yaml` |
| `--prompt-text`| 无 | [CosyVoice/Fish Speech] 参考音频对应的文本，使用 `cosy_voice` 或 `fish_speech` 引擎时必需 | `--prompt-text "你好世界"` |
| `--fp16` | 关闭 | [CosyVoice/IndexTTS] 启用FP16半精度推理以加速 | `--fp16` |

### 其他


### 策略说明

每种策略都在**同步性**、**音质**和**处理时间**之间做出了不同的权衡。

#### 1. 基础策略 (`basic`) - ⭐⭐⭐⭐⭐ (音质)
- **目标**: 追求最高质量、最自然的语音。
- **实现方法**:
    1. 对每一条字幕文本，调用一次TTS引擎生成最自然的语音。
    2. 完全**不进行任何时间调整**或拉伸操作。
    3. 最后，将所有生成的音频片段按照字幕顺序依次拼接起来。
- **适用场景**: 对音质有极致要求，且可以容忍时长偏差的场景，例如制作有声书、播客等。

#### 2. 拉伸策略 (`stretch`) - ⭐⭐⭐ (同步性)
- **目标**: 保证音频时长与字幕时长**绝对精确**匹配，实现严格同步。
- **实现方法**:
    1. 先生成自然的语音，然后通过加速或减速音频（时间拉伸），强制将音频时长与字幕完全对齐。
    2. 为了防止音质过度劣化，该策略会有一个“安全范围”，如果计算出的变速比例超出此范围，会以最大安全值进行拉伸。
- **适用场景**: 对口型、动作等时间点要求极为严格的视频配音，例如电影、电视剧的精配。



## 📋 输出示例

### 正常处理流程

```bash
INFO: 🔄 开始AI配音: 输入文件: movie.srt, 策略: stretch
INFO: 🔄 解析SRT文件
INFO: ✓ 成功解析 25 个字幕条目
INFO: 🔄 初始化处理策略
INFO: 🔄 生成音频片段
INFO: [================----] 20/25 (80.0%) - 条目 20: 这是第二十条字幕...
INFO: ✓ 成功生成 25 个音频片段
INFO: 🔄 合并音频片段
INFO: 🔄 导出音频文件
INFO: ✓ AI配音完成: 配音文件已保存至: result.wav (耗时: 45.23s)
```

### 常见警告

```bash
WARNING: 条目 5 需要加速 124% 才能匹配字幕时长，但超出安全范围，已限制为加速 100%
WARNING: 条目 12 与前一条目时间重叠
```

## ❓ 常见问题

### Q: 如何选择合适的参考语音？
A: 建议使用3-10秒的清晰语音文件，包含完整的语调变化，音质越好效果越佳。

### Q: stretch策略音质不如basic策略怎么办？
A: 这是因为时间拉伸会影响音质。建议：
- 检查SRT字幕时长是否合理，避免过度的时间拉伸
- 如果对音质要求很高，使用 `basic` 策略并接受时长偏差

### Q: 各策略如何选择？
A: 
- **basic**: 最佳音质，适合音频材料（如播客、有声书）
- **stretch**: 严格同步，适合对时间精度要求极高的场景


### Q: 处理大文件时内存不足怎么办？
A: 可以将长SRT文件分割成多个小文件分别处理，然后再合并音频。

### Q: 如何提升处理速度？
A: 使用GPU加速（确保CUDA环境配置正确），或降低音频采样率。

### Q: 支持哪些音频格式？
A: 输入支持WAV格式的参考音频，输出默认为WAV格式，可通过修改输出文件扩展名支持其他格式。

## 📄 许可证

本项目遵循MIT许可证，详见LICENSE文件。

## 🤝 贡献

欢迎提交Issue和Pull Request来帮助改进项目！ 