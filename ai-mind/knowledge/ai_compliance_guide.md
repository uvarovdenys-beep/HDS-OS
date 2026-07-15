# AI Compliance Guide
**Як перевіряти дії ШІ на відповідність HDS6**

**Authors**: Уваров Денис Юрійович, Александров Микита Олександрович, Уварова Анастасія Сергіївна

---

## Швидкий старт

```python
from agent.compliance import HDS6ComplianceChecker, ViolationLevel

checker = HDS6ComplianceChecker()

# Перевірка згенерованого ШІ коду
results = checker.check_all(
    content=ai_generated_code,
    context={
        "is_file": True,
        "uses_scribe": True,
        "task_id": "042",
        "operation": "write",
        "filepath": "ai-mind/tasks/active/042_module.py"
    }
)

# Блокування не-compliant операцій
if not checker.is_compliant(results):
    raise ComplianceError("AI action blocked by R-Series protocol")
```

## Що перевіряється

### Перевірка перед записом файлу

```python
# ШІ генерує код для файлу
code = """
class NewModule:
    def run(self):
        return True

if __name__ == "__main__":
    NewModule().run()
"""

# Перевірка
result = checker.check_r01_size(code)
if result.level == ViolationLevel.VIOLATION:
    print(f"BLOCKED: {result.message}")
    # ШІ має розбити на менші файли
```

### Перевірка inline коду в чаті

```python
# ШІ пропонує код в чаті
inline_code = """
def big_function():
    line1
    line2
    ...
    line25
"""

result = checker.check_r18_no_inline(inline_code, is_file=False)
if result.level == ViolationLevel.VIOLATION:
    print("INLINE CODE TOO BIG - create task file instead")
    # ШІ має створити файл в tasks/active/ замість inline
```

### Перевірка використання Scribe

```python
# ШІ пропонує код з записом файлу
ai_code = """
with open('file.txt', 'w') as f:
    f.write('data')
"""

result = checker.check_r19_no_direct_write(ai_code, uses_scribe=False)
if result.level == ViolationLevel.VIOLATION:
    print("DIRECT WRITE DETECTED - use HDS6Scribe instead")
```

## Приклади порушень та виправлень

### R-01: Файл занадто великий

**Порушення:**
```python
# 1200 рядків в одному файлі
class Monolith:
    ...  # 1200 lines
```

**Виправлення:**
```
ai-mind/tasks/active/
├── 001a_parser.py      # 400 lines
├── 001b_validator.py   # 350 lines  
├── 001c_main.py        # 300 lines (імпортує a і b)
```

### R-13: Відсутній task_id

**Порушення:**
```python
scribe.write_file("ai-mind/test.py", "# code")  # Без task_id!
```

**Виправлення:**
```python
scribe.write_file(
    "ai-mind/tasks/active/042_test.py",
    "# code",
    task_id="042",  # Обов'язково!
    require_task=True
)
```

### R-18: Inline код >20 рядків

**Порушення (в чаті):**
```
ШІ: Ось код:
def function():
    line1
    line2
    ...
    line30
```

**Виправлення:**
```
ШІ: Створю файл ai-mind/tasks/active/042_function.py з цим кодом.
```

### R-19: Прямий запис файлів

**Порушення:**
```python
with open('config.txt', 'w') as f:
    f.write('settings')
```

**Виправлення:**
```python
from agent.scribe import HDS6Scribe
scribe = HDS6Scribe()
scribe.write_file(
    'ai-mind/knowledge/config.md',
    '# Settings\nsettings',
    task_id='CFG01'
)
```

## Автоматичні перевірки (рекомендовані)

### 1. Перед кожною відповіддю ШІ

```python
def ai_response_filter(text: str) -> str:
    """Фільтр відповідей ШІ на відповідність R-Series."""
    checker = HDS6ComplianceChecker()
    
    # Перевірка R-08: Українська мова (для non-code)
    if not checker._is_code(text):
        result = checker.check_r08_language(text)
        if result.level == ViolationLevel.WARNING:
            text = f"[R-08 WARNING] {result.message}\n\n{text}"
    
    return text
```

### 2. Перед записом будь-якого файлу

