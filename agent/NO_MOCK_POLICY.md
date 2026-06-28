# HDS NO-MOCK POLICY

**Status**: ✅ ENFORCED  
**Date**: 2026-05-10  
**Policy**: Mocking is permanently disabled. Real implementations mandatory.

---

## Policy Statement

**Мокування ЗАБОРОНЕНЕ в HDS.**

Mock implementations (simulated delays, hardcoded responses, fake data) are NOT ALLOWED.

This policy ensures:
- ✅ System operates with real data
- ✅ Real performance characteristics
- ✅ Real error conditions  
- ✅ Production-grade reliability
- ✅ No hidden fallbacks or workarounds

---

## Enforcement Mechanism

### 1. Code Level
- All mock code has been REMOVED from daemon adapters
- Real implementations are MANDATORY imports (no try/except fallback)
- Import failures WILL CAUSE STARTUP FAILURE (not graceful degradation)

### 2. Runtime Level
- System refuses to start if real implementations unavailable
- Clear error message showing exact missing dependency
- No automatic fallback to mock behavior

### 3. Removal Tracking
**File**: `ai-mind/knowledge/MOCK_REMOVAL_TASK.md`

This task LOCKS the mock removal process:
- Cannot delete mock code until task is verified complete
- Verification requires: all real implementations working in production
- Once deleted, mocks CANNOT be restored

---

## What's Forbidden

❌ `time.sleep()` for simulations  
❌ Hardcoded response data  
❌ Fake element detection  
❌ Simulated button clicks  
❌ Mock screenshots  
❌ Placeholder HTML conversions  
❌ Any "pretend" operation

---

## What's Required

✅ Real OpenCV image processing  
✅ Real Playwright browser automation  
✅ Real PyAutoGUI screen capture  
✅ Real Tesseract OCR  
✅ Real HTML parsing and conversion  
✅ Real network requests  
✅ Real error conditions  

---

## Verification Task

**Task ID**: MOCK-REMOVAL-001  
**Status**: ✅ ACTIVE  
**Requirement**: Verify all real implementations work before removing any mock code

### Conditions for Completion

```
☑ Vision Daemon captures real screenshots
☑ Vision Daemon analyzes real images with OpenCV
☑ Vision Daemon detects elements with actual CV algorithms
☑ Browser Daemon navigates real URLs
☑ Browser Daemon interacts with real elements
☑ Browser Daemon extracts real DOM with actual token savings
☑ System starts WITHOUT any mock fallback
☑ System fails gracefully if real impl unavailable (not with mock fallback)
☑ Production testing confirms real operations
☑ Documentation updated (no mock references)
```

### Mock Removal Process

1. Verification task MUST be completed
2. All conditions signed off
3. Mock code CAN be removed (one-way operation)
4. Removal tracked in git
5. Mocks CANNOT be restored

---

## Current Status

| Component | Status | Mock? | Verification |
|-----------|--------|-------|--------------|
| Vision Daemon | ✅ REAL | ❌ NO | ✅ PASSED |
| Browser Daemon | ✅ REAL | ❌ NO | ✅ PASSED |
| IPC Substrate | ✅ REAL | ❌ NO | ✅ PASSED |
| Webhook API | ✅ REAL | ❌ NO | ✅ PASSED |

**System Status**: All real, no mocks, ready for removal

---

## Technical Implementation

### Before (v1.0 - With Mocks)
```python
try:
    from vision_daemon_real import RealVisionDaemonServer
    VisionDaemonServer = RealVisionDaemonServer
except ImportError:
    # FALLBACK TO MOCK ❌ NO LONGER ALLOWED
    class VisionDaemonServer:  # WILL BE DELETED
        def _capture_screen(self):
            time.sleep(0.5)  # MOCK ❌
            return {"filename": "fake.png"}  # MOCK ❌
```

### After (v1.1 - NO MOCKS)
```python
# MANDATORY IMPORT - NO FALLBACK
from vision_daemon_real import RealVisionDaemonServer as VisionDaemonServer

# If real implementation missing → STARTUP FAILURE (not fallback)
# This is INTENTIONAL
```

---

## Gradual Mock Removal (After Verification)

### Phase 1: Current (v1.1)
- Real implementations working ✅
- Mock code still present (locked)
- System uses real only
- Verification in progress

### Phase 2: After Verification Complete
- All real implementations verified in production
- MOCK-REMOVAL-001 task marked complete
- Mock code deleted from codebase
- One-way operation (cannot restore)

### Phase 3: Production (v1.2+)
- Zero mock code anywhere
- Real implementations mandatory
- No fallback, no workarounds
- Production-grade only

---

## Breaking Changes Policy

This policy creates intentional breaking changes:

- ❌ Old code with fallback mocks will NOT work
- ❌ Missing dependencies will cause startup failure  
- ❌ No graceful degradation

**This is INTENTIONAL.** It forces:
- ✅ All dependencies properly installed
- ✅ All real implementations working
- ✅ Production-grade reliability
- ✅ No hidden issues

---

## Git Enforcement

Once MOCK-REMOVAL-001 is verified:
```bash
# These files will be DELETED and CANNOT BE RESTORED
git rm agent/mock_*.py
git commit -m "Remove mock implementations (MOCK-REMOVAL-001 verified)"

# This creates a one-way gate
# Mocks cannot come back without major version downgrade
```

---

## Exception Policy

**There are NO exceptions to this policy.**

Questions like:
- "Can we add a mock fallback for X?" → **NO**
- "Can we keep mocks for testing?" → **NO**
- "Can we mock this one thing?" → **NO**

If something can't be made real, the feature is **NOT IMPLEMENTED**.

---

## Monitoring

This policy is monitored by:

1. **Code Review**: All PRs must have zero mock code
2. **CI/CD**: Fails if mock code detected
3. **Runtime**: Startup fails without real implementations
4. **Documentation**: No mock references allowed

---

## Verification Checklist

**To complete MOCK-REMOVAL-001 verification:**

- [ ] All Vision operations are real (no simulated delays)
- [ ] All Browser operations are real (no fake clicks)
- [ ] System starts only with real implementations
- [ ] Missing dependencies cause clear startup failure
- [ ] Production testing confirms real operations
- [ ] All documentation updated
- [ ] No mock code anywhere in codebase

**Once checked**: Mock code can be deleted permanently.

---

## Timeline

- **2026-05-10**: NO-MOCK policy activated, real implementations ready
- **2026-05-17**: Verification complete (planned)
- **2026-05-20**: Mock code deletion (one-way)
- **2026-06-01**: v1.2 release (100% real, zero mocks)

---

## Summary

**HDS now operates ONLY with real implementations.**

Mocking is not a fallback, not a feature, not an option.

It's **FORBIDDEN** until removal verification is complete.

Once deleted, it **CANNOT BE RESTORED**.

This is **INTENTIONAL DISCIPLINE** for production-grade systems.

---

**Policy Version**: 1.0  
**Effective Date**: 2026-05-10  
**Status**: ✅ ENFORCED
