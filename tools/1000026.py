"""Run the REAL liquid-deck trip on a fake world and check what it proves.

A full carrier used to be where the milk money stopped: the loop reported
"empty it or pick another carrier" and never emptied anything. The deck has an
address now (the owner's own 📍 Get coords reading), so the trip is wired — and
a trip that spends the session standing in town, or that calls a sale a sale
because a key was pressed, is worse than the old report. So this harness runs
`milkSellLiquidCarrier` itself and asks the questions the console cannot answer
afterwards: does a refusal cost a teleport? does a sale need the readout to
drop? does the player come back to the plot?

    python tools/1000026.py [path-to-luau.exe]
"""

import os
import pathlib
import re
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "1000051.lua"

# the real fold + the real measured deck, so the trip is tested with the names
# the game actually writes and the address the owner actually stood on
WANTED = ["spudNameKey", "spudSameEquipName", "spudLiquidSellSpot",
          "milkSellLiquidCarrier"]

PRE = r"""
-- ▸ a Vector3 that adds, subtracts and reports a Magnitude. The trip uses all
--   three (deck + 3 Y, and the flat startP - root.Position check in home()).
local V = {}
V.__add = function(a, b)
    return setmetatable({ X = a.X + b.X, Y = a.Y + b.Y, Z = a.Z + b.Z }, V)
end
V.__sub = function(a, b)
    return setmetatable({ X = a.X - b.X, Y = a.Y - b.Y, Z = a.Z - b.Z }, V)
end
V.__index = function(t, k)
    if k == "Magnitude" then return math.sqrt(t.X * t.X + t.Y * t.Y + t.Z * t.Z) end
    return nil
end
local function vec(x, y, z)
    return setmetatable({ X = x or 0, Y = y or 0, Z = z or 0 }, V)
end
Vector3 = { new = vec }
task = { wait = function() end }

-- ▸ the world: a character, and Objects.Equipment as a flat list this harness
--   moves by hand. No model is ever moved by the trip itself — that is the
--   point of the PivotTo tie below.
ROOTP = vec(0, 170, 0)                       -- the plot the pass started on
NO_ROOT = false
LocalPlayer = { Character = { FindFirstChild = function(_, n)
    if n == "HumanoidRootPart" and not NO_ROOT then
        return { Position = ROOTP, _root = true }
    end
    return nil
end } }

EQS = {}
local EQFOLDER = { Name = "Equipment", GetChildren = function() return EQS end }
local OBJECTS = { FindFirstChild = function(_, k)
    if k == "Equipment" then return EQFOLDER end
    return nil
end }
workspace = { FindFirstChild = function(_, n)
    if n == "Objects" then return OBJECTS end
    return nil
end }

local function carrier(name, x, z, attrs, parent)
    local m = { Name = name, x = x or 0, z = z or 0, y = 141,
        attrs = attrs or {}, Parent = parent or EQFOLDER }
    function m:GetPivot() return { Position = vec(self.x, self.y, self.z) } end
    function m:GetAttribute(k) return self.attrs[k] end
    return m
end

-- ▸ the stubs. Each one is the shape the build calls, and each one COUNTS what
--   it was asked to do so a refusal can be proved to have cost nothing.
LOGS, TPS, FRAMES, PRESSES, SPAWNS = {}, 0, 0, {}, {}
TANK, CAP = {}, {}
ACTS, PRESS_EFFECT, POLL_STEP = {}, nil, nil
FARM_BUSY, STOPPING, COINS = false, false, 1000

local function key(s) return spudNameKey(s) end

function milkStoreAmount(m)
    if not m then return nil end
    local k = key(m.Name)
    return TANK[k], CAP[k]
end
function milkStoreActs() return ACTS end
function milkStorePress(a)
    PRESSES[#PRESSES + 1] = a.name
    if PRESS_EFFECT then PRESS_EFFECT() end
    return "activate " .. a.name
end
function milkTp(target, noWait)
    TPS = TPS + 1
    if target then
        ROOTP = vec(target.X, target.Y, target.Z)
        LocalPlayer.Character._p = ROOTP
    end
end
function milkFrame() FRAMES = FRAMES + 1 end
function farmTookBody() return FARM_BUSY end
function milkStopping() return STOPPING end
function coinBalance() return COINS end
function log(s) LOGS[#LOGS + 1] = tostring(s) end
function managerAction(name, kind)
    SPAWNS[#SPAWNS + 1] = { name = name, kind = kind }
    if SPAWN_MOVES then
        for _, c in ipairs(EQS) do
            if spudSameEquipName(c.Name, name) then c.x, c.z = 86, -288 end
        end
    end
    return true
end
-- a poll that reads the predicate a few times, with the game free to change
-- the tank between reads (that is how a drain and a press-effect are told apart)
function milkPollFor(pred, seconds)
    for _ = 1, 3 do
        if pred() then return true end
        if POLL_STEP then POLL_STEP() end
    end
    return false
end

local function fresh()
    ROOTP = vec(0, 170, 0)                         -- every case starts on the plot
    LOGS, TPS, FRAMES, PRESSES, SPAWNS = {}, 0, 0, {}, {}
    TANK, CAP, ACTS = {}, {}, {}
    PRESS_EFFECT, POLL_STEP, SPAWN_MOVES = nil, nil, true
    FARM_BUSY, STOPPING, NO_ROOT = false, false, false
    COINS = 1000
    milkLiquidOff, milkLiquidTries, milkStoreQuietAt, milkStoreTarget = nil, 0, nil, nil
    EQS = {}
end
"""

