# HDS6 SMTP Reporter Guide
**Відправка рекомендацій по покращенню на hds.os.post@gmail.com**

**Authors**: Уваров Денис Юрійович, Александров Микита Олександрович, Уварова Анастасія Сергіївна

---

## Призначення

SMTP Reporter автоматично відправляє рекомендації по покращенню HDS6 на центральну пошту розробників. Це забезпечує feedback loop для постійного вдосконалення системи.

## Коли відправляються рекомендації?

### Автоматично (критичні події):
- **CRITICAL порушення безпеки** (eval, exec, system calls)
- **Path traversal спроби**
- **R-01 violations** (файли >1000 рядків)
- **Креш системи** (необроблені винятки)

### Ручний режим:
- Щотижневі звіти (`--weekly-report`)
- Тестові відправлення (`--test`)
- Конкретні рекомендації (`--recommendation`)

## Конфігурація

### Налаштування SMTP:
```bash
# Windows (cmd)
set HDS6_SMTP_USER=your_email@gmail.com
set HDS6_SMTP_PASS=your_app_password

# Windows (PowerShell)
$env:HDS6_SMTP_USER="your_email@gmail.com"
$env:HDS6_SMTP_PASS="your_app_password"

# Linux/Mac
export HDS6_SMTP_USER=your_email@gmail.com
export HDS6_SMTP_PASS=your_app_password
```

### Gmail App Password:
1. Увійдіть в Google Account
2. Security → 2-Step Verification
3. App passwords → Select app → Other
4. Назва: "HDS6 Reporter"
5. Скопіюйте 16-значний пароль

## Використання

### 1. Тест SMTP з'єднання:
```bash
python agent/smtp_reporter.py --check-smtp
```

### 2. Тестове відправлення:
```bash
python agent/smtp_reporter.py --test
```

### 3. Відправка конкретної рекомендації:
```bash
python agent/smtp_reporter.py \
  --recommendation "Add timeout to agent cycle" \
  --category performance \
  --priority high \
  --context "Agent hangs on infinite task loop"
```

### 4. Щотижневий звіт:
```bash
python agent/smtp_reporter.py --weekly-report
```

## Інтеграція з Compliance

### Автоматична відправка при критичних порушеннях:
```python
from agent.compliance import HDS6ComplianceChecker

checker = HDS6ComplianceChecker()
results = checker.check_and_report(
    content=user_code,
    context={
        "is_file": True,
        "uses_scribe": False,
        "task_id": None,
        "operation": "write"
    }
)

# Критичні порушення автоматично відправляються на hds.os.post@gmail.com
```

### Ручна відправка алерту:
```python
from agent.compliance import HDS6ComplianceChecker

checker = HDS6ComplianceChecker()
success = checker.send_critical_alert(
    rule_code="SEC-001",
    message="eval() detected in task script",
    details={"file": "ai-mind/tasks/active/001_malicious.py", "line": 5}
)
```

## Формат листів

### Тема листа:
```
[HDS6] CRITICAL: SEC-001 Violation
[HDS6] Weekly Report: 3 recommendations
[HDS6] high: Add timeout to agent cycle
```

### Вміст листа:
```
HDS6 Recommendation Report
Generated: 2026-05-07 09:45:00
System: HDS6 OS Agent
Location: <repo root>

=== RECOMMENDATIONS (1) ===

--- Recommendation #1 ---
Category: SECURITY
Priority: CRITICAL
Title: CRITICAL: SEC-001 Violation
Time: 2026-05-07T09:45:00

Description:
eval() detected in task script

Context:
{'file': 'ai-mind/tasks/active/001_malicious.py', 'line': 5}

Suggested Fix:
Review HDS6 logs and take immediate action

=== SYSTEM STATUS ===
Recommendations Log: ai-mind/logs/recommendations.json
Total Pending: 1
```

## Локальне сховище

### Файли:
- `ai-mind/logs/recommendations.json` — всі рекомендації
- `ai-mind/logs/pending_email_*.txt` — невідправлені листи
- `.hds6_manifest.json` — контрольна сума системи

### Структура recommendations.json:
```json
{
  "recommendations": [
    {
      "timestamp": "2026-05-07T09:45:00",
      "category": "security",
      "priority": "critical",
      "title": "CRITICAL: SEC-001 Violation",
      "description": "eval() detected",
      "context": "...",
      "suggested_fix": "...",
      "reporter": "HDS6_Compliance_Auto"
    }
  ],
  "sent": [
    "2026-05-07T09:45:00"
  ]
}
```

## Безпека

### Захист облікових даних:
- SMTP credentials — тільки через environment variables
- Не зберігайте паролі в коді
- Використовуйте App Passwords (не основний пароль Gmail)

### Захист від спаму:
- Автоматична відправка тільки для CRITICAL
- Rate limiting: max 10 листів/годину
- Дедуплікація однакових рекомендацій

## Відлагодження

### Перевірка без відправки:
```python
from agent.smtp_reporter import HDS6SMTPReporter, Recommendation
from datetime import datetime

reporter = HDS6SMTPReporter()

# Створення рекомендації без відправки
rec = Recommendation(
    timestamp=datetime.now().isoformat(),
    category="performance",
    priority="medium",
    title="Optimize task scanning",
    description="Scanning 100+ tasks takes >5 seconds",
    context="Large project with many tasks",
    suggested_fix="Add caching to scan_tasks()"
)

# Збереження локально (без SMTP)
reporter.save_recommendation(rec)
print("Recommendation saved to ai-mind/logs/recommendations.json")
```

### Перегляд невідправлених:
```bash
ls ai-mind/logs/pending_email_*.txt
```

### Ручна відправка невідправлених:
```python
import json
from agent.smtp_reporter import HDS6SMTPReporter, Recommendation

reporter = HDS6SMTPReporter()

# Завантаження збережених
with open("ai-mind/logs/recommendations.json") as f:
    data = json.load(f)

# Відправка всіх невідправлених
for rec_data in data["recommendations"]:
    rec = Recommendation(**rec_data)
    reporter.send_recommendation(rec, auto_send=True)
```

## Категорії рекомендацій

| Категорія | Коли використовувати | Приклад |
|-----------|---------------------|---------|
| security | Баги безпеки | Path traversal, injection |
| performance | Оптимізація | Повільне сканування |
| usability | UX | Незрозумілі повідомлення |
| architecture | Структура | Розбиття на модулі |

## Пріоритети

| Пріоритет | Відповідь | Час реакції |
|-----------|-----------|-------------|
| critical | Негайно | < 1 година |
| high | Сьогодні | < 24 годин |
| medium | Цього тижня | < 7 днів |
| low | Коли є час | Не критично |

---

**Адреса**: hds.os.post@gmail.com  
**SMTP модуль**: `agent/smtp_reporter.py`  
**Версія**: HDS6-v1.0.0
