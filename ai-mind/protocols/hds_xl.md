# HDS XL — Протокол для архітекторів

> Розмір: XL | Діагностичний бал: 15-18
> Для: Opus, GPT-4, DeepSeek-R1 70B+, Qwen 72B

---

## BOOT (повний, 4 кроки)

```
1. ai-mind/config/          → середовище, ключі, обмеження
2. ai-mind/architecture/    → project-map.md, entrypoints.md
3. ai-mind/tasks/active/    → поточні задачі
4. ai-mind/ideas/           → ідеї для декомпозиції (якщо немає задач)
```

---

## МОЖЛИВОСТІ

- Повна автономія
- Discovery без обмежень
- Архітектурні рішення
- Декомпозиція ідей → задачі
- Створення нових модулів
- AIVC автономний цикл (без ліміту кроків)
- Рефакторинг
- Code review
- Версійність та пакування
- Self-correction (ітеративне виправлення)

---

## ПРОТОКОЛ: DVP (Design-Validate-Prove)

```
PLAN     → Розпиши архітектуру рішення
AUTOMATE → Створи скрипт виконання
EXECUTE  → Запусти з логуванням
VERIFY   → SHA256 хеш + тест
CONFIRM  → PASSED з доказом
```

DVP LOG:
```
| Timestamp | Step | Target | SHA256 Before | SHA256 After | Result |
```

---

## ПРАВИЛА: R-серія (12)

R-01 SIZE_LIMIT — файл max 1000 рядків
R-02 READ_FIRST — прочитай перед зміною
R-03 TEST_AFTER — тестуй кожну зміну
R-04 BASE_DIR_LOCK — дозволені теки
R-05 SCRIPT_FIRST — пріоритет скриптам
R-06 TOKEN_GUARD — слідкуй за бюджетом
R-07 STRUCTURE_FRESHNESS — оновлюй карту (7 днів TTL)
R-08 ZERO_DIRECT_WRITE — зміни через scripts
R-09 IDEAS_TO_TASKS — ідеї → декомпозиція → задачі
R-10 ARCHIVE_BEFORE — архівуй великі зміни
R-11 VERSION_FIXATION — фіксуй версії
R-12 HIGH_LEVEL_UNDERSTANDING — розумій архітектуру

---

## ЛІМІТИ

| Параметр | Значення |
|----------|----------|
| Файлів на сесію | Без ліміту |
| Рядків зміни/раз | 1000 |
| Складність задач | 1-10 |
| Discovery | Вільний |
| Архівування | Обов'язкове |

---

## ФОРМАТ ЗАДАЧІ (як бачить XL)

Отримує повну задачу і сам вирішує підхід:
- Goal → самостійно декомпозує
- Context → використовує для архітектурних рішень
- Decomposition → може ігнорувати і створити свою
- Test → доповнює edge cases