POST = r"""
local fails = 0
local function check(name, ok, detail)
    if not ok then fails = fails + 1 end
    print(string.format("%-62s %s%s", name, ok and "PASS" or "FAIL",
        detail and ("  " .. detail) or ""))
end
local function joined() return table.concat(LOGS, " | ") end

-- ─────────────────────────── a silo never goes to town ────────────────────
fresh()
local bldg = { Name = "Buildings" }
local silo = carrier("Silo600", 0, 0, { EquipmentType = "Silo" }, bldg)
TANK[key(silo.Name)], CAP[key(silo.Name)] = 600, 600
local ok = milkSellLiquidCarrier(silo)
check("a machine the game calls a Silo is refused", ok == false, tostring(ok))
check("  and costs no teleport", TPS == 0, "tps " .. TPS)
check("  and no Equipment Manager call", #SPAWNS == 0, "spawns " .. #SPAWNS)
check("  and the line says why", LOGS[1] and LOGS[1]:find("silo", 1, true) and
    LOGS[1]:find("pick a trailer", 1, true) or false, LOGS[1] or "(no log)")

fresh()
local barn = carrier("WaterTank", 0, 0, {}, { Name = "Buildings" })
TANK[key(barn.Name)], CAP[key(barn.Name)] = 40, 40
milkSellLiquidCarrier(barn)
check("a tank that lives under Buildings is a silo too", TPS == 0 and #SPAWNS == 0,
    joined())

fresh()
milkStoreQuietAt = os.clock()
TANK[key(silo.Name)], CAP[key(silo.Name)] = 600, 600
milkSellLiquidCarrier(silo)
check("a silo already named this minute stays quiet", #LOGS == 0, joined())

-- ─────────────────────── the early-outs cost nothing ──────────────────────
fresh()
local tr = carrier("Trailer", 0, 0)
TANK[key(tr.Name)], CAP[key(tr.Name)] = 40, 40
FARM_BUSY = true
check("the farm loop owns the body: no trip", milkSellLiquidCarrier(tr) == false and TPS == 0,
    "tps " .. TPS)

fresh()
tr = carrier("Trailer", 0, 0)
TANK[key(tr.Name)] = 40
local gone = carrier("Trailer", 0, 0)
gone.Parent = nil
check("a carrier that left the world is not chased",
    milkSellLiquidCarrier(gone) == false and TPS == 0, "tps " .. TPS)

fresh()
tr = carrier("Trailer", 0, 0)
EQS = { tr }
TANK[key(tr.Name)] = 40
milkLiquidOff = true
check("a deck switched off this session is never visited again",
    milkSellLiquidCarrier(tr) == false and TPS == 0, "tps " .. TPS)

-- ───────────────────── a carrier already here pays no spawn ───────────────
fresh()
tr = carrier("Trailer", 86, -288)
EQS = { tr }
TANK[key(tr.Name)], CAP[key(tr.Name)] = 40, 40
milkSellLiquidCarrier(tr)
check("a carrier already on the deck is not spawned", #SPAWNS == 0,
    "spawns " .. #SPAWNS)

-- ───────────────── the only proof: the carrier's OWN readout ──────────────
fresh()
tr = carrier("Trailer", 86, -288)
EQS = { tr }
TANK[key(tr.Name)], CAP[key(tr.Name)] = 40, 40
POLL_STEP = function() TANK[key(tr.Name)] = 5 end      -- the pad drains a parked tank
ok = milkSellLiquidCarrier(tr)
check("a deck that drains a parked carrier sells it", ok == true, tostring(ok))
check("  pressing NOTHING", #PRESSES == 0, "presses " .. table.concat(PRESSES, ","))
check("  and says so", LOGS[#LOGS]:find("parked, pressing nothing", 1, true) ~= nil,
    LOGS[#LOGS])
check("  and the trip came back to the plot",
    TPS == 2 and ROOTP.X == 0 and ROOTP.Y == 173 and ROOTP.Z == 0,
    "tps " .. TPS .. " at " .. ROOTP.X .. "," .. ROOTP.Y .. "," .. ROOTP.Z)

fresh()
tr = carrier("Trailer", 86, -288)
EQS = { tr }
TANK[key(tr.Name)], CAP[key(tr.Name)] = 40, 40
ACTS = { { name = "Talk" }, { name = "Open Shop" } }
ok = milkSellLiquidCarrier(tr)
check("an offer list with no unload presses nothing", ok == false and #PRESSES == 0,
    "presses " .. #PRESSES)
check("  and prints the deck's verbatim list",
    LOGS[#LOGS]:find("Talk · Open Shop", 1, true) ~= nil, LOGS[#LOGS])

fresh()
tr = carrier("Trailer", 86, -288)
EQS = { tr }
TANK[key(tr.Name)], CAP[key(tr.Name)] = 40, 40
ACTS = { { name = "Talk" }, { name = "Unload Milk" } }
PRESS_EFFECT = function() TANK[key(tr.Name)] = 6 end
ok = milkSellLiquidCarrier(tr)
check("the game's own unload is driven through its own handler", ok == true, tostring(ok))
check("  and the line names the button", LOGS[#LOGS]:find("activate Unload Milk", 1, true) ~= nil,
    LOGS[#LOGS])

fresh()
tr = carrier("Trailer", 86, -288)
EQS = { tr }
TANK[key(tr.Name)], CAP[key(tr.Name)] = 40, 40
ACTS = { { name = "Unload Milk" } }
ok = milkSellLiquidCarrier(tr)
check("a press that leaves the tank alone is NOT a sale", ok == false, tostring(ok))
check("  and the line quotes the readout",
    LOGS[#LOGS]:find("still reads 40/40", 1, true) ~= nil, LOGS[#LOGS])

-- ──────────────────── a spawn that never arrives is named ─────────────────
fresh()
tr = carrier("Trailer", 86, 12)                    -- ~300 studs off the deck
EQS = { tr }
TANK[key(tr.Name)], CAP[key(tr.Name)] = 40, 40
SPAWN_MOVES = false
ok = milkSellLiquidCarrier(tr)
check("a spawn that does not bring it is a refusal", ok == false, tostring(ok))
check("  asking the Equipment Manager by name", #SPAWNS == 1 and SPAWNS[1].kind == "Spawn"
    and spudSameEquipName(SPAWNS[1].name, "Trailer"), joined())
check("  naming the real distance left", LOGS[#LOGS]:find("300 studs away", 1, true) ~= nil,
    LOGS[#LOGS])
check("  costing one miss", milkLiquidTries == 1, "tries " .. tostring(milkLiquidTries))
check("  and pressing nothing", #PRESSES == 0, "presses " .. #PRESSES)

fresh()
tr = carrier("Trailer", 86, 12)
EQS = { tr }
TANK[key(tr.Name)], CAP[key(tr.Name)] = 40, 40
POLL_STEP = function() TANK[key(tr.Name)] = 2 end
ok = milkSellLiquidCarrier(tr)
check("a far carrier is spawned in and then sold", ok == true, joined())
check("  and the spawn is asked for once", #SPAWNS == 1, "spawns " .. #SPAWNS)

-- ─────────────────── three misses stop the visits, once reset ─────────────
fresh()
tr = carrier("Trailer", 86, 12)
EQS = { tr }
TANK[key(tr.Name)], CAP[key(tr.Name)] = 40, 40
SPAWN_MOVES = false
milkSellLiquidCarrier(tr); milkSellLiquidCarrier(tr)
check("two misses still allow a third visit", milkLiquidOff ~= true and TPS == 4,
    "tps " .. TPS)
milkSellLiquidCarrier(tr)
check("three misses switch the deck off for the session", milkLiquidOff == true,
    tostring(milkLiquidOff))
check("  and say so", LOGS[#LOGS]:find("not visiting it again", 1, true) ~= nil, LOGS[#LOGS])

fresh()
tr = carrier("Trailer", 86, -288)
EQS = { tr }
TANK[key(tr.Name)], CAP[key(tr.Name)] = 40, 40
POLL_STEP = function() TANK[key(tr.Name)] = 5 end
milkLiquidTries = 2
milkSellLiquidCarrier(tr)
check("a sale resets the miss count", milkLiquidTries == 0, tostring(milkLiquidTries))

-- ──────────────── the label the game draws vs the model's name ────────────
fresh()
local stale = carrier("MilkTanker", 0, 0)          -- the instance the pick holds
stale.Parent = { Name = "Equipment" }
local live = carrier("Milk Tanker", 86, -288)      -- the model in the world now
EQS = { live }
TANK[key(live.Name)], CAP[key(live.Name)] = 40, 40
POLL_STEP = function() TANK[key(live.Name)] = 3 end
ok = milkSellLiquidCarrier(stale)
check("a spaced label finds the model it was folded from", ok == true, joined())
check("  and the sale is read off THAT model", milkStoreTarget == live,
    tostring(milkStoreTarget and milkStoreTarget.Name))

-- ─────────────────── unreadable is not a crash (rule 7) ──────────────────
fresh()
tr = carrier("Trailer", 86, -288)
EQS = { tr }
TANK[key(tr.Name)], CAP[key(tr.Name)] = 40, 40
NO_ROOT = true                                     -- no HumanoidRootPart to read
POLL_STEP = function() TANK[key(tr.Name)] = 1 end
ok = milkSellLiquidCarrier(tr)
check("a character position that cannot be read still sells", ok == true, tostring(ok))
check("  and the way home costs no phantom teleport", TPS == 1, "tps " .. TPS)

print(fails == 0 and "ALL OK" or (fails .. " FAILED"))
if fails > 0 then error("liquid deck checks failed") end
"""

