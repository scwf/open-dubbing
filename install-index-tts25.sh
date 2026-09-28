#!/bin/bash
set -e

# --- Configuration ---
CONDA_ENV_NAME="index-tts25"
PYTHON_VERSION="3.10"
INDEX_TTS25_MODEL="IndexTeam/IndexTTS-2.5"
DEPS_DIR="deps"
INDEX_TTS25_DIR="${DEPS_DIR}/index-tts-2.5"
MODEL_CACHE_DIR="models"
MODEL_DIR="${MODEL_CACHE_DIR}/IndexTTS-2.5"

# Get the absolute path of the project directory
PROJECT_DIR=$(pwd)

# --- Helper Functions ---
print_info() {
    echo " "
    echo "======================================================================="
    echo "=> $1"
    echo "======================================================================="
    echo " "
}

ensure_submodule() {
    local submodule_path="$1"
    git submodule update --init --recursive "${submodule_path}"
}

# --- Main Script ---

# 1. Check for Conda
if ! command -v conda &> /dev/null; then
    echo "Error: Conda is not installed or not in your PATH. Please install Conda first."
    exit 1
fi

# 2. Create and Activate Conda Environment
print_info "Setting up Conda environment: ${CONDA_ENV_NAME}"
if ! conda env list | grep -q "${CONDA_ENV_NAME}"; then
    conda create -n "${CONDA_ENV_NAME}" python=${PYTHON_VERSION} -y
fi

# Activate the environment for the rest of the script
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate "${CONDA_ENV_NAME}"

# 3. Install Dependencies
print_info "Installing dependencies..."
conda install -c conda-forge ffmpeg -y
pip install -r requirements.txt
# 未钉版本的 fastapi 会拉到 Starlette 1.x，和当前模板渲染不兼容。
pip install 'fastapi==0.116.1' 'python-multipart'
pip install torch==2.8.0 torchaudio==2.8.0 --index-url https://download.pytorch.org/whl/cu128
pip install huggingface-hub

# 4. Initialize and Install IndexTTS-2.5
print_info "Preparing and installing IndexTTS-2.5 engine..."
mkdir -p "${DEPS_DIR}"
ensure_submodule "${INDEX_TTS25_DIR}"
cd "${INDEX_TTS25_DIR}"
pip install -e .
cd "${PROJECT_DIR}"

# 5. Download IndexTTS-2.5 Model
print_info "Downloading IndexTTS-2.5 model..."
if [ -f "${MODEL_DIR}/config.yaml" ]; then
    echo "Model directory already exists. Skipping download."
else
    huggingface-cli download "${INDEX_TTS25_MODEL}" --local-dir "${MODEL_DIR}"
fi

# 6. Installation Complete
print_info "IndexTTS-2.5 installation completed successfully!"
echo " "
echo "IndexTTS-2 remains available in the index-tts2 environment."
echo "To start the Web UI server with IndexTTS-2.5, run:"
echo "  conda activate ${CONDA_ENV_NAME}"
echo "  python server.py"
echo " "
echo "The CLI and Web UI default to index_tts25."
echo " "
