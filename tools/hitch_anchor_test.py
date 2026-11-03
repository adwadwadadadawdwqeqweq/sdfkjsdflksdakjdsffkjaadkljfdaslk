"""The tow is welded ONLY to a proven, settled hitch — and never to itself.

Owner 2026-11-03: "bro make it anchor te tool permanantly behind the tractor
while it's hitched". v1.131 carries the implement through a teleport and v1.132
re-aims each grid stop from a fresh reading, but the tow is still the GAME's
constraint: the live v1.131 console still opens with `the blade is 32 studs off
stop 1`, because a tool on a slack line arrives wherever the solver managed in
the frames available. A `WeldConstraint` between the two hitch parts makes ride
+ implement one assembly, so the tool is where the ride put it.

That is a permanent change to a physics joint, so four things are pinned:

  * it happens only AFTER the tug test proved the hitch (`hitchTool` returns
    true), and it is UNDONE before anything asks the game to unhitch — an X
    press against a welded tow is a tug-of-war the script wins and the server
    loses, and the park's "it stayed put" proof would become a lie;
  * it welds a SETTLED pose only. `far`, `swinging`, `gone`, `none` and `stop`
    all refuse: freezing a frame the tow was passing through would hold the
    implement at an angle the game never rests it at, which is worse than the
    slack line the run has been working around;
  * a self-propelled job (the harvester, whose `impl` IS the ride) never welds
    anything — Part0 and Part1 would be the same assembly;
  * a weld this client created can be refused, and a refused weld must leave
    `spudAnchor` empty so the next settled hitch can try again.

    python tools/hitch_anchor_test.py [path-to-luau.exe]
"""

import os
import pathlib
import re
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "SpudFarm_Full.lua"

WANTED = ["spudAnchorTool", "spudUnanchorTool"]


def extract(text: str, name: str) -> str:
    m = re.search(r"^    (?:local )?function " + name + r"\(", text, re.M)
    if not m:
        return ""
    tail = text[m.start():]
    end = re.search(r"\n    (?:local function |function |-- )", tail[10:])
    block = tail[: end.start() + 10] if end else tail
    return "\n".join(l[4:] if l.startswith("    ") else l for l in block.splitlines())


PRE = r"""
local logs = {}
function log(msg) logs[#logs + 1] = tostring(msg) end
task = task or {}
task.wait = function(_) end
function stopping() return STOP end

LocalPlayer = { Name = "oksimba_1" }

-- ── the fake world ─────────────────────────────────────────────────────────
local welds, destroyed, owners, waits = {}, 0, {}, {}
local HITCH, ATTACH = {}, {}
local WELD_THROWS, OWNER_THROWS = false, false
local WAIT_V, STOP = "settled", false

local function part(name)
    local p = { Name = name, ClassName = "BasePart" }
    function p:SetNetworkOwner(who)
        if OWNER_THROWS then error("this part is not yours to own") end
        owners[#owners + 1] = { part = self, who = who }
    end
    return p
end

local function model(name, primary, withScan)
    local m = { Name = name, PrimaryPart = primary }
    function m:FindFirstChildWhichIsA(_) return withScan and self.PrimaryPart or nil end
    return m
end

function findHitchPart(m) return HITCH[m] end
function spudToolAttachment(m) return ATTACH[m] end
function spudWaitTool(ride, att, who)
    waits[#waits + 1] = { ride = ride, att = att, who = who }
    return WAIT_V, 20
end

Instance = { new = function(class)
    if WELD_THROWS then error("a WeldConstraint here is not allowed") end
    local w = { ClassName = class, destroyed = false }
    function w:Destroy() self.destroyed = true destroyed += 1 end
    welds[#welds + 1] = w
    return w
end }

local function reset()
    logs = {} welds = {} destroyed = 0 owners = {} waits = {}
    spudAnchor = nil
    WAIT_V = "settled" STOP = false WELD_THROWS = false OWNER_THROWS = false
end
"""

