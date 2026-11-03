"""Whose tractor/tool does a farming pass use, and HOW does it know what a
machine is? (equipOwnerRank + the game's own EquipmentType word)

Two rules are pinned here.

WHOSE: the sweep used to take the NEAREST machine in Objects.Equipment, whoever
owned it, so working another account's field borrowed that account's tractor
whenever a stranger's happened to be closer. Every machine carries
Configurations.Owner, so the pick is the selected farm owner's machine first,
an unowned/unreadable machine second, and another account's machine never.

WHAT: the pick used to be a table of MODEL NAMES (Cultivator="KQF3000",
Planter="KADL", HARVEST={SRC6}) that won outright, so a machine the game itself
tags "Harvester" but names JDS790 - or a Planter named anything new - lost to
an old one every time. Owner 2026-11-02: "make it use the games build in
scripts to know what is a harvester and what is what". The game's own
EquipmentType WORD (matched by stem) is the key now; a driver seat plus
Components.Hitchable is the structural answer when the build ships no word at
all, and a model name is only the last resort. A hauler or a harvester is never
pressed into being the tractor, and a refusal names the type words the world
actually holds.

    python tools/equip_owner_test.py [path-to-luau.exe]
"""

import os
import pathlib
import re
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "SpudFarm_Full.lua"
START = "-- >>> SPUD FARM MODULE"
END = "-- <<< SPUD FARM MODULE"

WANTED = [
    "milkStoreOwnerOf",
    "equipTypeOf",
    "equipInStorage",
    "spudEquipTypeKey",
    "spudEquipIs",
    "spudEquipSeat",
    "spudEquipTows",
    "spudEquipHereText",
    "equipOwnerRank",
    "findTractor",
    "findImplement",
]

# the real stem tables, read out of the build rather than re-typed here, so a
# quieter word list in the script fails this harness instead of hiding in it
TABLES = ["HARVEST_STEMS", "TRACTOR_STEMS", "HAULER_STEMS", "TOOL_STEMS",
          "TYPE_STEMS", "TYPE_MODEL"]

PRE = r"""
local V = {}
function V.__sub(a, b) return setmetatable({ X = a.X - b.X, Y = a.Y - b.Y, Z = a.Z - b.Z }, V) end
function V.__add(a, b) return setmetatable({ X = a.X + b.X, Y = a.Y + b.Y, Z = a.Z + b.Z }, V) end
V.__index = function(t, k)
    if k == "Magnitude" then return math.sqrt(t.X * t.X + t.Y * t.Y + t.Z * t.Z) end
    return nil
end
local function vec(x, y, z) return setmetatable({ X = x or 0, Y = y or 0, Z = z or 0 }, V) end

function typeof(v)
    if type(v) == "table" and getmetatable(v) == V then return "Vector3" end
    return type(v)
end

local NODE = {}
NODE.__index = NODE
function NODE:FindFirstChild(name)
    return self.kids[name]
end
function NODE:GetChildren()
    return self.list
end
function NODE:GetDescendants()
    local out = {}
    local function walk(n)
        for _, k in ipairs(n.list) do out[#out + 1] = k walk(k) end
    end
    walk(self)
    return out
end
function NODE:FindFirstChildWhichIsA(cls, recursive)
    for _, k in ipairs(self.list) do
        if k._cls == cls then return k end
        if recursive then
            local hit = k:FindFirstChildWhichIsA(cls, true)
            if hit then return hit end
        end
    end
    return nil
end
function NODE:IsA(cls)
    return cls == self._cls
end
function NODE:GetAttribute(n)
    return (self._attrs or {})[n]
end
function NODE:GetPivot()
    return { Position = self._pos or vec(0, 0, 0) }
end

local ROOTNODE
TYPE_MODEL = { Cultivator = "KQF3000", Planter = "KADL" }
local function node(name, parent, cls)
    local n = setmetatable({ Name = name, _name = name, _cls = cls or "Folder",
        kids = {}, list = {} }, NODE)
    if parent then
        n.Parent = parent
        parent.kids[name] = n
        parent.list[#parent.list + 1] = n
    else
        ROOTNODE = n
    end
    return n
end

-- a machine the way the live build exposes it: EquipmentType/InStorage
-- attributes, a Configurations.Owner tag, a painted name, one seat and (for a
-- ride) the captured Components.Hitchable the game builds onto a tractor
local function machine(name, etype, x, owner, stored, hitch)
    local m = node(name, nil, "Model")
    m._attrs = { EquipmentType = etype, InStorage = stored == true }
    m._pos = vec(x, 0, 0)
    local seat = node("DriveSeat", m, "VehicleSeat")
    seat.Position = vec(x, 0, 0)
    local conf = node("Configurations", m)
    if owner then
        local o = node("Owner", conf, "ObjectValue")
        o.Value = { Name = owner }
    end
    if hitch then
        local comp = node("Components", m)
        node("Hitchable", comp, "Attachment")
    end
    return m
end

-- fresh world: the machines are the only children of Objects.Equipment
local WORKSPACE
local function world(machines)
    local ws = node("Workspace", nil, "Workspace")
    local objects = node("Objects", ws)
    local eq = node("Equipment", objects)
    for _, m in ipairs(machines) do
        m.Parent = eq
        eq.kids[m.Name] = m
        eq.list[#eq.list + 1] = m
    end
    WORKSPACE = ws
    workspace = ws
    local char = node("Character", nil, "Model")
    local hrp = node("HumanoidRootPart", char, "Part")
    hrp.Position = vec(0, 0, 0)
    LocalPlayer = { Name = "simba", Character = char }
    farmOwnerPick = nil
end

function equipmentFolder()
    local objects = WORKSPACE:FindFirstChild("Objects")
    return objects and objects:FindFirstChild("Equipment")
end

-- the build closure's log; the loose-tractor line is the proof the structural
-- path ran, so keep the last message readable from POST
local LOGS = {}
function log(msg) LOGS[#LOGS + 1] = tostring(msg) end
function lastLog() return LOGS[#LOGS] end
"""

