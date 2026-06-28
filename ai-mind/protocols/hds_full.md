# HDS Full — Протокол для потужних моделей

> Для моделей: Opus, GPT-4o, Qwen 30B+, DeepSeek-R1 70B+
> Автор: Opus 4.6 | HDS OS v1.1

---

## BOOT SEQUENCE (повний)

```
STEP 0: Прочитай ai-mind/config/ → зрозумій середовище
STEP 1: Прочитай ai-mind/architecture/project-map.md → карта проєкту
STEP 2: Прочитай ai-mind/tasks/active/ → список задач
STEP 3: Обери задачу або створи нову з ai-mind/ideas/
```

---

## 12 ПРАВИЛ (R-серія)

| # | Правило | Опис |
|---|---------|------|
| R-01 | SIZE_LIMIT | Файл max 1000 рядків |
| R-02 | READ_FIRST | Прочитай перед зміною |
| R-03 | TEST_AFTER | Тестуй кожну зміну |
| R-04 | BASE_DIR_LOCK | Працюй тільки в дозволених теках |
| R-05 | SCRIPT_FIRST | Пріоритет скриптам |
| R-06 | TOKEN_GUARD | Слідкуй за бюджетом токенів |
| R-07 | STRUCTURE_FRESHNESS | Оновлюй карту проєкту кожні 7 днів |
| R-08 | ZERO_DIRECT_WRITE | Зміни через task scripts |
| R-09 | IDEAS_TO_TASKS | Ідеї → задачі через декомпозицію |
| R-10 | ARCHIVE_BEFORE_CHANGE | Архівуй перед великими змінами |
| R-11 | VERSION_FIXATION | Фіксуй версії |
| R-12 | HIGH_LEVEL_UNDERSTANDING | Розумій архітектуру перед зміною |

---

## DVP PROTOCOL (повний)

```
PLAN     → Розпиши кроки виконання
AUTOMATE → Створи скрипт для виконання
EXECUTE  → Запусти скрипт
VERIFY   → SHA256 хеш перевірка
CONFIRM  → PASSED / FAILED
```

DVP LOG таблиця обов'язкова:
```
| Timestamp | Script | Target | SHA256 Before | SHA256 After | Result |
```

---

## ПАМ'ЯТЬ (фрактальна, 5 шарів)

```
Cold Memory    → ai-mind/architecture/    (карта, правила)
Hot Memory     → ai-mind/tasks/active/    (поточні задачі)
Script Layer   → ai-mind/scripts/         (автоматизація)
Deep Memory    → ai-mind/archive/         (історія)
Experience     → ai-mind/experience/      (анти-паттерни)
```

---

## DISCOVERY

Дозволено досліджувати проєкт з бюджетом:
- Max 12 файлів / 120KB за discovery-сесію
- Результати → project-map.md (delta update)
- Whitelist тек в ai-mind/config/

---

## МОЖЛИВОСТІ

| Дія | Дозволено |
|-----|-----------|
| Архітектурні рішення | ✅ |
| Декомпозиція задач | ✅ |
| Створення модулів | ✅ |
| Code review | ✅ |
| Рефакторинг | ✅ |
| Версійність та пакування | ✅ |
| AIVC автономний цикл | ✅ |
| Ideas → Tasks | ✅ |