POST = r"""
local fails = 0
local function check(name, ok, detail)
    if not ok then fails = fails + 1 end
    print(string.format("%-54s %s%s", name, ok and "PASS" or "FAIL",
        detail and ("  " .. detail) or ""))
end

local rideHitch, implHitch, impl2Hitch = part("Hitchable"), part("HitchableSocket"), part("HitchableSocket")
local ride = model("ZM80", part("EquipmentRoot"))
local impl = model("S4204", part("PlowFrame"), true)
local impl2 = model("KADL", part("DrillFrame"), true)
HITCH[ride] = rideHitch HITCH[impl] = implHitch HITCH[impl2] = impl2Hitch
ATTACH[impl] = "RaycastPart.Attachment" ATTACH[impl2] = "Seed.RaycastPart"

-- a line is a line, whatever position it happens to sit at
local function logged(substr)
    for _, l in ipairs(logs) do
        if l:find(substr, 1, true) then return l end
    end
    return nil
end

-- ── 1. nothing to anchor: no pair, or a machine that IS the ride ───────────
reset()
check("no ride welds nothing", spudAnchorTool(nil, impl) == false and #welds == 0)
check("no implement welds nothing", spudAnchorTool(ride, nil) == false and #welds == 0)
check("the ride itself is never welded to itself",
    spudAnchorTool(ride, ride) == false and #welds == 0)
check("  and that says nothing (a harvester is normal)", #logs == 0)

-- ── 2. a hitch part missing is named, not assumed ──────────────────────────
reset() HITCH[impl] = nil
check("no hitch part on the tool refuses the weld",
    spudAnchorTool(ride, impl) == false and #welds == 0)
check("  the refusal names the parts",
    logs[1] ~= nil and logs[1]:find("no hitch part to weld") ~= nil)
check("  and says the tow keeps the game's constraint",
    logs[1] ~= nil and logs[1]:find("game's own constraint") ~= nil)
HITCH[impl] = implHitch
reset() HITCH[ride] = nil
check("no hitch part on the ride refuses too",
    spudAnchorTool(ride, impl) == false and #welds == 0)
HITCH[ride] = rideHitch

-- ── 3. only a SETTLED tow gets a permanent joint ───────────────────────────
-- `far` has its own line (it is the flung-tool case the whole tow work exists
-- for); the rest are named by what the settle wait actually read.
local LINES = { far = "off the hitch", swinging = "swinging", gone = "gone",
                none = "none" }
for _, v in ipairs({ "far", "swinging", "gone", "none" }) do
    reset() WAIT_V = v
    local ok = spudAnchorTool(ride, impl)
    check("a " .. v .. " tow is not welded", ok == false and #welds == 0)
    check("  the settle wait is asked first", #waits == 1 and waits[1].who == "anchor")
    check("  and the line names what it read",
        #logs == 1 and logs[1]:find(LINES[v]) ~= nil, logs[1])
end
reset() WAIT_V = "stop"
check("Stop during the wait welds nothing",
    spudAnchorTool(ride, impl) == false and #welds == 0)
check("  and Stop is silent", #logs == 0)

-- ── 4. the settled weld: one constraint, ride part to tool part ────────────
reset()
check("a settled tow is welded", spudAnchorTool(ride, impl) == true)
check("exactly one instance is made", #welds == 1)
local w = welds[1]
check("it is a WeldConstraint", w ~= nil and w.ClassName == "WeldConstraint")
check("named SpudTowAnchor", w ~= nil and w.Name == "SpudTowAnchor")
check("Part0 is the ride's hitch part", w ~= nil and w.Part0 == rideHitch)
check("Part1 is the implement's hitch part", w ~= nil and w.Part1 == implHitch)
check("it lives on the ride's own part", w ~= nil and w.Parent == rideHitch)
check("the tool is claimed for this client",
    #owners == 1 and owners[1].who == LocalPlayer)
check("the log says the tool is part of the ride",
    #logs == 1 and logs[1]:find("part of the ride") ~= nil)

-- ── 5. calling it again is not a second weld ───────────────────────────────
check("the same pair reads already anchored", spudAnchorTool(ride, impl) == true)
check("  no second constraint", #welds == 1)
check("  no second network claim", #owners == 1)
check("  and no second settle wait", #waits == 1)

-- ── 6. a new tool replaces the old tow, it does not stack ──────────────────
check("a different tool welds", spudAnchorTool(ride, impl2) == true and #welds == 2)
check("  the old weld is destroyed", welds[1].destroyed == true and destroyed == 1)
check("  the new one holds the new tool", welds[2].Part1 == impl2Hitch)
check("  and the release is logged", logged("anchor: released") ~= nil)

-- ── 7. releasing is idempotent and silent when there is nothing to release ─
check("releasing lets the tow go", spudUnanchorTool("the hitch has to be freed") == true)
check("  the weld is gone", welds[2].destroyed == true and destroyed == 2)
check("  and the line says why",
    logged("anchor: released (the hitch has to be freed)") ~= nil)
local before = #logs
check("releasing twice says nothing", spudUnanchorTool("again") == false and #logs == before)
check("  and an empty anchor state is not an error", spudAnchor == nil)

-- ── 8. a client weld can be refused — the state must stay clean ────────────
reset() WELD_THROWS = true
check("a refused constraint is answered honestly",
    spudAnchorTool(ride, impl) == false and #welds == 0)
check("  the line says it was refused", #logs == 1 and logs[1]:find("refused") ~= nil)
check("  and nothing is recorded as anchored", spudAnchor == nil)
WELD_THROWS = false
check("  the next settled hitch can weld", spudAnchorTool(ride, impl) == true)

-- ── 9. the network claim is a courtesy, not a requirement ──────────────────
reset() OWNER_THROWS = true
check("a refused SetNetworkOwner still welds",
    spudAnchorTool(ride, impl) == true and #welds == 1)
OWNER_THROWS = false
reset()
local bare = model("Trailer", nil) HITCH[bare] = part("Hitchable")
check("a tool with no readable part still welds",
    spudAnchorTool(ride, bare) == true and #welds == 1)
check("  and claims nothing", #owners == 0)

print(fails == 0 and "ALL OK" or (fails .. " FAILED"))
"""


