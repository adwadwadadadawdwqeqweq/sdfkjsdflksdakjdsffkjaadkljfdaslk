"""The stall scan after a milk teleport, on a virtual clock (spudStallScan).

Owner 2026-11-02: "when the barns and cows are too far from where the player
tps' it just stalls there". The live console named it —

    milk: desbiens1235 is 868 studs away - teleported to its plot
    milk: no stall found for desbiens1235 in 17 ms (0 skipped)

— while the same pass counted 32 cows. The plot folder is in the world at any
distance; the barn is a 3D building and has to stream in, so ONE read right
after the hop answers "no stalls" about a barn that is simply not loaded yet.

This asserts, against the real spudStallScan:
  * a pass that did not teleport reads once and waits zero (the old behaviour,
    byte for byte)
  * a pass that did re-reads until the game has stalls, and hands those back
  * each try is 0.25 s, and the wait is bounded (12 tries, 3 s)
  * a barn that never streams is logged as NOT STREAMED, names the owner, and
    says out loud that this is not "no barn" — it never claims an empty answer
  * Stop ends the wait at once
  * the skipped count and the plot it was asked about survive every re-read

Usage:  python tools/1000037.py [path-to-luau.exe]
"""

import os
import pathlib
import re
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "1000051.lua"
WANTED = ["spudStallScan"]

PRE = r"""
local VT = 0.0
os = { clock = function() return VT end }
task = { wait = function(t) VT = VT + (t or 0) end }

LOG = {}
log = function(s) LOG[#LOG + 1] = s end
STOP = false
milkStopping = function() return STOP end

-- the scripted stall read: SCRIPT[n] is what the n-th read finds — a stall
-- count, or a function that can flip STOP (or anything else) while being asked
SCANS = 0
SCRIPT = {}
CALLS = {}
SKIPPED = 0
milkStalls = function(who, cf, size)
    SCANS = SCANS + 1
    CALLS[SCANS] = { who = who, cf = cf, size = size }
    local n = SCRIPT[SCANS]
    if type(n) == "function" then n = n() end
    local out = {}
    for i = 1, (n or 0) do out[i] = { spot = i } end
    return out, SKIPPED
end

local function reset()
    SCANS, SCRIPT, CALLS, SKIPPED = 0, {}, {}, 0
    LOG, STOP, VT = {}, false, 0.0
end

local BOX = { Position = "plot" }
local SIZE = { X = 100, Z = 100 }
"""

