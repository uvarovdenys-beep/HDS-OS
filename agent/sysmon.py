#!/usr/bin/env python3
"""sysmon.py — host resource monitoring (free RAM), cross-platform.

Isolated here (not in the pipeline) because measuring free RAM needs a fixed
host binary on macOS (`vm_stat`). That is host monitoring with a constant argv
never derived from AI content — the same class as port_checker's netstat — so
exec_path_audit allowlists THIS file, keeping agent_ai_pipeline.py subprocess-free.
"""
import platform
import re
import subprocess


def free_ram_mb():
    """Best-effort free physical RAM in MB. None if unmeasurable — callers must
    not block on inability to measure."""
    s = platform.system()
    try:
        if s == "Linux":
            for ln in open("/proc/meminfo"):
                if ln.startswith("MemAvailable"):
                    return int(ln.split()[1]) // 1024
            return None
        if s == "Darwin":
            out = subprocess.run(["vm_stat"], capture_output=True,
                                 text=True, timeout=5).stdout
            ps = int(re.search(r"page size of (\d+)", out).group(1))
            pages = 0
            for k in ("Pages free", "Pages inactive", "Pages speculative"):
                m = re.search(rf"{k}:\s+(\d+)\.", out)
                if m:
                    pages += int(m.group(1))
            return pages * ps // 1048576
        if s == "Windows":
            import ctypes

            class MS(ctypes.Structure):
                _fields_ = [("dwLength", ctypes.c_ulong),
                            ("dwMemoryLoad", ctypes.c_ulong),
                            ("ullTotalPhys", ctypes.c_ulonglong),
                            ("ullAvailPhys", ctypes.c_ulonglong),
                            ("ullTotalPageFile", ctypes.c_ulonglong),
                            ("ullAvailPageFile", ctypes.c_ulonglong),
                            ("ullTotalVirtual", ctypes.c_ulonglong),
                            ("ullAvailVirtual", ctypes.c_ulonglong),
                            ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
            st = MS()
            st.dwLength = ctypes.sizeof(MS)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(st))
            return int(st.ullAvailPhys) // 1048576
    except Exception:
        return None
    return None
