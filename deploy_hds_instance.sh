#!/bin/bash
# deploy_hds_instance.sh
# Deploy an HDS instance for a specific AI system
# Usage: bash deploy_hds_instance.sh "GPT-4" --auto-kill --audio

set -e

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ $# -lt 1 ]; then
    cat << 'EOF'
Deploy HDS Instance for External AI System

Usage:
  bash deploy_hds_instance.sh <ai_name> [options]

Arguments:
  <ai_name>           Name of AI system (GPT-4, Claude, Llama, etc.)

Options:
  --auto-kill         Kill conflicting processes on startup
  --audio             Enable audio notifications (default: silent)
  --silent            Disable audio notifications
  --once              Run single cycle and exit
  --monitor           Run continuously (default)

Examples:
  # Deploy for GPT-4 with automatic conflict resolution
  bash deploy_hds_instance.sh "GPT-4" --auto-kill --audio --monitor

  # Deploy for Claude in silent mode
  bash deploy_hds_instance.sh "Claude" --silent --monitor

  # Deploy for local testing with audio
  bash deploy_hds_instance.sh "MyAI" --audio --once

EOF
    exit 1
fi

AI_NAME="$1"
shift

# Parse additional arguments
AUTO_KILL=""
AUDIO=""
MODE=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --auto-kill)
            AUTO_KILL="--auto-kill"
            shift
            ;;
        --audio)
            AUDIO="--audio"
            shift
            ;;
        --silent)
            AUDIO="--silent"
            shift
            ;;
        --monitor)
            MODE="--monitor"
            shift
            ;;
        --once)
            MODE="--once"
            shift
            ;;
        *)
            shift
            ;;
    esac
done

# Default to monitor mode if not specified
if [ -z "$MODE" ]; then
    MODE="--monitor"
fi

# Default to silent if not specified
if [ -z "$AUDIO" ]; then
    AUDIO="--silent"
fi

echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║          HDS DEPLOYMENT SERVICE                             ║"
echo "║                                                              ║"
echo "║  Deploying HDS instance for: $AI_NAME"
echo "║                                                              ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# Launch the smart startup with the AI name
bash "$BASE_DIR/start_hds_smart.sh" \
    --ai "$AI_NAME" \
    $AUTO_KILL \
    $AUDIO \
    $MODE

echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║          HDS Instance Shutdown                              ║"
echo "║          (AI System: $AI_NAME)                               ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
