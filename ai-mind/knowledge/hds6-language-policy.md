# HDS6 Language Policy
**Автоматичне перемикання мови на основі запиту користувача**

**Authors**: Уваров Денис Юрійович, Александров Микита Олександрович, Уварова Анастасія Сергіївна

---

## Політика HDS6

### Системна мова (HDS6 Core)
- **English** — всі системні файли HDS6, документація ядра, коментарі в коді
- Це забезпечує уніфікацію та сумісність між різними інсталяціями

### Мова відповідей ШІ
- **Автоматичне перемикання** на основі мови запиту користувача
- Якщо користувач пише українською → ШІ відповідає українською
- Якщо користувач пише англійською → ШІ відповідає англійською
- Якщо інша мова → Англійська (fallback)

## Принцип роботи

### Визначення мови запиту
```python
def detect_user_language(text: str) -> str:
    """
    Визначення мови запиту користувача.
    Повертає: 'uk', 'en', або 'auto'
    """
    cyrillic_chars = len(re.findall(r'[а-яА-ЯіїєґІЇЄҐ]', text))
    latin_chars = len(re.findall(r'[a-zA-Z]', text))
    
    if cyrillic_chars > latin_chars:
        return 'uk'  # Ukrainian
    elif latin_chars > 10:
        return 'en'  # English
    else:
        return 'auto'  # Невизначено, використати попередню
```

### Приклади перемикання

**Сценарій 1: Український запит**
```
Користувач: Створи задачу для парсингу JSON
ШІ: Готово. Створено файл ai-mind/tasks/active/045_json_parser.py
```

**Сценарій 2: Англійський запит**
```
User: Create a task for JSON parsing
AI: Done. Created file ai-mind/tasks/active/045_json_parser.py
```

**Сценарій 3: Змішаний запит**
```
Користувач: Create parser для JSON файлов
ШІ: [Визначає українську за перевагою кирилиці]
Готую задачу парсинга JSON...
```

## Технічні деталі

### Зберігання контексту мови
```python
# В сесії користувача зберігається preferred_language
user_context = {
    "preferred_language": "uk",  # або "en"
    "last_active": "2026-05-07T09:45:00"
}
```

### Пріоритет визначення
1. Явний запит користувача на зміну мови
2. Мова останнього повідомлення
3. Мова системи (fallback: en)

## Винятки

### Завжди англійською:
- Код (Python, JavaScript, etc.)
- Технічні терміни (API, JSON, URL)
- Шляхи файлів (`ai-mind/tasks/active/`)
- Назви функцій та класів

### Завжди мовою користувача:
- Пояснення та інструкції
- Помилки та попередження
- Документація створена для користувача
- Коментарі до коду (якщо файл для користувача)

## Впровадження в Compliance

### Оновлена перевірка R-08 (знята заборона)
```python
def check_r08_language_policy(self, content: str, is_response: bool) -> ComplianceResult:
    """
    R-08: Language matches user query (not enforced, only tracked).
    
    For HDS6 core: Always English.
    For AI responses: Match user language.
    """
    if not is_response:
        # Core files should be English
        return ComplianceResult(
            level=ViolationLevel.OK,
            rule_code="R-08",
            message="R-08 INFO: HDS6 core is English-language"
        )
    
    # For responses - just track, don't enforce
    detected_lang = self._detect_language(content)
    
    return ComplianceResult(
        level=ViolationLevel.OK,
        rule_code="R-08",
        message=f"R-08 OK: Response language detected as {detected_lang}"
    )
```

## Міграція з попередньої політики

### Старе правило (v1.0):
- R-08: PRIORITY_LANGUAGE — Ukrainian only

### Нове правило (v2.0):
- R-08: ADAPTIVE_LANGUAGE — Match user query
- HDS6 Core: English only
- AI Responses: User language

## Чекліст для ШІ

- [ ] Визначити мову запиту користувача
- [ ] Відповідати тією ж мовою
- [ ] HDS6 core файли залишати англійською
- [ ] Технічні терміни не перекладати
- [ ] При невизначеності — запитати користувача

---

**Policy Version**: 2.0  
**Effective Date**: 2026-05-07  
**Previous**: R-08 Ukrainian Priority (deprecated)
