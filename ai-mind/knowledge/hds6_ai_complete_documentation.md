# HDS6 AI System - Complete Documentation for AI Assistants

**Version**: 2.0  
**Last Updated**: May 8, 2026  
**Authors**: Уваров Денис Юрійович, Александров Микита Олександрович, Уварова Анастасія Сергіївна

---

## 📋 Table of Contents

1. [System Overview](#system-overview)
2. [Core Architecture](#core-architecture)
3. [Component Documentation](#component-documentation)
4. [Integration Guide](#integration-guide)
5. [Usage Examples](#usage-examples)
6. [Best Practices](#best-practices)
7. [Troubleshooting](#troubleshooting)
8. [Performance Optimization](#performance-optimization)
9. [Security Considerations](#security-considerations)
10. [Testing and Validation](#testing-and-validation)

---

## 🎯 System Overview

HDS6 AI System is a comprehensive artificial intelligence operating system designed for autonomous task execution, web analysis, computer vision, and intelligent automation. The system follows strict R-Series protocols for code quality and operational integrity.

### Key Features
- **Autonomous Task Execution** via AI-DRIVER Pipeline
- **Multi-modal AI Capabilities** (Text, Vision, Web)
- **Voice Feedback System** with British TTS
- **Browser Automation** with security controls
- **Real-time Monitoring** and crash testing
- **Plugin Architecture** for extensibility

### System Philosophy
- **R-Series Laws Enforcement**: Strict code quality protocols
- **Zero-Direct-Write**: All file operations through Scribe
- **Task-First Approach**: All operations require task context
- **Size Limitation**: Maximum 1000 lines per file
- **Continuous Monitoring**: Real-time system health checks

---

## 🏗️ Core Architecture

### System Layers

```
┌─────────────────────────────────────────────────────────────┐
│                    HDS6 AI OS                              │
├─────────────────────────────────────────────────────────────┤
│  Integration Layer (hds6_os_integration.py)                │
├─────────────────────────────────────────────────────────────┤
│  Task Execution Layer (enhanced_ai_driver_pipeline.py)      │
├─────────────────────────────────────────────────────────────┤
│  Service Layer                                             │
│  ├── AI-DRIVER Pipeline    ├── British TTS Edge             │
│  ├── Web Analysis Plugin  ├── AI Vision Controller          │
│  ├── Browser Agent         ├── Minimized Request Window     │
│  └── Enhanced Notifications                               │
├─────────────────────────────────────────────────────────────┤
│  Core Services                                             │
│  ├── Vox Service (voice)     ├── Scribe (file operations)   │
│  ├── Security Manager        ├── Compliance Checker        │
│  └── Plugin Manager                                      │
├─────────────────────────────────────────────────────────────┤
│  System Layer                                              │
│  ├── R-Series Protocol       ├── Quantum Security          │
│  ├── Zero-Trust Architecture  ├── Blockchain Audit          │
│  └── Performance Monitoring                                 │
└─────────────────────────────────────────────────────────────┘
```

### Data Flow

```
User Request → Task Creation → Pipeline Queue → Worker Execution → Result → Voice Feedback
     ↓              ↓              ↓              ↓              ↓
  Validation → Scheduling → Resource Alloc → Component Call → Storage → Notification
```

---

## 🧩 Component Documentation

### 1. Enhanced AI-DRIVER Pipeline

**File**: `enhanced_ai_driver_pipeline.py`

**Purpose**: Advanced task execution system with scheduling, dependencies, and resource management.

**Key Features**:
- Multiple task types (Script, Web Analysis, Vision, Integrated)
- Task scheduling with cron expressions
- Dependency management
- Resource allocation and monitoring
- Performance metrics and analytics
- Task templates and reuse

**Usage Example**:
```python
from enhanced_ai_driver_pipeline import EnhancedAIDriverPipeline, EnhancedPipelineTask, TaskType

# Initialize pipeline
pipeline = EnhancedAIDriverPipeline(max_workers=3)
pipeline.start()

# Create task
task = EnhancedPipelineTask(
    id="research_001",
    name="Web Research Task",
    task_type=TaskType.INTEGRATED,
    metadata={
        "components": ["web_analysis", "tts"],
        "url": "https://example.com",
        "tts_message": "Research completed"
    }
)

# Add and execute
pipeline.add_task(task)
```

**Task Types**:
- `SCRIPT`: Python script execution
- `WEB_ANALYSIS`: Web content analysis
- `VISION_ACTION`: Computer vision automation
- `INTEGRATED`: Multi-component tasks
- `SCHEDULED`: Periodic execution
- `CONDITIONAL`: Condition-based execution

### 2. British TTS Edge

**File**: `british_tts_edge.py`

**Purpose**: High-quality British English text-to-speech synthesis.

**Features**:
- Multiple voice options (Sonia, Ryan, George)
- Edge-based synthesis for natural sound
- Queue management for multiple utterances
- Volume and rate control
- Audio file export capability

**Voice Options**:
- `sonia`: Female voice, natural tone
- `ryan`: Male voice, professional
- `george`: Male voice, authoritative

**Usage Example**:
```python
from british_tts_edge import BritishTTSEdge

# Initialize TTS
tts = BritishTTSEdge(base_dir)
tts.start_playback()

# Speak with different voices
tts.speak("Hello, I am Sonia", "sonia")
tts.speak("And I am Ryan", "ryan")

# Stop playback
tts.stop_playback()
```

### 3. Web Analysis Plugin

**File**: `web_analysis_plugin.py`

**Purpose**: Local web content analysis and extraction.

**Features**:
- Content extraction and analysis
- Link and image processing
- Metadata extraction
- Text summarization
- Concurrent request handling

**Analysis Types**:
- `content`: Full content extraction
- `links`: Link analysis and validation
- `images`: Image processing and analysis
- `metadata`: Meta tag extraction
- `summary`: Content summarization

**Usage Example**:
```python
from web_analysis_plugin import WebAnalysisPlugin, AnalysisRequest

# Initialize plugin
web_analysis = WebAnalysisPlugin(base_dir)
web_analysis.start()

# Create analysis request
request = AnalysisRequest(
    id="analysis_001",
    url="https://example.com",
    analysis_type="content"
)

# Add request and get result
web_analysis.add_request(request)
result = web_analysis.get_result("analysis_001")
```

### 4. AI Vision Controller

**File**: `ai_vision_controller.py`

**Purpose**: Computer vision automation for GUI control.

**Features**:
- Screen capture and analysis
- Element detection and interaction
- Mouse and keyboard automation
- Safe mode for protection
- Template matching

**Action Types**:
- `SCREENSHOT`: Capture screen
- `CLICK`: Click on element
- `TYPE`: Type text
- `SCROLL`: Scroll page
- `WAIT`: Wait for element

**Usage Example**:
```python
from ai_vision_controller import AIVisionController, VisionAction, ActionType

# Initialize controller
vision = AIVisionController(base_dir, safe_mode=True)
vision.start_processing()

# Add action
action = VisionAction(
    id="click_button",
    action_type=ActionType.CLICK,
    description="Click submit button",
    element_selector="#submit-button"
)

vision.add_action(action)
```

### 5. Browser Agent

**File**: `browser_agent.py`

**Purpose**: Secure web browser automation with content extraction.

**Features**:
- Multiple browser support (Chrome, Firefox, Edge)
- Security levels and domain filtering
- Content extraction and sanitization
- Screenshot capture
- Session management

**Security Levels**:
- `MINIMAL`: Basic restrictions
- `STANDARD`: Standard security
- `STRICT`: High security
- `SANDBOX`: Maximum isolation

**Usage Example**:
```python
from browser_agent import HDS6BrowserAgent, NavigationRequest

# Initialize agent
agent = HDS6BrowserAgent()

# Create session
session_id = agent.create_session("research_session", {
    "security_level": "standard",
    "navigation_mode": "headless"
})

# Navigate and extract
request = NavigationRequest(
    session_id=session_id,
    url="https://example.com",
    screenshot=True,
    extract_content=True
)

response = agent.navigate(request)
```

### 6. Minimized Request Window

**File**: `minimized_request_window.py`

**Purpose**: Optimize AI requests to minimize token usage.

**Features**:
- Request optimization and compression
- Context window management
- Token usage tracking
- Batch processing
- Content filtering

**Usage Example**:
```python
from minimized_request_window import MinimizedRequestWindow

# Initialize optimizer
optimizer = MinimizedRequestWindow(base_dir)

# Optimize request
context = optimizer.optimize_request(
    {"url": "https://example.com", "content": "Large content..."},
    "task_context"
)

# Batch optimization
contexts = optimizer.batch_optimize([request1, request2, request3])
```

### 7. Enhanced Vox Notifications

**File**: `enhanced_vox_notifications.py`

**Purpose**: Advanced voice notification system for pipeline events.

**Features**:
- Task lifecycle announcements
- Priority-based notifications
- Cooldown management
- British TTS integration
- Detailed status reporting

**Notification Types**:
- Pipeline start/stop
- Task creation/completion/failure
- Queue status updates
- System alerts
- Dependency notifications

**Usage Example**:
```python
from enhanced_vox_notifications import PipelineVoxIntegration

# Initialize notifications
vox_integration = PipelineVoxIntegration(base_dir)

# Automatic notifications on pipeline events
vox_integration.on_task_started(task)
vox_integration.on_task_completed(task, duration)
vox_integration.on_task_failed(task, error, retry_count)
```

### 8. HDS6 OS Integration

**File**: `hds6_os_integration.py`

**Purpose**: Unified control system for all HDS6 components.

**Features**:
- Component lifecycle management
- Integrated task creation
- System monitoring
- Health checks
- Centralized configuration

**Usage Example**:
```python
from hds6_os_integration import HDS6OSIntegration

# Initialize system
integration = HDS6OSIntegration(base_dir)

# Start all components
integration.start_system()

# Create integrated task
integration.create_integrated_task(
    "research_task",
    "Complete web research",
    ["web_analysis", "tts", "vision"],
    {"url": "https://example.com"}
)

# Get system status
status = integration.get_system_status()
```

---

## 🔗 Integration Guide

### Quick Start Integration

```python
from hds6_os_integration import HDS6OSIntegration

# 1. Initialize the system
integration = HDS6OSIntegration(base_dir="/path/to/hds6")

# 2. Start all components
integration.start_system()

# 3. Create and execute tasks
integration.create_integrated_task(
    "example_task",
    "Example integrated task",
    ["tts", "web_analysis"],
    {"url": "https://example.com", "message": "Task completed"}
)

# 4. Monitor system
status = integration.get_detailed_status()
print(f"System status: {status['state']}")

# 5. Shutdown gracefully
integration.stop_system()
```

### Component-Specific Integration

#### AI-DRIVER Pipeline Integration

```python
from enhanced_ai_driver_pipeline import EnhancedAIDriverPipeline
from enhanced_ai_driver_pipeline import EnhancedPipelineTask, TaskType

# Create pipeline
pipeline = EnhancedAIDriverPipeline(base_dir, max_workers=5)
pipeline.start()

# Add different task types
# Script task
script_task = EnhancedPipelineTask(
    id="script_001",
    name="Data Processing",
    task_type=TaskType.SCRIPT,
    script_content="print('Processing data...')"
)

# Web analysis task
web_task = EnhancedPipelineTask(
    id="web_001", 
    name="Web Research",
    task_type=TaskType.WEB_ANALYSIS,
    metadata={"url": "https://example.com"}
)

# Integrated task
integrated_task = EnhancedPipelineTask(
    id="integrated_001",
    name="Complete Research",
    task_type=TaskType.INTEGRATED,
    metadata={
        "components": ["web_analysis", "tts"],
        "url": "https://example.com",
        "tts_message": "Research completed"
    }
)

# Add tasks to pipeline
for task in [script_task, web_task, integrated_task]:
    pipeline.add_task(task)
```

#### Browser Agent Integration

```python
from browser_agent import HDS6BrowserAgent, NavigationRequest

# Initialize agent
agent = HDS6BrowserAgent()

# Create secure session
session_id = agent.create_session("research_session", {
    "security_level": "standard",
    "allowed_domains": ["wikipedia.org", "github.com"],
    "blocked_domains": ["social-media.com"]
})

# Navigate with content extraction
request = NavigationRequest(
    session_id=session_id,
    url="https://wikipedia.org/wiki/Artificial_intelligence",
    extract_content=True,
    screenshot=True
)

response = agent.navigate(request)

# Process extracted data
if response.extracted_data:
    title = response.extracted_data.get('title', 'No title')
    text = response.extracted_data.get('text', '')[:1000]  # First 1000 chars
    print(f"Title: {title}")
    print(f"Content preview: {text[:200]}...")
```

---

## 💡 Usage Examples

### Example 1: Web Research Automation

```python
from hds6_os_integration import HDS6OSIntegration

# Initialize system
integration = HDS6OSIntegration(base_dir)
integration.start_system()

# Create comprehensive research task
integration.create_integrated_task(
    "ai_research",
    "Research AI developments",
    ["browser_agent", "web_analysis", "tts"],
    {
        "url": "https://arxiv.org/list/cs.AI/recent",
        "analysis_type": "content",
        "tts_message": "AI research completed successfully",
        "screenshot": True
    }
)

# Monitor progress
while True:
    status = integration.get_system_status()
    if status.state.value == "IDLE":
        break
    time.sleep(2)

integration.stop_system()
```

### Example 2: Automated Testing Pipeline

```python
from enhanced_ai_driver_pipeline import EnhancedAIDriverPipeline
from enhanced_ai_driver_pipeline import EnhancedPipelineTask, TaskType

# Create testing pipeline
pipeline = EnhancedAIDriverPipeline(base_dir, max_workers=3)
pipeline.start()

# Test suite tasks
test_tasks = [
    EnhancedPipelineTask(
        id="unit_tests",
        name="Run Unit Tests",
        task_type=TaskType.SCRIPT,
        script_content="import unittest; # run tests...",
        priority=TaskPriority.HIGH
    ),
    EnhancedPipelineTask(
        id="integration_tests",
        name="Run Integration Tests", 
        task_type=TaskType.SCRIPT,
        script_content="# integration tests...",
        dependencies=[TaskDependency("unit_tests")]
    ),
    EnhancedPipelineTask(
        id="ui_tests",
        name="Run UI Tests",
        task_type=TaskType.VISION_ACTION,
        metadata={"test_suite": "ui", "safe_mode": True}
    )
]

# Execute test suite
for task in test_tasks:
    pipeline.add_task(task)

# Wait for completion
time.sleep(60)
status = pipeline.get_enhanced_status()
print(f"Tests completed: {status['completed_tasks']}")
```

### Example 3: Content Analysis Pipeline

```python
from browser_agent import HDS6BrowserAgent, NavigationRequest
from web_analysis_plugin import WebAnalysisPlugin, AnalysisRequest

# Initialize components
agent = HDS6BrowserAgent()
web_analysis = WebAnalysisPlugin(base_dir)
web_analysis.start()

# Create analysis session
session_id = agent.create_session("content_analysis", {
    "security_level": "standard"
})

# Analyze multiple sources
sources = [
    "https://news-site.com/tech",
    "https://blog.example.com/ai",
    "https://research.org/papers"
]

for i, url in enumerate(sources):
    # Navigate and capture
    request = NavigationRequest(
        session_id=session_id,
        url=url,
        extract_content=True,
        screenshot=True
    )
    
    response = agent.navigate(request)
    
    if response.extracted_data:
        # Process content
        title = response.extracted_data.get('title', '')
        content = response.extracted_data.get('text', '')
        
        # Create analysis request
        analysis_request = AnalysisRequest(
            id=f"analysis_{i}",
            url=url,
            analysis_type="content",
            content=content
        )
        
        web_analysis.add_request(analysis_request)

# Collect results
results = []
for i in range(len(sources)):
    result = web_analysis.get_result(f"analysis_{i}")
    if result:
        results.append(result)

print(f"Analyzed {len(results)} sources")
```

---

## 🎯 Best Practices

### 1. Task Management

**DO**:
- Use descriptive task IDs and names
- Set appropriate priorities
- Define clear dependencies
- Include metadata for context
- Handle errors gracefully

**DON'T**:
- Create circular dependencies
- Use generic task names
- Ignore retry limits
- Skip error handling
- Overload single tasks

### 2. Resource Management

**DO**:
- Monitor memory usage
- Set reasonable timeouts
- Use resource limits
- Clean up resources
- Track performance metrics

**DON'T**:
- Ignore memory leaks
- Use infinite timeouts
- Overallocate resources
- Forget cleanup
- Skip monitoring

### 3. Security

**DO**:
- Use appropriate security levels
- Validate all inputs
- Filter sensitive content
- Monitor access patterns
- Update security policies

**DON'T**:
- Disable security features
- Trust external inputs
- Expose sensitive data
- Ignore access logs
- Use outdated configurations

### 4. Error Handling

**DO**:
- Implement comprehensive error handling
- Use meaningful error messages
- Log all errors
- Provide recovery mechanisms
- Test error scenarios

**DON'T**:
- Ignore exceptions
- Use generic error messages
- Skip error logging
- Leave systems in inconsistent states
- Assume success

---

## 🔧 Troubleshooting

### Common Issues and Solutions

#### 1. Pipeline Not Starting

**Symptoms**: Pipeline fails to start, workers not created

**Causes**:
- Missing dependencies
- Incorrect base directory
- Permission issues
- Port conflicts

**Solutions**:
```python
# Check dependencies
import sys
print("Python path:", sys.path)

# Verify base directory
from pathlib import Path
base_dir = Path("/path/to/hds6")
if not (base_dir / "ai-mind").exists():
    print("Invalid HDS6 directory")

# Check permissions
import os
if not os.access(base_dir, os.W_OK):
    print("No write permissions")
```

#### 2. TTS Not Working

**Symptoms**: No audio output, voice errors

**Causes**:
- Missing audio drivers
- Incorrect device configuration
- Network connectivity issues
- Voice model not available

**Solutions**:
```python
# Test audio system
import winsound
winsound.Beep(1000, 1000)  # Test beep

# Check TTS configuration
from british_tts_edge import BritishTTSEdge
tts = BritishTTSEdge(base_dir)
print("Available voices:", tts.get_available_voices())

# Test with simple message
try:
    tts.start_playback()
    tts.speak("Test message", "sonia")
    tts.stop_playback()
except Exception as e:
    print(f"TTS error: {e}")
```

#### 3. Browser Agent Issues

**Symptoms**: Navigation failures, security errors

**Causes**:
- Browser not installed
- WebDriver issues
- Security policy violations
- Network connectivity

**Solutions**:
```python
# Check browser availability
import subprocess
try:
    subprocess.run(["chrome", "--version"], check=True)
    print("Chrome available")
except:
    print("Chrome not found")

# Test with minimal security
from browser_agent import HDS6BrowserAgent
agent = HDS6BrowserAgent()

session_id = agent.create_session("test", {
    "security_level": "minimal",
    "navigation_mode": "api_only"  # Use API mode to avoid browser issues
})

# Test simple navigation
from browser_agent import NavigationRequest
request = NavigationRequest(
    session_id=session_id,
    url="https://httpbin.org/json"
)

response = agent.navigate(request)
print(f"Test navigation: {response.status_code}")
```

#### 4. Memory Issues

**Symptoms**: System slows down, out of memory errors

**Causes**:
- Memory leaks
- Too many concurrent tasks
- Large content processing
- Insufficient system resources

**Solutions**:
```python
import psutil
import gc

# Monitor memory usage
def check_memory():
    process = psutil.Process()
    memory_mb = process.memory_info().rss / 1024 / 1024
    print(f"Memory usage: {memory_mb:.2f} MB")
    
    if memory_mb > 1000:  # 1GB threshold
        print("High memory usage detected")
        gc.collect()  # Force garbage collection
        return False
    return True

# Limit concurrent tasks
max_concurrent = 3
if len(active_tasks) > max_concurrent:
    print("Too many concurrent tasks")
    # Wait or queue tasks

# Process content in chunks
def process_large_content(content, chunk_size=1000):
    for i in range(0, len(content), chunk_size):
        chunk = content[i:i+chunk_size]
        yield process_chunk(chunk)
```

### Debug Mode

Enable debug logging for detailed troubleshooting:

```python
import logging

# Enable debug logging
logging.basicConfig(level=logging.DEBUG)

# Component-specific debug
from enhanced_ai_driver_pipeline import EnhancedAIDriverPipeline
pipeline = EnhancedAIDriverPipeline(base_dir)
pipeline.logger.setLevel(logging.DEBUG)

# Monitor system resources
import psutil
while True:
    cpu = psutil.cpu_percent()
    memory = psutil.virtual_memory().percent
    print(f"CPU: {cpu}%, Memory: {memory}%")
    time.sleep(5)
```

---

## ⚡ Performance Optimization

### 1. Pipeline Optimization

**Task Batching**:
```python
# Batch similar tasks
batch_size = 10
tasks = create_tasks(100)  # Create 100 tasks

for i in range(0, len(tasks), batch_size):
    batch = tasks[i:i+batch_size]
    for task in batch:
        pipeline.add_task(task)
    
    # Wait for batch completion
    while pipeline.get_enhanced_status()['pending_tasks'] > 0:
        time.sleep(1)
```

**Resource Management**:
```python
# Optimize worker count
import psutil
cpu_cores = psutil.cpu_count()
optimal_workers = min(cpu_cores, 5)  # Cap at 5 workers

pipeline = EnhancedAIDriverPipeline(
    base_dir, 
    max_workers=optimal_workers,
    max_concurrent_tasks=optimal_workers * 2
)
```

### 2. Memory Optimization

**Content Processing**:
```python
# Process content in streams
def process_large_file(file_path):
    with open(file_path, 'r') as f:
        for line in f:
            yield process_line(line)

# Clear memory periodically
import gc
def periodic_cleanup():
    gc.collect()
    # Clear caches if needed
    if hasattr(pipeline, 'clear_cache'):
        pipeline.clear_cache()
```

### 3. Network Optimization

**Request Optimization**:
```python
# Use request optimizer
from minimized_request_window import MinimizedRequestWindow

optimizer = MinimizedRequestWindow(base_dir)

# Optimize before sending
optimized_request = optimizer.optimize_request(
    large_request,
    "task_context"
)

# Batch requests
batch_requests = [req1, req2, req3]
optimized_batch = optimizer.batch_optimize(batch_requests)
```

### 4. Caching Strategy

```python
# Enable caching
from web_analysis_plugin import WebAnalysisPlugin

web_analysis = WebAnalysisPlugin(
    base_dir,
    enable_cache=True,
    cache_ttl=3600  # 1 hour cache
)

# Use cached results
result = web_analysis.get_cached_result(request_id)
if not result:
    result = web_analysis.process_request(request)
    web_analysis.cache_result(request_id, result)
```

---

## 🔒 Security Considerations

### 1. Browser Security

**Domain Whitelisting**:
```python
# Configure allowed domains
session_config = {
    "security_level": "strict",
    "allowed_domains": [
        "wikipedia.org",
        "github.com",
        "stackoverflow.com"
    ],
    "blocked_domains": [
        "social-media.com",
        "ads-site.com"
    ]
}
```

**Content Filtering**:
```python
# Enable content sanitization
from browser_agent import HDS6BrowserAgent

agent = HDS6BrowserAgent()
session_id = agent.create_session("secure_session", {
    "security_level": "sandbox",
    "content_filtering": True,
    "block_scripts": True,
    "block_forms": True
})
```

### 2. Data Protection

**Sensitive Data Handling**:
```python
# Filter sensitive information
def sanitize_content(content):
    import re
    
    # Remove common sensitive patterns
    patterns = [
        r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b',  # Credit cards
        r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',  # Emails
        r'password["\']?\s*[:=]\s*["\']?[^\s"\']+["\']?',  # Passwords
    ]
    
    for pattern in patterns:
        content = re.sub(pattern, '[REDACTED]', content, flags=re.IGNORECASE)
    
    return content
```

### 3. Access Control

**Session Management**:
```python
# Limit session duration
max_session_duration = 3600  # 1 hour

def check_session_age(session):
    age = datetime.now() - session.created_at
    if age.total_seconds() > max_session_duration:
        agent.close_session(session.session_id)
        return False
    return True
```

---

## 🧪 Testing and Validation

### 1. Component Testing

**Unit Tests**:
```python
import unittest
from enhanced_ai_driver_pipeline import EnhancedAIDriverPipeline

class TestPipeline(unittest.TestCase):
    def setUp(self):
        self.pipeline = EnhancedAIDriverPipeline(base_dir)
        self.pipeline.start()
    
    def test_task_creation(self):
        task = EnhancedPipelineTask(
            id="test_task",
            name="Test Task",
            task_type=TaskType.SCRIPT,
            script_content="print('test')"
        )
        self.assertTrue(self.pipeline.add_task(task))
    
    def tearDown(self):
        self.pipeline.stop()

if __name__ == '__main__':
    unittest.main()
```

### 2. Integration Testing

**End-to-End Tests**:
```python
def test_complete_workflow():
    # Initialize system
    integration = HDS6OSIntegration(base_dir)
    integration.start_system()
    
    # Create test task
    integration.create_integrated_task(
        "test_workflow",
        "Complete workflow test",
        ["tts", "web_analysis"],
        {"url": "https://httpbin.org/json"}
    )
    
    # Wait for completion
    time.sleep(10)
    
    # Verify results
    status = integration.get_system_status()
    assert status.state.value == "IDLE"
    
    integration.stop_system()
```

### 3. Stress Testing

**Load Testing**:
```python
def stress_test_pipeline():
    pipeline = EnhancedAIDriverPipeline(base_dir, max_workers=5)
    pipeline.start()
    
    # Create many tasks
    for i in range(100):
        task = EnhancedPipelineTask(
            id=f"stress_task_{i}",
            name=f"Stress Task {i}",
            task_type=TaskType.SCRIPT,
            script_content=f"print('Task {i} completed')"
        )
        pipeline.add_task(task)
    
    # Monitor performance
    start_time = time.time()
    while pipeline.get_enhanced_status()['pending_tasks'] > 0:
        time.sleep(1)
    
    duration = time.time() - start_time
    print(f"Processed 100 tasks in {duration:.2f} seconds")
    
    pipeline.stop()
```

### 4. Crash Testing

**Automated Crash Test**:
```python
# Run the comprehensive crash test
import subprocess
import sys

def run_crash_test():
    test_file = base_dir / "ai-mind/tasks/active/hds6_crash_test.py"
    result = subprocess.run([sys.executable, str(test_file)], 
                          capture_output=True, text=True)
    
    print("Crash test output:")
    print(result.stdout)
    
    if result.stderr:
        print("Errors:")
        print(result.stderr)
    
    return result.returncode == 0

# Execute crash test
success = run_crash_test()
print(f"Crash test {'PASSED' if success else 'FAILED'}")
```

---

## 📚 Additional Resources

### Configuration Files

- **Task Templates**: `ai-mind/knowledge/task_templates.json`
- **Browser Config**: `ai-mind/knowledge/browser_agent_config.json`
- **Component Guide**: `ai-mind/knowledge/ai_os_components_guide.md`

### Log Locations

- **Pipeline Logs**: `ai-mind/logs/enhanced_pipeline.log`
- **Browser Logs**: `ai-mind/logs/browser_agent.log`
- **Crash Test Results**: `ai-mind/logs/hds6_crash_test_*.json`

### Monitoring

- **System Status**: Use `integration.get_detailed_status()`
- **Performance Metrics**: Check `pipeline.get_enhanced_status()`
- **Resource Usage**: Monitor with `psutil` library

---

## 🚀 Quick Reference

### Essential Commands

```python
# Start HDS6 System
from hds6_os_integration import HDS6OSIntegration
integration = HDS6OSIntegration(base_dir)
integration.start_system()

# Create Task
integration.create_integrated_task(
    "task_id",
    "Task Description",
    ["tts", "web_analysis"],
    {"param": "value"}
)

# Check Status
status = integration.get_system_status()

# Stop System
integration.stop_system()
```

### Common Patterns

```python
# Safe task execution
try:
    result = pipeline.execute_task(task)
except Exception as e:
    logger.error(f"Task failed: {e}")
    # Handle error
finally:
    # Cleanup
    pass

# Resource monitoring
import psutil
memory = psutil.virtual_memory().percent
cpu = psutil.cpu_percent()

# Error handling with retries
max_retries = 3
for attempt in range(max_retries):
    try:
        result = operation()
        break
    except Exception as e:
        if attempt == max_retries - 1:
            raise
        time.sleep(2 ** attempt)  # Exponential backoff
```

---

## 📞 Support

For issues and questions:

1. Check logs in `ai-mind/logs/`
2. Run crash test: `python ai-mind/tasks/active/hds6_crash_test.py`
3. Review component documentation
4. Check system requirements and dependencies

---

**Document Version**: 2.0  
**Last Updated**: May 8, 2026  
**Next Review**: June 8, 2026

This documentation provides comprehensive information for AI assistants to understand, integrate, and operate the HDS6 AI System effectively.
