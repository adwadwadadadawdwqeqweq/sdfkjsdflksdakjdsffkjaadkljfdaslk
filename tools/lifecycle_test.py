"""Run the REAL session-token block: do old loops stop on Unload / Reload?

Unload used to leave the milk loop, the delivery loop, the webhook pump, the
field scan and the FPS meter alive with no UI; every Reload stacked another
copy of each. The fix is a generation counter plus a per-build `spudAlive`.

This slices the real block out of SpudFarm_Full.lua and simulates builds, so it
catches both traps the naive fix had:
  * a GLOBAL spudAlive would be overwritten by the next build, and old loops
    would read the new build's token as "alive";
  * a counter in a BARE GLOBAL is only as shared as the environment the
    executor ran the file in. Live 2026-11-03 two builds ran side by side —
    two heartbeat streams and two fps streams, each passing its own token
    check — because an autostarted build and a hand-run one did not share
    `spudGen`. So the block reads `getgenv()`, and this harness gives it a
    shared table that is deliberately NOT the global environment, then proves
    nothing was written to the bare one.

    python tools/lifecycle_test.py [path-to-luau.exe]
"""

import os
import pathlib
import re
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "SpudFarm_Full.lua"

TOKEN = re.compile(
    r"(?m)^    spudEnv = \(getgenv and getgenv\(\)\) or _G\n"
    r"    spudEnv\.spudGen = \(spudEnv\.spudGen or 0\) \+ 1\n"
    r"    local myGen = spudEnv\.spudGen\n"
    r"(?:    --.*\n)*"
    r"    local function spudAlive\(\) return \(\(spudEnv and spudEnv\.spudGen\) or 0\) == myGen end\n"
)

# The fake executor: a table that survives across executions and is NOT _G, so
# a block that wrote a bare global would be visible to this harness as a miss.
PRE = """
SPUD_SHARED_ENV = { marker = "the executor's table" }
getgenv = function() return SPUD_SHARED_ENV end
"""

POST = r"""
local fails = 0
local function check(name, ok, detail)
    if not ok then fails = fails + 1 end
    print(string.format("%-56s %s%s", name, ok and "PASS" or "FAIL",
        detail and ("  " .. detail) or ""))
end

-- a fake long-lived loop: ticks while its own build is alive
local function loop(buildAlive)
    return function(limit)
        local n = 0
        while n < limit and buildAlive() do n += 1 end
        return n
    end
end

local a = newBuild()
check("the first build is alive", a() == true)
local b = newBuild()
check("the second build is alive", b() == true)
check("a rebuild stops the old build", a() == false and b() == true)

-- a real loop from the OLD build must stop at its next tick
local oldLoop = loop(a)
local ticks = oldLoop(1000)
check("an old loop stops instead of spinning", ticks == 0, "ticks " .. ticks)

-- ▸ THE COUNTER IS IN THE SHARED TABLE, NOT IN A BARE GLOBAL. This is the
--   whole v1.136 fix: two executions that do not share `_G` DO share
--   getgenv(), so the second build's bump is what ended the first.
check("every build bumped the shared counter",
    SPUD_SHARED_ENV.spudGen == 2, "shared " .. tostring(SPUD_SHARED_ENV.spudGen))
check("no build wrote a bare global spudGen", spudGen == nil,
    "bare global is " .. tostring(spudGen))
-- a bare-global bump must NOT be able to end (or fake-end) a session
spudGen = 999
check("a bare-global bump cannot end the session", b() == true)
spudGen = nil

-- Unload: bump the SHARED counter the way destroyUI does, everything stops
local env = getgenv()
env.spudGen = env.spudGen + 1
check("unload stops the current build", b() == false)
local liveLoop = loop(b)
ticks = liveLoop(1000)
check("the unloaded loop stops too", ticks == 0, "ticks " .. ticks)

-- Reload after Unload: a fresh build runs, and nothing old comes back
local c = newBuild()
check("a build after unload is alive", c() == true)
check("pre-unload builds stay dead", a() == false and b() == false)
check("the previous build's loops stay dead", loop(b)(10) == 0)

-- A clobbered pointer fails CLOSED: a build that cannot read the shared table
-- stops every loop instead of assuming it owns the session.
spudEnv = nil
check("a clobbered shared env stops the live build", c() == false)
check("so its loops stop", loop(c)(10) == 0, "ticks must be 0")
spudEnv = SPUD_SHARED_ENV
check("a restored env lets the owning build run again", c() == true)

print(fails == 0 and "ALL OK" or (fails .. " FAILED"))
if fails > 0 then
    -- `os` is not in the standalone Luau CLI, so a failed run must still be
    -- distinguishable: print the count loudly and index a nil value.
    print("LIFECYCLE FAILED " .. fails)
    local boom = nil
    print(boom.nothing)
end
"""

TIES = [
    ("the token block is the shared-env one",
     lambda src: TOKEN.search(src) is not None),
    ("stopping() also asks the session token",
     lambda src: "if not spudAlive() then return true end" in src),
    ("both stop-tests ask it (farm loop AND milk loop)",
     lambda src: src.count("if not spudAlive() then return true end") >= 2),
    ("the run heartbeat is token-guarded (while)",
     lambda src: "while beat and spudAlive() do" in src),
    ("the run heartbeat is token-guarded (before it logs)",
     lambda src: "if beat and spudAlive() then" in src),
    ("destroyUI bumps the SHARED counter",
     lambda src: "env.spudGen = (env.spudGen or 0) + 1" in src),
    ("no bare `spudGen =` assignment is left",
     lambda src: re.search(r"(?m)^\s*spudGen\s*=", src) is None),
    ("the shared pointer is read once, with a _G fallback",
     lambda src: "spudEnv = (getgenv and getgenv()) or _G" in src),
    ("the Doctor names a ghost build",
     lambda src: "GHOST BUILD" in src),
]


def main() -> int:
    base = pathlib.Path(os.environ.get("LOCALAPPDATA", ".")) / "Temp" / "opencode" / "luau"
    exe = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else base / "luau.exe"
    src = SRC.read_text(encoding="utf-8")
    m = TOKEN.search(src)
    if not m:
        print("session-token block not found in SpudFarm_Full.lua")
        return 2
    block = "\n".join(line[4:] if line.startswith("    ") else line
                      for line in m.group(0).splitlines())
    lua = (PRE + "\nlocal function newBuild()\n" + block
           + "\n    return spudAlive\nend\n\n" + POST)
    with tempfile.NamedTemporaryFile("w", suffix=".lua", delete=False, encoding="utf-8") as fh:
        fh.write(lua)
        path = fh.name
    out = subprocess.run([str(exe), path], capture_output=True, encoding="utf-8", errors="replace")
    print(out.stdout.strip())
    if out.returncode != 0:
        print(out.stderr.strip()[-1200:])
        return out.returncode

    # source ties: the three call sites that used to be ungarded
    fails = 0
    for name, test in TIES:
        ok = test(src)
        fails += 0 if ok else 1
        print("%-56s %s" % (name, "PASS" if ok else "FAIL"))
    print("ALL OK" if fails == 0 else ("%d TIE(S) FAILED" % fails))
    return 0 if fails == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
