# HDS6 AI Task Context System

**Purpose**: Provide localized, task-specific information to AI assistants with critical constraints and capabilities.

---

## 🎯 Task Context Structure

### **Critical Information Format**
```
TASK: [task_id] - [brief_description]
CONTEXT: [specific_context_for_this_task]
CAPABILITIES: [available_tools_for_this_task]
CONSTRAINTS: [critical_restrictions]
FORBIDDEN: [absolute_prohibitions]
REQUIRED: [mandatory_actions]
FULL_DOCS: [path_to_complete_documentation]
```

---

## 📋 Task Type Templates

### **1. Web Research Task**

```
TASK: WEB_RESEARCH_001 - Analyze website content
CONTEXT: Extract structured data from specific URL for research purposes
CAPABILITIES:
- Browser agent with headless mode
- Content extraction and analysis
- Screenshot capture
- Text summarization
CONSTRAINTS:
- Security level: STANDARD
- Max requests: 10 per minute
- Content filtering: ENABLED
FORBIDDEN:
- Direct file downloads
- Form submissions
- JavaScript execution
- Access to sensitive domains
REQUIRED:
- Use HDS6Scribe for all file operations
- Include task_id in all operations
- Validate content before processing
FULL_DOCS: ai-mind/knowledge/hds6_ai_complete_documentation.md
```

### **2. Script Execution Task**

```
TASK: SCRIPT_EXEC_001 - Execute Python script
CONTEXT: Run automated data processing script with error handling
CAPABILITIES:
- AI-DRIVER pipeline execution
- Script validation and security check
- Resource monitoring
- Progress tracking
CONSTRAINTS:
- Max execution time: 5 minutes
- Memory limit: 512MB
- R-01 compliance: ENFORCED
FORBIDDEN:
- Direct file writes (use HDS6Scribe)
- Network requests without approval
- System-level operations
- Infinite loops
REQUIRED:
- Include task_id in script
- Handle all exceptions
- Log execution progress
- Cleanup resources on completion
FULL_DOCS: ai-mind/knowledge/hds6_ai_complete_documentation.md
```

### **3. Vision Automation Task**

```
TASK: VISION_AUTO_001 - GUI automation
CONTEXT: Automate user interface interactions for testing
CAPABILITIES:
- Screen capture and analysis
- Element detection and interaction
- Mouse/keyboard automation
- Safe mode protection
CONSTRAINTS:
- Safe mode: ALWAYS ENABLED
- Max actions per minute: 30
- Confidence threshold: 0.8
FORBIDDEN:
- System-level interactions
- Administrative operations
- Password input automation
- File system access
REQUIRED:
- Verify element before interaction
- Use human-like timing
- Log all actions
- Emergency stop capability
FULL_DOCS: ai-mind/knowledge/hds6_ai_complete_documentation.md
```

### **4. Data Analysis Task**

```
TASK: DATA_ANALYSIS_001 - Process dataset
CONTEXT: Analyze and visualize data from provided files
CAPABILITIES:
- Data processing and transformation
- Statistical analysis
- Chart generation
- Report creation
CONSTRAINTS:
- Max file size: 100MB
- Processing time limit: 10 minutes
- Memory usage: 1GB max
FORBIDDEN:
- External data sources
- Network connections
- System modifications
- Sensitive data exposure
REQUIRED:
- Validate input data format
- Use HDS6Scribe for outputs
- Include data provenance
- Handle missing values appropriately
FULL_DOCS: ai-mind/knowledge/hds6_ai_complete_documentation.md
```

### **5. Integration Task**

```
TASK: INTEGRATION_001 - Multi-component workflow
CONTEXT: Coordinate multiple HDS6 components for complex task
CAPABILITIES:
- Component orchestration
- Task dependency management
- Resource allocation
- Progress monitoring
CONSTRAINTS:
- Max concurrent components: 3
- Total execution time: 15 minutes
- Resource monitoring: ENABLED
FORBIDDEN:
- Circular dependencies
- Resource exhaustion
- Unbounded loops
- Direct component bypass
REQUIRED:
- Define clear dependencies
- Monitor resource usage
- Handle component failures
- Provide progress updates
FULL_DOCS: ai-mind/knowledge/hds6_ai_complete_documentation.md
```

---

## 🚨 Critical R-Series Constraints

### **R-01: File Size Limit**
```
CONSTRAINT: Max 1000 lines per file
VIOLATION: DECOMPOSITION REQUIRED
ACTION: Split into smaller files
CHECK: Use HDS6Scribe._check_size_alert()
```

### **R-13: Task-First Protocol**
```
CONSTRAINT: All operations require task_id
VIOLATION: Use HDS6 task pipeline
ACTION: Include task_id in all operations
CHECK: Verify task_id presence before execution
```

### **R-19: No Direct Writes**
```
CONSTRAINT: Use HDS6Scribe for file operations
VIOLATION: Replace with HDS6Scribe.write_file()
ACTION: Refactor to use controlled writes
CHECK: Audit all file operations
```

---

## ⚡ Quick Decision Matrix

| Task Type | Critical Constraint | Required Tool | Max Time | Emergency Stop |
|-----------|-------------------|---------------|----------|----------------|
| Web Research | Security Level | Browser Agent | 5 min | Close session |
| Script Execution | R-01 Compliance | AI-DRIVER | 5 min | Terminate process |
| Vision Automation | Safe Mode | Vision Controller | 3 min | Stop processing |
| Data Analysis | Memory Limit | Local Processing | 10 min | Cancel analysis |
| Integration | Resource Usage | HDS6 Integration | 15 min | Stop system |

