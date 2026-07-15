# HDS6 OS AI Components Guide
**Comprehensive guide for AI-DRIVER, British TTS, Web Analysis, Vision Controller, and Request Optimization**

---

## 🏛 System Overview

HDS6 OS now includes advanced AI components for autonomous operation:

### Core Components
- **AI-DRIVER Pipeline** - Autonomous task execution without user waiting
- **British TTS Edge** - High-quality British English voice synthesis
- **Web Analysis Plugin** - Local AI-powered web content analysis
- **AI Vision Controller** - Computer vision and application control
- **Minimized Request Window** - AI request optimization for reduced token usage
- **HDS6 OS Integration** - Unified system management

---

## 🚀 AI-DRIVER Pipeline

### Purpose
Continuous task processing without requiring user interaction. Supports Qwen Coder and other AI models.

### Key Features
- Priority-based task queue
- Automatic retry mechanism
- Dependency resolution
- Parallel execution (3 workers by default)
- Integration with existing HDS6 task system

### Usage

#### Start Pipeline
```bash
cd HDS6/agent
python ai_driver_pipeline.py --start --workers 3
```

#### Add Task Programmatically
```python
from agent.ai_driver_pipeline import AIDriverPipeline, PipelineTask, TaskPriority

pipeline = AIDriverPipeline()
pipeline.start()

# Create task
task = PipelineTask(
    id="task_001",
    name="Data Processing",
    description="Process dataset and generate report",
    script_content="""
import pandas as pd
# Your processing code here
print("Processing complete")
""",
    priority=TaskPriority.HIGH,
    max_retries=3
)

pipeline.add_task(task)
```

#### Load Tasks from JSON
```json
{
  "tasks": [
    {
      "id": "web_scrape_001",
      "name": "Web Scraping Task",
      "description": "Scrape data from website",
      "script_path": "ai-mind/tasks/active/scrape_data.py",
      "priority": "HIGH",
      "max_retries": 3
    }
  ]
}
```

```bash
python ai_driver_pipeline.py --load tasks.json --start
```

#### Monitor Status
```bash
python ai_driver_pipeline.py --status
```

---

## 🎤 British TTS Edge Integration

### Purpose
High-quality British English text-to-speech using Microsoft Edge TTS for PowerVox notifications.

### Available Voices
- **Female**: Sonia (professional), Hazel (warm), Libby (youthful)
- **Male**: Ryan (natural), George (authoritative)

### Configuration
Update `ai-mind/knowledge/hds6-config.json`:
```json
{
  "speech": {
    "enabled": true,
    "voice": "sonia",
    "language": "en-GB",
    "volume": 0.8,
    "speed": 1.0
  }
}
```

### Usage

#### Direct Speech
```python
from agent.british_tts_edge import BritishTTSEdge

tts = BritishTTSEdge(voice="sonia", volume=0.8)
tts.start_playback()
tts.speak("Hello, I am your British AI assistant.")
tts.wait_until_done()
tts.stop_playback()
```

#### PowerVox Integration
```python
from agent.british_tts_edge import PowerVoxBritishTTS

vox_tts = PowerVoxBritishTTS()
vox_tts.speak("System operational", "INFO")
```

#### Test TTS
```bash
python british_tts_edge.py --test
python british_tts_edge.py --voice "sonia" --text "Testing British TTS"
```

#### Install Dependencies
```bash
pip install edge-tts pygame
```

---

## 🌐 Web Analysis Plugin

### Purpose
Local AI-powered web content analysis without external API calls.

### Features
- Article extraction and summarization
- Credibility assessment
- Sentiment analysis
- Keyword extraction
- Content caching
- Batch processing

### Usage

#### Start Plugin
```bash
python web_analysis_plugin.py --start --workers 2
```

#### Single URL Analysis
```bash
python web_analysis_plugin.py --analyze "https://example.com/article" --type "all"
```

#### Programmatic Usage
```python
from agent.web_analysis_plugin import WebAnalysisPlugin, AnalysisRequest

plugin = WebAnalysisPlugin()
plugin.start()

request = AnalysisRequest(
    id="analysis_001",
    url="https://example.com/article",
    analysis_type="content",  # content, sentiment, credibility, all
    callback="task_001"  # Optional callback task
)

plugin.add_request(request)
```

#### Get Results
```python
result = plugin.get_result("analysis_001")
if result:
    print(f"Title: {result.title}")
    print(f"Summary: {result.summary}")
    print(f"Credibility: {result.credibility_score}")
```

#### Install Dependencies
```bash
pip install aiohttp beautifulsoup4 newspaper3k
```

---

## 👁️ AI Vision Controller

