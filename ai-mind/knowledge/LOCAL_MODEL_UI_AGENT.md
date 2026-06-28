# HDS6 Local Model UI Agent

**Version**: 1.0  
**Created**: May 8, 2026  
**Purpose**: Interactive UI for local AI models (LM Studio, Ollama, etc.)

---

## Overview

The HDS6 Local Model UI Agent is a desktop application for interacting with local AI models running on:
- **LM Studio** (Recommended for Qwen Coder 14b)
- **Ollama** (For Qwen and other models)
- Custom local model servers

### Key Features

✅ **Server Configuration**
- Select server type (LM Studio, Ollama, custom)
- Auto-populate correct URLs
- Real-time connection status

✅ **Model Management**
- Auto-discover available models
- Refresh model list
- Select active model

✅ **Interactive Query Interface**
- Text input for prompts
- Real-time responses
- Code generation support

✅ **Text-to-Speech**
- Optional TTS output (British voices)
- VOX integration
- Configurable

✅ **Terminal/Logging**
- Real-time activity log
- Error reporting
- Performance metrics

---

## Installation & Setup

### Prerequisites

```bash
# 1. Python 3.8+
python3 --version

# 2. Required packages (usually pre-installed)
pip3 install requests

# 3. LM Studio OR Ollama installed locally
```

### Option A: LM Studio (Recommended for Qwen Coder 14b)

**Installation:**
1. Download: https://lmstudio.ai
2. Install and launch LM Studio
3. Load "qwen-coder-14b" model
4. Click "Start Server"
5. Should run on `http://localhost:1234/v1`

**Verify:**
```bash
curl -s http://localhost:1234/v1/models | python3 -m json.tool | head -10
```

### Option B: Ollama

**Installation:**
```bash
# macOS
brew install ollama

# Linux/Windows
# Download from https://ollama.ai

# Pull Qwen model
ollama pull qwen:14b

# Start server
ollama serve
```

**Verify:**
```bash
curl -s http://localhost:11434/api/tags | python3 -m json.tool
```

---

## Running the UI Agent

### Method 1: Launch Script (Easiest)

```bash
cd HDS6
./agent/run_ui_agent.sh
```

### Method 2: Direct Python

```bash
cd HDS6
python3 agent/local_model_ui_agent.py
```

### Method 3: From anywhere

```bash
python3 /path/to/HDS6/agent/local_model_ui_agent.py
```

---

## User Interface Walkthrough

### 1. Server Configuration Panel (Top)

```
Server Type: [LM Studio ▼]     Server URL: http://localhost:1234/v1    [Connect] ● Connected
```

- **Server Type**: Select LM Studio, Ollama, or Custom
- **Server URL**: Auto-populated based on selection (editable)
- **Connect Button**: Establish connection to server
- **Status**: Green ● = Connected | Red ● = Disconnected

**Quick Setup:**
1. Select "LM Studio" or "Ollama"
2. Click "Connect"
3. Should show "✓ Connected to [Server Name]" in terminal

### 2. Model Selection Panel

```
Available Models: [qwen-coder-14b ▼]    [Refresh Models]    ☐ Enable TTS
```

- **Model Dropdown**: Choose which model to use
- **Refresh Models**: Re-query server for available models
- **Enable TTS**: Check to enable voice output (optional)

**First Time:**
1. After connecting, click "Refresh Models"
2. Should populate dropdown with loaded models
3. Select the model you want to use

### 3. Query Panel (Left Side)

```
Prompt:
[Text area for your query]
[Send Query]  [Clear]
```

- **Enter your prompt/code request here**
- Click "Send Query" to process
- "Clear" to reset text

**Examples:**
```
Write a Python function to calculate factorial

def factorial(
```

```
Explain this code:

def hello():
    return "world"
```

### 4. Response Panel (Right Side)

```
Response:
[Model's generated output/response displays here]
```

- **Read-only text area**
- Shows model's response
- Auto-scrolls to end
- Can be copied/selected

### 5. Terminal/Logs Panel (Bottom)

```
[Timestamp] Message
[HH:MM:SS] Connecting to server...
[HH:MM:SS] ✓ Connected to LM Studio
[HH:MM:SS] Fetching available models...
[HH:MM:SS] Found 1 model(s): qwen-coder-14b
[HH:MM:SS] Sending query to qwen-coder-14b...
[HH:MM:SS] ✓ Query completed
```

- **Real-time activity log**
- Shows connections, errors, completions
- Can be cleared with "Clear Terminal" button

---

## Testing with Qwen Coder 14b

### Automated Test Script

```bash
cd HDS6

# Test against LM Studio (default)
python3 agent/test_lm_studio_qwen.py

# Test against Ollama
python3 agent/test_lm_studio_qwen.py http://localhost:11434
```

### What It Tests

1. **Connection Check**: Verifies server is running
2. **Model List**: Lists available models
3. **Code Generation**: Generates 3 code snippets
   - Fibonacci function
   - Palindrome checker
   - Max element finder
4. **Code Analysis**: Analyzes generated code

### Expected Output

```
============================================================
HDS6 - Qwen Coder 14b on LM Studio Test Suite
Time: 2026-05-08 23:30:45
============================================================

[1/4] Checking LM Studio connection...
✓ Connected to LM Studio

[2/4] Available models:
  • qwen-coder-14b

[3/4] Testing code generation...
  [1/3] Write a Python function to calculate fibonacci...
✓ Generation successful!
  Time: 45.23s
  Tokens: ~287

Generated Code:
------------------------------------------------------------
def fibonacci(n):
    if n <= 1:
        return n
    return fibonacci(n-1) + fibonacci(n-2)
------------------------------------------------------------

✓ All tests PASSED!
  Average generation time: 45.23s
```

