# HDS6 Internal Test Suite
**Вбудована система тестування HDS6 ОС**

**Authors**: Уваров Денис Юрійович, Александров Микита Олександрович, Уварова Анастасія Сергіївна

---

## Структура тестів в HDS6

```
HDS6/
├── agent/
│   ├── compliance.py       # ← Перевірка відповідності ШІ (R-Series)
│   ├── agent.py           # HDS (з тестами в __main__)
│   ├── vox.py             # PowerVox (з тестами в __main__)
│   ├── scribe.py          # OS DRIVER (з тестами в __main__)
│   └── _tests/            # ← Розширені тести агентів
│       ├── test_agent_core.py
│       ├── test_scribe_security.py
│       └── test_compliance_rules.py
├── ai-mind/knowledge/
│   └── hds6_test_suite.md # ← Цей файл (специфікація)
└── crash_test.py          # ← Головний краш-тест (зовнішній)
```

## Типи тестів

### 1. Self-Tests (вбудовані)
Кожен модуль має `self_test()` що запускається через `if __name__ == "__main__"`:

```bash
python agent/compliance.py    # Тест compliance
python agent/vox.py           # Тест PowerVox
python agent/scribe.py        # Тест OS DRIVER
```

### 2. Integration Tests (агенти)
Розширені тести в `agent/_tests/`:

| Тест | Призначення |
|------|-------------|
| `test_agent_core.py` | Цикли агента, сканування |
| `test_scribe_security.py` | R-01, R-19, path traversal |
| `test_compliance_rules.py` | R-Series валідація |

### 3. System Tests (зовнішні)
`crash_test.py` — комплексний стрес-тест.

## Список тестів HDS6

### Блок A: R-Series Compliance

| ID | Тест | Рівень | Опис |
|----|------|--------|------|
| R01-001 | Size OK | Unit | 500 рядків — дозволено |
| R01-002 | Size Warning 80% | Unit | 800 рядків — попередження |
| R01-003 | Size Critical 90% | Unit | 900 рядків — критичне |
| R01-004 | Size Violation 100% | Unit | 1001 рядок — відхилення |
| R01-005 | Size Alert Log | Integration | Перевірка що алерт записаний в лог |
| R08-001 | Language Ukrainian | Unit | Документація українською |
| R08-002 | Language Code OK | Unit | Код може бути англійською |
| R13-001 | Task ID Present | Unit | task_id присутній — OK |
| R13-002 | Task ID Missing | Unit | task_id відсутній — VIOLATION |
| R13-003 | Task ID Format | Unit | Перевірка формату TASK-001 |
| R18-001 | Inline Small | Unit | 10 рядків inline — OK |
| R18-002 | Inline Warning | Unit | 18 рядків — попередження |
| R18-003 | Inline Violation | Unit | 25 рядків — відхилення |
| R19-001 | Scribe Used | Unit | scribe.write_file() — OK |
| R19-002 | Direct Write Detected | Unit | open().write() — VIOLATION |

### Блок B: Security

| ID | Тест | Рівень | Опис |
|----|------|--------|------|
| SEC-001 | Eval Detection | Unit | eval() — CRITICAL |
| SEC-002 | Exec Detection | Unit | exec() — CRITICAL |
| SEC-003 | OS System Block | Unit | os.system() — CRITICAL |
| SEC-004 | Subprocess Block | Unit | subprocess.call() — CRITICAL |
| SEC-005 | Import Block | Unit | __import__() — CRITICAL |
| SEC-006 | Path Traversal | Integration | ../../../etc/passwd — блокування |
| SEC-007 | Path Absolute | Integration | /etc/passwd — блокування |

### Блок C: Agent Core (HDS)

| ID | Тест | Рівень | Опис |
|----|------|--------|------|
| MT-001 | Agent Init | Unit | Ініціалізація без помилок |
| MT-002 | Empty Cycle | Integration | Цикл без задач не падає |
| MT-003 | Task Scanning | Integration | Пошук 50+ задач |
| MT-004 | Task Execution | Integration | Виконання валідної задачі |
| MT-005 | Syntax Error Handle | Integration | Задача з синтаксичною помилкою — обробка |
| MT-006 | Vox Logging | Integration | 50 повідомлень під навантаженням |
| MT-007 | Archive Creation | Integration | Автоматичне створення .archive/ |

