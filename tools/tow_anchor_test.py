"""The tow is CARRIED, never welded — and the carry is what holds the rig together.

Owner 2026-11-03: "it's making the wheels glitch, use mumuplayer and controll it
i wont be home, patch the bugs and keep it bug free".

v1.133 welded the hitched implement to the ride with a client `WeldConstraint`.
The emulator answered it (logcat + screenshot, the same run):

    anchor: JDShank welded to the ChallengerMT9's HitchRoot — the tool is part of
      the ride while it is hitched
    hitch gap at arrival: 1.1 studs
    remote plow: fired 9 of 98 cell(s) from 12 stop(s), 3x3 per stop — 0 took, 98 left

and the screenshot showed a **wheel lying on the field** next to a tractor at
`Speed 0`. So the server does accept the weld, and that is the problem: the game's
own hitch constraint ALREADY joins those two models into one assembly, so adding a
second joint makes a loop, and a loop is over-constrained — the solver throws a
part off. The weld also moved the merged assembly's network ownership to this
client while the server keeps simulating the implement, so the two stopped
agreeing about where the blade is; `0 took` on the very next grid is that
divergence, and it is a worse failure than the swing the weld was meant to remove.

What actually anchors the tow is v1.131's carry, and this harness is the guard
that it stays the only joint-free answer:

  * no weld symbol may appear in the build at all (`WeldConstraint`,
    `SpudTowAnchor`, `spudAnchorTool`, `spudUnanchorTool`, `spudAnchor`), so the
    feature cannot be half-reintroduced;
  * `SetNetworkOwner` may sit in exactly one place — `claimOwnership`, on the
    RIDE the player is driving — because claiming the implement is the other half
    of the divergence;
  * the carry is real arithmetic, not a comment: a ride teleport moves the
    implement by the same delta and the gap stays the tow-bar length, a nil tool
    costs no carry, and a `tool == ride` job moves the ride ONCE (the harvest job
    tows itself, and a second delta would land the harvester twice the trip away);
  * every field-facing teleport still goes through `spudPivotRig` — no bare
    `ride:PivotTo(` survives in `hopTo`, `spudRadialFire` or `spudHopCells`;
  * `hitchTool` returns true without touching any anchor name, so a proven hitch
    adds nothing to the physics.

    python tools/tow_anchor_test.py [path-to-luau.exe]
"""

import os
import pathlib
import re
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "SpudFarm_Full.lua"
WANTED = ["spudPivotRig"]

PRE = r"""
-- ── the fake world ─────────────────────────────────────────────────────────
-- The game's own physics: a ride teleport moves ONLY the ride, so the implement
-- has to be moved by the script. This fake starts 20 studs behind the tractor
-- (the measured tow-bar length) and only ever moves when carried.
local V = {}
function V.__add(a, b) return setmetatable({ X = a.X + b.X, Y = a.Y + b.Y, Z = a.Z + b.Z }, V) end
function V.__sub(a, b) return setmetatable({ X = a.X - b.X, Y = a.Y - b.Y, Z = a.Z - b.Z }, V) end
function V.__mul(a, b)
    if type(a) == "number" then return setmetatable({ X = b.X * a, Y = b.Y * a, Z = b.Z * a }, V) end
    return setmetatable({ X = a.X * b, Y = a.Y * b, Z = a.Z * b }, V)
end
V.__index = function(t, k)
    if k == "Magnitude" then return math.sqrt(t.X * t.X + t.Y * t.Y + t.Z * t.Z) end
    return nil
end
Vector3 = { new = function(x, y, z) return setmetatable({ X = x or 0, Y = y or 0, Z = z or 0 }, V) end }

local POSE = {}
POSE.__index = POSE
function POSE.__sub(a, b) return { rot = true } end

local CF = {}
CF.__index = function(t, k)
    if k == "Position" then return t.p end
    return rawget(CF, k)
end
function CF.__mul(a, b) return setmetatable({ p = a.p, rot = b }, CF) end
function CF.__sub(a, b) return { pose = true } end
CFrame = { new = function(p) return setmetatable({ p = p }, CF) end }
CFrame.lookAt = function(a, b) return setmetatable({ p = a }, CF) end

task = { wait = function() end }
local stopped = false
function stopping() return stopped end
local logged = {}
function log(s) logged[#logged + 1] = tostring(s) end

local moves, carries, toolRotKept = 0, 0, 0
local pos = Vector3.new(0, 0, 0)
local toolPos = Vector3.new(0, 0, -20)
local TOOL_THROWS = false

local ride = {}
function ride:GetPivot() return setmetatable({ Position = pos, rot = 0 }, POSE) end
function ride:PivotTo(cf) moves = moves + 1; pos = cf.p end

local tool = {}
function tool:GetPivot() return setmetatable({ Position = toolPos, rot = 7 }, POSE) end
function tool:PivotTo(cf)
    if TOOL_THROWS then error("this model will not move") end
    carries = carries + 1
    toolPos = cf.p
    -- the pose handed to the implement is (old position + the ride's delta)
    -- times the tool's OWN old rotation — a ride turn must not spin the plow,
    -- so the second half has to arrive rather than the ride's frame.
    if cf.rot then toolRotKept = toolRotKept + 1 end
end

local function place(x, y, z)
    pos = Vector3.new(x, y, z)
    toolPos = Vector3.new(x, y, z - 20)
    moves, carries, toolRotKept = 0, 0, 0
    stopped = false
end
local function gap()
    return (pos - Vector3.new(toolPos.X, toolPos.Y, toolPos.Z)).Magnitude
end
"""

