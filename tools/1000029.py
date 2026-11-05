"""Find top-level name collisions in 1000051.lua (the 200-local wall).

Every feature that needs a register is converted from `local` to a global so the
build closure stays under Luau's 200-local limit. The catch: a bare global
assignment silently CLOBBERS whatever already held that name. That is exactly
how `function milkDrops(...)` (the jug counter) overwrote `milkDrops = {}` (the
three farm dropdowns) - every later `milkDrops[slot]` then indexed a function.

This scans the top level of the build closure (4-space indentation) and reports
any name that is assigned more than once in a way a global would clobber.

    python tools/1000029.py
"""

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "1000051.lua"

PATTERNS = [
    # (regex, kind, is_local)
    (re.compile(r"^    function ([A-Za-z_]\w*)\s*\("), "function", False),
    (re.compile(r"^    local function ([A-Za-z_]\w*)\s*\("), "local function", True),
    (re.compile(r"^    ([A-Za-z_]\w*)\s*=(?!=)"), "global", False),
    (re.compile(r"^    local ([A-Za-z_]\w*)\s*=(?!=)"), "local", True),
]

COUNTER = re.compile(r"^    [A-Za-z_]\w*\s*(\+=|-=|\*=|/=)")


def later_local_calls(lines, seen):
    """A global function that calls a `local` declared LATER in the file.

    A 4-space `function NAME(...)` is a global assignment, so its body compiles
    every identifier that is NOT already a visible local as a *global* lookup.
    When that name only becomes a local further down, the global is nil at
    runtime and the call is `attempt to call a nil value` - in the live v1.129
    run, `spudEquipHereText` (line 641) calling `equipmentFolder` (line 841)
    killed the farm loop at the seed check. The harness cannot see this: it
    slices the function out and stubs the callee.
    """
    out = []
    for n, line in enumerate(lines, 1):
        m = re.match(r"^    function ([A-Za-z_]\w*)\s*\(", line)
        if not m:
            continue
        j = n
        while j < len(lines):
            if re.match(r"^    (?:local )?function [A-Za-z_]", lines[j]) \
                    or re.match(r"^    end\s*$", lines[j]):
                break
            j += 1
        body = "\n".join(lines[n:j])
        for call in sorted(set(re.findall(r"\b([A-Za-z_]\w*)\(", body))):
            hits = seen.get(call, [])
            # only a name whose top-level declarations are ALL locals, and whose
            # earliest one comes after this global's own definition, is invisible
            if not hits or any(not h[2] for h in hits):
                continue
            if min(h[0] for h in hits) > n:
                out.append((m.group(1), n, call, min(h[0] for h in hits)))
    return out


def main() -> int:
    src = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else SRC
    lines = src.read_text(encoding="utf-8").splitlines()
    seen: dict[str, list[tuple[int, str, bool]]] = {}
    counters: dict[str, list[int]] = {}

    for n, line in enumerate(lines, 1):
        for pat, kind, is_local in PATTERNS:
            m = pat.match(line)
            if m:
                seen.setdefault(m.group(1), []).append((n, kind, is_local))
                break
        m = COUNTER.match(line)
        if m:
            counters.setdefault(m.group(0).split("=")[0].strip(), []).append(n)

    bad = []
    for name, hits in sorted(seen.items()):
        globals_ = [h for h in hits if not h[2]]
        if not globals_:
            continue
        # a global assigned more than once is a clobber; so is a global whose
        # name is also declared local at top level (the local only shadows
        # AFTER its declaration, so the global can still be hit by earlier code)
        if len(globals_) > 1 or len(hits) > 1:
            bad.append((name, hits))

    # +=/-= on a name that is declared `local` in this scope is fine; on an
    # undeclared name it is a global that other builds also touch.
    for name, where in sorted(counters.items()):
        if name not in seen:
            bad.append((name, [(w, "undeclared counter", False) for w in where]))

    # a global that calls a local not yet in scope is a nil call at runtime
    for gname, gline, lname, decl in later_local_calls(lines, seen):
        bad.append((gname, [(gline, "calls local " + lname + " declared at line "
                             + str(decl), False)]))

    if not bad:
        print(f"name audit: clean ({len(seen)} top-level names)")
        return 0

    print(f"name audit: {len(bad)} name(s) assigned more than once at the top level")
    for name, hits in bad:
        print(f"  {name}: " + " · ".join(f"line {n} {kind}" for n, kind, _ in hits))
    return 1


if __name__ == "__main__":
    sys.exit(main())
