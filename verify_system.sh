#!/bin/bash
# HDS System Verification Script
# Validates all components and dependencies are properly installed

set -e

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$BASE_DIR"

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Counters
PASSED=0
FAILED=0
WARNINGS=0

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

check_command() {
    local cmd=$1
    local friendly_name=$2

    if command -v "$cmd" &> /dev/null; then
        echo -e "${GREEN}✅${NC} $friendly_name is installed"
        ((PASSED++)) || true
    else
        echo -e "${RED}❌${NC} $friendly_name is NOT installed"
        ((FAILED++)) || true
    fi
}

check_python_module() {
    local module=$1
    local friendly_name=$2

    if python3 -c "import $module" 2>/dev/null; then
        echo -e "${GREEN}✅${NC} Python module: $friendly_name"
        ((PASSED++)) || true
    else
        echo -e "${RED}❌${NC} Python module: $friendly_name NOT FOUND"
        ((FAILED++)) || true
    fi
}

check_file() {
    local filepath=$1
    local friendly_name=$2

    if [ -f "$filepath" ]; then
        echo -e "${GREEN}✅${NC} $friendly_name exists"
        ((PASSED++)) || true
    else
        echo -e "${RED}❌${NC} $friendly_name NOT FOUND: $filepath"
        ((FAILED++)) || true
    fi
}

check_directory() {
    local dirpath=$1
    local friendly_name=$2

    if [ -d "$dirpath" ]; then
        echo -e "${GREEN}✅${NC} $friendly_name directory exists"
        ((PASSED++)) || true
    else
        echo -e "${YELLOW}⚠️ ${NC}  $friendly_name directory NOT FOUND: $dirpath"
        ((WARNINGS++)) || true
    fi
}

# ============================================================================
# HEADER
# ============================================================================

echo ""
echo "╔════════════════════════════════════════════════════════════╗"
echo "║          HDS v1.1 SYSTEM VERIFICATION SCRIPT              ║"
echo "║  Checks all dependencies, files, and configurations        ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

# ============================================================================
# SYSTEM REQUIREMENTS
# ============================================================================

echo -e "${BLUE}Phase 1: System Requirements${NC}"
echo "─────────────────────────────────────────────────────────────"

check_command "python3" "Python 3"
check_command "node" "Node.js"
check_command "npm" "NPM"
check_command "git" "Git"

# Check Python version
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
echo -e "  Python version: $PYTHON_VERSION"

echo ""

# ============================================================================
# VISION DAEMON DEPENDENCIES
# ============================================================================

echo -e "${BLUE}Phase 2: Vision Daemon Dependencies${NC}"
echo "─────────────────────────────────────────────────────────────"

check_python_module "cv2" "OpenCV (cv2)"
check_python_module "PIL" "Pillow (PIL)"
check_python_module "pyautogui" "PyAutoGUI"
check_python_module "pytesseract" "Tesseract OCR"
check_python_module "numpy" "NumPy"

# Check Tesseract system binary
if command -v tesseract &> /dev/null; then
    TESSERACT_VERSION=$(tesseract --version 2>&1 | head -n1)
    echo -e "${GREEN}✅${NC} Tesseract system binary: $TESSERACT_VERSION"
    ((PASSED++)) || true
else
    echo -e "${YELLOW}⚠️ ${NC}  Tesseract system binary NOT FOUND"
    echo "     Install with:"
    echo "     macOS: brew install tesseract"
    echo "     Linux: sudo apt-get install tesseract-ocr"
    ((WARNINGS++)) || true
fi

echo ""

# ============================================================================
# BROWSER DAEMON DEPENDENCIES
# ============================================================================

echo -e "${BLUE}Phase 3: Browser Daemon Dependencies${NC}"
echo "─────────────────────────────────────────────────────────────"

check_python_module "playwright" "Playwright"
check_python_module "bs4" "BeautifulSoup4"
check_python_module "html2text" "html2text"

echo ""

# ============================================================================
# CORE PYTHON DEPENDENCIES
# ============================================================================

echo -e "${BLUE}Phase 4: Core Dependencies${NC}"
echo "─────────────────────────────────────────────────────────────"

check_python_module "requests" "Requests"
check_python_module "yaml" "PyYAML"

echo ""

# ============================================================================
# AGENT FILES
# ============================================================================

echo -e "${BLUE}Phase 5: Agent Files${NC}"
echo "─────────────────────────────────────────────────────────────"

check_file "agent/agent.py" "Main Agent (agent.py)"
check_file "agent/vision_daemon.py" "Vision Daemon wrapper"
check_file "agent/vision_daemon_real.py" "Vision Daemon real implementation"
check_file "agent/browser_daemon.py" "Browser Daemon wrapper"
check_file "agent/browser_daemon_real.py" "Browser Daemon real implementation"
check_file "agent/microkernel_ipc.py" "Microkernel IPC"
check_file "agent/port_registry.py" "Port Registry"
check_file "agent/port_checker.py" "Port Checker"

echo ""

# ============================================================================
# DIRECTORY STRUCTURE
# ============================================================================

echo -e "${BLUE}Phase 6: Directory Structure${NC}"
echo "─────────────────────────────────────────────────────────────"

check_directory "agent" "Agent directory"
check_directory "gui" "React GUI directory"
check_directory "ai-mind" "AI-MIND directory"
check_directory "ai-mind/tasks" "Tasks directory"
check_directory "ai-mind/logs" "Logs directory"

