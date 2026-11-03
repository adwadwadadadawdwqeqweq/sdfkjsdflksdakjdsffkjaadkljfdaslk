"""Equipment actions through the game's own remotes (captured 2026-10-30).

SpudRemoteProbe recorded these from the game's own client while the actions
were done by hand (spawn/store a machine, mount a tractor, hitch/unhitch a
tool, pick a crate up), all under Modules.Larry:

    FNCEnterEquipment(vehicle, seat)
    FNCAttemptHitch(tractor.Components.Hitchable, tool.Chassis.HitchableSocket)
    FNCUnhitch(tractor.Components.Hitchable)
    FNCSpawnEquipment(model) / FNCStoreEquipment(model)
    EVTRequestToCarry(draggable) / EVTRequestToDrop()
    EVTSellAtStore(harvester, pad) / FNCRequestStorePurchase({crate})

Every helper fires the call only where the game offers the action and demands
proof before trusting it:

  * enter   -> the humanoid is seated in that vehicle
  * hitch   -> the caller's tug (unchanged, in attemptHitch)
  * unhitch -> the caller's tug (unchanged, in dropImplementAtOrigin)
  * spawn   -> InStorage flips false or the model moves > 100 studs
  * store   -> InStorage flips true
  * carry   -> carrying() turns true

An ignored call counts a miss; three take that action back to keys/UI for the
session. Nothing here can skip the old path.

v1.135 adds the two things a live run proved and this file did not check:

  * the machine is looked up by the game's FOLDED name (the planter's model is
    TempoL16 while its card and HUD draw "Tempo L16"), and every path that
    hands the action to the Equipment Manager now SAYS which half broke —
    no model, already in that state, no remote, a throwing remote, or the call
    switched off for the session;
  * the Equipment Manager's card list is filtered to the tab the game last
    showed, so a run that stores its ride at the end of every pass could never
    reach that ride's card again (`no card for ChallengerMT9` next to a list of
    two Planter cards). A miss now clicks the game's own `All` tab through its
    own handler and re-reads, and a build with no such tab says so.

    python tools/equip_remote_test.py [path-to-luau.exe]
"""

import os
import pathlib
import re
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "SpudFarm_Full.lua"
WANTED = [
    "spudNameKey",
    "spudEquipRemoteKit",
    "spudEquipRemoteMiss",
    "spudEquipRemoteCall",
    "spudEquipRemoteAct",
    "spudEnterRemote",
    "spudHitchParts",
    "spudHitchRemote",
    "spudUnhitchRemote",
    "spudCarryRemote",
    "spudDropRemote",
    "spudSellRemote",
    "spudPurchaseRemote",
]

