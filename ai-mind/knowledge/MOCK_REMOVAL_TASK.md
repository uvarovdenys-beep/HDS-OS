# MOCK-REMOVAL-001: Verification & Deletion Task

**Task ID**: MOCK-REMOVAL-001  
**Status**: 🔒 LOCKED (Verification in progress)  
**Created**: 2026-05-10  
**Target Completion**: 2026-05-17  
**Category**: SYSTEM HARDENING  

---

## Overview

This is a **LOCKING TASK** that prevents removal of mock code until all real implementations are verified working in production.

Once this task is marked COMPLETE:
- All mock code will be **permanently deleted**
- Deletion is **ONE-WAY** (cannot be restored)
- System becomes **100% real** with no fallback

---

## Why This Task Exists

HDS enforces a NO-MOCK policy:
- Mocking is **FORBIDDEN** in production code
- Real implementations are **MANDATORY**
- Fallback behavior is **NOT ALLOWED**

This task ensures mock code removal is tracked and intentional.

---

## Verification Checklist

**ALL ITEMS MUST BE VERIFIED BEFORE DELETION**

### Vision Daemon (Port 9001)

- [ ] **Screen Capture**: Real PyAutoGUI screenshot (not simulated)
  - Test: `curl -X POST http://localhost:9001/execute -d '{"type":"capture_screen","task_id":"VERIFY-001"}'`
  - Expected: Actual PNG file saved to `ai-mind/tasks/captures/`
  - NOT expected: Simulated with `time.sleep(0.5)`

- [ ] **Image Analysis**: Real OpenCV processing (not hardcoded)
  - Test: Submit real image, verify OpenCV analysis
  - Expected: Real button/input/text detection via CV algorithms
  - NOT expected: Hardcoded `["button", "text", "input_field"]`

- [ ] **Element Detection**: Real CV element detection (not fake data)
  - Test: Detect 10-15 actual elements with real bounding boxes
  - Expected: Actual contours, MSER, edge detection results
  - NOT expected: Fixed 2-element mock responses

- [ ] **OCR**: Real Tesseract text extraction (not mock)
  - Test: Extract text from image with Tesseract
  - Expected: Actual OCR output (may be empty if no text in image)
  - NOT expected: "Text detected (OCR unavailable)"

### Browser Daemon (Port 9002)

- [ ] **Navigation**: Real Playwright browser (not simulated)
  - Test: `curl -X POST http://localhost:9002/execute -d '{"type":"navigate","task_id":"VERIFY-002","url":"https://example.com"}'`
  - Expected: Real Chromium instance, network wait, actual page title
  - NOT expected: `time.sleep(1.0)` followed by `"title": "Mock Page Title"`

- [ ] **Element Interaction**: Real Playwright clicking (not fake)
  - Test: Click actual element with CSS selector
  - Expected: Real element found and clicked, potential navigation
  - NOT expected: Simulated with `time.sleep(0.5)` and fixed response

- [ ] **DOM Extraction**: Real HTML parsing (not template)
  - Test: Extract page DOM and convert to markdown
  - Expected: Real page content, variable token savings (46-70%)
  - NOT expected: Static template like `"# Page Content\n\nThis is a mock extraction."`

- [ ] **Token Savings**: Actual calculation (not hardcoded "~70%")
  - Test: Verify real HTML → Markdown conversion reduces tokens
  - Expected: Real percentage based on actual conversion
  - NOT expected: Fixed "~70%" or "Token savings: ~70%"

### System Behavior

- [ ] **Startup**: System starts ONLY with real implementations
  - Test: Stop all daemons, start system
  - Expected: System initializes all real daemons
  - NOT expected: "Falling back to mock" messages

- [ ] **Dependency Failure**: Missing deps cause FATAL startup error
  - Test: Uninstall OpenCV, try to start Vision daemon
  - Expected: `[Vision Daemon] ❌ FATAL: Real implementation not available` + sys.exit(1)
  - NOT expected: Graceful fallback to mock behavior

- [ ] **No Mock Code In Process Memory**
  - Test: Check running processes, verify no mock implementation loaded
  - Expected: Only real implementations in memory
  - NOT expected: Any mock simulation code

### Documentation

- [ ] **README**: No references to "mock" or "fallback"
  - Updated: All docs reflect real-only status
  - Removed: References to graceful degradation or mock fallback

- [ ] **Architecture Docs**: Clear that system is real-only
  - Updated: HDS_ARCHITECTURE.md references real implementations only
  - Removed: Adapter pattern documentation

- [ ] **Release Notes**: v1.1 documents transition to real-only
  - Updated: RELEASE_NOTES.md shows mock removal timeline
  - Removed: Mock fallback mentions

---

## Mock Code to Delete (After Verification)

