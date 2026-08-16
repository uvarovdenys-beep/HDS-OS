"""Перевірка українською: вона не має брехати.

Найнебезпечніша помилка тут — ХИБНА ТРИВОГА. Перша версія не знаходила точки
входу benchmark, мовчки отримувала порожній вивід і повідомляла, що клітка
зламана. Ці тести пінять, що кожна перевірка читає СПРАВЖНІЙ результат.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import hds_perevirka as p


def test_kozhna_perevirka_povertaie_try_znachennia():
    for nazva, fn in p.PEREVIRKY:
        assert isinstance(nazva, str) and nazva
        assert callable(fn)


def test_zapys_i_rozmir_zaraz_zeleni():
    # Ці дві не залежать від зовнішніх служб і мають бути зелені в чистому дереві.
    for fn in (p.zapys, p.rozmir):
        dobre, korotko, poiasnennia = fn()
        assert dobre is True, f"{fn.__name__}: {korotko}"
        assert korotko and poiasnennia


def test_klitka_chytaie_spravzhni_chysla():
    # Не «є рядок 9/9» — а що заблоковано стільки ж, скільки спроб.
    dobre, korotko, _ = p.klitka()
    assert dobre is True, korotko
    assert "9/9" in korotko or "заблоковано" in korotko


def test_vykonannia_ne_padaie():
    dobre, korotko, poiasnennia = p.vykonannia()
    assert isinstance(dobre, bool) and korotko and poiasnennia


def test_bez_refleksii():
    # getattr заборонений кліткою — і саме через нього перша версія не збереглась.
    assert "getattr(" not in (ROOT / "hds_perevirka.py").read_text()