### Purpose
Computer vision and automated application control through mouse and keyboard.

### Features
- Screen capture and analysis
- Text recognition (OCR)
- Template matching for UI elements
- Mouse and keyboard automation
- Safety mechanisms (safe mode by default)

### Usage

#### Start Controller
```bash
python ai_vision_controller.py --start --safe-mode
```

#### Find and Click Elements
```python
from agent.ai_vision_controller import AIVisionController, VisionAction, ActionType

controller = AIVisionController(safe_mode=True)
controller.start_processing()

# Find text and click
action = VisionAction(
    id="click_submit",
    action_type=ActionType.CLICK,
    description="Click submit button",
    target="Submit"  # Text to find on screen
)

controller.add_action(action)
```

#### Take Screenshot
```bash
python ai_vision_controller.py --screenshot
```

#### Find Text on Screen
```bash
python ai_vision_controller.py --find-text "Login"
```

#### Safety Features
- **Safe Mode**: Logs actions instead of executing (default)
- **Emergency Stop**: `Ctrl+C` or programmatic stop
- **Fail-safe**: Mouse movement to screen corner stops execution

#### Install Dependencies
```bash
pip install pyautogui opencv-python mss pillow pytesseract
# Also install Tesseract OCR from https://github.com/tesseract-ocr/tesseract
```

---

## 📝 Minimized Request Window

### Purpose
Optimize AI requests to minimize token usage and reduce information load.

### Features
- Content compression and optimization
- Context-aware data reduction
- Essential information extraction
- Request deduplication
- Smart caching
- Token usage estimation

### Usage

#### Optimize Single Request
```python
from agent.minimized_request_window import MinimizedRequestWindow

optimizer = MinimizedRequestWindow()

request_data = {
    "url": "https://example.com",
    "content": "Long content that needs optimization...",
    "headers": {"User-Agent": "...", "Accept": "..."},
    "metadata": {"title": "Page Title"}
}

optimized = optimizer.optimize_request(request_data, "web_scrape")
print(f"Tokens saved: {optimizer.get_statistics()['tokens_saved']}")
```

#### Batch Optimization
```python
requests = [request1, request2, request3]
contexts = optimizer.batch_optimize(requests)
```

#### Test Optimization
```bash
python minimized_request_window.py --test
```

#### Custom Rules
```python
from agent.minimized_request_window import OptimizationRule

rule = OptimizationRule(
    name="remove_images",
    pattern=r"<img[^>]*>",
    action="remove",
    target="body"
)
optimizer.add_custom_rule(rule)
```

---

## 🎛️ HDS6 OS Integration

### Purpose
Unified management system for all AI components.

### Features
- Centralized system control
- Component health monitoring
- Integrated task creation
- Statistics tracking
- Emergency stop functionality

### Usage

#### Start Complete System
```bash
python hds6_os_integration.py --start
```

#### System Status
```bash
python hds6_os_integration.py --status
python hds6_os_integration.py --detailed
```

#### Create Integrated Tasks
```python
from agent.hds6_os_integration import HDS6OSIntegration

system = HDS6OSIntegration()
system.start_system()

# Create task using multiple components
system.create_integrated_task(
    task_id="research_001",
    description="Research topic and present findings",
    components=["web_analysis", "tts"],
    parameters={
        "url": "https://example.com/research",
        "tts_message": "Research completed. Key findings summarized."
    }
)
```

#### Emergency Controls
```bash
# Emergency stop all components
python hds6_os_integration.py --emergency-stop

# Clear all caches
python hds6_os_integration.py --clear-caches

# Export configuration
python hds6_os_integration.py --export-config system_config.json
```

---

## 📊 System Monitoring

### Component Status
All components provide status information:
- Online/offline status
- Active tasks/requests
- Success/failure rates
- Performance metrics

### Logging
Each component logs to `ai-mind/logs/`:
- `integration.log` - System integration
- `pipeline.log` - AI-DRIVER pipeline
- `tts.log` - British TTS
- `web_analysis.log` - Web analysis
- `vision.log` - Vision controller
- `request_optimizer.log` - Request optimization

### Statistics
Track system performance:
```python
system = HDS6OSIntegration()
status = system.get_detailed_status()

print(f"Total tasks: {status['statistics']['total_tasks']}")
print(f"Tokens saved: {status['statistics']['tokens_saved']}")
print(f"Web requests: {status['statistics']['web_requests']}")
```

---

## 🔧 Configuration

### Main Configuration
File: `ai-mind/knowledge/hds6-config.json`

