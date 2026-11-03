"""Where does an arc hop land? (hopTo)

User: "when the harvester is coming back from somewhere it should drop from
higher, because right now it is coming from under."

The hop used to keep the TAKEOFF height at both ends, so a return leg from the
lower Fulfillment pad (top ~140) to the field (~172) flew the whole way under
the field and only surfaced on the last frame. v1.121 then parked a full tank
"on" a pad 28 studs ABOVE it, because the fix (`max(takeoff, target)`) also kept
the takeoff height on the OUTBOUND leg. The rule now:

  * the landing height is the TARGET's own height — a trip up lands ON the
    higher target and a trip down lands ON the lower one, which is what
    "park on the pad" has to mean for a pad that drains by contact;
  * the arc always clears the landing height by ~12 studs, so the ride comes
    DOWN onto it instead of arriving flat or from below;
  * a target with no height keeps the takeoff height;
  * the log names both heights, so a live pass can be checked.

    python tools/hop_test.py [path-to-luau.exe]
"""

import os
import pathlib
import re
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "SpudFarm_Full.lua"
WANTED = ["hopTo", "spudPivotRig"]

PRE = r"""
local V = {}
function V.__add(a, b) return setmetatable({ X = a.X + b.X, Y = a.Y + b.Y, Z = a.Z + b.Z }, V) end
function V.__sub(a, b) return setmetatable({ X = a.X - b.X, Y = a.Y - b.Y, Z = a.Z - b.Z }, V) end
function V.__mul(a, b)
    if type(a) == "number" then return setmetatable({ X = b.X * a, Y = b.Y * a, Z = b.Z * a }, V) end
    return setmetatable({ X = a.X * b, Y = a.Y * b, Z = a.Z * b }, V)
end
function V.__div(a, b) return setmetatable({ X = a.X / b, Y = a.Y / b, Z = a.Z / b }, V) end
V.__index = function(t, k)
    if k == "Magnitude" then return math.sqrt(t.X * t.X + t.Y * t.Y + t.Z * t.Z) end
    return nil
end
Vector3 = { new = function(x, y, z)
    return setmetatable({ X = x or 0, Y = y or 0, Z = z or 0 }, V)
end }

local PIVOT = {}
PIVOT.__index = PIVOT
function PIVOT.__sub(a, b) return { rot = true } end

local CF = {}
CF.__index = function(t, k)
    -- spudPivotRig reads a pose as `.Position`; this stub stores it as `.p`, so
    -- the key is served on demand (metamethods are looked up on the metatable
    -- itself, so answering from a function here does not hide __mul/__sub)
    if k == "Position" then return t.p end
    return rawget(CF, k)
end
function CF.__mul(a, b) return a end
function CF.__sub(a, b) return { pose = true } end

CFrame = { new = function(p) return setmetatable({ p = p }, CF) end }

local logged = {}
function log(s) logged[#logged + 1] = tostring(s) end
function loggedText() return table.concat(logged, "\n") end

task = { wait = function() end }
local stopped = false
function stopping() return stopped end
SELL_HOP_SPEED = 140

-- a ride whose pivot is the only thing the hop reads or writes
local moves = {}
local pos = Vector3.new(0, 0, 0)
local ride = {}
function ride:GetPivot() return setmetatable({ Position = pos }, PIVOT) end
function ride:PivotTo(cf)
    pos = cf.p
    moves[#moves + 1] = { X = pos.X, Y = pos.Y, Z = pos.Z }
end

-- The implement is a SEPARATE model joined by the game's own hitch, so a
-- ride:PivotTo does not move it — that is the live v1.130 failure the carry
-- exists to fix (`hitch gap at arrival: 277.7 studs`). This fake starts 20
-- studs behind the ride and only ever moves when it is carried.
local toolPos = Vector3.new(0, 0, -20)
local carried = 0
local tool = {}
function tool:GetPivot() return setmetatable({ Position = toolPos }, PIVOT) end
function tool:PivotTo(cf)
    carried = carried + 1
    toolPos = cf.p
end
local function place(x, y, z)
    pos = Vector3.new(x, y, z)
    toolPos = Vector3.new(x, y, z - 20)
    moves = {}
    carried = 0
    stopped = false
end
local function gap() return (pos - toolPos).Magnitude end
"""