PRE = r"""
local V = {}
function V.__sub(a, b) return setmetatable({ X = a.X - b.X, Y = a.Y - b.Y, Z = a.Z - b.Z }, V) end
function V.__add(a, b) return setmetatable({ X = a.X + b.X, Y = a.Y + b.Y, Z = a.Z + b.Z }, V) end
V.__index = function(t, k)
    if k == "Magnitude" then return math.sqrt(t.X * t.X + t.Y * t.Y + t.Z * t.Z) end
    return nil
end
Vector3 = { new = function(x, y, z) return setmetatable({ X = x, Y = y, Z = z }, V) end }
local function v(x, y, z) return Vector3.new(x, y, z) end

local logs = {}
function log(msg) logs[#logs + 1] = tostring(msg) end
function stopping() return false end
task = task or {}
task.wait = function(_) end
function require(x) return x end

local function newInst(name, class)
    local o = { Name = name, ClassName = class, kids = {}, attrs = {} }
    function o:IsA(c) return self.ClassName == c end
    function o:FindFirstChild(n)
        for _, k in ipairs(self.kids) do
            if k.Name == n then return k end
        end
        return nil
    end
    function o:FindFirstChildOfClass(c)
        for _, k in ipairs(self.kids) do
            if k.ClassName == c then return k end
        end
        return nil
    end
    function o:IsDescendantOf(root)
        local cur = self.Parent
        while cur do
            if cur == root then return true end
            cur = cur.Parent
        end
        return false
    end
    function o:GetChildren() return self.kids end
    function o:GetAttribute(k) return self.attrs[k] end
    function o:SetAttribute(k, val) self.attrs[k] = val end
    function o:GetPivot() return { Position = self.pivot or v(0, 0, 0) } end
    return o
end
local function adopt(parent, kid)
    parent.kids[#parent.kids + 1] = kid
    kid.Parent = parent
    return kid
end

spudEquipRemoteState = { kit = nil, fails = {}, off = {} }

local mode = { enter = "ok", store = "ok", spawn = "ok", carry = "ok", drop = "ok" }

local function newRemote(name, class, handler)
    local o = newInst(name, class)
    o.fireCalls, o.invokeCalls = 0, 0
    local function remember(...)
        local a = table.pack(...)
        o.lastArgs = a
    end
    function o:FireServer(...)
        self.fireCalls += 1
        remember(...)
        if handler then handler(...) end
    end
    function o:InvokeServer(...)
        self.invokeCalls += 1
        remember(...)
        if handler then return handler(...) end
        return true
    end
    return o
end

local hum = newInst("Humanoid", "Humanoid")
local char = newInst("Char", "Model")
adopt(char, hum)
LocalPlayer = { Character = char }

local function enterHandler(vehicle, seat)
    if mode.enter == "ok" then hum.SeatPart = seat end
end
local function storeHandler(model)
    if mode.store == "ok" then model:SetAttribute("InStorage", true) end
end
local function spawnHandler(model)
    if mode.spawn == "ok" then
        model:SetAttribute("InStorage", false)
    elseif mode.spawn == "move" then
        model.pivot = (model.pivot or v(0, 0, 0)) + v(500, 0, 0)
    end
end
local function carryHandler(model)
    if mode.carry == "ok" then carryingFlag = true end
end
local function dropHandler()
    if mode.drop == "ok" then carryingFlag = false end
end

local enterRemote = newRemote("FNCEnterEquipment", "RemoteFunction", enterHandler)
local hitchRemote = newRemote("FNCAttemptHitch", "RemoteFunction", nil)
local unhitchRemote = newRemote("FNCUnhitch", "RemoteFunction", nil)
local spawnRemote = newRemote("FNCSpawnEquipment", "RemoteFunction", spawnHandler)
local storeRemote = newRemote("FNCStoreEquipment", "RemoteFunction", storeHandler)
local carryRemote = newRemote("EVTRequestToCarry", "RemoteEvent", carryHandler)
local dropRemote = newRemote("EVTRequestToDrop", "RemoteEvent", dropHandler)
local sellRemote = newRemote("EVTSellAtStore", "RemoteEvent", nil)
local purchaseRemote = newRemote("FNCRequestStorePurchase", "RemoteFunction", nil)

local larry = newInst("Larry", "Folder")
adopt(larry, enterRemote)
adopt(larry, hitchRemote)
adopt(larry, unhitchRemote)
adopt(larry, spawnRemote)
adopt(larry, storeRemote)
adopt(larry, carryRemote)
adopt(larry, dropRemote)
adopt(larry, sellRemote)
adopt(larry, purchaseRemote)
local modules = newInst("Modules", "Folder")
adopt(modules, larry)
local rs = newInst("ReplicatedStorage", "ReplicatedStorage")
adopt(rs, modules)
game = { GetService = function(_, name) return rs end }

-- equipment folder (equipmentFolder() is a global here; an upvalue in the real file)
local equipFolder = newInst("Equipment", "Folder")
local kadl = adopt(equipFolder, newInst("KADL", "Model"))
kadl:SetAttribute("InStorage", true)
local zm80 = adopt(equipFolder, newInst("ZM80", "Model"))
-- the planter the live game has: a MODEL name with no space, while the card
-- and the HUD both draw "Tempo L16". The call path used to look the model up
-- with FindFirstChild(vehicleName) only, so a name that arrives spaced (the
-- label, not the model) silently missed and the whole action fell to the UI.
local tempo = adopt(equipFolder, newInst("TempoL16", "Model"))
tempo:SetAttribute("InStorage", true)
function equipmentFolder() return equipFolder end
function lastLog() return logs[#logs] or "" end

-- tool hitch parts (captured paths)
local tcomps = adopt(zm80, newInst("Components", "Folder"))
local tractorHitch = adopt(tcomps, newInst("Hitchable", "Attachment"))
local kchassis = adopt(kadl, newInst("Chassis", "Model"))
local toolSocket = adopt(kchassis, newInst("HitchableSocket", "Attachment"))

carryingFlag = false
function carrying() return carryingFlag end

local function resetState()
    spudEquipRemoteState.kit = nil
    spudEquipRemoteState.fails = {}
    spudEquipRemoteState.off = {}
    carryingFlag = false
    hum.SeatPart = nil
    kadl:SetAttribute("InStorage", true)
    kadl.pivot = v(0, 0, 0)
    mode.enter, mode.store, mode.spawn, mode.carry, mode.drop = "ok", "ok", "ok", "ok", "ok"
end
"""