POST = r"""
local fails = 0
local function check(name, ok, detail)
    if not ok then fails = fails + 1 end
    print(string.format("%-60s %s%s", name, ok and "PASS" or "FAIL",
        detail and ("  " .. detail) or ""))
end

local function equipNames(machines)
    local out = {}
    for _, m in ipairs(machines) do out[#out + 1] = m.Name .. "@" .. (m._pos.X) end
    return table.concat(out, ", ")
end

-- ── 1. the rank itself ─────────────────────────────────────────────────────
world({})
local mine = machine("ZM80", "Tractor", 10, "simba")
local bob = machine("ZM80", "Tractor", 20, "bob")
local loose = machine("ZM80", "Tractor", 30, nil)
check("rank: my machine is rank 0", equipOwnerRank(mine) == 0, tostring(equipOwnerRank(mine)))
check("rank: another account is refused", equipOwnerRank(bob) == nil, tostring(equipOwnerRank(bob)))
check("rank: no owner tag is rank 1 (usable)", equipOwnerRank(loose) == 1, tostring(equipOwnerRank(loose)))
farmOwnerPick = "bob"
check("rank: the picked farm's machine is rank 0", equipOwnerRank(bob) == 0)
check("rank: mine ranks below the pick but stays usable", equipOwnerRank(mine) == 1,
    tostring(equipOwnerRank(mine)))
local alice = machine("ZM80", "Tractor", 40, "alice")
check("rank: a third account is refused under a pick", equipOwnerRank(alice) == nil)
check("rank: an untagged machine ranks below mine under a pick", equipOwnerRank(loose) == 2,
    tostring(equipOwnerRank(loose)))

-- ── 2. tractors: the nearest is no longer enough ───────────────────────────
world({ machine("ZM80", "Tractor", 1, "bob"), machine("ZM80", "Tractor", 100, "simba") })
local tr = findTractor()
check("tractor: mine wins even when a stranger's is nearer",
    tr and tr.Name == "ZM80" and tr._pos.X == 100,
    tr and ("x=" .. tr._pos.X) or "none")

world({ machine("ZM80", "Tractor", 1, "bob") })
tr = findTractor()
check("tractor: a stranger's spawn is never borrowed", tr == nil,
    tr and tr._pos and ("x=" .. tr._pos.X) or "none")

world({ machine("ZM80", "Tractor", 10, nil), machine("ZM80", "Tractor", 100, "simba") })
tr = findTractor()
check("tractor: owner beats an unreadable owner",
    tr and tr._pos.X == 100, tr and ("x=" .. tr._pos.X) or "none")

world({ machine("ZM80", "Tractor", 10, nil) })
tr = findTractor()
check("tractor: an unreadable owner is still usable", tr and tr._pos.X == 10,
    tr and ("x=" .. tr._pos.X) or "none")

world({ machine("ZM80", "Tractor", 1, "bob"), machine("ZM80", "Tractor", 100, "simba") })
farmOwnerPick = "bob"
tr = findTractor()
check("tractor: the picked farm gets its own machine",
    tr and tr._pos.X == 1, tr and ("x=" .. tr._pos.X) or "none")

-- the owner's machine is in storage and a stranger's is out: spawn OURS
world({ machine("ZM80", "Tractor", 1, "bob"), machine("ZM80", "Tractor", 100, "simba", true) })
tr = findTractor()
check("tractor: our stored one is reported for spawning, not the other's",
    tr == nil, tr and ("x=" .. tr._pos.X) or "none")
-- findTractor returns stashedModel in slot 4
local stored = (findTractor())
stored = select(4, findTractor())
check("tractor: the stored model handed back is ours",
    stored ~= nil and stored._pos.X == 100,
    stored and ("x=" .. stored._pos.X) or "none")

-- ── 3. implements ──────────────────────────────────────────────────────────
world({ machine("KQF3000", "Cultivator", 1, "bob"), machine("KQF3000", "Cultivator", 100, "simba") })
local impl, dist, basis = findImplement("Cultivator", vec(0, 0, 0), nil)
check("implement: mine wins over a nearer stranger's",
    impl and impl._pos.X == 100, impl and ("x=" .. impl._pos.X .. " via " .. tostring(basis)) or "none")
check("implement: the distance returned is the real one", math.abs((dist or -1) - 100) < 0.01,
    tostring(dist))
check("implement: the basis names the WORD the game wrote, not the model",
    basis == "EquipmentType Cultivator", tostring(basis))

world({ machine("KQF3000", "Cultivator", 1, "bob") })
impl = findImplement("Cultivator", vec(0, 0, 0), nil)
check("implement: a stranger's tool is never hooked", impl == nil,
    impl and ("x=" .. impl._pos.X) or "none")

world({ machine("KQF3000", "Cultivator", 1, "bob"), machine("KQF3000", "Cultivator", 100, "simba") })
farmOwnerPick = "bob"
impl = findImplement("Cultivator", vec(0, 0, 0), nil)
check("implement: the picked farm gets its own tool", impl and impl._pos.X == 1,
    impl and ("x=" .. impl._pos.X) or "none")

world({ machine("GENERIC", "Cultivator", 50, "simba") })
impl, dist, basis = findImplement("Cultivator", vec(0, 0, 0), nil)
check("implement: an unknown model name still works off the type alone",
    impl ~= nil and basis == "EquipmentType Cultivator", tostring(basis))

world({ machine("KQF3000", "Cultivator", 5, "simba", true) })
impl = findImplement("Cultivator", vec(0, 0, 0), nil)
check("implement: a stored tool is skipped for hitching", impl == nil)
impl = findImplement("Cultivator", vec(0, 0, 0), nil, true)
check("implement: the respawn check can still see it", impl ~= nil and impl._pos.X == 5)

world({ machine("KQF3000", "Cultivator", 5, nil) })
impl = findImplement("Cultivator", vec(0, 0, 0), nil)
check("implement: an unreadable owner is still usable", impl ~= nil and impl._pos.X == 5)

-- ── 4. the game's own WORD decides what a machine is ───────────────────────
world({})
local jd = machine("JDS790", "Harvester", 10, "simba")
check("word: a brand-new harvester model name is still a harvester",
    spudEquipIs(jd, HARVEST_STEMS) == true, tostring(spudEquipTypeKey(jd)))
local odd = machine("Weird Thing", "  Skid-Steer ", 20, "simba")
check("word: case and punctuation are stripped, never guessed around",
    spudEquipTypeKey(odd) == "skidsteer", tostring(spudEquipTypeKey(odd)))
check("word: a machine with no attribute has no key at all",
    spudEquipTypeKey(machine("X", nil, 30, "simba")) == nil)
check("word: an empty word is no key (unreadable is not a type)",
    spudEquipTypeKey(machine("Y", "   ", 40, "simba")) == nil)

world({ machine("KADL", "Cultivator", 1, "simba"),
        machine("PDRILL22", "Planter", 100, "simba") })
impl = findImplement("Planter", vec(0, 0, 0), nil)
check("implement: the game's word beats the script's old name table",
    impl ~= nil and impl.Name == "PDRILL22", impl and impl.Name or "none")

world({ machine("KADL", nil, 40, "simba") })
impl, dist, basis = findImplement("Planter", vec(0, 0, 0), nil)
check("implement: a build with NO attribute still falls back to the model name",
    impl ~= nil and basis == "model name KADL", tostring(basis))

world({ machine("OLDKADL", nil, 5, "simba") })
impl = findImplement("Planter", vec(0, 0, 0), nil)
check("implement: a name-matched tool is never invented for a new type", impl == nil)

-- ── 5. a ride the game does not call a Tractor is still a ride ─────────────
world({ machine("BIGBEAR", nil, 5, "simba", false, true) })
tr = findTractor()
check("tractor: a seat plus a Hitchable makes it a ride with no type word",
    tr ~= nil and tr.Name == "BIGBEAR", tr and tr.Name or "none")
check("tractor: taking the structural ride is said out loud",
    lastLog() ~= nil and lastLog():find("driver seat and a Hitchable") ~= nil, tostring(lastLog()))

world({ machine("BIGBEAR", nil, 5, "simba", false, true),
        machine("ZM80", "Tractor", 100, "simba") })
tr = findTractor()
check("tractor: a machine the game CALLS a Tractor outranks the structural one",
    tr and tr._pos.X == 100, tr and ("x=" .. tr._pos.X) or "none")

world({ machine("HAYHaul", "Truck", 5, "simba", false, true) })
tr = findTractor()
check("tractor: a hauler with a seat and a hitch is never the ride", tr == nil,
    tr and tr.Name or "none")

world({ machine("SRC6", "Harvester", 5, "simba", false, true) })
tr = findTractor()
check("tractor: a harvester is not pressed into being the tractor", tr == nil,
    tr and tr.Name or "none")

world({ machine("KQF3000", "Cultivator", 5, "simba", false, true) })
tr = findTractor()
check("tractor: a tool is never the ride", tr == nil, tr and tr.Name or "none")

world({ machine("SEATONLY", nil, 5, "simba", false, false) })
tr = findTractor()
check("tractor: a seat with no hitch is not a tractor either", tr == nil,
    tr and tr.Name or "none")

-- ── 6. a refusal names the world it looked in ──────────────────────────────
world({ machine("JDS790", "Harvester", 5, "simba"),
        machine("MTS12", nil, 9, "simba", true) })
local here = spudEquipHereText()
check("here: the list carries the real type words and the stored flag",
    here:find("JDS790=Harvester", 1, false) ~= nil
    and here:find("MTS12=no type %(stored%)", 1, false) ~= nil, here)
world({})
check("here: an empty world says so instead of returning nothing",
    spudEquipHereText():find("no machine readable") ~= nil, spudEquipHereText())

print(fails == 0 and "ALL OK" or (fails .. " FAILED"))
"""