# home() compares against the recorded start, so the checks read the position the
# milkTp stub left behind rather than trusting a teleport count alone.


def dedent(block_src: str) -> str:
    return "\n".join(l[4:] if l.startswith("    ") else l for l in block_src.splitlines())


def extract(text: str, name: str) -> str:
    m = re.search(r"^    (?:local )?function " + name + r"\(", text, re.M)
    if not m:
        return ""
    tail = text[m.start():]
    end = re.search(r"\n    (?:local function |function |-- )", tail[4:])
    block_src = tail[: end.start() + 4] if end else tail
    return dedent(block_src)


def block(text: str, name: str) -> str:
    """A function's source, indentation kept, for the ties."""
    m = re.search(r"^    (?:local )?function " + name + r"\(", text, re.M)
    if not m:
        return ""
    body = text[m.end():]
    nxt = re.search(r"\n    (?:local )?function \w+\(", body)
    return text[m.start(): m.end() + (nxt.start() if nxt else len(body))]


def main() -> int:
    base = pathlib.Path(os.environ.get("LOCALAPPDATA", ".")) / "Temp" / "opencode" / "luau"
    exe = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else base / "luau.exe"
    src = SRC.read_text(encoding="utf-8")

    missing = [n for n in WANTED if not extract(src, n)]
    if missing:
        print("MISSING from the build: " + ", ".join(missing))
        return 2

    near = re.search(r"^    spudLiquidDeckNear = (\d+)", src, re.M)
    if not near:
        print("MISSING from the build: spudLiquidDeckNear")
        return 2

    lua = ("\n".join(extract(src, n) for n in WANTED)
           + "\n" + near.group(0).strip() + "\n" + POST)
    with tempfile.NamedTemporaryFile("w", suffix=".lua", delete=False, encoding="utf-8") as fh:
        fh.write(PRE + "\n" + lua + "\n")
        path = fh.name
    out = subprocess.run([str(exe), path], capture_output=True, encoding="utf-8",
                         errors="replace")
    print(out.stdout.strip())
    if out.returncode != 0:
        print(out.stderr.strip()[-1200:])
        return out.returncode

    # ▸ the wiring, so a later edit cannot quietly invent a mechanism
    ties = []

    def tie(name, ok, detail=""):
        ties.append((name, bool(ok), detail))

    trip = block(src, "milkSellLiquidCarrier")
    tie("the deck is the owner's measured spot",
        re.search(r"function spudLiquidSellSpot\(\)\s*\n\s*return Vector3\.new\(86, 141, -288\)",
                  src) is not None,
        "must stay 86, 141, -288 (📍 Get coords)")
    tie("the band is the constant, not a literal at the call sites",
        near.group(1) == "45" and trip.count("spudLiquidDeckNear") >= 4)
    tie("nothing is moved but the character",
        ":PivotTo" not in trip and "PivotTo(" not in trip)
    tie("no key is pressed the deck has never shown",
        "pressKey" not in trip and "keyDown" not in trip and "Mouse" not in trip)
    tie("no remote whose arguments nobody captured",
        "FireServer" not in trip and "InvokeServer" not in trip
        and "EVTSellAtStore" not in trip)
    tie("the live offer comes from the reader the fill step already trusts",
        "milkStoreActs()" in trip and "milkStorePress(" in trip
        and "PCGP_ContextActions" not in trip and "milkFeedButton" not in trip)
    tie("the readout is the only proof of a sale",
        trip.count("milkPollFor(drained") == 2 and "drained()" in trip
        and "local n = c and milkStoreAmount(c) or nil" in trip)
    tie("a park with no input is tried before any button",
        trip.index("pressing nothing") < trip.index("milkStoreActs()"))
    tie("the way home is declared before the refusal that uses it",
        trip.index("local function home()") < trip.index("local function noSale("))
    tie("every refusal goes through the one counter",
        trip.count("return noSale(") >= 2 and trip.count("milkLiquidTries =") == 3)
    tie("a silo is refused before the first teleport",
        trip.index('isSilo = true') < trip.index("milkTp(deck"))
    tie("the trip comes back with the coins it started with",
        "local coins0 = coinBalance()" in trip and "tostring(coins0)" in trip)

    dep = block(src, "milkStoreDeposit")
    tie("a FULL carrier gets the deck trip, not a instruction to a person",
        "milkSellLiquidCarrier(dest)" in dep)
    tie("the honest report survives as the else",
        "is FULL (%d/%d) — empty it or pick another carrier" in dep
        and dep.index("milkSellLiquidCarrier(dest)") < dep.index("empty it or pick another"))
    tie("the learned state is reset per build",
        re.search(r"milkLiquidOff, milkLiquidTries = nil, 0", src) is not None)
    # ▸ the 15 s store scan drives SetValue(), and SetValue re-enters the
    #   dropdown's own Callback — so a pick that is already the pick must not
    #   log itself as if the owner had chosen it.
    tie("a refresh that re-sets the same store pick logs no choice",
        re.search(r"if v == milkStorePick then return end\s*\n\s*milkStorePick = v",
                  src) is not None,
        "the Callback must bail before it assigns and logs")
    tie("the store scan still runs on its own timer",
        re.search(r"pcall\(milkStoreRefresh, true\)", src) is not None)

    for name, ok, detail in ties:
        print("%-62s %s%s" % (name, "PASS" if ok else "FAIL", ("  " + detail) if detail else ""))
    bad = [n for n, ok, _ in ties if not ok]
    if bad:
        print("%d FAILED" % len(bad))
        return 1
    print("ALL OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
