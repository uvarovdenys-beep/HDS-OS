# HDS6 Pipeline Fixes - Implementation Guide
**Date**: May 8, 2026  
**Target**: Fix Qwen Coder integration and queue execution

---

## 🔧 FIXES REQUIRED

### Fix #1: Enable Real Local Model Calls

**File**: `agent/universal_ai_interface.py`  
**Lines**: 207-237 (LocalAIProvider.generate_response)

**BEFORE** (Mock):
```python
async def generate_response(self, request: AIRequest) -> AIResponse:
    """Generate response using local model."""
    start_time = time.time()
    
    try:
        await asyncio.sleep(0.05)  # Simulate processing time
        
        # ✗ FAKE RESPONSE
        content = f"Local AI response to: {request.prompt[:50]}..."
        
        return AIResponse(...)
```

**AFTER** (Real):
```python
async def generate_response(self, request: AIRequest) -> AIResponse:
    """Generate response using local model via Qwen or Ollama."""
    start_time = time.time()
    
    try:
        if request.request_type == AIRequestType.CODE_GENERATION:
            # Use real Qwen Coder
            from .qwen_coder_handler import get_qwen_handler
            handler = get_qwen_handler()
            
            qwen_request = QwenRequest(
                prompt=request.prompt,
                context=request.context.get("context") if request.context else None,
                language=request.context.get("language", "python") if request.context else "python"
            )
            
            qwen_response = handler.generate_code(qwen_request)
            
            if qwen_response.success:
                content = qwen_response.code
            else:
                raise Exception(qwen_response.error)
        else:
            # For analysis/text, use basic local model via Ollama
            content = await self._call_ollama(request.prompt)
        
        processing_time = time.time() - start_time
        
        return AIResponse(
            request_id=request.request_id,
            success=True,
            content=content,
            processing_time=processing_time,
            model_used="qwen" if request.request_type == AIRequestType.CODE_GENERATION else "local"
        )
        
    except Exception as e:
        processing_time = time.time() - start_time
        return AIResponse(
            request_id=request.request_id,
            success=False,
            content="",
            error_message=str(e),
            processing_time=processing_time
        )

async def _call_ollama(self, prompt: str) -> str:
    """Helper to call Ollama API."""
    try:
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={"model": "qwen", "prompt": prompt, "stream": False},
            timeout=30
        )
        if response.status_code == 200:
            return response.json().get("response", "")
        else:
            return f"Ollama error: {response.status_code}"
    except Exception as e:
        return f"Connection error: {e}"
```

---

### Fix #2: Improve Queue Task Routing

**File**: `agent/ai_driver_pipeline.py`  
**Lines**: 197-259 (_execute_task)

