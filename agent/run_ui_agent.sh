#!/bin/bash
# Launch HDS6 Local Model UI Agent

# Check if Python3 is available
if ! command -v python3 &> /dev/null; then
    echo "Error: Python3 is not installed"
    exit 1
fi

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR/.."

echo "🚀 Launching HDS6 Local Model UI Agent..."
echo "   Make sure LM Studio or Ollama is running first!"
echo ""

# Launch the UI agent
python3 agent/local_model_ui_agent.py

