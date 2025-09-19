# TTS 引擎使用指南

这个项目支持多个 TTS (Text-to-Speech) 引擎。使用 `run.sh` 脚本可以轻松切换和管理不同的引擎。

## 支持的 TTS 引擎

| 引擎名称 | 安装脚本 | Conda 环境名 | 描述 |
|---------|----------|-------------|-----|
| fish-speech | install-fish-speech.sh | fish-speech | 默认引擎，高质量语音合成 |
| cosyvoice | install-cosyvoice.sh | cosyvoice | 阿里开源的语音合成引擎 |
| f5-tts | install-f5-tts.sh | f5-tts | F5-TTS 语音合成引擎 |
| index-tts | install-index-tts.sh | index-tts | Index TTS 引擎 |
| index-tts2 | install-index-tts2.sh | index-tts2 | Index TTS 2.0 引擎 |

## 基本用法

### 查看帮助信息
```bash
./run.sh --help
```

### 查看引擎安装状态
```bash
./run.sh --status
```

### 使用默认引擎 (fish-speech)
```bash
./run.sh
```

### 使用特定引擎
```bash
./run.sh cosyvoice        # 安装并运行 CosyVoice
./run.sh f5-tts           # 安装并运行 F5-TTS
./run.sh index-tts        # 安装并运行 Index TTS
```

## 高级选项

### 只安装引擎（不启动服务器）
```bash
./run.sh cosyvoice --install-only
./run.sh f5-tts --install-only
```

### 只启动服务器（假设引擎已安装）
```bash
./run.sh cosyvoice --server-only
./run.sh fish-speech --server-only
```

## 引擎切换流程

1. **查看当前状态**：
   ```bash
   ./run.sh --status
   ```

2. **安装新引擎**：
   ```bash
   ./run.sh [engine-name] --install-only
   ```

3. **启动服务器**：
   ```bash
   ./run.sh [engine-name] --server-only
   ```

## 故障排除

### 常见问题

1. **Conda 环境未找到**：
   ```
   Error: Conda environment 'xxx' not found.
   ```
   解决方案：运行 `./run.sh [engine] --install-only` 重新安装

2. **安装脚本不存在**：
   ```
   Error: Install script 'xxx' not found
   ```
   解决方案：确保对应的 `install-*.sh` 文件存在

3. **权限问题**：
   ```bash
   chmod +x run.sh
   chmod +x install-*.sh
   ```

### 环境管理

每个 TTS 引擎都有独立的 Conda 环境：

- 查看所有环境：`conda env list`
- 手动激活环境：`conda activate [env-name]`
- 删除环境：`conda env remove -n [env-name]`

## 开发者指南

### 添加新引擎

1. 创建新的安装脚本 `install-[engine-name].sh`
2. 在 `run.sh` 中的 `TTS_ENGINES` 数组添加新条目
3. 在 `get_engine_env_name()` 函数中添加环境名映射
4. 更新本文档

### 脚本结构

```bash
run.sh
├── 配置部分（引擎列表、默认设置）
├── 辅助函数
│   ├── print_info()      # 信息显示
│   ├── print_usage()     # 帮助信息
│   ├── get_engine_env_name() # 环境名映射
│   ├── install_engine()  # 引擎安装
│   ├── check_engine_status() # 状态检查
│   ├── show_status()     # 状态显示
│   └── start_server()    # 服务器启动
└── 主逻辑（参数解析和执行）
```

## 注意事项

1. 确保安装了 Conda
2. 每个引擎需要独立的安装时间和磁盘空间
3. 不同引擎可能有不同的依赖要求
4. 建议在切换引擎前先停止当前服务器