POST = r"""
local fails = 0
local function check(name, ok, detail)
    if not ok then fails = fails + 1 end
    print(string.format("%-58s %s%s", name, ok and "PASS" or "FAIL",
        detail and ("  " .. detail) or ""))
end

-- ── 1. the carry is what holds the tow together ────────────────────────────
place(0, 166, 0)
spudPivotRig(ride, CFrame.new(Vector3.new(286, 140, 0)), tool)
check("a ride teleport carries the implement too",
    carries == 1 and toolPos.X == 286 and toolPos.Y == 140 and toolPos.Z == -20,
    string.format("tool now (%d, %d, %d)", toolPos.X, toolPos.Y, toolPos.Z))
check("  the gap stays the tow-bar length", gap() == 20, string.format("%.1f", gap()))
check("  the ride moved once", moves == 1)
check("  and the tool keeps its own rotation", toolRotKept == 1)

-- ── 2. no tool, no carry (an un-hitched ride is a plain teleport) ──────────
place(0, 166, 0)
spudPivotRig(ride, CFrame.new(Vector3.new(50, 166, 0)), nil)
check("a nil tool costs no carry", moves == 1 and carries == 0)

-- ── 3. the harvest job tows ITSELF — one move, not two ─────────────────────
place(0, 166, 0)
spudPivotRig(ride, CFrame.new(Vector3.new(286, 166, 0)), ride)
check("tool == ride moves the ride ONCE", moves == 1 and carries == 0
    and pos.X == 286, string.format("moves %d, carries %d, x %d", moves, carries, pos.X))

-- ── 4. a zero delta carries nothing ────────────────────────────────────────
place(100, 166, 100)
spudPivotRig(ride, CFrame.new(Vector3.new(100, 166, 100)), tool)
check("an unchanged pose carries nothing", moves == 1 and carries == 0)

-- ── 5. a tool that will not move costs the ride nothing ─────────────────────
place(0, 166, 0)
TOOL_THROWS = true
local ok = pcall(spudPivotRig, ride, CFrame.new(Vector3.new(120, 166, 0)), tool)
TOOL_THROWS = false
check("a refused tool pivot is swallowed", ok and moves == 1)

-- ── 6. a chain of grid stops keeps the hitch taut-free ─────────────────────
place(0, 166, 0)
for i = 1, 12 do
    spudPivotRig(ride, CFrame.new(Vector3.new(i * 20, 166, 0)), tool)
end
check("12 stops, 12 carries, gap always 20", carries == 12 and gap() == 20,
    string.format("carries %d, gap %.1f", carries, gap()))

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


def body(text: str, header: str) -> str:
    """The source of one function, from its `function name(` line to the next
    4-space definition or comment block — enough to tie what it calls."""
    i = text.find(header)
    if i < 0:
        return ""
    tail = text[i:]
    m = re.search(r"\n    (?:local function |function )[a-zA-Z_]", tail[10:])
    return tail[: m.start()] if m else tail


def main() -> int:
    base = pathlib.Path(os.environ.get("LOCALAPPDATA", ".")) / "Temp" / "opencode" / "luau"
    exe = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else base / "luau.exe"
    src = SRC.read_text(encoding="utf-8")
    fails: list[str] = []

    def tie(pattern: str, why: str, present: bool = True) -> None:
        found = re.search(pattern, src, re.M) is not None
        if found == present:
            print(f"{why:<58} PASS")
        else:
            fails.append(why)

    def count(text: str, needle: str) -> int:
        return text.count(needle)

    # ── the weld must be GONE, not merely unused ─────────────────────────────
    for needle, why in (
        ("WeldConstraint", "no WeldConstraint anywhere in the build"),
        ("SpudTowAnchor", "no weld name left behind"),
        ("spudAnchorTool", "the anchor maker is deleted, not dead code"),
        ("spudUnanchorTool", "the anchor release is deleted too"),
        ('Instance.new("Weld"', "no classic Weld either"),
    ):
        if needle in src:
            fails.append(why + f" — found {src.count(needle)} occurrence(s)")
        else:
            print(f"{why:<58} PASS")
    if re.search(r"\bspudAnchor\b", src):
        fails.append("a `spudAnchor` state still exists — the weld would be "
                     "one edit away from coming back")
    else:
        print(f"{'no anchor state variable survives':<58} PASS")

    # ── ownership: the RIDE only. Claiming the implement is half of why the
    #    welded build disagreed with the server about the blade.
    claims = [m.start() for m in re.finditer(r"SetNetworkOwner", src)]
    if len(claims) != 1:
        fails.append(f"SetNetworkOwner appears {len(claims)} time(s) — exactly one "
                     "claim is allowed, on the ride the player drives")
    elif "claimOwnership" not in src[max(0, claims[0] - 400): claims[0]]:
        fails.append("the surviving SetNetworkOwner is not inside claimOwnership")
    else:
        print(f"{'the only network claim is the ride in claimOwnership':<58} PASS")

    # ── the carry is present, whole and the ONLY tow join ────────────────────
    rig = extract(src, "spudPivotRig")
    before_rig = len(fails)
    if not rig:
        fails.append("spudPivotRig is gone — the carry WAS the anchor")
    else:
        for needle, why in (
            ("function spudPivotRig(ride, cf, tool)", "the carry is defined once"),
            ("if tool and tool ~= ride then", "the self-propelled guard is intact"),
            ("ride:PivotTo(cf)", "the ride still moves first"),
            ("tool:PivotTo(CFrame.new(tp.Position + d)",
             "the implement is moved by the ride's own delta"),
        ):
            if needle not in rig:
                fails.append(why + f" — missing from spudPivotRig")
        if count(src, "function spudPivotRig") != 1:
            fails.append("spudPivotRig is defined "
                         + str(count(src, "function spudPivotRig")) + " times")
        if count(src, "spudPivotRig(") < 8:   # 1 definition + 7 call sites
            fails.append("only " + str(count(src, "spudPivotRig(")) +
                         " spudPivotRig mentions — the teleports stopped carrying")
        if "tp - tp.Position" not in rig:
            fails.append("the carry lost the rotation split — a teleport would "
                         "spin the plow with the ride")
        if len(fails) == before_rig:
            print(f"{'the carry is whole: delta + own rotation + self guard':<58} PASS")

    # ── every field-facing teleport still goes through it ────────────────────
    for header, who in (
        ("function hopTo(tr, target, speed, towed)", "the arc hop"),
        ("function spudRadialFire(", "the stop-and-burst grid"),
        ("function spudHopCells(", "the per-cell hop"),
    ):
        b = body(src, header)
        if not b:
            fails.append(f"{who} is unfindable — its teleport cannot be judged")
            continue
        bare = count(b, "tr:PivotTo(") + count(b, "ride:PivotTo(")
        if bare:
            fails.append(f"{who} has {bare} bare PivotTo — it abandons the tow "
                         "and is how the wheel came loose again")
        elif "spudPivotRig(" not in b:
            fails.append(f"{who} never calls spudPivotRig — the implement is left behind")
        else:
            print(f"{who + ' carries the implement through every move':<58} PASS")

    # ── a proven hitch adds NOTHING to the physics ───────────────────────────
    hitch = body(src, "local function hitchTool(tr, impl)")
    if not hitch:
        fails.append("hitchTool is unfindable")
    elif "Anchored" in hitch or "Anchor" in hitch:
        fails.append("hitchTool still touches an anchor — a proven hitch would "
                     "join the assemblies the game already joined")
    else:
        print(f"{'a proven hitch welds nothing':<58} PASS")

    # ── the reason stays in the file, not only in the commit message ─────────
    tie(r'THE TOW IS CARRIED, NEVER WELDED',
        "the build says out loud why there is no weld")
    tie(r'Do not re-add a weld to the tow',
        "and tells the next reader not to")

    parts = [PRE]
    for name in WANTED:
        code = extract(src, name)
        if not code:
            print("missing " + name)
            return 2
        parts.append(code)
    parts.append(POST)

    with tempfile.NamedTemporaryFile("w", suffix=".lua", delete=False, encoding="utf-8") as fh:
        fh.write("\n\n".join(parts) + "\n")
        path = fh.name
    try:
        out = subprocess.run([str(exe), path], capture_output=True, encoding="utf-8",
                             errors="replace")
        print(out.stdout.strip())
        if out.returncode != 0:
            print(out.stderr.strip()[-1500:])
        if fails:
            for f in fails:
                print("FAIL  " + f)
            return 1
        return out.returncode
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
