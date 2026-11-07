"""One gate for the whole script: compile, register budget, name audit, every
harness, and the doctor report.

The hand-run suite once missed the doctor harness (it never matched the test
glob), and the name audit exists because a "make it global to save a register"
edit silently clobbered a table. This runs all of it in one command:

    python tools/1000032.py [folder-with-luau.exe]
"""

import os
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
# ▸ the harnesses quote the console, and the console quotes the game — `Y 166 →
#   138`, `Empty → Plowed`. Windows' default cp1252 stream cannot encode that
#   arrow, so `1000024.py` died in its own `print` and the gate called the build
#   broken. UTF-8 for every child is what the AGENTS §2.2 loop already does by
#   hand; doing it here means one command and no false FAIL.
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
BASE = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else (
    pathlib.Path(os.environ.get("LOCALAPPDATA", ".")) / "Temp" / "opencode" / "luau")
EXE = BASE / "luau.exe"
COMPILE = BASE / "luau-compile.exe"

# ▸ Every file in this repo is named with numbers now, so a glob can no longer
#   tell a test from a gate from a measurement bench. These two lists are the
#   whole distinction, and EXPECTED_HARNESS_COUNT is the guard: a gate that
#   discovers nothing would otherwise print a green "4/4" having run only the
#   compile, the budget and the audit. Add a harness -> raise the number; lose a
#   file -> this command stops being green and says what it found.
GATES = {"1000027.py", "1000029.py", "1000032.py"}          # budget, name audit, this file
BENCHES = {"1000004.py", "1000036.py", "1000038.py"}        # cow scan, stall scan, store timing
# ▸ and the PC-side tools that live in this folder but are not tests of the
#   build: the emulator watcher and the clipboard decoder it uses. They were
#   added without touching this list and the count guard said so out loud
#   ("found 37 test(s), expected 35") instead of quietly running them as
#   harnesses or dropping the real ones.
TOOLS = {"spudwatch.py", "spud_clip.py"}
EXPECTED_HARNESS_COUNT = 35


def discover_harnesses() -> list[pathlib.Path]:
    tools = ROOT / "tools"
    return sorted(p for p in tools.glob("*.py") if p.name not in GATES | BENCHES | TOOLS)


def run(label: str, cmd: list[str], scan_stdout: bool = True) -> bool:
    out = subprocess.run(cmd, cwd=ROOT, capture_output=True, encoding="utf-8", errors="replace")
    # the harnesses print PASS/FAIL and mostly exit 0, so a return code alone
    # would call a failing suite "OK". luau-compile is the exception: its stdout
    # is the compiled bytecode, so a "FAIL" inside any string constant in the
    # script would read as a broken build -- for it the exit code and stderr are
    # the whole verdict.
    ok = out.returncode == 0 and (not scan_stdout or "FAIL" not in out.stdout)
    print(f"{'OK  ' if ok else 'FAIL'} {label}")
    if not ok:
        print((out.stdout + out.stderr).strip() if scan_stdout else out.stderr.strip())
    return ok


def main() -> int:
    if not EXE.exists() or not COMPILE.exists():
        print(f"luau tools not found under {BASE}")
        print("pass the folder as the first argument (it needs luau.exe and luau-compile.exe)")
        return 2

    checks = [
        ("compile 1000051.lua", [str(COMPILE), "--binary", "1000051.lua"], False),
        ("register budget", [sys.executable, "tools/1000027.py"]),
        ("name audit", [sys.executable, "tools/1000029.py"]),
    ]
    tests = discover_harnesses()
    if len(tests) != EXPECTED_HARNESS_COUNT:
        # ▸ This is the whole point of the list above. The harnesses are named by
        #   numbers now, so a glob cannot tell a test from a gate from a bench —
        #   and a gate that silently discovers 0 tests still prints a green "4/4".
        #   Losing a file, or running a bench as a test, has to be an error.
        print(f"FAIL harness discovery found {len(tests)} test(s), expected "
              f"{EXPECTED_HARNESS_COUNT}: "
              + ", ".join(t.name for t in tests[:40]))
        return 1
    for t in tests:
        checks.append((t.name, [sys.executable, str(t), str(EXE)]))

    results = [run(*c) for c in checks]
    failed = results.count(False)
    print(f"\n{len(results) - failed}/{len(results)} checks passed")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
