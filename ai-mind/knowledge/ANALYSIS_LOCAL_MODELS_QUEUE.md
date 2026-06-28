# HDS6 Local Model & Task Queue Analysis
**Analysis Date**: May 8, 2026  
**Focus**: Issues with Qwen Coder and queue task execution

---

## 🔴 CRITICAL FINDINGS

### Issue #1: Local Models Not Receiving Tasks from Queue
**Severity**: CRITICAL  
**Status**: CONFIRMED

#### Root Causes:
1. **No Queue-to-Model Bridge** (Line: `ai_driver_pipeline.py:260-288`)
   - Pipeline creates temporary files but doesn't communicate with local models
   - Only checks for `HDS6Agent` execution, ignoring local model preference
   - No fallback to local models if agent execution fails

2. **Mock AI Responses** (Line: `universal_ai_interface.py:207-237`)
   ```python
   # LocalAIProvider generates FAKE responses
   content = f"Local AI response to: {request.prompt[:50]}..."  # MOCK!
   ```
   - LocalAIProvider doesn't actually call Qwen, Ollama, or LMS
   - All local model responses are simulated
   - No real model integration exists

3. **Framework Detection Missing** (Line: `universal_ai_interface.py:488-514`)
   - `_select_provider()` has hardcoded logic for ANALYSIS/CLASSIFICATION
   - Doesn't consider request urgency (CODE_GENERATION should go to Qwen)
   - No priority weighting for local models

---

### Issue #2: Queue Processing Doesn't Check Task Dependencies Before Execution
**Severity**: HIGH  
**Status**: CONFIRMED

#### Location: `ai_driver_pipeline.py:315-350`

```python
def _worker_loop(self, worker_id: int):
    while self.is_running:
        task_id = None
        
        # Get next available task
        with threading.Lock():
            for tid in self.task_queue[:]:
                if self._can_execute_task(tid):  # ← CHECKS DEPENDENCIES
                    # BUT: No timeout if dependency never completes!
                    task_id = tid
                    self.task_queue.remove(tid)
                    break
```

**Problems**:
- `_can_execute_task()` silently waits for dependencies (Line 185-195)
- No timeout for stuck dependencies
- No notification when task is blocked
- Worker threads spin in `time.sleep(1)` loop doing nothing

---

### Issue #3: Qwen Coder Can't Tell System What It's Doing
**Severity**: HIGH  
**Status**: CONFIRMED

#### No Feedback Channel:
- Pipeline expects tasks to finish or fail (binary outcome)
- Qwen Coder can't say "I'm thinking" or "I need clarification"
- No streaming response support for long-running code generation
- No checkpoint/resume mechanism

#### Location: `ai_driver_pipeline.py:197-259`
```python
def _execute_task(self, task_id: str) -> bool:
    # Task runs, then returns True/False. That's it.
    # No intermediate status updates for long-running tasks
```

---

### Issue #4: ThreadPool Workers Are Inefficient for Local Models
**Severity**: MEDIUM  
**Status**: CONFIRMED

#### Current Design (Line `ai_driver_pipeline.py:364-368`):
```python
for i in range(self.max_workers):
    worker = threading.Thread(target=self._worker_loop, args=(i+1,))
    worker.daemon = True  # ← Killed on shutdown without cleanup
    worker.start()
```

**Problems for Local Models**:
1. Qwen/Ollama models need to run sequentially (single GPU)
2. Multiple workers cause model context switching overhead
3. Daemon threads don't allow graceful shutdown
4. No worker-to-model affinity

---

## 📋 DETAILED ISSUE BREAKDOWN

### A. Task Flow Diagram (Current, Broken)

```
Task Added to Queue
        ↓
Worker checks: Can I execute? (dependency check)
        ↓
   NO → Wait in loop (time.sleep(1))
        ↓ (after 1 second)
   Check again... (BUSY WAITING)
        ↓
   YES → Create temp file
        ↓
   Try HDS6Agent.execute_task_script()
        ↓
   ✗ Agent not available (Qwen Coder is local, not agent)
        ↓
   ✗ Task FAILS
        ↓
   Auto-retry (exponential backoff)
        ↓
   ✗ Task FAILS AGAIN (same reason)
        ↓
   After max_retries → Task marked FAILED
```

