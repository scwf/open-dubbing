---
name: subtitle-voice-dubbing
description: >-
  Turns SRT/TXT subtitles into voice-cloned dubbed WAV (字幕配音 / 字幕转语音).
  Use when the user asks to dub subtitles, 给字幕配音, generate narration from
  SRT or TXT, clone a reference voice for speech, run ai_dubbing/run_dubbing.py,
  or operate the open-dubbing repo CLI/Web UI. Not for generic TTS outside this
  repo or for editing deps/fish-speech.
---

# 字幕配音（Subtitle Voice Dubbing）

将 SRT/TXT 字幕合成为配音 WAV。**Agent 默认走 CLI**；Web UI 仅用于人工交互。

本 Skill 可随仓库位于 `skills/subtitle-voice-dubbing/`，也可复制到 Cursor / Claude Code 等平台的技能目录；**配音命令始终在 open-dubbing 仓库根目录执行**（挂载方式见 [reference.md](reference.md#在-agent-平台中使用)）。

## 仓库根目录（执行命令前必读）

**仓库根目录**指 clone 后的 `open-dubbing/` 顶层目录，即同时包含以下路径的那一层：

```text
<REPO_ROOT>/
├── ai_dubbing/run_dubbing.py   ← CLI 入口
├── server.py
├── resources/reference_voices/
├── deps/
└── models/                     ← 模型缓存（安装后生成）
```

**如何确定 `<REPO_ROOT>`**（与 Skill 文件放在哪里无关）：

1. 在 open-dubbing 仓库内：`git rev-parse --show-toplevel`
2. 确认该目录下存在 `ai_dubbing/run_dubbing.py` 与 `server.py`
3. 路径不明时：**向用户询问** open-dubbing 的 clone 路径

**硬性要求：凡执行配音相关 shell 命令，必须先 `cd` 到 `<REPO_ROOT>`，再执行后续命令。** 不得在其它目录直接调用 `python ai_dubbing/run_dubbing.py`（IndexTTS2 等引擎依赖相对路径缓存，cwd 错误会导致重复下载或失败）。

```bash
cd "<REPO_ROOT>"   # 每条配音命令前必须有这一步（或与 cd 同条的 bash -lc）
pwd                # 可选：确认当前目录为仓库根
```

WSL / 远程调用时同样必须先 `cd`：

```bash
wsl.exe -e bash -lc 'cd "<REPO_ROOT>" && conda activate index-tts2 && python ai_dubbing/run_dubbing.py ...'
```

## 工作流

面向用户的五步流程；环境安装细节见 [reference.md](reference.md)。

```
- [ ] 1. 获取配音内容：用户提供 SRT/TXT 路径（或协助准备字幕文件）
- [ ] 2. 选择参考音：默认展示内置参考音列表供用户点选，末项为「自定义参考音」
- [ ] 3. 选择克隆引擎：展示可用 TTS 引擎供用户点选（默认 index_tts2）
- [ ] 4. 执行配音：先 `cd <REPO_ROOT>`，激活 Conda 环境，再运行 run_dubbing.py
- [ ] 5. 交付结果：确认 WAV 生成成功，将输出路径交给用户
```

### 1. 获取配音内容

向用户确认要克隆配音的**字幕/文本文件**：

- 支持 **SRT**（带时间轴，默认 `stretch` 策略）或 **TXT**（纯文本，默认 `basic` 策略）
- 记录 `--input-file` 的绝对或相对路径，执行前确认文件存在

用户只有文稿、没有字幕时：先协助生成 SRT/TXT，再进入下一步（字幕优化见 [reference.md](reference.md#附属脚本)）。

### 2. 选择参考音

**默认做法**：向用户展示内置参考音列表，请其选择一项；**最后一项固定为「自定义参考音（用户提供音频 + 文本）」**。

内置选项（路径与文本见 `resources/reference_voices/`，文本也可读同名 `.txt`）：

| # | 名称 | 说明 |
| --- | --- | --- |
| 1 | mcs | 默认男声，科技讲解风格 |
| 2 | wm1 | 短句示例 |
| 3 | qjc | 古风 |
| 4 | tyzr | 太乙真人 |
| 5 | zxx | 周星驰风格 |
| 6 | karpathy | 英文科技讲解 |
| 7 | **自定义** | 用户提供 `--voice-files` 与 `--prompt-texts`（可多对） |

用户选中内置项后：Agent 读取对应 `{name}.ext` 与 `{name}.txt`（或 `dubbing.conf.example` 中 `[内置音频:{name}]` 的 `text`），作为 `--voice-files` / `--prompt-texts`。

用户选「自定义」时：收集参考音频路径及**该段音频对应的原文**；多参考音须成对提供。

### 3. 选择克隆引擎

向用户展示可用 **TTS 克隆引擎**，请其选择一项（用户未指定时默认 **IndexTTS2**）：

| # | 显示名 | `--tts-engine` | Conda 环境 | 特点 |
| --- | --- | --- | --- | --- |
| 1 | IndexTTS2（默认） | `index_tts2` | `index-tts2` | 推荐；支持情感控制 |
| 2 | Fish Speech | `fish_speech` | `fish-speech` | openaudio-s1-mini |
| 3 | F5-TTS | `f5_tts` | `f5-tts` | 轻量基线 |
| 4 | CosyVoice | `cosy_voice` | `cosyvoice` | Fun-CosyVoice3 |

用户选定后：记录 `--tts-engine` 值及需 `conda activate` 的环境名。环境或模型未安装时，引导运行对应 `install-*.sh`（见 [reference.md](reference.md#引擎与环境)）。

选 **IndexTTS2** 时，可额外询问 `--emotion-text`（默认「平静」）与 `--emotion-alpha`（默认 `0.5`）。

### 4. 执行配音

**执行顺序固定为：`cd` → `conda activate` → `python ai_dubbing/run_dubbing.py`**。禁止跳过 `cd`。

```bash
cd "<REPO_ROOT>"
conda activate <步骤3所选环境>

python ai_dubbing/run_dubbing.py \
  --input-file "<用户字幕路径>" \
  --output-file "<输出路径，如 output/dubbed.wav>" \
  --tts-engine <步骤3所选引擎> \
  --voice-files "<参考音频1>" ["<参考音频2>" ...] \
  --prompt-texts "<参考文本1>" ["<参考文本2>" ...]
```

路径说明：

- `--input-file` / `--output-file`：可用绝对路径，或**相对于 `<REPO_ROOT>`** 的相对路径（如 `output/dubbed.wav`）
- `--voice-files`：内置参考音用 `resources/reference_voices/...`（相对 `<REPO_ROOT>`）

用户选内置 **mcs** 且未改参考音时，可省略 `--voice-files` / `--prompt-texts`（CLI 默认即 mcs）；其余内置项或自定义须显式传入。

Agent 必须在终端**实际执行**上述命令并等待结束，勿在未跑完时编造输出文件。长任务可能持续较久；只向用户摘要进度。

### 5. 交付结果

- 确认命令 exit 0，且 `--output-file` 指向的 WAV **存在且非空**
- 将**输出音频路径**交给用户，并简要说明所用参考音、引擎与策略
- 勿把完整运行日志灌回对话；失败时见 [reference.md](reference.md#故障排查)

## 安全与边界

- **不要**编辑源码，仅执行声音克隆命令，生成音频
- 长字幕和长文本音频克隆可能数分甚至几个小时；用终端跑命令并汇报进度摘要，勿同步阻塞编造结果
- 安装/下载模型：`./install-<engine>.sh`（需用户网络与 GPU 环境）

## 内置参考音

成对存放于 `resources/reference_voices/{name}.{ext}` + `{name}.txt`，供步骤 2 向用户展示选项。

## 延伸阅读

- 引擎表、安装、配置、故障排查：[reference.md](reference.md)
- 人类可读完整文档：[README.md](../../README.md)