POST = r"""
local fails = 0
local function check(name, ok, detail)
    if not ok then fails = fails + 1 end
    print(string.format("%-58s %s%s", name, ok and "PASS" or "FAIL",
        detail and ("  " .. detail) or ""))
end

resetState()

-- 1. the kit resolves the captured names on the captured path
local kit = spudEquipRemoteKit()
check("all seven equipment remotes resolve",
    kit and kit.enter and kit.hitch and kit.unhitch and kit.spawn
        and kit.store and kit.carry and kit.drop)
check("the field and equipment kits are independent",
    kit.enter.remote == enterRemote and kit.carry.remote == carryRemote)

-- 2. store: the call itself is FNCStoreEquipment(model)
kadl:SetAttribute("InStorage", false)
local s0 = storeRemote.invokeCalls
local done = spudEquipRemoteAct("KADL", "Store")
check("store fires FNCStoreEquipment with the model",
    storeRemote.invokeCalls - s0 == 1
        and storeRemote.lastArgs[1] == kadl)
check("store is confirmed by InStorage turning true", done == true
    and kadl:GetAttribute("InStorage") == true)

-- 3. spawn: InStorage flips false
resetState()
local p0 = spawnRemote.invokeCalls
done = spudEquipRemoteAct("KADL", "Spawn")
check("spawn fires FNCSpawnEquipment with the model",
    spawnRemote.invokeCalls - p0 == 1
        and spawnRemote.lastArgs[1] == kadl)
check("spawn is confirmed by InStorage turning false", done == true
    and kadl:GetAttribute("InStorage") == false)

-- 4. a spawn that rebuilds the model is confirmed by the move
resetState()
kadl:SetAttribute("InStorage", true)
mode.spawn = "move"
done = spudEquipRemoteAct("KADL", "Spawn")
check("a >100-stud move confirms a rebuilt spawn", done == true,
    string.format("done=%s stored=%s x=%s fails=%s", tostring(done),
        tostring(kadl:GetAttribute("InStorage")),
        tostring(kadl.pivot and kadl.pivot.X), tostring(spudEquipRemoteState.fails.spawn)))

-- 5. an ignored store falls back (false) and counts a miss
resetState()
kadl:SetAttribute("InStorage", false)
mode.store = "none"
done = spudEquipRemoteAct("KADL", "Store")
check("an ignored store returns false (the UI runs)",
    done == false and spudEquipRemoteState.fails.store == 1)

-- 6. three misses switch that action off for the session
resetState()
spudEquipRemoteMiss("hitch")
spudEquipRemoteMiss("hitch")
spudEquipRemoteMiss("hitch")
check("three misses switch the action off", spudEquipRemoteState.off.hitch == true)
local h0 = hitchRemote.invokeCalls
check("a switched-off action fires nothing",
    spudEquipRemoteCall("hitch", tractorHitch, toolSocket) == false
        and hitchRemote.invokeCalls == h0)

-- 7. enter: proven by the seat
resetState()
local seat = adopt(zm80, newInst("DriveSeat", "VehicleSeat"))
local e0 = enterRemote.invokeCalls
check("enter fires FNCEnterEquipment(vehicle, seat) and proves the seat",
    spudEnterRemote(zm80, seat) == true
        and enterRemote.invokeCalls - e0 == 1
        and enterRemote.lastArgs[1] == zm80
        and enterRemote.lastArgs[2] == seat)

-- 8. a refused enter reports false and counts a miss
resetState()
mode.enter = "none"
check("a refused enter returns false and counts a miss",
    spudEnterRemote(zm80, seat) == false
        and spudEquipRemoteState.fails.enter == 1)

-- 9. hitch parts: the captured pair, or nil
resetState()
local th, is = spudHitchParts(zm80, kadl)
check("hitch parts are Components.Hitchable + Chassis.HitchableSocket",
    th == tractorHitch and is == toolSocket)

local noParts = newInst("Trailer", "Model")
check("a tool without the captured parts returns nil",
    spudHitchParts(zm80, noParts) == nil)

local hi0 = hitchRemote.invokeCalls
check("hitch fires FNCAttemptHitch(hitchable, socket)",
    spudHitchRemote(zm80, kadl) == true
        and hitchRemote.invokeCalls - hi0 == 1
        and hitchRemote.lastArgs[1] == tractorHitch
        and hitchRemote.lastArgs[2] == toolSocket)

-- 10. unhitch: FNCUnhitch(hitchable)
local u0 = unhitchRemote.invokeCalls
check("unhitch fires FNCUnhitch(hitchable)",
    spudUnhitchRemote(zm80) == true
        and unhitchRemote.invokeCalls - u0 == 1
        and unhitchRemote.lastArgs[1] == tractorHitch)
check("a vehicle without a hitchable reports false",
    spudUnhitchRemote(noParts) == false)

-- 11. carry: EVTRequestToCarry(draggable), proven by carrying()
resetState()
local c0 = carryRemote.fireCalls
check("carry fires EVTRequestToCarry(crate) and proves the hands",
    spudCarryRemote(kadl) == true
        and carryRemote.fireCalls - c0 == 1
        and carryRemote.lastArgs[1] == kadl)

resetState()
mode.carry = "none"
check("a refused carry returns false and counts a miss",
    spudCarryRemote(kadl) == false
        and spudEquipRemoteState.fails.carry == 1)

-- 12. drop: EVTRequestToDrop() with no arguments, proven by empty hands
resetState()
carryingFlag = true
local d0 = dropRemote.fireCalls
check("drop fires EVTRequestToDrop() with no arguments",
    spudDropRemote() == true and dropRemote.fireCalls - d0 == 1
        and dropRemote.lastArgs.n == 0)

resetState()
carryingFlag = true
mode.drop = "none"
check("a refused drop returns false and counts a miss",
    spudDropRemote() == false and spudEquipRemoteState.fails.drop == 1)

-- 13. sell: EVTSellAtStore(ride, padPart)
resetState()
local pad = newInst("DropOff", "Part")
local sl0 = sellRemote.fireCalls
check("sell fires EVTSellAtStore(ride, pad)",
    spudSellRemote(zm80, pad) == true
        and sellRemote.fireCalls - sl0 == 1
        and sellRemote.lastArgs[1] == zm80
        and sellRemote.lastArgs[2] == pad)
check("sell without a pad fires nothing", spudSellRemote(zm80, nil) == false)

-- 14. buy: FNCRequestStorePurchase({crate})
local pu0 = purchaseRemote.invokeCalls
check("purchase fires FNCRequestStorePurchase({crate})",
    spudPurchaseRemote(kadl) == true
        and purchaseRemote.invokeCalls - pu0 == 1
        and type(purchaseRemote.lastArgs[1]) == "table"
        and purchaseRemote.lastArgs[1][1] == kadl)
check("purchase without a crate fires nothing", spudPurchaseRemote(nil) == false)

-- 15. the kit goes away with the module folder
resetState()
larry.Name = "LarryX"
check("no Modules.Larry -> no equipment kit", spudEquipRemoteKit() == nil)

-- 16. every fall-through says WHICH half broke (v1.135: three of these
--     paths returned false in silence, so the console could not tell the
--     remote path, the absent machine and the switched-off call apart)
kadl:SetAttribute("InStorage", true)
done = spudEquipRemoteAct("KADL", "Spawn")
check("no kit -> the spawn names the remote this build has not got",
    done == false and lastLog():find("remote is not in this build") ~= nil,
    lastLog())
larry.Name = "Larry"

resetState()
done = spudEquipRemoteAct("NoSuchMachine", "Spawn")
check("a machine that is not in the folder is named, not guessed",
    done == false and lastLog():find("no NoSuchMachine model") ~= nil
        and lastLog():find("Equipment Manager") ~= nil, lastLog())

-- 17. the folder is searched by the game's FOLDED name: the pass holds the
--     label the card draws ("Tempo L16"), the model is named without a space
resetState()
tempo:SetAttribute("InStorage", true)
local te0 = spawnRemote.invokeCalls
done = spudEquipRemoteAct("Tempo L16", "Spawn")
check("a spaced label finds the model named without spaces",
    spawnRemote.invokeCalls - te0 == 1 and spawnRemote.lastArgs[1] == tempo
        and done == true, lastLog())

resetState()
tempo:SetAttribute("InStorage", false)
te0 = storeRemote.invokeCalls
done = spudEquipRemoteAct("Tempo  L16", "Store")
check("the fold survives extra spacing and punctuation",
    storeRemote.invokeCalls - te0 == 1 and storeRemote.lastArgs[1] == tempo
        and done == true, lastLog())

-- 18. a machine already in the state asked for is not called for, and says why
resetState()
kadl:SetAttribute("InStorage", true)
local st0 = storeRemote.invokeCalls
done = spudEquipRemoteAct("KADL", "Store")
check("already stored is named, and fires no store call",
    done == false and storeRemote.invokeCalls == st0
        and lastLog():find("already reads InStorage=true") ~= nil, lastLog())

-- 19. a call switched off for the session is named as that, not as a refusal
resetState()
kadl:SetAttribute("InStorage", true)
spudEquipRemoteState.off.spawn = true
local sp0 = spawnRemote.invokeCalls
done = spudEquipRemoteAct("KADL", "Spawn")
check("a session-switched call says it is switched off",
    done == false and spawnRemote.invokeCalls == sp0
        and lastLog():find("switched off this session") ~= nil, lastLog())

print(fails == 0 and "ALL OK" or (fails .. " FAILED"))
if fails > 0 then error("equipment remote checks failed") end
"""


