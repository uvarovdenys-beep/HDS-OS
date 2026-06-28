#!/bin/bash
# start_hds_daemons.sh
# HDS Microkernel Daemon Startup
# Запускає Vision і Browser демони для мікроядерної архітектури

set -e

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AGENT_DIR="$BASE_DIR/agent"

echo "═══════════════════════════════════════════════════════════"
echo "  HDS MICROKERNEL DAEMON STARTUP"
echo "═══════════════════════════════════════════════════════════"
echo ""

# Функція для запуску демона з перевіркою портів
start_daemon() {
    local name=$1
    local port=$2
    local script=$3

    # Перевіряємо чи порт уже використовується
    if netstat -tuln 2>/dev/null | grep -q ":$port "; then
        echo "⚠️  Port $port is already in use (likely $name daemon running)"
        return
    fi

    echo "Starting $name Daemon on port $port..."
    cd "$AGENT_DIR"
    python3 "$script" "$port" &
    local pid=$!
    echo "  PID: $pid"

    # Чекаємо що демон стартнув
    sleep 1
    if curl -s http://localhost:$port/health > /dev/null 2>&1; then
        echo "  ✅ $name Daemon is ready!"
    else
        echo "  ⚠️  Could not verify $name Daemon status"
    fi
}

echo ""
echo "Component Status:"
echo "─────────────────────────────────────────────────────────"

# Vision Daemon
if curl -s http://localhost:9001/health > /dev/null 2>&1; then
    echo "✅ Vision Daemon (9001) - RUNNING"
else
    echo "❌ Vision Daemon (9001) - NOT RUNNING"
    start_daemon "Vision" 9001 "vision_daemon.py"
fi

echo ""

# Browser Daemon
if curl -s http://localhost:9002/health > /dev/null 2>&1; then
    echo "✅ Browser Daemon (9002) - RUNNING"
else
    echo "❌ Browser Daemon (9002) - NOT RUNNING"
    start_daemon "Browser" 9002 "browser_daemon.py"
fi

echo ""
echo "═══════════════════════════════════════════════════════════"
echo "All daemons started. Press Ctrl+C to stop."
echo ""
echo "API Endpoints:"
echo "  Vision:  http://localhost:9001"
echo "  Browser: http://localhost:9002"
echo ""
echo "Health Check:"
echo "  curl http://localhost:9001/health"
echo "  curl http://localhost:9002/health"
echo ""
echo "Keeping processes alive..."
echo "═══════════════════════════════════════════════════════════"
echo ""

# Чекаємо на Ctrl+C
wait
