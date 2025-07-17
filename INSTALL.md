# SRT Dubbing 配置指导文档

本指南详细介绍如何为不同TTS引擎配置srt_dubbing项目环境。

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

现在使用 `.env` 文件统一管理所有路径配置，无需手动修改代码。

#### 1.1 复制配置文件
```bash
cd /path/to/srt_dubbing
cp .env.example .env
```

#### 1.2 编辑配置文件
编辑 `.env` 文件，根据实际路径修改：

```bash
# 项目根目录
PROJECT_ROOT=/home/xiaofei/code/index-tts

# 模型缓存目录
MODEL_CACHE_DIR=model-dir

# TTS引擎源码目录
FISH_SPEECH_DIR=${PROJECT_ROOT}/fish-speech
INDEX_TTS_DIR=${PROJECT_ROOT}/index-tts
COSYVOICE_DIR=${PROJECT_ROOT}/CosyVoice

# 模型目录（自动下载或手动放置）
FISH_SPEECH_MODEL=${MODEL_CACHE_DIR}/openaudio-s1-mini
INDEX_TTS_MODEL=${MODEL_CACHE_DIR}/index_tts
F5_TTS_MODEL=${MODEL_CACHE_DIR}/F5TTS_v1_Base
COSYVOICE_MODEL=${MODEL_CACHE_DIR}/cosyvoice-2-0.5b

# 输出目录
OUTPUT_DIR=output
```

### 2. 环境配置

#### 2.1 安装依赖
```bash
# 安装python-dotenv
pip install python-dotenv
```

#### 2.2 通用创建环境流程
每个引擎的环境创建步骤相同：

```bash
# 以fish-speech为例
conda create -n fish-speech python=3.10
conda activate fish-speech

# 安装系统依赖
apt-get install ffmpeg
# 或使用conda
conda install -c conda-forge ffmpeg

# 安装音频处理依赖
pip install librosa numpy soundfile

# 安装日志依赖
pip install colorama tqdm

# 安装分句依赖包
pip install pysbd

# 安装python-dotenv
pip install python-dotenv

# 安装PyTorch（请根据你的CUDA版本选择合适的指令）
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu118
```

### 3. TTS引擎配置（按需配置）

#### Fish Speech 配置（推荐）

##### 克隆源码
```bash
git clone https://github.com/fishaudio/fish-speech.git
```

##### 安装引擎
```bash
cd fish-speech
pip install -e .
```

##### 模型下载
```bash
# 首次运行时会自动下载模型到 model-dir/openaudio-s1-mini/
# 如需手动下载：
huggingface-cli download fishaudio/openaudio-s1-mini \
  --local-dir model-dir/openaudio-s1-mini
```

#### IndexTTS 配置

##### 克隆源码
```bash
git clone https://github.com/index-tts/index-tts.git
```

##### 安装引擎
```bash
cd index-tts
pip install -e .
```

##### 模型下载
```bash
# 首次运行时会自动下载模型到 model-dir/index_tts/
# 如需手动下载：
huggingface-cli download IndexTeam/IndexTTS-1.5 \
  config.yaml bigvgan_discriminator.pth bigvgan_generator.pth \
  bpe.model dvae.pth gpt.pth unigram_12000.vocab \
  --local-dir model-dir/index_tts
```

#### F5-TTS 配置

##### 安装引擎
```bash
pip install f5-tts
```

##### 模型下载
```bash
# 首次运行时会自动下载模型到 model-dir/F5TTS_v1_Base/
```

#### CosyVoice 配置

##### 克隆源码
```bash
git clone --recursive https://github.com/FunAudioLLM/CosyVoice.git
```

##### 安装引擎
```bash
cd CosyVoice
pip install -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/
sudo apt-get install sox libsox-dev
```

##### 模型下载
```bash
# 首次运行时会自动下载模型到 model-dir/cosyvoice-2-0.5b/
# 如需手动下载：

# 使用SDK下载（推荐）
python -c "
from modelscope import snapshot_download
snapshot_download('iic/CosyVoice2-0.5B', local_dir='model-dir/cosyvoice-2-0.5b')
snapshot_download('iic/CosyVoice-300M', local_dir='model-dir/cosyvoice-300m')
snapshot_download('iic/CosyVoice-300M-SFT', local_dir='model-dir/cosyvoice-300m-sft')
snapshot_download('iic/CosyVoice-300M-Instruct', local_dir='model-dir/cosyvoice-300m-instruct')
snapshot_download('iic/CosyVoice-ttsfrd', local_dir='model-dir/cosyvoice-ttsfrd')
"

# 使用git下载（需安装git-lfs）
git lfs install
git clone https://www.modelscope.cn/iic/CosyVoice2-0.5B.git model-dir/cosyvoice-2-0.5b
git clone https://www.modelscope.cn/iic/CosyVoice-300M.git model-dir/cosyvoice-300m
git clone https://www.modelscope.cn/iic/CosyVoice-300M-SFT.git model-dir/cosyvoice-300m-sft
git clone https://www.modelscope.cn/iic/CosyVoice-300M-Instruct.git model-dir/cosyvoice-300m-instruct
git clone https://www.modelscope.cn/iic/CosyVoice-ttsfrd.git model-dir/cosyvoice-ttsfrd

# 可选：安装ttsfrd包以获得更好的文本标准化性能
# cd model-dir/cosyvoice-ttsfrd/
# unzip resource.zip -d .
# pip install ttsfrd_dependency-0.1-py3-none-any.whl
# pip install ttsfrd-0.4.2-cp310-cp310-linux_x86_64.whl
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