def extract(text: str, name: str) -> str:
    m = re.search(r"^    (?:local )?function " + name + r"\(", text, re.M)
    if not m:
        return ""
    tail = text[m.start():]
    end = re.search(r"\n    (?:local function |function |-- )", tail[10:])
    block = tail[: end.start() + 10] if end else tail
    return "\n".join(l[4:] if l.startswith("    ") else l for l in block.splitlines())


def block(text: str, name: str) -> str:
    """A function's source with its indentation kept, for the tie checks —
    managerAction is a nested local the harness cannot run, so its wiring is
    read instead."""
    m = re.search(r"^( +)(?:local )?function " + name + r"\(", text, re.M)
    if not m:
        return ""
    indent = m.group(1)
    body = text[m.end():]
    nxt = re.search(r"\n" + indent + r"(?:local )?function \w+\(", body)
    return text[m.start(): m.end() + (nxt.start() + 1 if nxt else len(body))]


def main() -> int:
    base = pathlib.Path(os.environ.get("LOCALAPPDATA", ".")) / "Temp" / "opencode" / "luau"
    exe = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else base / "luau.exe"
    src = SRC.read_text(encoding="utf-8")
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

    # ▸ the wiring the sliced functions cannot show: the Equipment Manager is a
    #   nested local, and a fall-through that stopped logging is invisible here
    ties = []

    def tie(name, ok, detail=""):
        ties.append((name, bool(ok), detail))

    manager = block(src, "managerAction")
    tie("a missed card asks the game's own All tab",
        'spudNameKey(t.Name) == "all"' in manager
        and "clickEffect(allTab" in manager)
    tie("the tab is clicked, never mouse-operated",
        "Mouse" not in manager and 'IsA("GuiButton")' in manager)
    tie("a build with no All tab says so instead of silently failing",
        "no All tab in this build" in manager)
    tie("the tab rescue runs BEFORE the card is declared absent",
        0 < manager.find('if allTab then')
        < manager.find('log("equipment manager: no card for ') if manager else False)
    tie("the tab rescue is reached only from a miss",
        manager.count("if not card then") >= 2)

    act = extract(src, "spudEquipRemoteAct")
    tie("the call path folds the model name too",
        "spudNameKey(m.Name) == nKey" in act)
    tie("a machine it cannot find is named with what the folder read",
        "#folder:GetChildren()" in act and "no %s model in Objects.Equipment" in act)
    tie("a machine already in that state is named, not called for",
        "already reads InStorage=%s" in act)
    tie("a dead call names WHICH half is dead",
        "switched off this session after 3 ignored calls" in act
        and "the remote is not in this build" in act
        and "the call threw" in act)

    for name, ok, detail in ties:
        print("%-58s %s%s" % (name, ok and "PASS" or "FAIL", ("  " + detail) if detail else ""))
    bad = [n for n, ok, _ in ties if not ok]
    if bad:
        print("%d FAILED" % len(bad))
        return 1
    print("ALL OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
