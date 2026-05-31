# 字幕配音 — Reference

按需阅读；主流程见 [SKILL.md](SKILL.md)。

## 引擎与环境

| `--tts-engine` | Conda 环境 | 默认模型 | 安装脚本 |
| --- | --- | --- | --- |
| `index_tts2` | `index-tts2` | `IndexTTS-2` | `./install-index-tts2.sh` |
| `fish_speech` | `fish-speech` | `openaudio-s1-mini` | `./install-fish-speech.sh` |
| `f5_tts` | `f5-tts` | `F5TTS_v1_Base` | `./install-f5-tts.sh` |
| `cosy_voice` | `cosyvoice` | `Fun-CosyVoice3-0.5B` | `./install-cosyvoice.sh` |

模型权重目录：`models/`（gitignore，由安装脚本下载）。

## CLI 参数速查

```text
--input-file       SRT 或 TXT（必填）
--output-file      输出 WAV（必填）
--voice-files      参考音频，默认 resources/reference_voices/mcs.mp3
--prompt-texts     参考文本，默认读 mcs.txt；与 voice-files 数量一致
--tts-engine       index_tts2 | fish_speech | f5_tts | cosy_voice
--strategy         stretch | basic；省略则 SRT→stretch，TXT→basic
--emotion-text     IndexTTS2 情感描述，默认「平静」
--emotion-alpha    IndexTTS2 情感强度 0.0–1.0，默认 0.5
```

## 参考音频

目录：`resources/reference_voices/`

| 名称 | 音频 | 用途 |
| --- | --- | --- |
| mcs | mcs.mp3 | CLI 默认 |
| wm1, qjc, tyzr, zxx, karpathy | .wav | 内置示例 |
| wf1–wf7 | .mp3/.wav | 扩展内置示例（见目录） |

## 附属脚本

| 脚本 | 作用 |
| --- | --- |
| `ai_dubbing/run_optimize_subtitles.py` | LLM 优化字幕文本（不合成），主要是长字幕语速过快问题优化 |
| `ai_dubbing/validate_durations.py` | 检查 SRT 条目时长是否合理，识别是否有长字幕语速过快问题 |
| `test-index-tts2.sh` 等 | 引擎冒烟测试 |

## 故障排查

| 现象 | 处理 |
| --- | --- |
| 找不到引擎 / import 失败 | 确认 `conda activate` 与 `--tts-engine` 匹配；重装 `install-*.sh` |
| IndexTTS 重复下载 HF 缓存 | 必须在**仓库根**执行 `run_dubbing.py` |
| submodule 空目录 | `git submodule update --init --recursive` |
| voice/prompt 数量不一致 | `--voice-files` 与 `--prompt-texts` 必须同长度 |

## 结构化错误回报

命令失败时向用户（或上层 Agent）返回：

1. **步骤**：环境检查 / 冒烟 / 正式配音
2. **命令**：实际执行的完整命令
3. **错误类型**：环境缺失 / 参数 / 模型 / GPU / 其他
4. **stderr 摘要**：末 20–30 行
5. **建议**：如运行 `./install-index-tts2.sh` 或 `./test-index-tts2.sh`