POST = r"""
local fails = 0
local function check(name, ok, detail)
    if not ok then fails = fails + 1 end
    print(string.format("%-58s %s%s", name, ok and "PASS" or "FAIL",
        detail and ("  " .. detail) or ""))
end

-- 1. no teleport: the scan is asked once, nothing is slept, nothing is logged
reset()
SCRIPT = { 0 }
local stalls, skipped, ms = spudStallScan("desbiens1235", BOX, SIZE, false)
check("no hop: reads once", SCANS == 1, tostring(SCANS))
check("no hop: waits zero", ms == 0, tostring(ms))
check("no hop: logs nothing", #LOG == 0, table.concat(LOG, " / "))
check("no hop: still answers a list", type(stalls) == "table" and #stalls == 0)

-- 2. teleport, the barn arrives on the third read
reset()
SCRIPT = { 0, 0, 12 }
stalls, skipped, ms = spudStallScan("desbiens1235", BOX, SIZE, true)
check("hop: re-reads until the stalls are there", SCANS == 3, tostring(SCANS))
check("hop: hands back what streamed in", #stalls == 12, tostring(#stalls))
check("hop: 0.25 s a try", math.abs(ms - 500) < 0.01, tostring(ms))
check("hop: logs the stream", LOG[#LOG]:find("streamed in") ~= nil, LOG[#LOG])
check("hop: names the stall count", LOG[#LOG]:find("12 stall") ~= nil, LOG[#LOG])

-- 3. the same plot every time — a re-read that drifted to another farm is a bug
check("hop: every re-read asks the same owner", CALLS[1].who == CALLS[3].who
    and CALLS[3].who == "desbiens1235")
check("hop: every re-read asks the same box", CALLS[1].cf == CALLS[3].cf
    and CALLS[1].size == CALLS[3].size)

-- 4. a barn that never streams: bounded, honest, and never a claim of "no barn"
reset()
SKIPPED = 7
stalls, skipped, ms = spudStallScan("desbiens1235", BOX, SIZE, true)
check("never: the wait is bounded at 12 tries", SCANS == 13, tostring(SCANS))
check("never: the cap is 3 s", math.abs(ms - 3000) < 0.01, tostring(ms))
check("never: answers an empty list, not nil", type(stalls) == "table" and #stalls == 0)
check("never: keeps the skipped count", skipped == 7, tostring(skipped))
local line = LOG[#LOG] or ""
check("never: names the owner", line:find("desbiens1235") ~= nil, line)
check("never: says the plot reads", line:find("plot reads") ~= nil, line)
check("never: says the barn has not streamed", line:find("has not streamed in") ~= nil, line)
check("never: refuses to call it no barn", line:find('not "no barn"') ~= nil, line)

-- 5. Stop ends the wait between tries
reset()
SCRIPT = { 0, 0, function() STOP = true return 0 end }
stalls, skipped, ms = spudStallScan("desbiens1235", BOX, SIZE, true)
check("stop: ends the wait at once", SCANS == 3, tostring(SCANS))
check("stop: cost 0.5 s, not 3", math.abs(ms - 500) < 0.01, tostring(ms))

-- 6. a barn that is there the first time costs nothing extra after a hop
reset()
SCRIPT = { 12 }
stalls, skipped, ms = spudStallScan("desbiens1235", BOX, SIZE, true)
check("hop with a loaded barn: one read", SCANS == 1, tostring(SCANS))
check("hop with a loaded barn: no wait", ms == 0, tostring(ms))
check("hop with a loaded barn: no stream line", #LOG == 0, table.concat(LOG, " / "))

print(fails == 0 and "ALL OK" or (fails .. " FAILED"))
"""


def extract(text: str, name: str) -> str:
    m = re.search(r"^    (?:local )?function " + name + r"\(", text, re.M)
    if not m:
        return ""
    tail = text[m.start():]
    end = re.search(r"\n    (?:local function |function |-- )", tail[10:])
    block = tail[: end.start() + 10] if end else tail
    return "\n".join(l[4:] if l.startswith("    ") else l for l in block.splitlines())


def ties(src: str) -> list:
    """The wiring the harness cannot run: milkCycle must scan through the
    helper, and the helper must be told by the teleports that just ran."""
    out = []
    out.append(("milkCycle scans through spudStallScan",
                "spudStallScan(owner, cf, size, hopped)" in src))
    out.append(("the direct one-shot scan is gone from milkCycle",
                src.count("local stalls, skipped = milkStalls(owner, cf, size)") == 1))
    out.append(("both plot teleports report whether they moved",
                src.count("hopped = milkTp(") == 2))
    out.append(("the scan answer decides the wait, not a flat sleep",
                "if #stalls == 0 and hopped then" in src))
    i = src.find("spudStallScan(owner, cf, size, hopped)")
    out.append(("the timing stamp is taken after the scan, not before it",
                i >= 0 and "local stallAt = os.clock()" in src[i:i + 300]))
    return out


def main() -> int:
    base = pathlib.Path(os.environ.get("LOCALAPPDATA", ".")) / "Temp" / "opencode" / "luau"
    exe = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else base / "luau.exe"
    src = SRC.read_text(encoding="utf-8")
    failed = 0
    for name, ok in ties(src):
        print("%-58s %s" % (name, "PASS" if ok else "FAIL"))
        if not ok:
            failed += 1
    code = extract(src, "spudStallScan")
    if not code:
        print("missing spudStallScan")
        return 2
    with tempfile.NamedTemporaryFile("w", suffix=".lua", delete=False, encoding="utf-8") as fh:
        fh.write(PRE + "\n" + code + "\n" + POST)
        path = fh.name
    try:
        out = subprocess.run([str(exe), path], capture_output=True, encoding="utf-8",
                             errors="replace")
        print(out.stdout.strip())
        if out.returncode != 0:
            print(out.stderr.strip()[-1500:])
        return out.returncode if out.returncode != 0 else (1 if failed else 0)
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