```json
{
  "hds6_version": "1.0.0",
  "speech": {
    "enabled": true,
    "voice": "sonia",
    "language": "en-GB",
    "volume": 0.8,
    "speed": 1.0
  },
  "notifications": {
    "smtp_enabled": false,
    "log_level": "INFO"
  },
  "security": {
    "r01_max_lines": 1000,
    "auto_block_violations": true
  },
  "ui": {
    "power_vox_enabled": true,
    "power_vox_pause_ms": 600
  }
}
```

### Component-Specific Settings
- **Pipeline**: Worker count, retry limits
- **Web Analysis**: Concurrent requests, cache size
- **Vision**: Safe mode, screen resolution
- **TTS**: Voice selection, audio settings

---

## 🚨 Safety and Security

### Safe Mode Defaults
- Vision controller: Safe mode enabled (logs actions only)
- Pipeline: Task validation and sandboxing
- Web analysis: Content filtering and validation

### Emergency Procedures
1. **Emergency Stop**: `--emergency-stop` flag
2. **Component Restart**: Stop and start individual components
3. **Cache Clear**: `--clear-caches` to reset all caches
4. **System Reset**: Complete restart via `--restart`

### Access Control
- All file operations through HDS6 Scribe
- Task validation and sandboxing
- Request optimization prevents data leaks
- Vision controller requires explicit confirmation

---

## 📝 Best Practices

### Performance Optimization
1. Use request optimization for all AI interactions
2. Enable caching for repeated operations
3. Monitor token usage and adjust accordingly
4. Use appropriate worker counts for parallel processing

### Task Management
1. Break large tasks into smaller subtasks
2. Set appropriate priorities and retry limits
3. Use dependencies for complex workflows
4. Monitor task completion and handle failures

### Voice Integration
1. Choose appropriate voice for context
2. Adjust volume and rate for clarity
3. Use TTS for important notifications only
4. Cache frequently used phrases

### Vision Automation
1. Always test in safe mode first
2. Use reliable element identification
3. Implement proper error handling
4. Set reasonable timeouts for operations

---

## 🔍 Troubleshooting

### Common Issues

#### Pipeline Not Starting
```bash
# Check dependencies
pip install aiohttp beautifulsoup4

# Verify configuration
python ai_driver_pipeline.py --status
```

#### TTS Not Working
```bash
# Install audio dependencies
pip install edge-tts pygame

# Test audio system
python british_tts_edge.py --test
```

#### Vision Controller Issues
```bash
# Install OCR dependencies
pip install pyautogui opencv-python mss pillow pytesseract

# Test screen capture
python ai_vision_controller.py --screenshot
```

#### Web Analysis Failures
```bash
# Check network connectivity
python web_analysis_plugin.py --analyze "https://google.com" --type content
```

### Log Analysis
```bash
# View recent errors
tail -f ai-mind/logs/integration.log

# Check component-specific logs
grep ERROR ai-mind/logs/*.log
```

### Performance Issues
1. Monitor system resources
2. Adjust worker counts
3. Clear caches if needed
4. Check network connectivity for web analysis

---

## 📚 Advanced Usage

### Custom Component Integration
```python
from agent.hds6_os_integration import HDS6OSIntegration

class CustomComponent:
    def __init__(self):
        self.is_running = False
    
    def start(self):
        self.is_running = True
    
    def stop(self):
        self.is_running = False

# Integrate with main system
system = HDS6OSIntegration()
custom = CustomComponent()
system.components['custom'] = custom
```

### Batch Operations
```python
# Process multiple URLs
urls = ["https://site1.com", "https://site2.com", "https://site3.com"]

for i, url in enumerate(urls):
    request = AnalysisRequest(
        id=f"batch_{i}",
        url=url,
        analysis_type="content"
    )
    system.add_web_analysis_request(request)
```

### Scheduled Tasks
```python
import schedule
import time

def daily_analysis():
    system.create_integrated_task(
        "daily_report",
        "Daily system analysis",
        ["web_analysis", "tts"],
        {"url": "https://example.com/daily", "tts_message": "Daily report ready"}
    )

schedule.every().day.at("09:00").do(daily_analysis)

while True:
    schedule.run_pending()
    time.sleep(60)
```

---

## 🎯 Next Steps

1. **Install Dependencies**: Ensure all required packages are installed
2. **Configure System**: Update `hds6-config.json` with your preferences
3. **Test Components**: Use individual test commands to verify functionality
4. **Start Integration**: Launch the complete system with `--start`
5. **Create Tasks**: Begin using integrated tasks for complex workflows
6. **Monitor Performance**: Use status commands to track system health

---

**Authors**: Уваров Денис Юрійович, Александров Микита Олександрович, Уварова Анастасія Сергіївна  
**License**: HDS6 Standard  
**Version**: 1.0.0  
**Last Updated**: 2025-01-08