echo ""

# ============================================================================
# SCRIPTS
# ============================================================================

echo -e "${BLUE}Phase 7: Startup Scripts${NC}"
echo "─────────────────────────────────────────────────────────────"

check_file "hds_dev_start.sh" "Development launcher"
check_file "start_hds_smart.sh" "Smart startup script"
check_file "verify_system.sh" "System verification (this script)"

echo ""

# ============================================================================
# DOCUMENTATION
# ============================================================================

echo -e "${BLUE}Phase 8: Documentation${NC}"
echo "─────────────────────────────────────────────────────────────"

check_file "REAL_IMPLEMENTATIONS.md" "Real implementations guide"
check_file "FIRST_RUN.md" "First run guide"
check_file "requirements_real.txt" "Dependencies file"

echo ""

# ============================================================================
# PORT CHECKING
# ============================================================================

echo -e "${BLUE}Phase 9: Port Availability${NC}"
echo "─────────────────────────────────────────────────────────────"

check_port_available() {
    local port=$1
    local name=$2

    if ! netstat -tln 2>/dev/null | grep -q ":$port "; then
        echo -e "${GREEN}✅${NC} Port $port ($name) is available"
        ((PASSED++)) || true
    else
        echo -e "${YELLOW}⚠️ ${NC}  Port $port ($name) is in use"
        ((WARNINGS++)) || true
    fi
}

check_port_available 9001 "Vision Daemon"
check_port_available 9002 "Browser Daemon"
check_port_available 8080 "Webhook API"
check_port_available 3000 "React GUI"

echo ""

# ============================================================================
# REACT GUI
# ============================================================================

echo -e "${BLUE}Phase 10: React GUI Setup${NC}"
echo "─────────────────────────────────────────────────────────────"

if [ -d "gui" ]; then
    if [ -d "gui/node_modules" ]; then
        echo -e "${GREEN}✅${NC} React dependencies installed (node_modules found)"
        ((PASSED++)) || true
    else
        echo -e "${YELLOW}⚠️ ${NC}  React dependencies NOT installed"
        echo "     Run: cd gui && npm install"
        ((WARNINGS++)) || true
    fi

    check_file "gui/package.json" "React package.json"
    check_file "gui/vite.config.js" "Vite configuration"
else
    echo -e "${RED}❌${NC} GUI directory not found"
    ((FAILED++)) || true
fi

echo ""

# ============================================================================
# TEST CONNECTIVITY
# ============================================================================

echo -e "${BLUE}Phase 11: Quick Connectivity Tests${NC}"
echo "─────────────────────────────────────────────────────────────"

# Test Python import of key modules
if python3 -c "import sys; sys.path.insert(0, 'agent'); from microkernel_ipc import MicrokernelIPCServer, MicrokernelIPCClient; print('✅ Microkernel IPC imports successful')" 2>/dev/null; then
    ((PASSED++)) || true
else
    echo -e "${RED}❌${NC} Microkernel IPC import failed"
    ((FAILED++)) || true
fi

if python3 -c "from pathlib import Path; print('✅ Path utilities working')" 2>/dev/null; then
    ((PASSED++)) || true
else
    echo -e "${RED}❌${NC} Path utilities import failed"
    ((FAILED++)) || true
fi

echo ""

# ============================================================================
# SUMMARY
# ============================================================================

echo "╔════════════════════════════════════════════════════════════╗"
echo "║                    VERIFICATION SUMMARY                   ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

TOTAL=$((PASSED + FAILED + WARNINGS))

echo -e "  ${GREEN}✅ Passed:${NC}   $PASSED"
echo -e "  ${YELLOW}⚠️  Warnings:${NC} $WARNINGS"
echo -e "  ${RED}❌ Failed:${NC}   $FAILED"
echo ""
echo "  Total checks: $TOTAL"
echo ""

# ============================================================================
# NEXT STEPS
# ============================================================================

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}✅ System is ready!${NC}"
    echo ""
    echo "Next steps:"
    echo ""
    echo "1. Install Python dependencies:"
    echo "   ${BLUE}pip install -r requirements_real.txt${NC}"
    echo ""
    echo "2. Install Playwright browsers:"
    echo "   ${BLUE}playwright install chromium${NC}"
    echo ""
    echo "3. Start the complete system:"
    echo "   ${BLUE}bash hds_dev_start.sh${NC}"
    echo ""
else
    echo -e "${RED}⚠️  System has $FAILED missing component(s)${NC}"
    echo ""
    echo "Please install missing dependencies and try again."
    echo ""
fi

if [ $WARNINGS -gt 0 ]; then
    echo -e "${YELLOW}Note: There are $WARNINGS warning(s) to address.${NC}"
    echo "Check the output above for details."
    echo ""
fi

# Level-3 guard: single write path — no raw writes past scribe
echo ""
echo "Checking write-path integrity (Level-3)..."
if python3 write_path_audit.py; then
    PASSED=$((PASSED + 1))
else
    echo -e "${RED}✗ New write path past scribe detected${NC}"
    FAILED=$((FAILED + 1))
fi

echo "═══════════════════════════════════════════════════════════"
echo ""

# Exit with error if there are failures
if [ $FAILED -gt 0 ]; then
    exit 1
else
    exit 0
fi
