#!/usr/bin/env bash
# Перевірка стану HDS українською — усе одразу, зрозумілою мовою.
# Назва файлу навмисно латиницею: кирилиця в .command ламає подвійний
# клік у Finder, а вивід від цього не змінюється.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/../.."
export PATH="$HOME/.local/bin:$PATH"
python3 hds_perevirka.py "$@"
echo
read -n 1 -s -r -p "Натисни будь-яку клавішу, щоб закрити..."
