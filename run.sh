#!/bin/bash
set -e

# --- Configuration ---
PROJECT_DIR=$(pwd)
DEPS_DIR="deps"
MODEL_CACHE_DIR="models"

# Available TTS engines
declare -A TTS_ENGINES=(
    ["fish-speech"]="install-fish-speech.sh"
    ["cosyvoice"]="install-cosyvoice.sh"
    ["f5-tts"]="install-f5-tts.sh"
    ["index-tts"]="install-index-tts.sh"
    ["index-tts2"]="install-index-tts2.sh"
)

# Default engine
DEFAULT_ENGINE="fish-speech"

# --- Helper Functions ---
print_info() {
    echo " "
    echo "======================================================================="
    echo "=> $1"
    echo "======================================================================="
    echo " "
}

print_usage() {
    echo "Usage: $0 [ENGINE] [OPTIONS]"
    echo ""
    echo "Available TTS engines:"
    for engine in "${!TTS_ENGINES[@]}"; do
        if [ "$engine" = "$DEFAULT_ENGINE" ]; then
            echo "  $engine (default)"
        else
            echo "  $engine"
        fi
    done
    echo ""
    echo "Options:"
    echo "  --install-only    Only install the engine, don't start the server"
    echo "  --server-only     Only start the server (assume engine is installed)"
    echo "  --force-install   Force reinstall even if engine already exists"
    echo "  --status          Show installation status of all engines"
    echo "  --help, -h        Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0                                # Install and run with default engine (fish-speech)"
    echo "  $0 cosyvoice                      # Install and run with CosyVoice"
    echo "  $0 f5-tts --install-only          # Only install F5-TTS"
    echo "  $0 cosyvoice --force-install      # Force reinstall CosyVoice"
    echo "  $0 --server-only                  # Only start server with current environment"
    echo "  $0 --status                       # Show installation status of all engines"
}

get_engine_env_name() {
    local engine="$1"
    case "$engine" in
        "fish-speech") echo "fish-speech" ;;
        "cosyvoice") echo "cosyvoice" ;;
        "f5-tts") echo "f5-tts" ;;
        "index-tts") echo "index-tts" ;;
        "index-tts2") echo "index-tts2" ;;
        *) echo "unknown" ;;
    esac
}

install_engine() {
    local engine="$1"
    local install_script="${TTS_ENGINES[$engine]}"
    local env_name=$(get_engine_env_name "$engine")
    
    if [ -z "$install_script" ]; then
        echo "Error: Unknown engine '$engine'"
        echo "Available engines: ${!TTS_ENGINES[*]}"
        exit 1
    fi
    
    if [ ! -f "$install_script" ]; then
        echo "Error: Install script '$install_script' not found"
        exit 1
    fi
    
    # Check if engine is already installed (unless force install)
    if conda env list | grep -q "^${env_name}\s" && [ "$FORCE_INSTALL" != true ]; then
        echo " "
        echo "🔍 Engine '$engine' (conda env: $env_name) is already installed."
        read -p "Do you want to reinstall? [y/N]: " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            echo "✅ Skipping installation of '$engine'"
            return 0
        fi
        echo "🔄 Proceeding with reinstallation..."
    elif conda env list | grep -q "^${env_name}\s" && [ "$FORCE_INSTALL" = true ]; then
        echo "🔄 Force reinstalling engine '$engine'..."
    fi
    
    print_info "Installing TTS engine: $engine"
    chmod +x "$install_script"
    bash "$install_script"
}

check_engine_status() {
    local engine="$1"
    local env_name=$(get_engine_env_name "$engine")
    
    if conda env list | grep -q "^${env_name}\s"; then
        echo "✅ $engine (installed)"
    else
        echo "❌ $engine (not installed)"
    fi
}

show_status() {
    print_info "TTS Engine Installation Status"
    for engine in "${!TTS_ENGINES[@]}"; do
        check_engine_status "$engine"
    done
}

start_server() {
    local engine="$1"
    local env_name=$(get_engine_env_name "$engine")
    
    # Check if conda environment exists
    if ! conda env list | grep -q "^${env_name}\s"; then
        echo "Error: Conda environment '$env_name' not found."
        echo "Please install the engine first: $0 $engine --install-only"
        exit 1
    fi
    
    # Activate the environment
    source "$(conda info --base)/etc/profile.d/conda.sh"
    conda activate "$env_name"
    
    print_info "Starting the Web UI server with $engine engine..."
    echo " "
    echo "Server is running at http://127.0.0.1:8000"
    echo "Press Ctrl+C to stop the server."
    echo " "
    python server.py
}

# --- Main Script ---

# Parse command line arguments
ENGINE="$DEFAULT_ENGINE"
INSTALL_ONLY=false
SERVER_ONLY=false
SHOW_STATUS=false
FORCE_INSTALL=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --help|-h)
            print_usage
            exit 0
            ;;
        --install-only)
            INSTALL_ONLY=true
            shift
            ;;
        --server-only)
            SERVER_ONLY=true
            shift
            ;;
        --force-install)
            FORCE_INSTALL=true
            shift
            ;;
        --status)
            SHOW_STATUS=true
            shift
            ;;
        -*)
            echo "Error: Unknown option $1"
            print_usage
            exit 1
            ;;
        *)
            if [[ -n "${TTS_ENGINES[$1]}" ]]; then
                ENGINE="$1"
            else
                echo "Error: Unknown engine '$1'"
                print_usage
                exit 1
            fi
            shift
            ;;
    esac
done

# Check for Conda
if ! command -v conda &> /dev/null; then
    echo "Error: Conda is not installed or not in your PATH. Please install Conda first."
    exit 1
fi

# Execute based on options
if [ "$SHOW_STATUS" = true ]; then
    show_status
elif [ "$SERVER_ONLY" = true ]; then
    start_server "$ENGINE"
elif [ "$INSTALL_ONLY" = true ]; then
    install_engine "$ENGINE"
else
    # Install and start server
    install_engine "$ENGINE"
    start_server "$ENGINE"
fi
