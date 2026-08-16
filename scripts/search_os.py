#!/usr/bin/env python3
"""
HDS OS Search Utility
Скрипт для пошуку тексту, функцій або коду у файлах системи.
"""

import os
import argparse
from pathlib import Path

def search_in_files(root_dir, query, file_types=None, exact_match=False):
    # За замовчуванням шукаємо у цих форматах (можна додати інші)
    if file_types is None:
        file_types = ['.py', '.md', '.json', '.yaml', '.yml', '.txt', '.sh']
        
    # Директорії, які ми ігноруємо (щоб пошук був миттєвим)
    ignore_dirs = {'.git', '__pycache__', 'venv', 'env', 'node_modules', '.claude'}
    
    results = []
    
    # Нормалізація запиту якщо пошук нечутливий до регістру
    search_query = query if exact_match else query.lower()
    
    for dirpath, dirnames, filenames in os.walk(root_dir):
        # Відсікаємо непотрібні папки одразу
        dirnames[:] = [d for d in dirnames if d not in ignore_dirs and not d.startswith('.')]
        
        for file in filenames:
            ext = os.path.splitext(file)[1].lower()
            if ext in file_types:
                filepath = Path(dirpath) / file
                try:
                    # Читаємо файл безпечно, ігноруючи бінарні баги кодування
                    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                        for line_number, line in enumerate(f, 1):
                            line_content = line if exact_match else line.lower()
                            if search_query in line_content:
                                results.append({
                                    'file': str(filepath.relative_to(root_dir)),
                                    'line_num': line_number,
                                    'content': line.strip()
                                })
                except Exception:
                    # Ігноруємо файли, які неможливо прочитати
                    pass
                    
    return results

def main():
    parser = argparse.ArgumentParser(description="HDS Code Search Tool (Пошук по системі)")
    parser.add_argument("query", help="Текст, назва функції або шматок коду для пошуку")
    parser.add_argument("--exact", "-e", action="store_true", help="Враховувати регістр (Case-sensitive)")
    parser.add_argument("--dir", "-d", type=str, default=".", help="Директорія для пошуку (за замовчуванням: поточна)")
    
    args = parser.parse_args()
    
    search_dir = Path(args.dir).resolve()
    
    print(f"🔍 Шукаємо '{args.query}' у системі ({search_dir.name}/)...\n")
    
    matches = search_in_files(search_dir, args.query, exact_match=args.exact)
    
    if not matches:
        print("❌ Нічого не знайдено.")
        return
        
    print(f"✅ Знайдено {len(matches)} збігів:\n")
    
    current_file = ""
    for match in matches:
        # Групуємо результати по файлах для красивого виводу
        if match['file'] != current_file:
            print(f"\n📄 \033[96m{match['file']}\033[0m")
            current_file = match['file']
            
        # Форматований вивід: Жовтий номер рядка і сам текст
        print(f"  \033[93mLine {match['line_num']:<4}\033[0m : {match['content']}")
        
    print("\n" + "-"*40)
    print(f"Пошук завершено. Знайдено рядків: {len(matches)}")

if __name__ == "__main__":
    main()