### Блок D: OS Driver (HDS6 Scribe)

| ID | Тест | Рівень | Опис |
|----|------|--------|------|
| OSD-001 | Basic Write | Unit | Запис файлу через scribe |
| OSD-002 | Deep Nesting | Unit | Створення 20 рівнів директорій |
| OSD-003 | Overwrite | Unit | Перезапис існуючого файлу |
| OSD-004 | Update File | Unit | Редагування частини файлу |
| OSD-005 | Empty Content | Unit | Запис порожнього файлу |
| OSD-006 | Unicode Filename | Unit | Файл з unicode ім'ям |
| OSD-007 | Binary Content | Unit | Бінарні дані в текстовому файлі |

### Блок E: PowerVox

| ID | Тест | Рівень | Опис |
|----|------|--------|------|
| VOX-001 | Basic Log | Unit | Запис повідомлення |
| VOX-002 | Long Message | Unit | Повідомлення 10KB |
| VOX-003 | Unicode | Unit | Unicode + emoji |
| VOX-004 | Special Path | Unit | Шлях з пробілами |
| VOX-005 | Rapid Fire | Stress | 100 msg/sec |
| VOX-006 | All Levels | Unit | INFO, WARN, ERROR, CRITICAL |

### Блок F: Integration & Stress

| ID | Тест | Рівень | Опис |
|----|------|--------|------|
| INT-001 | Full Pipeline | System | Scribe → Agent → Execution → Log |
| INT-002 | Agent + Tasks | System | 3 задачі послідовно |
| INT-003 | Error Recovery | System | Падіння задачі не падає агент |
| STR-001 | Many Files | Stress | 100 файлів одночасно |
| STR-002 | Unicode Storm | Stress | 50 unicode повідомлень |
| STR-003 | Rapid Tasks | Stress | 50 задач за 60 секунд |

## Запуск тестів

### Швидкий запуск (всі self-tests)
```bash
cd HDS6
python agent/compliance.py
python agent/vox.py
python agent/scribe.py
python -c "from agent.agent import HDS6Agent; print('Agent OK')"
```

### Розширені тести
```bash
python agent/_tests/test_agent_core.py
python agent/_tests/test_scribe_security.py
python agent/_tests/test_compliance_rules.py
```

### Повний краш-тест
```bash
python crash_test.py --quick
```

### Верифікація системи
```bash
python verify-hds6.py
```

## Очікувані результати

**Self-Tests:**
- compliance.py: ✓ 7/7 tests
- vox.py: ✓ 6/6 tests
- scribe.py: ✓ 10/10 tests

**Crash Test:**
- Quick mode: 85-95% pass rate
- Full mode: 80-90% pass rate

**Known Issues:**
- Path traversal на Windows (потребує виправлення)
- Unicode emoji в консолі Windows

## Тестування відповідності ШІ

### Як перевірити що ШІ дотримується правил:

```python
from agent.compliance import HDS6ComplianceChecker

checker = HDS6ComplianceChecker()

# Перевірка перед операцією
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

# Блокування якщо не compliant
if not checker.is_compliant(results):
    print("AI OPERATION BLOCKED: Non-compliant with R-Series")
    for r in results:
        if not r.allowed:
            print(f"  - {r.rule_code}: {r.message}")
```

### Автоматичні перевірки при кожній операції:

1. **До запису файлу** → compliance.check_all()
2. **Після генерації коду** → R-01 size check
3. **При inline пропозиції** → R-18 check (>20 lines)
4. **При зміні файлів** → R-19 check (scribe usage)
5. **При відповіді користувачу** → R-08 check (Ukrainian)

## Метрики якості

**Target Metrics:**
- Test Coverage: >80%
- R-Series Compliance: 100%
- Security Violations: 0
- Performance: <100ms per check

---

**Last Updated**: 2026-05-07
**Version**: HDS6 Test Suite v1.0