**ADD after line 200**:
```python
def _execute_task(self, task_id: str) -> bool:
    task = self.tasks[task_id]
    task.status = TaskStatus.RUNNING
    task.started_at = datetime.now()
    
    self.logger.info(f"Executing task {task_id}: {task.name}")
    self.vox_integration.on_task_starting(task)
    
    # ← ADD THIS ROUTING LOGIC
    # Route based on task type
    if self._is_code_generation_task(task):
        return self._execute_code_generation_task(task)
    elif self._is_python_script_task(task):
        return self._execute_python_script(task)
    else:
        return self._execute_generic_script(task)

def _is_code_generation_task(self, task: PipelineTask) -> bool:
    """Check if task requires code generation."""
    if not task.name or not task.description:
        return False
    
    keywords = ["code", "qwen", "generate", "write", "function", "class", "algorithm"]
    text = (task.name + " " + task.description).lower()
    return any(kw in text for kw in keywords)

def _execute_code_generation_task(self, task: PipelineTask) -> bool:
    """Execute code generation via Qwen Coder."""
    try:
        from .qwen_coder_handler import get_qwen_handler, QwenRequest
        
        handler = get_qwen_handler()
        
        # Check if model is available
        if not handler.check_model_available():
            raise Exception("Qwen Coder model not available. Start Ollama with: ollama run qwen:7b-code")
        
        # Create request
        qwen_request = QwenRequest(
            prompt=task.script_content or task.name,
            context=task.description,
            language="python"
        )
        
        # Progress callback
        def on_progress(msg: str):
            self.logger.info(f"[{task.id}] {msg}")
            self.vox_integration.on_task_progress(task, msg)
        
        # Generate code
        response = handler.generate_code(qwen_request, progress_callback=on_progress)
        
        if not response.success:
            raise Exception(response.error)
        
        # Save result
        output_file = self.base_dir / "ai-mind" / "tasks" / "active" / f"{task.id}_generated.py"
        output_file.write_text(response.code)
        
        task.result = {
            "generated_code": response.code,
            "generation_time": response.generation_time,
            "tokens": response.tokens_used
        }
        
        task.status = TaskStatus.COMPLETED
        task.completed_at = datetime.now()
        self.completed_tasks.append(task_id)
        self.stats['completed_tasks'] += 1
        
        self.logger.info(f"Task {task_id} code generation completed in {response.generation_time:.2f}s")
        self.vox_integration.on_task_completed(task, response.generation_time)
        
        return True
        
    except Exception as e:
        task.error_message = str(e)
        task.retry_count += 1
        
        self.logger.error(f"Code generation failed: {e}")
        
        if task.auto_retry and task.retry_count < task.max_retries:
            task.status = TaskStatus.RETRYING
            self.vox_integration.on_task_failed(task, str(e), task.retry_count)
            time.sleep(2 ** task.retry_count)
            self._enqueue_task(task_id)
            return False
        else:
            task.status = TaskStatus.FAILED
            self.failed_tasks.append(task_id)
            self.stats['failed_tasks'] += 1
            self.vox_integration.on_task_failed(task, str(e), task.retry_count)
            return False

def _execute_python_script(self, task: PipelineTask) -> bool:
    """Execute Python script (existing logic)."""
    # ... use existing _execute_script_content() logic ...
    return self._execute_script_content(task)

def _execute_generic_script(self, task: PipelineTask) -> bool:
    """Execute generic script (existing logic)."""
    # ... use existing _execute_script_file() logic ...
    return self._execute_script_file(task)
```

---

### Fix #3: Add Dependency Timeout Detection

**File**: `agent/ai_driver_pipeline.py`  
**Lines**: 185-195 (_can_execute_task)

**REPLACE**:
```python
def _can_execute_task(self, task_id: str) -> bool:
    """Check if task dependencies are satisfied."""
    task = self.tasks[task_id]
    
    for dep_id in task.dependencies:
        if dep_id not in self.completed_tasks:
            # ✗ OLD: Just return False
            return False
    
    return True
```

**WITH**:
```python
def _can_execute_task(self, task_id: str) -> bool:
    """Check if task dependencies are satisfied with timeout detection."""
    task = self.tasks[task_id]
    current_time = datetime.now()
    
    # Initialize dependency wait time if not set
    if not hasattr(task, '_dependency_wait_start'):
        task._dependency_wait_start = {}
    
    for dep_id in task.dependencies:
        if dep_id not in self.completed_tasks:
            # Track wait start time
            if dep_id not in task._dependency_wait_start:
                task._dependency_wait_start[dep_id] = current_time
            
            # Check for timeout (10 minutes default)
            wait_duration = (current_time - task._dependency_wait_start[dep_id]).total_seconds()
            
            if wait_duration > 600:  # 10 minutes
                self.logger.error(
                    f"DEPENDENCY TIMEOUT: Task {task_id} waiting for {dep_id} "
                    f"for {wait_duration:.1f} seconds"
                )
                
                # Check if dependency is stuck
                dep_task = self.tasks.get(dep_id)
                if dep_task:
                    self.logger.error(
                        f"Dependency {dep_id} status: {dep_task.status.value}, "
                        f"retries: {dep_task.retry_count}/{dep_task.max_retries}"
                    )
                
                # Notify user
                self.vox_integration.on_dependency_timeout(task, dep_id, wait_duration)
                
                # Mark as failed to break deadlock
                if wait_duration > 1200:  # 20 minutes - hard timeout
                    task.status = TaskStatus.FAILED
                    task.error_message = f"Dependency {dep_id} timeout"
                    self.failed_tasks.append(task_id)
                    return False
            
            return False
    
    return True
```

---

### Fix #4: Reduce Worker Threads for Local Models

**File**: `agent/ai_driver_pipeline.py`  
**Line**: 364-368 (start method)

**BEFORE**:
```python
def start(self):
    """Start the pipeline."""
    if self.is_running:
        return
    
    self.is_running = True
    self.stats['start_time'] = datetime.now()
    
    # Start worker threads
    self.workers = []
    for i in range(self.max_workers):  # ← Uses all configured workers
        worker = threading.Thread(target=self._worker_loop, args=(i+1,))
        worker.daemon = True  # ← Killed abruptly
        worker.start()
```