---

## 🔧 Component Access Rules

### **Browser Agent**
```
ALLOWED: Headless navigation, content extraction
FORBIDDEN: Form submission, file downloads
SECURITY: Domain whitelist, content filtering
LIMITS: 10 requests/minute, 30 second timeout
```

### **AI-DRIVER Pipeline**
```
ALLOWED: Script execution, task management
FORBIDDEN: Direct system calls, network access
SECURITY: Script validation, resource monitoring
LIMITS: 5 minute timeout, 512MB memory
```

### **Vision Controller**
```
ALLOWED: Screen capture, element interaction
FORBIDDEN: System UI, administrative actions
SECURITY: Safe mode always on, confidence threshold
LIMITS: 30 actions/minute, emergency stop
```

### **British TTS**
```
ALLOWED: Text-to-speech synthesis
FORBIDDEN: Audio file manipulation
SECURITY: Content filtering, queue management
LIMITS: 10 messages/minute, voice selection
```

---

## 📊 Task Execution Checklist

### **Pre-Execution**
- [ ] Validate task_id format
- [ ] Check resource availability
- [ ] Verify security constraints
- [ ] Load required components
- [ ] Set monitoring parameters

### **During Execution**
- [ ] Monitor resource usage
- [ ] Log progress events
- [ ] Check constraint compliance
- [ ] Handle errors gracefully
- [ ] Update task status

### **Post-Execution**
- [ ] Cleanup resources
- [ ] Save results via HDS6Scribe
- [ ] Update task completion status
- [ ] Generate summary report
- [ ] Verify no violations occurred

---

## 🚨 Emergency Procedures

### **Resource Exhaustion**
```
SYMPTOM: Memory > 1GB or CPU > 90%
ACTION: Stop current task, release resources
RECOVERY: Restart with reduced scope
```

### **Security Violation**
```
SYMPTOM: Access to forbidden domain/operation
ACTION: Immediate termination, log violation
RECOVERY: Review security settings, retry with proper constraints
```

### **Component Failure**
```
SYMPTOM: Component unresponsive or error
ACTION: Isolate failed component, continue with alternatives
RECOVERY: Restart component, fallback to manual mode
```

### **Protocol Violation**
```
SYMPTOM: R-Series rule breach detected
ACTION: Stop operation, record violation
RECOVERY: Refactor to comply, retry with proper protocol
```

---

## 📝 Task Examples

### **Example 1: Safe Web Research**
```
TASK: WEB_RESEARCH_SAFE_001
GOAL: Extract article content from Wikipedia
APPROACH:
1. Create browser session with STANDARD security
2. Navigate to target URL
3. Extract text content only
4. Save via HDS6Scribe with task_id
5. Close session

CONSTRAINTS CHECKED:
✓ Security level: STANDARD
✓ Domain whitelist: wikipedia.org
✓ No form submissions
✓ Content filtering enabled
```

### **Example 2: Compliant Script Execution**
```
TASK: SCRIPT_SAFE_001
GOAL: Process CSV data and generate report
APPROACH:
1. Validate script with R-01 check
2. Execute via AI-DRIVER with task_id
3. Monitor memory usage (<512MB)
4. Save results via HDS6Scribe
5. Log completion

CONSTRAINTS CHECKED:
✓ Task_id included
✓ File size <1000 lines
✓ No direct writes
✓ Resource limits enforced
```

---

## 🔍 Context Optimization

### **Minimal Context (Default)**
```
TASK: [ID] - [Brief description]
CAPABILITIES: [Essential tools only]
CONSTRAINTS: [Critical restrictions only]
FORBIDDEN: [Absolute prohibitions]
```

### **Extended Context (On Request)**
```
[Full minimal context]
+
DETAILS: [Additional information]
EXAMPLES: [Usage examples]
TROUBLESHOOTING: [Common issues]
REFERENCES: [Full documentation links]
```

### **Full Documentation**
```
Reference: ai-mind/knowledge/hds6_ai_complete_documentation.md
Contains: Complete system documentation, all components, integration guides
Use: When detailed understanding is required for complex tasks
```

---

## 🎯 Implementation Guidelines

### **For AI Assistants**
1. **Always check constraints first** - Before any action
2. **Use minimal context by default** - Request extended only if needed
3. **Follow R-Series protocols strictly** - No exceptions
4. **Log all decisions** - Include reasoning in task logs
5. **Prioritize safety** - Emergency stop if uncertain

### **For Task Creators**
1. **Provide clear task objectives** - Specific, measurable goals
2. **Define appropriate constraints** - Not too restrictive, not too permissive
3. **Include relevant context** - Just enough for task completion
4. **Specify success criteria** - How to determine task completion
5. **Plan for failures** - Fallback options and error handling

---

## 📚 Quick Reference

### **Critical Commands**
```python
# Check constraints
if not validate_constraints(task):
    raise ConstraintViolation("Task violates R-Series protocols")

# Execute safely
try:
    result = execute_with_monitoring(task)
except Exception as e:
    handle_error_gracefully(e)
    emergency_stop()

# Save results
scribe = HDS6Scribe(base_dir)
scribe.write_file(output_path, result, task_id=task.id)
```

### **Emergency Numbers**
- **Resource Limit**: 1GB memory, 90% CPU
- **Time Limits**: 3-15 minutes by task type
- **Security Levels**: MINIMAL → STANDARD → STRICT → SANDBOX
- **Violation Response**: Immediate stop + log + report

---

**System Version**: 2.0  
**Last Updated**: May 8, 2026  
**Purpose**: Task-specific AI guidance with critical constraints