def dedent(block: str) -> str:
    return "\n".join(l[4:] if l.startswith("    ") else l for l in block.splitlines())


def extract(text: str, name: str) -> str:
    m = re.search(r"^    (?:local )?function " + name + r"\(", text, re.M)
    if not m:
        return ""
    tail = text[m.start():]
    end = re.search(r"\n    (?:local function |function |-- )", tail[10:])
    block = tail[: end.start() + 10] if end else tail
    return dedent(block)


def extract_table(text: str, name: str) -> str:
    """The real `local NAME = { ... }` block, braces counted, so the harness
    runs the build's own word lists instead of a copy that can drift."""
    m = re.search(r"^    local " + name + r" = \{", text, re.M)
    if not m:
        return ""
    depth, i = 0, text.index("{", m.start())
    for j in range(i, len(text)):
        if text[j] == "{":
            depth += 1
        elif text[j] == "}":
            depth -= 1
            if depth == 0:
                return dedent(text[m.start():text.index("\n", j)])
    return ""


def module(text: str) -> str:
    a, b = text.find(START), text.find(END)
    if a < 0 or b <= a:
        return ""
    return text[a:b].strip() + "\n"


def main() -> int:
    base = pathlib.Path(os.environ.get("LOCALAPPDATA", ".")) / "Temp" / "opencode" / "luau"
    exe = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else base / "luau.exe"
    src = SRC.read_text(encoding="utf-8")
    parts = []
    mod = module(src)
    if not mod:
        print("missing SPUD FARM MODULE markers in SpudFarm_Full.lua")
        return 2
    for name in TABLES:
        code = extract_table(src, name)
        if not code:
            print("missing local " + name)
            return 2
        parts.append(code)
    for name in WANTED:
        code = extract(src, name)
        if not code:
            print("missing " + name)
            return 2
        parts.append(code)
    with tempfile.NamedTemporaryFile("w", suffix=".lua", delete=False, encoding="utf-8") as fh:
        fh.write(mod + "\n" + PRE + "\n" + "\n\n".join(parts) + "\n" + POST)
        path = fh.name
    try:
        out = subprocess.run([str(exe), path], capture_output=True, encoding="utf-8",
                             errors="replace")
        print(out.stdout.strip())
        if out.returncode != 0:
            print(out.stderr.strip()[-2000:])
        return out.returncode
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