**AFTER**:
```python
def start(self):
    """Start the pipeline with smart worker allocation."""
    if self.is_running:
        return
    
    self.is_running = True
    self.stats['start_time'] = datetime.now()
    
    # Detect if using local models and reduce workers to avoid GPU contention
    effective_workers = self.max_workers
    if self._has_local_models():
        effective_workers = min(2, self.max_workers)
        self.logger.info(
            f"Local models detected. Reducing workers from {self.max_workers} "
            f"to {effective_workers} to avoid GPU contention."
        )
    
    # Start worker threads
    self.workers = []
    for i in range(effective_workers):
        worker = threading.Thread(
            target=self._worker_loop,
            args=(i+1,),
            name=f"HDS6-Pipeline-Worker-{i+1}",
            daemon=False  # Allow graceful shutdown
        )
        worker.start()
        self.workers.append(worker)
    
    self.logger.info(f"Pipeline started with {effective_workers} workers")
    self.vox_integration.on_pipeline_started(effective_workers)

def _has_local_models(self) -> bool:
    """Check if any local models are configured."""
    # This is a simple heuristic - can be improved
    return any(
        "local" in str(p.config.get("base_url", "")).lower()
        or "localhost" in str(p.config.get("base_url", "")).lower()
        for p in self.providers.values()
    ) if hasattr(self, 'providers') else False
```

---

### Fix #5: Add Queue Status Monitoring

**File**: `agent/ai_driver_pipeline.py`  
**Add to _worker_loop method around line 340**:

```python
def _worker_loop(self, worker_id: int):
    """Worker thread main loop with status monitoring."""
    self.logger.info(f"Worker {worker_id} started")
    
    stuck_task_check_counter = 0
    
    while self.is_running:
        task_id = None
        
        # Get next available task
        with threading.Lock():
            for tid in self.task_queue[:]:
                if self._can_execute_task(tid) and tid not in self.running_tasks:
                    task_id = tid
                    self.task_queue.remove(tid)
                    break
        
        if task_id:
            # Execute task
            self.running_tasks[task_id] = threading.current_thread()
            try:
                self._execute_task(task_id)
            finally:
                self.running_tasks.pop(task_id, None)
                self.stats['last_activity'] = datetime.now()
            
            stuck_task_check_counter = 0  # Reset on successful task
        else:
            # No tasks available
            stuck_task_check_counter += 1
            
            # Every 30 seconds, report queue status
            if stuck_task_check_counter % 30 == 0:
                pending = len(self.task_queue)
                running = len(self.running_tasks)
                
                self.logger.info(
                    f"Worker {worker_id}: Queue status - "
                    f"Pending: {pending}, Running: {running}"
                )
                
                # Notify via VOX if queue is stuck
                if pending > 0 and running == 0:
                    self.logger.warning(
                        f"Potential queue deadlock: {pending} tasks pending, "
                        f"0 running. Checking dependencies..."
                    )
                    self.vox_integration.on_queue_stuck(pending)
            
            time.sleep(1)
    
    self.logger.info(f"Worker {worker_id} stopped")
```

---

## 📋 TESTING CHECKLIST

After implementing fixes:

- [ ] Test Qwen Coder availability check
- [ ] Test real code generation (requires running ollama/lms)
- [ ] Test dependency timeout detection with circular dependencies
- [ ] Test reduced worker count with local models
- [ ] Test queue status reporting
- [ ] Monitor CPU usage with multiple workers
- [ ] Verify no busy-waiting when queue is empty
- [ ] Test task failure recovery
- [ ] Verify VOX notifications for blocked tasks

---

## 🚀 QUICK START AFTER FIXES

```bash
# 1. Start Qwen Coder locally
ollama pull qwen:7b-code
ollama run qwen:7b-code

# 2. Start HDS6 pipeline
python -c "
from agent.ai_driver_pipeline import AIDriverPipeline, PipelineTask, TaskPriority
pipeline = AIDriverPipeline()
pipeline.start()

# Add code generation task
task = PipelineTask(
    id='gen_001',
    name='Generate Fibonacci Function',
    description='Write efficient fibonacci function',
    script_content='Create a function that calculates fibonacci(n)',
    priority=TaskPriority.HIGH
)
pipeline.add_task(task)
"

# 3. Monitor execution
# ... pipeline will now actually call Qwen Coder
```