---

## Performance Characteristics

### Qwen Coder 14b on LM Studio

**System Requirements:**
- GPU: NVIDIA RTX 3060 or better (24GB VRAM recommended)
- CPU: Fallback to CPU possible (slow)
- RAM: 16GB minimum

**Performance:**
```
Prompt Length  | Generation Time | Tokens Generated | Quality
───────────────┼─────────────────┼──────────────────┼─────────
Short (50 chars)  |  20-30s     |  100-200         |  Good
Medium (200 chars)|  30-60s     |  200-500         |  Excellent
Long (500 chars)  |  60-120s    |  500-2000        |  Excellent
```

**Optimization Tips:**
- Keep prompts concise
- Use GPU for faster generation
- Set temperature to 0.3 for code (more consistent)
- Use temperature 0.5-0.8 for analysis/explanation

---

## Troubleshooting

### Problem: "Cannot reach localhost:1234"

**Solution:**
```bash
# 1. Check if LM Studio is running
curl -s http://localhost:1234/v1/models

# 2. Start LM Studio server
# In LM Studio UI: Click "Start Server"

# 3. Verify server is running
lsof -i :1234  # Should show node.js process

# 4. Try different port
# Change URL in UI to http://localhost:XXXX/v1
```

### Problem: "No models found"

**Solution:**
```bash
# 1. Load a model in LM Studio
# In LM Studio: Select model → Load

# 2. Start the server
# Click "Start Server" in LM Studio

# 3. Refresh in UI
# Click "Refresh Models" button
```

### Problem: "Query timeout (>300s)"

**Causes:**
- Model is generating very long output
- GPU memory is exhausted
- System is overloaded

**Solutions:**
- Reduce max_tokens in settings
- Close other applications
- Restart LM Studio
- Use smaller model

### Problem: TTS not working

**Solution:**
```bash
# 1. Install required packages
pip3 install edge-tts pygame

# 2. Check audio output
# Play test sound: python3 -c "import pygame; pygame.mixer.init()"

# 3. Enable TTS in UI
# Check "Enable TTS" checkbox
```

---

## Advanced Configuration

### Modify Server Settings

Edit `ai-mind/config/ai_providers.json`:

```json
{
  "providers": [
    {
      "provider_id": "lm_studio",
      "framework": "lms",
      "config": {
        "base_url": "http://localhost:1234/v1",
        "timeout": 300,
        "max_tokens": 2000
      },
      "enabled": true
    }
  ]
}
```

### Change Model Parameters

In `agent/local_model_ui_agent.py`, line ~250:

```python
json={
    "prompt": query,
    "max_tokens": 2000,      # ← Change this
    "temperature": 0.3,      # ← Or this
    "top_p": 0.95,          # ← Or this
    "top_k": 40             # ← Or this
}
```

Lower values = more consistent  
Higher values = more creative

---

## Use Cases

### 1. Quick Code Generation

```
Prompt: Write a function to validate email addresses

Result: Qwen generates working email validator in Python
```

### 2. Code Review

```
Prompt: Review this code for bugs:

<your code>

Result: Qwen provides feedback and improvements
```

### 3. Learning

```
Prompt: Explain how REST APIs work

Result: Clear explanation with code examples
```

### 4. Problem Solving

```
Prompt: How do I sort a list of dictionaries by key?

Result: Solution with multiple examples
```

---

## Integration with HDS6

### Using Generated Code in Pipeline

```python
from agent.ai_driver_pipeline import AIDriverPipeline, PipelineTask

pipeline = AIDriverPipeline()
pipeline.start()

task = PipelineTask(
    id='generated_001',
    name='Generate python function',
    description='Write fibonacci function',
    script_content='def fibonacci(',
    priority=TaskPriority.HIGH
)

pipeline.add_task(task)

# Generated code saved to:
# ai-mind/tasks/active/generated_001_generated.py
```

### Chaining Tasks

UI Agent Output → Save to file → Load in pipeline → Execute

---

## Security & Privacy

✅ **All processing is local**
- No data sent to cloud
- No API calls (except to your local server)
- Fully private

⚠️ **Keep LM Studio secure**
- Only expose on localhost
- Don't open port 1234 to internet
- Use firewall rules if needed

---

## Tips & Tricks

### 1. Code Generation Tips

**DO:**
- Be specific in prompts
- Provide context
- Ask for explanations

**DON'T:**
- Use vague requests
- Ask for huge functions (>500 lines)
- Expect perfect first-try code

### 2. Performance Tips

- Keep queries under 500 characters
- Use lower temperature for code (0.2-0.3)
- Close unused applications
- Monitor GPU memory usage

### 3. Workflow Tips

- Start with simple queries
- Iterate and refine
- Save good responses
- Create a prompt library

---

## Support & Feedback

**For issues:**
1. Check terminal logs in UI
2. Run `test_lm_studio_qwen.py` to verify setup
3. Check `ai-mind/logs/ui_agent.log`

**Common log messages:**
```
✓ = Success (green)
✗ = Error (red)  
⚠ = Warning (yellow)
```

---

**Status**: ✅ **READY TO USE**

Launch it: `./agent/run_ui_agent.sh`