### B. Missing Qwen Integration

**What SHOULD happen**:
1. Queue detects CODE_GENERATION task
2. Routes to LocalAIProvider(framework=OLLAMA, model="qwen-coder")
3. Sends request to http://localhost:11434 (or LMS at :1234)
4. Model processes in background
5. Task polls for results
6. Result returned to queue

**What ACTUALLY happens**:
1. Queue detects CODE_GENERATION task
2. Routes to LocalAIProvider (mock)
3. Returns fake response: "Local AI response to: [prompt[:50]]..."
4. Task completes (incorrectly)
5. User doesn't realize the model never ran

---

### C. Queue Blocking Issues

**Problem**: Tasks can deadlock
```
Task A depends on Task B
Task B depends on Task A
↓
Both tasks wait forever (circular dependency)
No detection, no error, no timeout
```

**Current Code** (Line 185-195):
```python
def _can_execute_task(self, task_id: str) -> bool:
    task = self.tasks[task_id]
    for dep_id in task.dependencies:
        if dep_id not in self.completed_tasks:
            return False  # ← Just returns False, no timeout tracking
    return True
```

---

## 🛠️ SOLUTIONS

### Solution 1: Real Qwen Coder Integration

**File to create**: `agent/qwen_coder_handler.py`
```python
import requests
import json
from typing import Optional

class QwenCoderHandler:
    """Direct interface to Qwen Coder via Ollama/LMS"""
    
    def __init__(self, base_url: str = "http://localhost:11434"):
        self.base_url = base_url
        self.model = "qwen:7b-code"
    
    def generate_code(self, prompt: str, context: str = "") -> str:
        """
        Send code generation request to local Qwen model.
        Returns actual generated code, not mock response.
        """
        payload = {
            "model": self.model,
            "prompt": f"{context}\n{prompt}",
            "stream": False
        }
        
        try:
            response = requests.post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=300  # 5 minutes for code generation
            )
            
            if response.status_code == 200:
                result = response.json()
                return result.get("response", "")
            else:
                raise Exception(f"Model error: {response.status_code}")
                
        except requests.exceptions.ConnectionError:
            raise Exception("Qwen Coder not running at " + self.base_url)
```

### Solution 2: Queue Task Routing

**Modify**: `ai_driver_pipeline.py:_execute_task()`
```python
def _execute_task(self, task_id: str) -> bool:
    task = self.tasks[task_id]
    
    # Route to appropriate handler
    if self._is_code_generation_task(task):
        return self._execute_with_qwen(task)
    elif self._is_python_task(task):
        return self._execute_script_content(task)
    else:
        return self._execute_script_file(task)

def _is_code_generation_task(self, task: PipelineTask) -> bool:
    return "code" in task.name.lower() or "qwen" in task.description.lower()

def _execute_with_qwen(self, task: PipelineTask) -> bool:
    from .qwen_coder_handler import QwenCoderHandler
    
    qwen = QwenCoderHandler()
    try:
        result = qwen.generate_code(
            prompt=task.script_content or "",
            context=task.description
        )
        
        # Save generated code
        output_file = self.base_dir / "ai-mind" / "tasks" / "active" / f"{task.id}_generated.py"
        with open(output_file, 'w') as f:
            f.write(result)
        
        task.result = result
        return True
    except Exception as e:
        task.error_message = str(e)
        return False
```

### Solution 3: Dependency Timeout Mechanism

