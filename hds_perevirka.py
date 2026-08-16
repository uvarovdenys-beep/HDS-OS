#!/usr/bin/env python3
"""hds_perevirka.py — усі перевірки HDS, зрозумілою мовою.

Кожна перевірка тут уже існує окремо, але кожна говорить по-своєму і
англійською: "Level-3 OK — 110 write sites", "9/9 = 100%". Що це означає і чи
все гаразд — доводилось здогадуватись.

Цей скрипт нічого нового не перевіряє. Він запускає ті самі перевірки і каже
простими словами: що саме перевірено, який результат, і що робити, якщо
негаразд.

Процесів не породжує (єдина exec-поверхня — sandbox/), тому pytest запускається
всередині цього ж процесу через pytest.main.

    python3 hds_perevirka.py           # усе
    python3 hds_perevirka.py --швидко  # без тестів (лише аудити, ~2 с)
"""
import io
import re
import sys
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parent

OK, BAD, WARN = "  ✅", "  ❌", "  ⚠️ "


def _tyxo(fn):
    """Запустити щось, що друкує у stdout, і повернути (код, текст)."""
    buf = io.StringIO()
    code = 0
    try:
        with redirect_stdout(buf):
            code = fn() or 0
    except SystemExit as e:
        code = e.code or 0
    except Exception as e:
        return 1, f"{type(e).__name__}: {e}"
    return code, buf.getvalue()


def testy():
    """Тести: чи не зламалось те, що вже працювало."""
    import pytest
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = pytest.main(["tests/", "-q", "--no-header", "-p", "no:cacheprovider"])
    out = buf.getvalue()
    passed = 0
    for line in out.splitlines():
        if " passed" in line:
            for i, part in enumerate(line.replace(",", " ").split()):
                if part == "passed" and i:
                    passed = line.replace(",", " ").split()[i - 1]
            break
    if code == 0:
        return True, f"{passed} тестів пройшло", "нічого не зламано"
    return False, "є тести, що впали", "запусти: python3 -m pytest tests/ -q"


def zapys():
    """R-19: чи всі записи у файли йдуть через клітку."""
    sys.path.insert(0, str(ROOT))
    import write_path_audit
    code, out = _tyxo(write_path_audit.main)
    if code == 0:
        m = re.search(r"(\d+)\s+write sites", out)
        return True, f"усі записи через клітку ({m.group(1) if m else '?'} місць)", \
               "жоден модуль не пише файли повз перевірку"
    return False, "зʼявився запис повз клітку", \
           "або проведи його через scribe, або узакон: write_path_audit.py --freeze"


def vykonannia():
    """Чи ніхто, крім пісочниці, не запускає процеси."""
    sys.path.insert(0, str(ROOT))
    import exec_path_audit
    try:
        breaches = exec_path_audit.run()
    except Exception as e:
        return False, f"перевірка не виконалась: {e}", "перевір exec_path_audit.py"
    if not breaches:
        return True, "запуск процесів лише в пісочниці", \
               "згенерований код не може виконатись повз ізоляцію"
    return False, f"{len(breaches)} місць запускають процеси повз пісочницю", \
           "перенеси виклик у sandbox/ або прибери subprocess"


def rozmir():
    """R-300: чи не розповзаються файли."""
    sys.path.insert(0, str(ROOT))
    import decompose_audit
    code, out = _tyxo(decompose_audit.main)
    if code == 0:
        return True, "жоден файл не переріс 300 рядків", \
               "старий борг заморожено і він не росте"
    grew = [ln.strip() for ln in out.splitlines()
            if "GREW" in ln or "NEW" in ln]
    return False, "файл виріс за межу", \
           ("розділи його: " + (grew[0] if grew else "див. decompose_audit.py"))


def klitka():
    """Чи клітка досі ловить небезпечні записи і не чіпає безпечні."""
    sys.path.insert(0, str(ROOT))
    import benchmark
    # benchmark exposes run(), not main(). The first version fell back to a
    # no-op lambda, produced no output, and reported the cage as BROKEN — a
    # false alarm is worse than no check, so the entry point is required now.
    # benchmark.run напряму: getattr — це рефлексія, і клітка її забороняє
    # (правильно). Перша версія цього файлу через getattr не пройшла перевірку.
    code, out = _tyxo(benchmark.run)
    m_block = re.search(r"BLOCK RATE\s*:\s*(\d+)/(\d+)", out)
    m_false = re.search(r"FALSE-POSITIVE\s*:\s*(\d+)/(\d+)", out)
    if not m_block:
        return False, "benchmark не дав результату", f"вивід: {out[:80]}"
    blocked = m_block.group(1) == m_block.group(2)
    false_pos = bool(m_false) and m_false.group(1) == "0"
    if blocked and false_pos:
        return True, f"заблоковано {m_block.group(0).split(':')[1].strip()}, хибних тривог 0", \
               "захист не послаблено і не заважає роботі"
    if not blocked:
        return False, "клітка пропустила небезпечний запис", \
               "це найсерйозніше: дивись benchmark.py"
    return False, "клітка блокує безпечний код", \
           "правило занадто широке — звузь його до небезпечної операції"


PEREVIRKY = [
    ("Тести", testy),
    ("Запис файлів", zapys),
    ("Запуск процесів", vykonannia),
    ("Розмір файлів", rozmir),
    ("Захист клітки", klitka),
]


def main():
    shvydko = "--швидко" in sys.argv or "--fast" in sys.argv
    print("HDS OS — перевірка стану\n")
    problemy = []
    for nazva, fn in PEREVIRKY:
        if shvydko and nazva == "Тести":
            print(f"  ⏭  {nazva:18s} пропущено (--швидко)")
            continue
        dobre, korotko, poiasnennia = fn()
        znak = OK if dobre else BAD
        print(f"{znak} {nazva:18s} {korotko}")
        print(f"      {poiasnennia}")
        if not dobre:
            problemy.append((nazva, poiasnennia))

    print()
    if not problemy:
        print("  Усе гаразд. Можна працювати далі.")
        return 0
    print(f"  Проблем: {len(problemy)}. Що робити:")
    for nazva, shcho in problemy:
        print(f"    · {nazva}: {shcho}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