POST = r"""
local fails = 0
local function check(name, ok, detail)
    if not ok then fails = fails + 1 end
    print(string.format("%-58s %s%s", name, ok and "PASS" or "FAIL",
        detail and ("  " .. detail) or ""))
end
local function peak()
    local hi = -1e9
    for _, m in ipairs(moves) do if m.Y > hi then hi = m.Y end end
    return hi
end

-- 1. the reported bug: the return leg from the lower pad lands ON the field
place(0, 140, 0)
check("return: the hop completes", hopTo(ride, Vector3.new(100, 172, 0), 140) == true)
check("return: it lands on the field height", moves[#moves].Y == 172,
    tostring(moves[#moves].Y))
check("return: it climbs above the field first", peak() >= 184,
    string.format("peak %.1f", peak()))
-- the loop's last frame and the closing PivotTo both sit on the target, so the
-- frame before those is the last one still in the air
check("return: it arrives from ABOVE", moves[#moves - 2].Y > moves[#moves].Y,
    string.format("%.1f -> %.1f", moves[#moves - 2].Y, moves[#moves].Y))
check("return: x/z reach the target", moves[#moves].X == 100 and moves[#moves].Z == 0)
check("return: the log names both heights", loggedText():find("Y 140 → 172") ~= nil,
    loggedText())

-- 2. a trip down lands ON the lower target — this is the v1.121 bug: the ride
--    parked "on" a Fulfillment pad with its wheels 28 studs above it, so the
--    pad never drained and the harvest never restarted
place(0, 172, 0)
hopTo(ride, Vector3.new(100, 140, 0), 140)
check("outbound: a lower target is the landing height",
    moves[#moves].Y == 140, tostring(moves[#moves].Y))
check("outbound: the arc still lifts off the field it leaves", peak() > 172,
    string.format("peak %.1f", peak()))
check("outbound: it arrives at the pad from ABOVE",
    moves[#moves - 2].Y > moves[#moves].Y,
    string.format("%.1f -> %.1f", moves[#moves - 2].Y, moves[#moves].Y))

-- 3. level ground stays level, and the arc still jumps
place(0, 160, 0)
hopTo(ride, Vector3.new(200, 160, 0), 140)
check("level: it lands level", moves[#moves].Y == 160)
check("level: it still jumps", peak() > 180, string.format("peak %.1f", peak()))

-- 4. no height on the target keeps the takeoff height (a bare table, because
--    Vector3.new can only ever make a Y — a nil Y has to be passed as-is)
place(0, 150, 0)
hopTo(ride, { X = 50, Y = nil, Z = 0 }, 140)
check("nil target Y: the takeoff height is kept", moves[#moves].Y == 150)

-- 5. a zero-length hop is one move, no arc
place(10, 200, 10)
hopTo(ride, Vector3.new(10, 260, 10), 140)
check("zero length: one move, no flight", #moves == 1, #moves .. " move(s)")
check("zero length: it still takes the higher height", moves[1].Y == 260)

-- 6. stopping aborts the hop and never lands it
place(0, 140, 0)
stopped = true
local aborted = hopTo(ride, Vector3.new(100, 172, 0), 140)
check("stopping: the hop aborts", aborted == nil)
check("stopping: the ride is not landed on the target", #moves == 0)

-- 7. THE TOW (owner 2026-11-03: "we need to anchor the tractor when it tps
--    because the tool drags it"). The ride moves; the implement is a separate
--    model on the game's own hitch, so a hop that does not carry it puts the
--    constraint under the whole length of the trip.
place(0, 140, 0)
hopTo(ride, Vector3.new(100, 172, 0), 140, tool)
check("tow: the hop carries the implement", carried > 0,
    carried .. " carry(ies) over " .. #moves .. " move(s)")
check("tow: the hitch stays the same 20 studs",
    gap() > 19 and gap() < 21, string.format("%.1f studs", gap()))
check("tow: the landing carries it too",
    toolPos.Z == moves[#moves].Z - 20,
    string.format("tool z %.1f, ride z %.1f", toolPos.Z, moves[#moves].Z))
place(0, 140, 0)
hopTo(ride, Vector3.new(100, 172, 0), 140)
check("no implement: the hop carries nothing", carried == 0,
    carried .. " carry(ies)")

-- the harvest job's `impl` IS the ride, so the carry must not translate it a
-- second time — that hop would land the harvester twice the trip away
place(0, 140, 0)
hopTo(ride, Vector3.new(100, 172, 0), 140, ride)
check("self-propelled: the hop lands the ride, not twice the ride",
    moves[#moves].X == 100 and moves[#moves].Y == 172,
    string.format("landed at %.0f, %.0f", moves[#moves].X, moves[#moves].Y))

-- 8. the control the live run hit: a bare ride teleport leaves the blade on the
--    ground 286 studs away, which is the drag and the refused passes
place(0, 140, 0)
ride:PivotTo(CFrame.new(Vector3.new(286, 140, 0)))
check("control: a ride-only hop is what leaves the tow behind",
    gap() > 200, string.format("%.1f studs of hitch", gap()))

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


def main() -> int:
    base = pathlib.Path(os.environ.get("LOCALAPPDATA", ".")) / "Temp" / "opencode" / "luau"
    exe = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else base / "luau.exe"
    src = SRC.read_text(encoding="utf-8")
    # The arc mover must go through the pivot that carries the tow: a bare
    # ride:PivotTo in here is the live v1.130 bug (277 studs of taut hitch)
    # coming back, and this harness would still report a perfect landing.
    hopBody = extract(src, "hopTo")
    if "spudPivotRig(tr," not in hopBody:
        print("hopTo no longer carries the implement — this harness is stale")
        return 2
    if re.search(r"\btr:PivotTo\(", hopBody):
        print("hopTo still has a bare ride:PivotTo — the tow is left behind")
        return 2
    parts = []
    for name in WANTED:
        code = extract(src, name)
        if not code:
            print("missing " + name)
            return 2
        parts.append(code)
    with tempfile.NamedTemporaryFile("w", suffix=".lua", delete=False, encoding="utf-8") as fh:
        fh.write(PRE + "\n" + "\n\n".join(parts) + "\n" + POST)
        path = fh.name
    try:
        out = subprocess.run([str(exe), path], capture_output=True, encoding="utf-8",
                             errors="replace")
        print(out.stdout.strip())
        if out.returncode != 0:
            print(out.stderr.strip()[-1500:])
        return out.returncode
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