**Add to**: `ai_driver_pipeline.py`
```python
@dataclass
class PipelineTask:
    # ... existing fields ...
    dependency_timeout_seconds: int = 600  # 10 minutes
    dependency_wait_since: Optional[datetime] = None

def _can_execute_task(self, task_id: str) -> bool:
    task = self.tasks[task_id]
    current_time = datetime.now()
    
    for dep_id in task.dependencies:
        if dep_id not in self.completed_tasks:
            # Track when dependency wait started
            if task.dependency_wait_since is None:
                task.dependency_wait_since = current_time
            
            # Check if timeout exceeded
            wait_duration = (current_time - task.dependency_wait_since).total_seconds()
            if wait_duration > task.dependency_timeout_seconds:
                # Dependency timeout!
                self.logger.error(
                    f"Dependency timeout: Task {task_id} waiting for {dep_id} "
                    f"for {wait_duration:.1f}s"
                )
                # Notify via VOX
                self.vox_integration.on_dependency_timeout(task, dep_id, wait_duration)
                return False
            
            return False
    
    return True
```

### Solution 4: Smart Queue Worker Pool

**Replace**: `ai_driver_pipeline.py:start()` and `_worker_loop()`

```python
def start(self):
    """Start pipeline with smart worker allocation."""
    if self.is_running:
        return
    
    self.is_running = True
    self.stats['start_time'] = datetime.now()
    
    # For local models, use fewer workers (avoid GPU thrashing)
    effective_workers = self.max_workers
    if self._has_local_models():
        effective_workers = min(2, self.max_workers)  # Max 2 for single GPU
        self.logger.info(f"Local models detected, reducing workers to {effective_workers}")
    
    self.workers = []
    for i in range(effective_workers):
        worker = threading.Thread(
            target=self._worker_loop,
            args=(i+1,),
            name=f"HDS6-Worker-{i+1}"
        )
        worker.daemon = False  # Graceful shutdown
        worker.start()
        self.workers.append(worker)

def _has_local_models(self) -> bool:
    """Check if any local models are configured."""
    return any(
        isinstance(p, (LocalAIProvider, OllamaProvider, LMSProvider))
        for p in self.providers.values()
    )
```

### Solution 5: Task Progress Notifications

**Add to**: `enhanced_ai_driver_pipeline.py`
```python
class TaskProgressTracker:
    def __init__(self):
        self.callbacks: Dict[str, List[Callable]] = {}
    
    def on_task_waiting(self, task_id: str, reason: str):
        """Notify that task is waiting (e.g., for dependency)."""
        # Don't spam console, just log
        self.logger.debug(f"Task {task_id} waiting: {reason}")
    
    def on_task_processing(self, task_id: str, current_step: str):
        """For long-running tasks (Qwen code generation)."""
        self.vox.speak(f"Processing task {task_id}: {current_step}", "INFO")
```

---

## 📊 IMPACT ASSESSMENT

| Component | Impact | Priority |
|-----------|--------|----------|
| LocalAIProvider mock responses | Tasks complete without running | CRITICAL |
| No Qwen integration | Can't use Qwen Coder at all | CRITICAL |
| Queue busy-waiting | CPU waste, sluggish response | HIGH |
| No dependency timeout | Deadlock possible | HIGH |
| Daemon thread cleanup | Tasks lost on shutdown | MEDIUM |
| No progress feedback | Qwen can't report status | MEDIUM |

---

## 🚀 IMPLEMENTATION ROADMAP

### Phase 1: Quick Fix (2-3 hours)
1. Remove mock responses from LocalAIProvider
2. Add Ollama/LMS HTTP client
3. Route CODE_GENERATION tasks to local models

### Phase 2: Stability (1-2 hours)
1. Add dependency timeout detection
2. Implement task deadlock prevention
3. Add progress notifications

### Phase 3: Optimization (3-4 hours)
1. Intelligent worker pool sizing
2. GPU affinity for local models
3. Graceful shutdown mechanism

---

## ⚠️ WARNINGS FOR CURRENT USE

**DO NOT** use HDS6 pipeline with:
- Qwen Coder (won't execute)
- Circular task dependencies
- Long-running code generation (no progress updates)
- Multiple GPU-based models (workers will thrash)

**INSTEAD**, use:
- Direct Qwen calls outside pipeline
- HDS6Agent for Python tasks
- Simple linear task chains (no dependencies)

