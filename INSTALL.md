# AI Dubbing Tool 配置指导文档

本指南详细介绍如何为不同TTS引擎配置AI配音工具项目环境。

## 支持的TTS引擎

项目目前支持以下开源TTS引擎：
- **IndexTTS** - 工业级可控零样本文本转语音系统
- **F5-TTS** - 基于流匹配的快速TTS系统
- **CosyVoice** - 多语言零样本语音合成器
- **Fish Speech** - 开源多语言TTS，支持语音克隆

## 部署策略概览

根据引擎特性分为两种部署方式：

| 引擎 | 部署方式 | 是否有Wheels | 推荐环境 |
|------|----------|--------------|----------|
| IndexTTS | 源码安装 | ❌ | Conda + 源码 |
| F5-TTS | pip安装 | ✅ | pip + conda |
| CosyVoice | 源码安装 | ❌ | Conda + 源码 |
| Fish Speech | 源码安装 | ❌ | Conda + 源码 |

## 全新配置方式（推荐）

### 1. 环境配置文件

项目使用 `.env` 文件管理TTS引擎路径配置，避免硬编码。

#### 1.1 复制配置文件
```bash
cd ai_dubbing
cp .env.example .env
```

#### 1.2 编辑配置文件
编辑 `ai_dubbing/.env` 文件，设置各引擎的绝对路径：

```bash
# 模型缓存目录（建议设置绝对路径），模型会自动下载到此目录
MODEL_CACHE_DIR=/home/xiaofei/code/open-dubbing/model-dir

# TTS引擎源码目录（建议设置绝对路径）
FISH_SPEECH_DIR=/home/xiaofei/code/fish-speech
INDEX_TTS_DIR=/home/xiaofei/code/index-tts
COSYVOICE_DIR=/home/xiaofei/code/CosyVoice
```

### 2. TTS引擎配置（按需配置）

#### Fish Speech 配置（推荐）

**完整安装步骤：**

```bash
# 1. 创建独立环境
conda create -n fish-speech python=3.10
conda activate fish-speech

# 2. 安装系统依赖
apt-get install ffmpeg
# 或使用conda
conda install -c conda-forge ffmpeg

# 3. 安装Python依赖
pip install librosa numpy soundfile colorama tqdm pysbd python-dotenv
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu118

# 4. 克隆并安装引擎
git clone https://github.com/fishaudio/fish-speech.git
cd fish-speech
pip install -e .

# 5. 更新.env配置
# 编辑 ai_dubbing/.env 文件，设置：
# FISH_SPEECH_DIR=/absolute/path/to/fish-speech

# 6. 模型下载（首次运行自动下载，或手动下载）
huggingface-cli download fishaudio/openaudio-s1-mini \
  --local-dir model-dir/openaudio-s1-mini
```

#### IndexTTS 配置

**完整安装步骤：**

```bash
# 1. 创建独立环境
conda create -n index-tts python=3.10
conda activate index-tts

# 2. 安装系统依赖
apt-get install ffmpeg
# 或使用conda
conda install -c conda-forge ffmpeg

# 3. 安装Python依赖
pip install librosa numpy soundfile colorama tqdm pysbd python-dotenv
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu118

# 4. 克隆并安装引擎
git clone https://github.com/index-tts/index-tts.git
cd index-tts
pip install -e .

# 5. 更新.env配置
# 编辑 ai_dubbing/.env 文件，设置：
# INDEX_TTS_DIR=/absolute/path/to/index-tts

# 6. 模型下载（首次运行自动下载，或手动下载）
huggingface-cli download IndexTeam/IndexTTS-1.5 \
  config.yaml bigvgan_discriminator.pth bigvgan_generator.pth \
  bpe.model dvae.pth gpt.pth unigram_12000.vocab \
  --local-dir model-dir/index_tts
```

#### F5-TTS 配置

**完整安装步骤：**

```bash
# 1. 创建独立环境
conda create -n f5-tts python=3.10
conda activate f5-tts

# 2. 安装系统依赖
apt-get install ffmpeg
# 或使用conda
conda install -c conda-forge ffmpeg

# 3. 安装Python依赖
pip install librosa numpy soundfile colorama tqdm pysbd python-dotenv
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu118

# 4. 安装引擎
pip install f5-tts

# 5. 模型自动下载（首次运行时自动下载到 model-dir/F5TTS_v1_Base/）
```

#### CosyVoice 配置

**完整安装步骤：**

```bash
# 1. 创建独立环境
conda create -n cosyvoice python=3.10
conda activate cosyvoice

# 2. 安装系统依赖
apt-get install ffmpeg sox libsox-dev
# 或使用conda
conda install -c conda-forge ffmpeg

# 3. 安装Python依赖
pip install librosa numpy soundfile colorama tqdm pysbd python-dotenv
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu118

# 4. 克隆并安装引擎
git clone --recursive https://github.com/FunAudioLLM/CosyVoice.git
cd CosyVoice
pip install -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/

# 5. 更新.env配置
# 编辑 ai_dubbing/.env 文件，设置：
# COSYVOICE_DIR=/absolute/path/to/CosyVoice

# 6. 模型下载（首次运行自动下载，或手动下载）
# 使用SDK下载（推荐）
python -c "
from modelscope import snapshot_download
snapshot_download('iic/CosyVoice2-0.5B', local_dir='model-dir/cosyvoice-2-0.5b')
snapshot_download('iic/CosyVoice-300M', local_dir='model-dir/cosyvoice-300m')
snapshot_download('iic/CosyVoice-300M-SFT', local_dir='model-dir/cosyvoice-300m-sft')
snapshot_download('iic/CosyVoice-300M-Instruct', local_dir='model-dir/cosyvoice-300m-instruct')
snapshot_download('iic/CosyVoice-ttsfrd', local_dir='model-dir/cosyvoice-ttsfrd')
"

# 或使用git下载（需安装git-lfs）
git lfs install
git clone https://www.modelscope.cn/iic/CosyVoice2-0.5B.git model-dir/cosyvoice-2-0.5b
```

## 环境使用原则

**重要：每个TTS引擎使用独立的conda环境，激活哪个环境就使用对应的TTS引擎。**

```bash
# 使用Fish Speech引擎（推荐）
conda activate fish-speech

# 使用IndexTTS引擎
conda activate index-tts

# 使用F5-TTS引擎  
conda activate f5-tts

# 使用CosyVoice引擎
conda activate cosyvoice
```