Once this task is COMPLETE, these files/code will be **PERMANENTLY DELETED**:

### Files to Delete
```
# No mock files exist - only real implementations
# Real implementations: vision_daemon_real.py, browser_daemon_real.py
# Adapters now enforce real-only: vision_daemon.py, browser_daemon.py
```

### Code to Delete from agent/

```python
# FROM agent/vision_daemon.py:
# (ALREADY DELETED - NO MOCK FALLBACK)

# FROM agent/browser_daemon.py:
# (ALREADY DELETED - NO MOCK FALLBACK)
```

**Status**: Mock fallback code already removed. Only deletion step remaining: verify then document completion.

---

## Verification Process

### Step 1: Manual Testing (2026-05-10 to 2026-05-14)
- [ ] Test each Vision daemon feature manually
- [ ] Test each Browser daemon feature manually
- [ ] Verify startup behavior with missing dependencies
- [ ] Document all successful tests

### Step 2: Production Verification (2026-05-15 to 2026-05-17)
- [ ] Run system in production environment for 3 days
- [ ] Verify real operations under load
- [ ] Monitor for any fallback-to-mock behavior (should be zero)
- [ ] Document production test results

### Step 3: Completion (2026-05-17)
- [ ] Sign off on all checklist items
- [ ] Create completion report
- [ ] Mark task as VERIFIED ✅
- [ ] Proceed with mock code deletion (one-way)

---

## Post-Deletion (After Verification Complete)

### Git Commands to Execute
```bash
# After task is marked VERIFIED
cd HDS_creator_OS

# Document the completion
git log --oneline | head -1
# Should show "Complete MOCK-REMOVAL-001 verification"

# This creates the one-way gate
# Mocks CANNOT be restored without major version downgrade
```

### Timeline After Verification
- **2026-05-20**: Final deletion commit
- **2026-06-01**: v1.2.0 release (100% real, zero mocks, zero fallback)
- **2026-06-01+**: Production grade only

---

## What Happens If Verification Fails

If any verification item **FAILS**:

1. **Do NOT delete any code**
2. **Task remains LOCKED**
3. **Fix the failing component**
4. **Restart verification from failing point**
5. **Do NOT continue until ALL items pass**

Example:
- Vision daemon captures real screenshots ✅
- Vision daemon analyzes real images ✅
- Vision daemon detects elements ❌ **FAILS**
  - Fix element detection in vision_daemon_real.py
  - Re-test element detection
  - Restart from step 3
  - Do NOT proceed to Browser daemon until Vision is 100% passing

---

## Exception Policy

**There are NO exceptions to this verification process.**

Questions like:
- "Can we delete mock code anyway?" → **NO**
- "Can we keep some mock fallback?" → **NO**
- "Can we mark incomplete items as done?" → **NO**

**All items must be verified or task remains LOCKED.**

---

## Current Status

### Completed (v1.1 Release)
- ✅ Real Vision daemon implemented
- ✅ Real Browser daemon implemented
- ✅ Real Webhook API implemented
- ✅ Mock fallback removed from adapters
- ✅ NO-MOCK policy documented
- ✅ This verification task created

### In Progress (v1.1 Verification)
- 🔄 Manual testing of real implementations
- 🔄 Production verification
- 🔄 Documentation review

### To Do (v1.2 Release)
- ⏳ Complete all verification items
- ⏳ Delete all remaining mock code
- ⏳ Release v1.2.0 (100% real)

---

## Responsible Team

**Architect**: HDS Development Team  
**Verification Lead**: TBD (Assign person responsible for sign-off)  
**System Owner**: TBD (Assign person who approves deletion)  

---

## Lock Mechanism

**This task LOCKS the system from removing any mock code.**

To remove the lock:

1. **All items above must be checked** ☑️
2. **Verification lead must sign off**
3. **System owner must approve**
4. **Task status must be changed to VERIFIED**

Without all three, mock code CANNOT be deleted.

---

## Summary

| Phase | Status | Deliverable |
|-------|--------|------------|
| Real Implementation | ✅ DONE | vision_daemon_real.py, browser_daemon_real.py |
| NO-MOCK Enforcement | ✅ DONE | vision_daemon.py, browser_daemon.py (no fallback) |
| Verification Task | 🔄 ACTIVE | This document (MOCK-REMOVAL-001) |
| Mock Code Removal | ⏳ LOCKED | Awaiting task completion |
| v1.2 Release | ⏳ PENDING | 100% real, zero mocks |

---

**Task Type**: LOCKING TASK  
**Priority**: CRITICAL  
**Block**: Mock code deletion  
**Date Created**: 2026-05-10  
**Est. Completion**: 2026-05-17  
**Status**: 🔒 ACTIVE & LOCKED
