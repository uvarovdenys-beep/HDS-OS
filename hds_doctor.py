#!/usr/bin/env python3
"""hds_doctor.py — what HDS needs, what it has, and what to run for the rest.

The pieces were already there and scattered: `lang._toolchain.status()` knew
about compilers, `sandbox.provision.status()` knew about isolation, `lang`
knew which extensions had validators, and nothing put them in one place. A gap
you have to run three commands to notice is a gap nobody notices.

Three failures this makes visible, all of them found by running it:

  * a language GATED with no validator — every write of it is refused, so the
    language is advertised and unusable;
  * a validator whose TOOLCHAIN is absent — validation silently drops to the
    hygiene denylist, which catches `system()` but not broken syntax;
  * isolation missing — generated code runs on the host instead of a container,
    and nothing in the MCP surface says so.

WHAT `--install` DOES, AND DOES NOT. It runs HDS's own sandbox provisioner: a
no-root install into the user's home, which is HDS's to manage. It does NOT
install compilers. Pulling Xcode or the .NET SDK onto someone's machine without
them asking is not a repair, and the command is printed instead.

    python3 hds_doctor.py            # report; exit 1 if something essential is missing
    python3 hds_doctor.py --install  # additionally provision the sandbox
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
for _p in (str(ROOT), str(ROOT / "agent")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

OK, WARN, BAD = "  ok  ", " warn ", " MISS "


def _line(state: str, label: str, detail: str = "") -> None:
    print(f"[{state}] {label:<34} {detail}")


def check_isolation() -> bool:
    """Isolation is the one that must never degrade quietly."""
    print("\n── isolation ──────────────────────────────────────────────")
    try:
        from sandbox.provision import status
        from sandbox.runner import SandboxRunner
        st = status()
        runner = SandboxRunner()
    except Exception as e:
        _line(BAD, "sandbox", f"unavailable: {e}")
        return False

    if runner.isolated:
        _line(OK, "container backend", runner.backend.name)
        return True
    _line(BAD, "container backend",
          f"{runner.backend.name} — generated code would run ON THE HOST")
    _line(WARN, "remedy", "python3 -m sandbox.provision --install")
    if not st.get("docker_cli"):
        _line(WARN, "note", "docker CLI not on PATH — check PATH when spawned "
                            "from an editor, not just from your shell")
    return False


def check_toolchains() -> list:
    """Present compilers, and the exact command for the absent ones."""
    print("\n── toolchains ─────────────────────────────────────────────")
    from lang._toolchain import resolve, status
    missing = []
    for row in status():
        tool = row["tool"]
        where = resolve(tool)
        if where:
            _line(OK, tool, str(where))
        else:
            _line(WARN, tool, "validation falls back to the hygiene denylist")
            _line("      ", "", f"install: {row['install']}")
            missing.append(tool)
    return missing


def check_languages() -> list:
    """Every gated extension: does it have a validator, and can that run?"""
    print("\n── languages ──────────────────────────────────────────────")
    import lang
    import scribe
    from lang._toolchain import resolve

    # Which tool each validator shells out to. Kept here rather than guessed:
    # a wrong mapping would report a healthy language as broken.
    TOOL = {".py": None, ".svg": None, ".html": None, ".htm": None,
            ".js": "node", ".jsx": "node", ".mjs": "node", ".cjs": "node",
            ".ts": "tsc", ".tsx": "tsc",
            ".c": "clang", ".h": "clang",
            ".cpp": "clang++", ".cc": "clang++", ".hpp": "clang++",
            ".cs": "dotnet", ".php": "php"}

    unusable = []
    for ext in sorted(scribe.CODE_EXTS):
        validator = lang.get_validator(ext)
        if validator is None:
            _line(BAD, ext, "gated but NO validator — every write is refused")
            unusable.append(ext)
            continue
        tool = TOOL.get(ext)
        if tool and resolve(tool) is None:
            _line(WARN, ext, f"validator present, '{tool}' missing — hygiene only")
        else:
            _line(OK, ext, f"validated{f' via {tool}' if tool else ''}")

    # Two different holes, and the second is easy to miss.
    print()
    orphans = [e for e in TOOL if lang.get_validator(e) and e not in scribe.CODE_EXTS]
    for ext in sorted(orphans):
        _line(BAD, ext, "validator exists but ext is NOT in scribe.CODE_EXTS "
                        "— written as unscanned data")
        unusable.append(ext)

    # Code extensions that are neither gated NOR validated. These are the
    # quietest failure of all: no refusal, no scan, the file just lands.
    # .mjs and .cjs are JavaScript; .h is a C header.
    UNGATED = (".h", ".mjs", ".cjs", ".vue", ".svelte", ".kt", ".swift", ".scala")
    silent = [e for e in UNGATED
              if e not in scribe.CODE_EXTS and lang.get_validator(e) is None]
    for ext in sorted(silent):
        _line(BAD, ext, "neither gated nor validated — written unscanned")
        unusable.append(ext)

    if not orphans and not silent:
        _line(OK, "extension routing", "every code extension is reachable")
    return unusable
def check_models() -> bool:
    """A local model is what does the work; without one HDS can only validate."""
    print("\n── local models ───────────────────────────────────────────")
    try:
        from model_scan import discover_models
        served = discover_models()
    except Exception as e:
        _line(WARN, "model scan", f"failed: {e}")
        return False
    total = sum(len(v) for v in served.values())
    for provider, models in served.items():
        _line(OK if models else WARN, provider,
              f"{len(models)} served" if models else "none served")
    if not total:
        _line(WARN, "remedy", "start ollama or LM Studio, then pull a coder model")
    return total > 0


def check_memory() -> bool:
    print("\n── memory ─────────────────────────────────────────────────")
    try:
        from sysmon import free_ram_mb
        free = free_ram_mb()
    except Exception as e:
        _line(WARN, "free RAM", f"unmeasurable: {e}")
        return True
    if free is None:
        _line(WARN, "free RAM", "unmeasurable — model loading will not be blocked")
        return True
    state = OK if free >= 4000 else WARN
    _line(state, "free RAM", f"{free} MB"
          + ("" if free >= 4000 else " — a large model may be refused or thrash"))
    return True


def main() -> int:
    ap = argparse.ArgumentParser(description="HDS OS readiness check")
    ap.add_argument("--install", action="store_true",
                    help="provision the sandbox (HDS's own no-root installer). "
                         "Compilers are printed, never installed for you.")
    args = ap.parse_args()

    print("HDS OS — readiness")
    isolated = check_isolation()
    missing_tools = check_toolchains()
    unusable = check_languages()
    check_models()
    check_memory()

    if args.install and not isolated:
        print("\n── provisioning the sandbox ───────────────────────────────")
        try:
            from sandbox.provision import install
            install()
            isolated = check_isolation()
        except Exception as e:
            _line(BAD, "install failed", str(e))

    print("\n── summary ────────────────────────────────────────────────")
    problems = []
    if not isolated:
        problems.append("isolation is DOWN — generated code runs on the host")
    if unusable:
        problems.append(f"{len(unusable)} extension(s) unusable: {' '.join(unusable)}")
    if missing_tools:
        problems.append(f"{len(missing_tools)} toolchain(s) absent: "
                        f"{' '.join(missing_tools)} (hygiene-only validation)")
    if not problems:
        print("  everything HDS needs is present.")
        return 0
    for p in problems:
        print(f"  · {p}")
    # Isolation down is the only condition that makes HDS unsafe rather than
    # merely limited, so it alone decides the exit code.
    return 1 if not isolated else 0


if __name__ == "__main__":
    raise SystemExit(main())