def main() -> int:
    base = pathlib.Path(os.environ.get("LOCALAPPDATA", ".")) / "Temp" / "opencode" / "luau"
    exe = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else base / "luau.exe"
    src = SRC.read_text(encoding="utf-8")
    parts = [PRE]
    for name in WANTED:
        code = extract(src, name)
        if not code:
            print("missing " + name)
            return 2
        parts.append(code)

    fails = []

    def tie(pattern: str, why: str, present: bool = True) -> None:
        found = re.search(pattern, src, re.M) is not None
        if found == present:
            print(f"{why:<54} PASS")
        else:
            fails.append(why)

    # The anchor is made only on the PROVEN hitch. hitchTool returns true at the
    # bottom, after the attempt loop; `spudAnchorTool` has to sit below the
    # gave-up branch, so a failed hitch can never weld anything.
    hitch = src[src.find("local function hitchTool(tr, impl)"):]
    hitch = hitch[: hitch.find("\n    -- ")] if "\n    -- " in hitch else hitch
    if "spudAnchorTool(tr, impl)" not in hitch:
        fails.append("hitchTool never anchors the tow — the weld would only "
                     "happen wherever someone remembered to call it")
    elif "if not didHitch then" not in hitch or \
            hitch.index("if not didHitch then") > hitch.index("spudAnchorTool(tr, impl)"):
        fails.append("the anchor sits BEFORE the gave-up branch — a failed "
                     "hitch would weld a tool that is not on the hitch")
    else:
        print(f"{'the weld sits after a proven hitch':<54} PASS")

    # …and it comes OFF before anything asks the game to unhitch, at every site
    # that does: the park, the wrong-tool swap, the blind X at attempt 3, both
    # loop stops and the unload.
    for reason, why in (
        ("the tool is being parked", "parking the tool releases the weld first"),
        ("the hitch has to be freed", "a wrong tool on the hitch releases first"),
        ("an X press is going to the hitch", "the blind X release comes off the weld first"),
        ("the wrong tool came off the hitch", "the neighbour grab releases before X"),
        ("the farming loop ended", "an ended loop releases the tow"),
        ("the farming loop was stopped", "a stopped loop releases the tow"),
        ("the script unloaded", "destroyUI releases the tow"),
    ):
        tie(re.escape(f'spudUnanchorTool("{reason}")'), why)

    tie(r'w\.Name = "SpudTowAnchor"', "the weld is named for what it is")
    tie(r'local v = spudWaitTool\(ride, spudToolAttachment\(impl\), "anchor"\)',
        "the settle is read before anything is welded")
    tie(r'if v ~= "settled" then', "only a settled tow is welded")
    tie(r'Instance\.new\("Weld"\)', "a classic Weld must not come back "
        "(it needs Part0.CFrame upkeep)", present=False)
    if src.count("spudAnchor = ") != 2:
        fails.append("spudAnchor is assigned " + str(src.count("spudAnchor = ")) +
                     " time(s) — the anchor state must be set once and cleared once")
    else:
        print(f"{'the anchor state has one owner':<54} PASS")

    with tempfile.NamedTemporaryFile("w", suffix=".lua", delete=False, encoding="utf-8") as fh:
        fh.write("\n\n".join(parts) + "\n" + POST)
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
