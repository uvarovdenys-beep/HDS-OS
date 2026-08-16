#!/usr/bin/env python3
"""hello cage — the smallest possible HDS demo.

Run:  python3 core/example.py
Shows the cage: a 'thinking' model graded 's' proposes writes; scribe lets the
safe one into the sandbox and rejects the dangerous / out-of-bounds ones.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))  # OS root (own dir)

import scribe  # the cage

proposals = [
    {"op": "write", "path": "storage/hello.txt", "content": "hi from a caged model\n"},
    {"op": "write", "path": "agent/backdoor.py", "content": "import os"},   # code → blocked at 's'
    {"op": "delete", "path": "storage/hello.txt"},                          # delete → blocked at 's'
]

for p in proposals:
    try:
        print("✅", scribe.execute(p, protocol_size="s")[0])
    except scribe.ScribeError as e:
        print("⛔", e)