```python
def ai_file_write_guard(filepath: str, content: str, task_id: str = None):
    """Захист запису файлів від ШІ."""
    checker = HDS6ComplianceChecker()
    
    # Перевірка всіх правил
    context = {
        "is_file": True,
        "uses_scribe": True,
        "task_id": task_id,
        "operation": "write",
        "filepath": filepath
    }
    
    results = checker.check_all(content, context)
    
    if not checker.is_compliant(results):
        violations = [r for r in results if not r.allowed]
        raise PermissionError(
            f"AI write blocked: {[v.rule_code for v in violations]}"
        )
```

### 3. Моніторинг активності ШІ

```python
class AIActivityMonitor:
    """Моніторинг всіх дій ШІ."""
    
    def __init__(self):
        self.checker = HDS6ComplianceChecker()
        self.violations_log = []
    
    def log_ai_action(self, action_type: str, content: str, context: dict):
        """Логування та перевірка дії ШІ."""
        results = self.checker.check_all(content, context)
        
        for result in results:
            if result.level in (ViolationLevel.VIOLATION, ViolationLevel.CRITICAL):
                self.violations_log.append({
                    "action": action_type,
                    "rule": result.rule_code,
                    "message": result.message,
                    "timestamp": datetime.now().isoformat()
                })
        
        return self.checker.is_compliant(results)
```

## Логування порушень ШІ

### Формат запису:
```json
{
  "timestamp": "2026-05-07T09:45:00",
  "ai_action": "file_write",
  "violation": {
    "rule": "R-01",
    "level": "VIOLATION", 
    "message": "Content has 1200 lines (max 1000)",
    "context": {
      "filepath": "ai-mind/tasks/active/001_big.py",
      "task_id": "001"
    }
  },
  "resolution": "BLOCKED"
}
```

### Локація логів:
- `ai-mind/logs/ai_violations.log` — порушення ШІ
- `ai-mind/logs/vox.log` — загальні події
- `ai-mind/logs/compliance_audit.log` — аудит перевірок

## Чекліст для ШІ

Перед кожною операцією ШІ має перевірити:

- [ ] **R-01**: Файл < 1000 рядків? (Якщо >800 — планувати декомпозицію)
- [ ] **R-08**: Відповідь українською (для non-code)?
- [ ] **R-13**: Є task_id для запису файлів?
- [ ] **R-18**: Inline код < 20 рядків?
- [ ] **R-19**: Використовується scribe.write_file()?
- [ ] **SEC**: Немає eval/exec/os.system?

## Приклад повної інтеграції

```python
# ai_controller.py
from agent.compliance import HDS6ComplianceChecker, ViolationLevel
from agent.vox import VoxService

class AIController:
    """Контролер дій ШІ з HDS6 compliance."""
    
    def __init__(self):
        self.checker = HDS6ComplianceChecker()
        self.vox = VoxService()
    
    def approve_file_write(self, filepath: str, content: str, task_id: str) -> bool:
        """Схвалення запису файлу від ШІ."""
        context = {
            "is_file": True,
            "uses_scribe": True,
            "task_id": task_id,
            "operation": "write",
            "filepath": filepath
        }
        
        results = self.checker.check_all(content, context)
        
        if self.checker.is_compliant(results):
            self.vox.speak(f"AI file write approved: {filepath}")
            return True
        else:
            for result in results:
                if result.level == ViolationLevel.VIOLATION:
                    self.vox.speak(f"AI VIOLATION {result.rule_code}: {result.message}", "ERROR")
            return False
    
    def approve_chat_response(self, response: str) -> str:
        """Схвалення відповіді в чаті."""
        # Перевірка R-18 (inline code)
        if self.checker._is_code(response):
            result = self.checker.check_r18_no_inline(response, is_file=False)
            if result.level == ViolationLevel.VIOLATION:
                return f"[SYSTEM: {result.message}]\n\nCreate task file instead."
        
        # Перевірка R-08 (language)
        result = self.checker.check_r08_language(response)
        if result.level == ViolationLevel.WARNING:
            return f"[R-08 TIP: {result.message}]\n\n{response}"
        
        return response

# Використання
controller = AIController()
approved = controller.approve_file_write("test.py", "# code", "001")
```

## Результат

З цим гайдом ШІ може:
1. Перевіряти сам себе перед кожною дією
2. Автоматично блокувати порушення R-Series
3. Логувати всі спроби порушень для аудиту
4. Пропонувати виправлення замість заборони (де можливо)

---

**Integration**: `from agent.compliance import HDS6ComplianceChecker`
**Test**: `python agent/compliance.py`
**Version**: HDS6 AI Compliance v1.0
