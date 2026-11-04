"""Field work through the game's own remotes (captured 2026-10-30).

SpudRemoteProbe caught the game firing, while cultivating by hand:

    EVTCultivateFieldCell:FireServer(field, {cellId}, {raycastAttachment})
    FNCFillSeeder:InvokeServer(seeder)

`cellId` is the FieldHelper.GetCells key (x*128+y), and the attachment is the
hitched tool's own RaycastPart attachment. The plow/seed/harvest calls are the
sibling remotes on the same path, so `spudFieldRemotePass` fires one call per
remaining cell id, re-reads the stages, and reports what the server took:

  * every cell took the call  -> true, 0   (the sweep is not driven)
  * some took it              -> true, n   (drive the rest)
  * none took it / unreadable -> false, n  (drive; the job's fast path is off)

Nothing is trusted: the stage re-read is the proof, and the drive-over sweep
stays the fallback. `spudFillSeederRemote` is only counted as a fill once the
seeder's own seed count rises (checked by the caller, which keeps V).

    python tools/field_remote_test.py [path-to-luau.exe]
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
    "cellsAtStage",
    "spudRadialFire",
    "spudHopCells",
    "spudFieldRemoteKit",
    "spudFieldCellIds",
    "spudToolAttachment",
    "spudFieldRemoteCall",
    "spudFieldRemoteCallMany",
    "spudFieldRemotePass",
    "spudFillSeederRemote",
    "spudHarvestFull",
    "spudToolTrail",
    "spudWaitTool",
    "spudPivotRig",
    "spudToolExtraTiles",
    "spudBlockSide",
]

PRE = r"""
-- ▸ fake instancing: only what the helpers touch (Name/Parent/IsA/kids)
local function newInst(name, class)
    local o = { Name = name, ClassName = class, kids = {} }
    function o:IsA(c) return self.ClassName == c end
    function o:FindFirstChild(n)
        for _, k in ipairs(self.kids) do
            if k.Name == n then return k end
        end
        return nil
    end
    function o:GetDescendants()
        local out = {}
        local function walk(node)
            for _, k in ipairs(node.kids) do
                out[#out + 1] = k
                walk(k)
            end
        end
        walk(self)
        return out
    end
    return o
end
local function adopt(parent, kid)
    parent.kids[#parent.kids + 1] = kid
    kid.Parent = parent
    return kid
end

local logs = {}
function log(msg) logs[#logs + 1] = tostring(msg) end
function loggedText() return table.concat(logs, "|") end
function stopping() return false end
task = task or {}
task.wait = function(_) end
function require(x) return x end

grownStage = function(s) return s == "Grown" end
spudFieldRemoteState = { kit = nil, off = {} }
spudFieldReach = 24
-- the strict "this reading actually took" band the BURST BLOCK is sized against:
-- 20 is the widest sideways distance the live server ever accepted (30 refused)
spudFieldTaken = 20
-- the game's cell pitch: the block grouping measures its spans in this, and
-- spudBlockSide sizes the square with it
spudFieldPitch = 10
-- the beat the grid takes between two blocks, in MILLISECONDS (the owner's
-- 2026-11-04 number: "make it wait 100ms after before going to the next 3x3")
spudBlockPause = 100
-- the tow-settle gate's own numbers (a stubbed blade moves with the ride, so
-- every hop reads as already settled and the existing counts stay valid)
spudToolSwing = 3
spudToolFar = 90

-- ▸ vectors/CFrames for the hop fixtures (cellsAtStage + spudHopCells)
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
Vector3 = { new = function(x, y, z)
    return setmetatable({ X = x or 0, Y = y or 0, Z = z or 0 }, V)
end }
local CF = {}
-- the build reads a pose as `.Position`; this stub stores it as `.pos`, so the
-- key is served on demand (metamethods are looked up on the table itself, so
-- redefining __index this way does not hide __mul/__sub)
CF.__index = function(t, k)
    if k == "Position" then return t.pos end
    return rawget(CF, k)
end
CF.__mul = function(a, b)
    if a.base then return { Position = a.Position + (b.pos or b.Position) } end
    return a
end
CF.__sub = function(a, b) return { rot = true } end
CFrame = { new = function(x, y, z)
    if type(x) == "table" then return setmetatable({ pos = x }, CF) end
    return setmetatable({ pos = Vector3.new(x or 0, y or 0, z or 0) }, CF)
end }
function cellPosOf(id)
    local x, y = math.floor(id / 128), id % 128
    return Vector3.new((x - 3) * 10, 0, (y - 2) * 10) -- the fixture's rows = 3 (643 is Seeded)
end
ATTPARENT = nil
RIDE_POS = Vector3.new(0, 0, 0)

local fieldState = {}
local fieldHelper = newInst("FieldHelper", "ModuleScript")
function fieldHelper.GetCells(field) return fieldState[field] or {} end

local function newRemote(name, class, handler)
    local o = newInst(name, class)
    o.fireCalls, o.invokeCalls = 0, 0
    local function remember(...)
        local a = table.pack(...)
        o.lastArg, o.lastField = a[1], a[1]
        o.lastAtt = type(a[3]) == "table" and a[3][1] or a[3]
        if type(a[2]) == "table" then o.lastId = a[2][#a[2]] end
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

local mode = { seed = "all", fill = "ok" }
local acceptR = 2 -- how close the blade must be for the server to take a cell
local tries = {}
spudBatchRemotes = false

local function seedHandler(field, ids)
    if mode.seed == "none" then return end
    -- a server that validates ONE id per call ignores a longer list
    if mode.seed == "oneOnly" and #ids ~= 1 then return end
    local cells = fieldState[field]
    for _, id in ipairs(ids) do
        local cell = cells and cells[id]
        if cell and cell.Stage == "Cultivated" then
            local take
            if mode.seed == "retryOnce" then
                tries[id] = (tries[id] or 0) + 1
                take = tries[id] >= 2
            elseif mode.seed == "all" or mode.seed == "oneOnly" then
                take = true
            elseif mode.seed == "first" then
                take = (id == 641)
            elseif mode.seed == "firstBatch" then
                -- takes the first id of a list, but any single-id call
                take = (id == 641) or (#ids == 1)
            end
            if take and mode.atCell then
                -- the live rule: only a cell the blade is over is accepted
                local p = ATTPARENT and ATTPARENT.Position
                if not (p and (p - cellPosOf(id)).Magnitude <= acceptR) then take = false end
            end
            if take then cell.Stage = "Seeded" end
        end
    end
end
local function harvestHandler(field, ids)
    local cells = fieldState[field]
    for _, id in ipairs(ids) do
        local cell = cells and cells[id]
        if cell and cell.Stage == "Grown" then cell.Stage = "Empty" end
    end
end
local function fillHandler()
    if mode.fill == "no" then return false end
    return true
end

local function cultHandler(field, ids)
    local cells = fieldState[field]
    for _, id in ipairs(ids) do
        local cell = cells and cells[id]
        if cell and cell.Stage == "Cultivated" then
            local p = ATTPARENT and ATTPARENT.Position
            if not mode.atCell or (p and (p - cellPosOf(id)).Magnitude <= acceptR) then
                cell.Stage = "Seeded"
            end
        end
    end
end

local seedRemote = newRemote("FNCSeedFieldCell", "RemoteFunction", seedHandler)
local cultRemote = newRemote("EVTCultivateFieldCell", "RemoteEvent", cultHandler)
local plowRemote = newRemote("EVTPlowFieldCell", "RemoteEvent", nil)
local harvestRemote = newRemote("FNCHarvestFieldCell", "RemoteFunction", harvestHandler)
local fillRemote = newRemote("FNCFillSeeder", "RemoteFunction", fillHandler)

local larry = newInst("Larry", "Folder")
adopt(larry, seedRemote)
adopt(larry, cultRemote)
adopt(larry, plowRemote)
adopt(larry, harvestRemote)
adopt(larry, fillRemote)
local modules = newInst("Modules", "Folder")
adopt(modules, larry)
adopt(modules, fieldHelper)
local rs = newInst("ReplicatedStorage", "ReplicatedStorage")
adopt(rs, modules)
game = { GetService = function(_, name) return rs end }

local field = newInst("Field", "Model")
local function resetCells()
    tries = {}
    fieldState[field] = {
        [641] = { Stage = "Cultivated" },
        [642] = { Stage = "Cultivated" },
        [643] = { Stage = "Seeded" },
        ["odd"] = { Stage = "Cultivated" },
    }
end
resetCells()

local tool = newInst("KADL", "Model")
local comps = adopt(tool, newInst("Components", "Folder"))
local impl = adopt(comps, newInst("Seeder", "Model"))
local att = adopt(adopt(impl, newInst("RaycastPart", "Part")), newInst("Attachment", "Attachment"))

-- ▸ THE IMPLEMENT IS ITS OWN MODEL, and a ride teleport does not move it (that
--   is the live defect: `arc hop: 286 studs` then `hitch gap at arrival: 277.7
--   studs`). The old stub dragged ATTPARENT along with the ride, which is
--   exactly why no harness ever saw it. So the tool gets a real pivot, and every
--   carry the build performs lands here — CARRIED counts them.
CARRIED = 0
-- a hitch is a CONSTRAINT, not a parent. After a jump the implement settles at
-- the ride's own rest offset — NOT the commanded point — so a park aimed from a
-- stale reading leaves the blade off the block. TRAIL_REST models that offset
-- (section 17), and TRAIL_STUCK an implement caught on something, for which a
-- park command changes nothing at all.
TRAIL_REST = nil
TRAIL_STUCK = false
RIDE_JAMMED = false
function tool:GetPivot()
    if not ATTPARENT then return nil end
    return setmetatable({ pos = ATTPARENT.Position }, CF)
end
function tool:PivotTo(cf)
    CARRIED = CARRIED + 1
    if not ATTPARENT or TRAIL_STUCK then return end
    if TRAIL_REST then
        ATTPARENT.Position = RIDE_POS + TRAIL_REST
    else
        ATTPARENT.Position = cf.pos
    end
end

local decoyTool = newInst("S4204", "Model")
adopt(adopt(decoyTool, newInst("Misc", "Part")), newInst("Attachment", "Attachment"))

local noAttTool = newInst("Empty", "Model")

local function resetState()
    spudFieldRemoteState.kit = nil
    spudFieldRemoteState.off = {}
end
"""

POST = r"""
local fails = 0
local function check(name, ok, detail)
    if not ok then fails = fails + 1 end
    print(string.format("%-58s %s%s", name, ok and "PASS" or "FAIL",
        detail and ("  " .. detail) or ""))
end

-- 1. cell ids come from the game's own dict, keyed x*128+y
local ids = spudFieldCellIds(field, "Cultivated")
check("ids for a stage are sorted and numeric-only",
    ids and #ids == 2 and ids[1] == 641 and ids[2] == 642,
    ids and table.concat(ids, ",") or "nil")
check("a stage with no cells returns an empty list",
    spudFieldCellIds(field, "Plowed") and #spudFieldCellIds(field, "Plowed") == 0)
check("a stage predicate is accepted",
    spudFieldCellIds(field, function(s) return s == "Seeded" end)[1] == 643)

local realGet = fieldHelper.GetCells
fieldHelper.GetCells = function() return nil end
check("a failed cell read stays unknown (nil), not empty",
    spudFieldCellIds(field, "Cultivated") == nil)
fieldHelper.GetCells = realGet

-- 2. the attachment the game sends is the tool's raycast one
check("the RaycastPart attachment is chosen", spudToolAttachment(tool) == att)
-- ▸ THE HARVESTER HAS NO RAYCAST PART: any attachment on the machine is used
--   rather than switching the whole remote pass off (which harvested nothing)
check("a tool with only a plain attachment still gives one (the harvester)",
    spudToolAttachment(decoyTool) ~= nil)
-- a harvest-sounding part outranks a plain one and "any" (live 2026-10-31: the
-- SRC6 sent EquipmentRoot.L0StrutAttachment and every call was refused)
local headTool = newInst("SRC6", "Model")
local headPart = adopt(headTool, newInst("HarvestHead", "Part"))
local headAtt = adopt(headPart, newInst("Attachment", "Attachment"))
local strut = adopt(adopt(headTool, newInst("EquipmentRoot", "Part")), newInst("Bolt", "Attachment"))
check("a HarvestHead point outranks a strut",
    spudToolAttachment(headTool) == headAtt,
    strut and tostring(strut.Name) or nil)
check("a tool with no attachment at all returns nil",
    spudToolAttachment(noAttTool) == nil)
check("nil tool -> nil", spudToolAttachment(nil) == nil)

local seedJob = { verb = "seed", stage = "Cultivated",
    remote = "FNCSeedFieldCell", prog = "seeding" }

-- 3. a full batch: one call per id with (field, {id}, {attachment})
resetCells()
resetState()
local before = seedRemote.invokeCalls
local done, left = spudFieldRemotePass(seedJob, field, tool)
check("full batch is reported done", done == true and left == 0,
    tostring(done) .. "," .. tostring(left))
check("one call per addressable cell", seedRemote.invokeCalls - before == 2,
    tostring(seedRemote.invokeCalls - before))
check("the call carries the field, the id list and the attachment",
    seedRemote.lastField == field and seedRemote.lastId == 642
        and seedRemote.lastAtt == att,
    string.format("field=%s id=%s att=%s",
        tostring(seedRemote.lastField == field), tostring(seedRemote.lastId),
        tostring(seedRemote.lastAtt == att)))

-- 4. a partial batch keeps the fast path on and hands back the remainder
resetCells()
resetState()
mode.seed = "first"
done, left = spudFieldRemotePass(seedJob, field, tool)
check("partial batch -> done with cells left", done == true and left == 1,
    tostring(done) .. "," .. tostring(left))
check("partial batch does not disable the job", spudFieldRemoteState.off.seed ~= true)

-- 5. an ignored batch drives instead and switches the job off for the session
resetCells()
resetState()
mode.seed = "none"
done, left = spudFieldRemotePass(seedJob, field, tool)
check("ignored batch -> false with every cell left", done == false and left == 2,
    tostring(done) .. "," .. tostring(left))
check("ignored batch switches the job off", spudFieldRemoteState.off.seed == true)
local calls = seedRemote.invokeCalls
spudFieldRemotePass(seedJob, field, tool)
check("a job switched off fires nothing", seedRemote.invokeCalls == calls)

-- 6. TESTS · batch field remote (off by default): one call with every id
spudBatchRemotes = true
resetCells()
resetState()
mode.seed = "all"
local b0 = seedRemote.invokeCalls
done, left = spudFieldRemotePass(seedJob, field, tool)
check("batch test: one call finishes the field", done == true and left == 0,
    tostring(done) .. "," .. tostring(left))
check("batch test: exactly one call was made", seedRemote.invokeCalls - b0 == 1,
    tostring(seedRemote.invokeCalls - b0))
check("batch test: the call carries every id",
    seedRemote.lastId == 642 and seedRemote.lastAtt == att)
check("batch test: it says the whole field took the list",
    loggedText():find("✅ batch test") ~= nil)

resetCells()
resetState()
mode.seed = "firstBatch"
b0 = seedRemote.invokeCalls
done, left = spudFieldRemotePass(seedJob, field, tool)
check("batch test: a partial list still finishes the field",
    done == true and left == 0, tostring(done) .. "," .. tostring(left))
check("batch test: the rest go one call per cell", seedRemote.invokeCalls - b0 == 2,
    tostring(seedRemote.invokeCalls - b0))
check("batch test: the log names the partial take",
    loggedText():find("took the id list") ~= nil)

resetCells()
resetState()
mode.seed = "oneOnly"
b0 = seedRemote.invokeCalls
done, left = spudFieldRemotePass(seedJob, field, tool)
check("batch test: an ignored list falls back to per-cell",
    done == true and left == 0, tostring(done) .. "," .. tostring(left))
check("batch test: an ignored list never switches the job off",
    spudFieldRemoteState.off.seed ~= true)
check("batch test: the log names the ignored list",
    loggedText():find("ignored the id list") ~= nil)
spudBatchRemotes = false

-- 7. no attachment / no remote -> no calls, drive instead
resetCells()
resetState()
mode.seed = "all"
calls = seedRemote.invokeCalls
done, left = spudFieldRemotePass(seedJob, field, noAttTool)
check("no attachment -> drive, no calls",
    done == false and seedRemote.invokeCalls == calls)
check("no attachment switches the job off", spudFieldRemoteState.off.seed == true)

resetCells()
resetState()
seedRemote.Name = "hidden"
done, left = spudFieldRemotePass(seedJob, field, tool)
check("missing remote -> drive, no calls",
    done == false and spudFieldRemoteState.off.seed == true)
seedRemote.Name = "FNCSeedFieldCell"

-- 6b. a seeder only fires as many calls as it holds seeds
local capConf = adopt(tool, newInst("Configurations", "Folder"))
local capVal = adopt(capConf, newInst("Capacity", "IntValue"))
capVal.Value = 0
resetCells()
resetState()
mode.seed = "all"
local d0 = seedRemote.invokeCalls
local dry
done, left, dry = spudFieldRemotePass(seedJob, field, tool)
check("empty seeder: not one seed call is fired", seedRemote.invokeCalls == d0,
    (seedRemote.invokeCalls - d0) .. " call(s)")
check("empty seeder: the pass hands the field back (dry)",
    done == true and left == 2 and dry == true,
    string.format("%s,%s,%s", tostring(done), tostring(left), tostring(dry)))
check("empty seeder: the job stays on", spudFieldRemoteState.off.seed ~= true)
capVal.Value = 1
resetCells()
resetState()
d0 = seedRemote.invokeCalls
done, left, dry = spudFieldRemotePass(seedJob, field, tool)
-- a budget smaller than the field is spent by the BLOCKS, not at the corner
-- (live 2026-10-31: 28 seeds against 46 cells all fired out of reach)
check("one seed against two cells: the corner fires nothing",
    seedRemote.invokeCalls == d0,
    (seedRemote.invokeCalls - d0) .. " call(s)")
check("one seed against two cells: handed to the blocks, not dry",
    done == true and left == 2 and dry ~= true,
    string.format("%s,%s", tostring(left), tostring(dry)))
fieldState[field][642].Stage = "Plowed"
fieldState[field][643].Stage = "Plowed"
done, left, dry = spudFieldRemotePass(seedJob, field, tool)
check("one seed against one cell: exactly one call",
    seedRemote.invokeCalls - d0 == 1,
    (seedRemote.invokeCalls - d0) .. " call(s)")
fieldState[field][642].Stage = "Cultivated"
fieldState[field][643].Stage = "Seeded"
capVal.Value = 50
resetCells()
resetState()
d0 = seedRemote.invokeCalls
done, left, dry = spudFieldRemotePass(seedJob, field, tool)
check("a full seeder: the whole field in one pass",
    done == true and left == 0 and not dry and seedRemote.invokeCalls - d0 == 2,
    string.format("%s,%s", tostring(done), tostring(left)))

-- 8. the harvest sibling is a RemoteFunction on the grown predicate
resetCells()
fieldState[field][700] = { Stage = "Grown" }
resetState()
local hv0 = harvestRemote.invokeCalls
local hf0 = harvestRemote.fireCalls
local harvestJob = { verb = "harvest", grown = true,
    remote = "FNCHarvestFieldCell", prog = "harvesting" }
done, left = spudFieldRemotePass(harvestJob, field, tool)
check("harvest uses InvokeServer, not FireServer",
    harvestRemote.invokeCalls - hv0 == 1 and harvestRemote.fireCalls == hf0,
    tostring(harvestRemote.invokeCalls - hv0))
check("harvest batch reports done", done == true and left == 0,
    tostring(done) .. "," .. tostring(left))

-- 8b. a harvester only takes what its tank has room for, and the tail is
--     retried once before a single row is driven
local maxVal = adopt(capConf, newInst("MaxCapacity", "IntValue"))
capVal.Value = 49
maxVal.Value = 50
fieldState[field][701] = { Stage = "Grown" }
resetCells()
fieldState[field][700] = { Stage = "Grown" }
fieldState[field][701] = { Stage = "Grown" }
resetState()
hv0 = harvestRemote.invokeCalls
capVal.Value = 50 -- tank full
done, left, dry = spudFieldRemotePass(harvestJob, field, tool)
check("full tank: no harvest call is fired", harvestRemote.invokeCalls == hv0,
    (harvestRemote.invokeCalls - hv0) .. " call(s)")
check("full tank: the pass hands the field back (dry)",
    done == true and left == 2 and dry == true,
    string.format("%s,%s,%s", tostring(done), tostring(left), tostring(dry)))
capVal.Value = 49 -- room for one, two cells standing: the sell runs first
resetCells()
fieldState[field][700] = { Stage = "Grown" }
fieldState[field][701] = { Stage = "Grown" }
resetState()
hv0 = harvestRemote.invokeCalls
done, left, dry = spudFieldRemotePass(harvestJob, field, tool)
check("one slot against two cells: no call is fired",
    harvestRemote.invokeCalls == hv0,
    (harvestRemote.invokeCalls - hv0) .. " call(s)")
check("one slot against two cells: dry with both standing",
    done == true and left == 2 and dry == true,
    string.format("%s,%s,%s", tostring(done), tostring(left), tostring(dry)))
capVal.Value = 49 -- one slot against one cell: the slot is used
resetCells()
fieldState[field][700] = { Stage = "Grown" }
resetState()
hv0 = harvestRemote.invokeCalls
done, left, dry = spudFieldRemotePass(harvestJob, field, tool)
check("one slot against one cell: exactly one harvest call",
    harvestRemote.invokeCalls - hv0 == 1,
    (harvestRemote.invokeCalls - hv0) .. " call(s)")
check("one slot against one cell: the field is finished",
    done == true and left == 0 and dry ~= true,
    string.format("%s,%s", tostring(left), tostring(dry)))

-- 8c. a refused tail is retried once, and a full seeder still needs no rows
capVal.Value = 50
maxVal.Value = 50
resetCells()
resetState()
mode.seed = "retryOnce"
d0 = seedRemote.invokeCalls
done, left, dry = spudFieldRemotePass(seedJob, field, tool)
check("retry: the refused tail is fired again", seedRemote.invokeCalls - d0 == 4,
    (seedRemote.invokeCalls - d0) .. " call(s)")
check("retry: the field finishes with no row",
    done == true and left == 0 and not dry,
    string.format("%s,%s", tostring(done), tostring(left)))
check("retry: the log says the retry finished it",
    loggedText():find("the retry finished the field") ~= nil)
mode.seed = "all"

-- 9. FillSeeder: fired with the seeder, refusal falls back to V
resetState()
mode.fill = "ok"
local f0 = fillRemote.invokeCalls
check("FillSeeder fires with the seeder model",
    spudFillSeederRemote(tool) == true and fillRemote.invokeCalls - f0 == 1
        and fillRemote.lastArg == tool)
check("FillSeeder with no seeder fires nothing",
    spudFillSeederRemote(nil) == false)
mode.fill = "no"
check("a refused FillSeeder reports false (V is the fallback)",
    spudFillSeederRemote(tool) == false)

-- 10. the kit goes away with the module folder
resetState()
larry.Name = "LarryX"
check("no Modules.Larry -> no kit", spudFieldRemoteKit() == nil)
larry.Name = "Larry"

-- 11. the ride is hopped onto each remaining cell so the blade is over it
local hopAttPart = newInst("RaycastPart", "Part")
hopAttPart.Position = Vector3.new(0, 0, -5)
local hopAtt = newInst("Attachment", "Attachment")
hopAtt.Parent = hopAttPart
ATTPARENT = hopAttPart
RIDE_POS = Vector3.new(0, 0, 0)
local hopRide = {}
local rides = 0
function hopRide:GetPivot() return setmetatable({ Position = RIDE_POS }, CF) end
-- a RIDE-ONLY teleport: the game moves the tractor and the hitched implement
-- stays on the ground behind it, so a pass that wants its blade has to carry it
function hopRide:PivotTo(cf)
    rides = rides + 1
    -- section 17: a rig that cannot move at all (the command is sent, the world
    -- does not obey) — the honest model of a blade that will not land
    if RIDE_JAMMED then return end
    RIDE_POS = cf.pos
end
local baseCF = setmetatable({ base = true, Position = Vector3.new(0, 0, 0) }, CF)
local baseSize = Vector3.new(50, 1, 20)
capVal.Value = 50
mode.seed = "all"
mode.atCell = true
resetCells()
resetState()
local h0 = seedRemote.invokeCalls
local tookHop, hopDry = spudHopCells(seedJob, field, hopRide, tool, "Cultivated",
    baseCF, baseSize, hopAtt)
check("hop: the blade is lined up on both cells", tookHop == 2, tostring(tookHop))
check("hop: one call per cell", seedRemote.invokeCalls - h0 == 2,
    (seedRemote.invokeCalls - h0) .. " call(s)")
check("hop: the field is done afterwards",
    #spudFieldCellIds(field, "Cultivated") == 0)
check("hop: a full seeder means not dry", hopDry == false, tostring(hopDry))

resetCells()
resetState()
capVal.Value = 1
local tookOne, dryOne = spudHopCells(seedJob, field, hopRide, tool, "Cultivated",
    baseCF, baseSize, hopAtt)
check("hop: one seed hops one cell and hands back",
    tookOne == 1 and dryOne == true,
    string.format("%s,%s", tostring(tookOne), tostring(dryOne)))
capVal.Value = 50
mode.atCell = false

-- 12. a field is covered by teleports only (the serpentine tween was
--     removed: every move in a field pass is a teleport)
local function sweepGrid()
    fieldState[field] = {}
    for x = 1, 5 do
        for y = 1, 3 do
            fieldState[field][x * 128 + y] = { Stage = "Cultivated" }
        end
    end
end

-- 13. STOP AND BURST: the remaining ids fired from a grid of parked blades —
--     the live band (20 studs to the side taken, 30 refused, +80 up taken)
--     means one stop reaches ~2 tiles, so a few stops cover a whole field
RIDE_POS = Vector3.new(80, 0, 80)
ATTPARENT.Position = RIDE_POS + Vector3.new(0, 0, -5)
acceptR = 60
mode.atCell = true
capVal.Value = 50
sweepGrid()
resetState()
local rj0 = rides
local cj0 = seedRemote.invokeCalls
local tookR, dryR = spudRadialFire(seedJob, field, hopRide, tool, "Cultivated",
    baseCF, baseSize, hopAtt)
check("radial: every cell takes from the stops", tookR == 15, tostring(tookR))
check("radial: one call per cell", seedRemote.invokeCalls - cj0 == 15,
    (seedRemote.invokeCalls - cj0) .. " call(s)")
check("radial: the field is empty afterwards",
    #spudFieldCellIds(field, "Cultivated") == 0)
check("radial: one teleport per stop, no tween", rides - rj0 == 2,
    (rides - rj0) .. " pivot(s)")
check("radial: a full seeder means not dry", dryR == false, tostring(dryR))
check("radial: the log says what it did",
    loggedText():find("from 2 stop") ~= nil
        and loggedText():find("3x3 per stop") ~= nil)

-- 13b. THE BEAT BETWEEN TWO BLOCKS (owner 2026-11-04: "when it's doing the 3x3
--      make it wait 100ms after before going to the next 3x3"). The nine calls
--      of a block leave the server mid-update and the next stop's teleport used
--      to land on top of that. Counted here as a DURATION, not a sleep: the
--      grid must wait spudBlockPause/1000 seconds once per block it moves on
--      from, and the LAST stop must not pay a beat for nothing.
RIDE_POS = Vector3.new(80, 0, 80)
ATTPARENT.Position = RIDE_POS + Vector3.new(0, 0, -5)
acceptR = 60
mode.atCell = true
capVal.Value = 50
sweepGrid()
resetState()
local beatDur = {}
local realBeat = task.wait
task.wait = function(s)
    beatDur[s] = (beatDur[s] or 0) + 1
    return nil
end
local tookBeat = spudRadialFire(seedJob, field, hopRide, tool, "Cultivated",
    baseCF, baseSize, hopAtt)
task.wait = realBeat
check("the beat is the owner's 100 ms, not a guessed sleep",
    beatDur[spudBlockPause / 1000] ~= nil,
    "waited for " .. tostring(spudBlockPause / 1000) .. "s "
        .. tostring(beatDur[spudBlockPause / 1000] or 0) .. " time(s)")
check("a 2-stop grid pays the beat ONCE — the last stop waits for nothing",
    beatDur[spudBlockPause / 1000] == 1,
    tostring(beatDur[spudBlockPause / 1000] or 0) .. " beat(s)")
check("the beat does not cost the field a cell", tookBeat == 15,
    tostring(tookBeat))

-- a seeder can only fire as many calls as it holds seeds
capVal.Value = 4
sweepGrid()
resetState()
cj0 = seedRemote.invokeCalls
local tookRB, dryRB = spudRadialFire(seedJob, field, hopRide, tool, "Cultivated",
    baseCF, baseSize, hopAtt)
check("radial: 4 seeds fire 4 calls", seedRemote.invokeCalls - cj0 == 4,
    (seedRemote.invokeCalls - cj0) .. " call(s)")
check("radial: the seeder runs dry", dryRB == true and tookRB == 4,
    string.format("%s,%s", tostring(tookRB), tostring(dryRB)))

-- a blade that reaches nothing takes nothing, and leaves every cell standing
acceptR = 5
capVal.Value = 50
sweepGrid()
resetState()
local tookRI, dryRI = spudRadialFire(seedJob, field, hopRide, tool, "Cultivated",
    baseCF, baseSize, hopAtt)
check("radial: a small reach takes nothing", tookRI == 0, tostring(tookRI))
check("radial: every cell is still standing",
    #spudFieldCellIds(field, "Cultivated") == 15)
check("radial: an ignored single-spot fire is not dry", dryRI == false, tostring(dryRI))

-- a long field needs more than one stop: 9x3 is covered by three, one call
-- per cell and no duplicates
acceptR = 200
capVal.Value = 50
fieldState[field] = {}
for x = 1, 9 do
    for y = 1, 3 do
        fieldState[field][x * 128 + y] = { Stage = "Cultivated" }
    end
end
resetState()
local rf0 = rides
cj0 = seedRemote.invokeCalls
local tookRF, dryRF = spudRadialFire(seedJob, field, hopRide, tool, "Cultivated",
    baseCF, baseSize, hopAtt)
check("radial: a long field is covered by several stops",
    tookRF == 27 and seedRemote.invokeCalls - cj0 == 27,
    (seedRemote.invokeCalls - cj0) .. " call(s), took " .. tostring(tookRF))
check("radial: the stops are teleports, not a tween", rides - rf0 == 3,
    (rides - rf0) .. " pivot(s)")
check("radial: the log says how many of how many",
    loggedText():find("fired 27 of 27 cell") ~= nil)
check("radial: the field is empty afterwards",
    #spudFieldCellIds(field, "Cultivated") == 0)

-- a server that takes nothing from a parked blade pays for ONE stop, then
-- hands the field to the sweep
acceptR = -1
fieldState[field] = {}
for x = 1, 9 do
    for y = 1, 3 do
        fieldState[field][x * 128 + y] = { Stage = "Cultivated" }
    end
end
resetState()
rf0 = rides
cj0 = seedRemote.invokeCalls
local tookRG, dryRG = spudRadialFire(seedJob, field, hopRide, tool, "Cultivated",
    baseCF, baseSize, hopAtt)
check("radial: an ignored grid stops after one stop", rides - rf0 == 1,
    (rides - rf0) .. " pivot(s)")
check("radial: an ignored grid retries that stop exactly once",
    seedRemote.invokeCalls - cj0 == 18,
    (seedRemote.invokeCalls - cj0) .. " call(s)")
check("radial: an ignored grid leaves every cell standing",
    tookRG == 0 and #spudFieldCellIds(field, "Cultivated") == 27,
    tostring(tookRG))
check("radial: an ignored grid is not dry", dryRG == false, tostring(dryRG))

-- ▸ THE FIRST-CALL ARTIFACT: the server still holds the old pose after the
--   long ride and refuses the first burst at every cell. The grid must settle
--   and fire that same stop once more instead of handing a healthy field to
--   the tween (that is what "it's still driving" was).
mode.seed = "retryOnce"
acceptR = 200
capVal.Value = 50
fieldState[field] = {}
for x = 1, 3 do
    fieldState[field][x * 128 + 1] = { Stage = "Cultivated" }
end
resetState()
tries = {}
rf0 = rides
cj0 = seedRemote.invokeCalls
local tookRY, dryRY = spudRadialFire(seedJob, field, hopRide, tool, "Cultivated",
    baseCF, baseSize, hopAtt)
check("radial: a first burst the server refuses is retried at the same stop",
    tookRY == 3 and rides - rf0 == 1,
    string.format("%d took, %d pivot(s)", tookRY, rides - rf0))
check("radial: the retry costs one more call per cell, never a third",
    seedRemote.invokeCalls - cj0 == 6,
    (seedRemote.invokeCalls - cj0) .. " call(s)")
check("radial: the field is empty after the retry",
    #spudFieldCellIds(field, "Cultivated") == 0)
check("radial: the retry is not dry", dryRY == false, tostring(dryRY))
mode.seed = "all"

-- 16. REACH: the corner pass spends no round trip on a cell the blade cannot
--     reach. Live 2026-11-02 (owner: "before every tool use on the field it
--     waits a bit like 10 seconds"): a 50-cell corner pass cost 11 s because
--     seed/harvest are InvokeServer and EVERY call waits for the server, yet
--     only 6 of those calls could land at all — the rest sit past the 2-tile
--     band, and the blocks fire them from a stop with the blade on them.
local function rowOfEight()
    fieldState[field] = {}
    for x = 1, 8 do
        fieldState[field][x * 128 + 1] = { Stage = "Cultivated" }
    end
end
local rCF = setmetatable({ base = true, Position = Vector3.new(0, 0, 0) }, CF)
local rSize = Vector3.new(80, 1, 10) -- 8 columns along X, so -35..35
mode.seed = "all"
mode.atCell = false
spudBatchRemotes = false
capVal.Value = 50

att.Position = Vector3.new(0, 170, 0)
rowOfEight()
resetState()
local logN = #logs
cj0 = seedRemote.invokeCalls
done, left, dry = spudFieldRemotePass(seedJob, field, tool, rCF, rSize)
local function justLogged()
    local out = {}
    for i = logN + 1, #logs do out[#out + 1] = logs[i] end
    return table.concat(out, "|")
end
check("reach: only the cells inside the band are called",
    seedRemote.invokeCalls - cj0 == 4, (seedRemote.invokeCalls - cj0) .. " call(s)")
check("reach: the far cells are handed to the blocks, not dropped",
    done == true and left == 4, tostring(done) .. "," .. tostring(left))
check("reach: a reach bail is not dry", dry ~= true, tostring(dry))
check("reach: the log says the blocks take the rest",
    justLogged():find("the blocks take the last 4") ~= nil)
check("reach: leftovers out of the band are not retried",
    justLogged():find("retry") == nil, justLogged())

att.Position = Vector3.new(200, 170, 0)
rowOfEight()
resetState()
cj0 = seedRemote.invokeCalls
done, left, dry = spudFieldRemotePass(seedJob, field, tool, rCF, rSize)
check("reach: nothing in reach fires no call at all",
    seedRemote.invokeCalls - cj0 == 0, (seedRemote.invokeCalls - cj0) .. " call(s)")
check("reach: the whole field still goes to the blocks",
    done == true and left == 8 and dry == false,
    string.format("%s,%s,%s", tostring(done), tostring(left), tostring(dry)))
check("reach: the refusal names the band",
    loggedText():find("none is within 24 studs of the blade") ~= nil)
check("reach: an out-of-reach bail does not switch the job off",
    spudFieldRemoteState.off.seed ~= true)

att.Position = Vector3.new(0, 170, 0)
rowOfEight()
resetState()
cj0 = seedRemote.invokeCalls
done, left = spudFieldRemotePass(seedJob, field, tool)
check("reach: no field frame means no filter (unreadable is not a skip)",
    seedRemote.invokeCalls - cj0 == 8 and done == true and left == 0,
    (seedRemote.invokeCalls - cj0) .. " call(s), " .. tostring(done) .. "," .. tostring(left))

resetCells()
mode.atCell = false
acceptR = 2

-- 14. THE TOW SETTLES BEFORE THE NEXT JUMP (owner 2026-11-02: "when it tp's the
--     tools make the whole thing glitch and it falls out the map, make it wait
--     for the tool to be behind the tractor before tping again")
check("settle: no readable tool is nothing to wait for",
    (spudWaitTool(hopRide, nil, "seed")) == "none")
RIDE_POS = Vector3.new(0, 0, 0)
ATTPARENT.Position = Vector3.new(0, 0, -5)
check("settle: a tool parked behind the ride is settled",
    (spudWaitTool(hopRide, hopAtt, "seed")) == "settled")
ATTPARENT.Position = Vector3.new(300, 0, 0)
local farHow, farDist = spudWaitTool(hopRide, hopAtt, "seed")
check("settle: a tool 300 studs off the hitch is FLUNG, not towed",
    farHow == "far" and farDist > 90, tostring(farHow) .. " " .. tostring(farDist))

-- a blade that keeps moving never settles: the wait is bounded, and the verdict
-- is "swinging" so the caller logs it instead of teleporting forever
local OSC = 0
local oscRide = {}
function oscRide:GetPivot() return setmetatable({ Position = RIDE_POS }, CF) end
function oscRide:PivotTo(cf) RIDE_POS = cf.pos end
RIDE_POS = Vector3.new(0, 0, 0)
ATTPARENT.Position = Vector3.new(12, 0, 0)
local realWait = task.wait
task.wait = function(_)
    OSC = OSC + 1
    -- the pendulum: a different spot on every beat, so it never settles
    ATTPARENT.Position = Vector3.new(OSC % 2 == 0 and 12 or 28, 0, 0)
    return realWait(_)
end
local swingHow, swingDist = spudWaitTool(oscRide, hopAtt, "seed")
task.wait = realWait
check("settle: a swinging tool is named, and the wait is bounded",
    swingHow == "swinging" and OSC == 30,
    tostring(swingHow) .. " after " .. OSC .. " beat(s) at " .. tostring(swingDist))

-- the grid stops rather than dragging a flung implement across the map
acceptR = 60
mode.seed = "all"
mode.atCell = false
spudBatchRemotes = false
sweepGrid()
RIDE_POS = Vector3.new(0, 0, 0)
ATTPARENT.Position = Vector3.new(400, 0, 0)   -- not on the hitch any more
local gridRides = rides
resetState()
local gj0 = seedRemote.invokeCalls
local tookFar = spudRadialFire(seedJob, field, hopRide, tool, "Cultivated",
    baseCF, baseSize, hopAtt)
check("flung tool: the grid fires nothing and stops",
    seedRemote.invokeCalls - gj0 == 0 and rides == gridRides,
    (seedRemote.invokeCalls - gj0) .. " call(s), " .. (rides - gridRides) .. " jump(s)")
check("flung tool: the pass says the implement is off the hitch",
    loggedText():find("not on the hitch any more") ~= nil)

-- 15. BIGGER TOOL, BIGGER BURST (owner: "if the tool is bigger cant the burst
--     things also be bigger?") — the extra is the implement's OWN width past one
--     tile; unreadable parts must give 0 and keep the measured 3x3 / 24 studs
SpudFarm = {
    partBoxes = function() return { { x = 0, z = 0, sx = 40, sy = 1, sz = 10,
        r = { 1, 0, 0 }, u = { 0, 1, 0 }, l = { 0, 0, 1 } } } end,
    widthFromParts = function(parts, step)
        return (step and step.X and step.X > 0) and 40 or 10
    end,
    widthTiles = function(w) return math.ceil(w / 10) end,
}
check("wide tool: the extra tiles are the width past one",
    spudToolExtraTiles(tool) == 3, tostring(spudToolExtraTiles(tool)))
check("no tool at all adds no reach", spudToolExtraTiles(nil) == 0)
SpudFarm.partBoxes = function() error("no such API") end
check("a build that will not answer keeps the measured 3x3",
    spudToolExtraTiles(tool) == 0, tostring(spudToolExtraTiles(tool)))

SpudFarm = {
    partBoxes = function() return { { x = 0, z = 0, sx = 40, sy = 1, sz = 10,
        r = { 1, 0, 0 }, u = { 0, 1, 0 }, l = { 0, 0, 1 } } } end,
    widthFromParts = function(parts, step)
        return (step and step.X and step.X > 0) and 40 or 10
    end,
    widthTiles = function(w) return math.ceil(w / 10) end,
}
RIDE_POS = Vector3.new(80, 0, 80)
ATTPARENT.Position = RIDE_POS + Vector3.new(0, 0, -5)
sweepGrid()
resetState()
local tookWide = spudRadialFire(seedJob, field, hopRide, tool, "Cultivated",
    baseCF, baseSize, hopAtt)
-- ▸ the wide implement grows the CORNER PASS, never the burst BLOCK: the call
--   carries one attachment point and a square's corners sit on a diagonal, where
--   a bar that widens one axis earns nothing (owner 2026-11-03, the cross).
check("wide tool: the block stays an equal 3x3, not a wider square",
    loggedText():find("3x3 per stop") ~= nil,
    "took " .. tostring(tookWide))
check("equal squares: the measured 20-stud band gets a 3x3",
    spudBlockSide(20) == 3, tostring(spudBlockSide(20)))
check("equal squares: a 4x4 needs its own corner (21.2) inside the band",
    spudBlockSide(21) == 3 and spudBlockSide(22) == 4,
    string.format("%d / %d", spudBlockSide(21), spudBlockSide(22)))
check("equal squares: a 5x5 needs 28.3",
    spudBlockSide(29) == 5 and spudBlockSide(35) == 5,
    tostring(spudBlockSide(29)))
check("equal squares: capped at 7x7 however generous the band",
    spudBlockSide(400) == 7, tostring(spudBlockSide(400)))
check("equal squares: never smaller than the owner's 3x3",
    spudBlockSide(0) == 3 and spudBlockSide(nil) == 3,
    tostring(spudBlockSide(0)))

-- 16. ANCHOR THE TOW (owner: "we need to anchor the tractor when it tps because
--     the tool drags it, also the tractor tps before the tool can get back in
--     place"). Live v1.130 measured the failure: `arc hop: 286 studs` then
--     `hitch gap at arrival: 277.7 studs` — the ride moved and the plow did not,
--     so the hitch went taut (the drag) and no 1.5 s settle could ever close
--     277 studs (every pass then refused and the field fired 0 calls).
RIDE_POS = Vector3.new(0, 0, 0)
ATTPARENT.Position = Vector3.new(0, 0, -5)
local rotOf = CFrame.new(0, 0, 0) - Vector3.new(0, 0, 0)   -- heading with no position
local gapOf = function()
    local d = spudToolTrail(hopRide, hopAtt)
    return d or -1
end

-- the fixture is honest first: a bare ride teleport DOES leave the blade behind,
-- exactly like the game — otherwise every check below proves nothing
local spin = CFrame.new(Vector3.new(286, 0, 0)) * rotOf
hopRide:PivotTo(spin)
check("a ride-only teleport leaves the implement on the ground (like the game)",
    gapOf() > 200, "gap became " .. tostring(gapOf()))

-- and the carrying one does not
ATTPARENT.Position = Vector3.new(286, 0, -5)
local c0 = CARRIED
spudPivotRig(hopRide, CFrame.new(Vector3.new(0, 0, 0)) * rotOf, tool)
check("carry: the implement moves with the ride, hitch slack kept",
    gapOf() <= 6 and CARRIED == c0 + 1,
    "gap " .. tostring(gapOf()) .. ", " .. (CARRIED - c0) .. " carry")

local jumped = rides
local carried = CARRIED
RIDE_POS = Vector3.new(0, 0, 0)
ATTPARENT.Position = Vector3.new(0, 0, -5)
sweepGrid()
resetState()
local tookCarry = spudRadialFire(seedJob, field, hopRide, tool, "Cultivated",
    baseCF, baseSize, hopAtt)
check("grid: every jump carries the implement (no jump left towing nothing)",
    CARRIED - carried == rides - jumped,
    (rides - jumped) .. " jump(s), " .. (CARRIED - carried) .. " carry(ies)")
check("grid: the blade is still on the hitch after the last stop",
    gapOf() <= 6, "gap " .. tostring(gapOf()))
check("grid: the carried tow still takes the cells",
    tookCarry and tookCarry > 0, tostring(tookCarry))

jumped, carried = rides, CARRIED
RIDE_POS = Vector3.new(0, 0, 0)
ATTPARENT.Position = Vector3.new(0, 0, -5)
sweepGrid()
resetState()
local tookHopC = spudHopCells(seedJob, field, hopRide, tool, "Cultivated",
    baseCF, baseSize, hopAtt)
check("hop: every cell jump carries the implement",
    CARRIED - carried == rides - jumped,
    (rides - jumped) .. " jump(s), " .. (CARRIED - carried) .. " carry(ies)")
check("hop: the tow is still behind the ride at the end",
    gapOf() <= 6, "gap " .. tostring(gapOf()))
check("hop: the carried tow still takes the cells",
    tookHopC and tookHopC > 0, tostring(tookHopC))

-- an unreadable tool is not a reason to stop moving
local before0, cNoTool = rides, CARRIED
spudPivotRig(hopRide, CFrame.new(Vector3.new(30, 0, 30)) * rotOf, nil)
check("carry: a ride with nothing towed still jumps",
    rides == before0 + 1 and CARRIED == cNoTool,
    tostring(rides - before0) .. " jump(s), " .. (CARRIED - cNoTool) .. " carry(ies)")

-- ▸ the harvest job's `impl` IS the ride (self-propelled). Carrying a model onto
--   itself would add the delta a second time and land the harvester twice the
--   trip away — the guard in spudPivotRig is the only thing preventing it.
RIDE_POS = Vector3.new(0, 0, 0)
local selfCF = CFrame.new(Vector3.new(286, 0, 0)) * rotOf
local selfBefore = hopRide:GetPivot().Position
local js0, cs0 = rides, CARRIED
spudPivotRig(hopRide, selfCF, hopRide)
check("self-propelled: the ride is moved once, not twice",
    rides == js0 + 1 and CARRIED == cs0
    and (hopRide:GetPivot().Position - selfBefore).X == 286,
    "moved " .. string.format("%.0f",
        (hopRide:GetPivot().Position - selfBefore).X) .. " studs")

-- 17. THE FIRST STOP HAS TO LAND (owner 2026-11-03: "the seeding is bugging,
--     probably because the tool is attatched to the tractor"). The live console
--     lost the FIRST stop of every seed grid —
--       remote seed: the blade is 32 studs off stop 1 — firing anyway
--       remote seed: fired 48 of 2398 cell(s) from 280 stop(s), 3x3 per stop — 36 took, 2362 left
--       remote seed: the blade is 41 studs off stop 1 — firing anyway
--       remote seed: fired 9 of 2362 cell(s) from 276 stop(s), 3x3 per stop — 0 took, 2362 left
--     and that `fired 9` is exactly ONE 3x3 block: the honesty gate read those 0
--     takes after stop 1 and gave up the whole grid, while the first grid spent
--     its 48 seeds with 36 of them refused. A hitch is a CONSTRAINT: after a park
--     the implement settles at the ride's own rest trail, so a park aimed from
--     the pre-jump reading — stale straight out of a 288-stud arc — lands the
--     blade 41 studs off the block, and only a re-aim from the FRESH reading
--     closes it. TRAIL_REST models that settle.
RIDE_POS = Vector3.new(0, 0, 0)
TRAIL_REST = Vector3.new(0, 0, -5)           -- where the hitch actually leaves it
ATTPARENT.Position = Vector3.new(0, 0, -46)  -- mid-swing: 41 past the rest trail
mode.seed = "all"
mode.atCell = true
acceptR = 20                                 -- the real measured band
capVal.Value = 50
sweepGrid()
resetState()
rf0 = rides
cj0 = seedRemote.invokeCalls
local tookStale = spudRadialFire(seedJob, field, hopRide, tool, "Cultivated",
    baseCF, baseSize, hopAtt)
check("stale first trail: every block still gets its burst",
    seedRemote.invokeCalls - cj0 == 15,
    (seedRemote.invokeCalls - cj0) .. " call(s)")
check("stale first trail: and every cell takes", tookStale == 15, tostring(tookStale))
check("stale first trail: aiming costs extra jumps, not calls",
    rides - rf0 > 2, (rides - rf0) .. " pivot(s)")
check("stale first trail: nothing was handed over",
    loggedText():find("leaving this block") == nil)
TRAIL_REST = nil

-- and a blade that demonstrably is NOT on the block spends NOTHING (each call
-- there is refused, and a refused call is still a seed the seeder paid for).
-- RIDE_JAMMED + TRAIL_STUCK: the rig cannot be put on the block at all.
local function longField()
    fieldState[field] = {}
    for x = 1, 9 do
        for y = 1, 3 do
            fieldState[field][x * 128 + y] = { Stage = "Cultivated" }
        end
    end
end
-- a 9x3 plate on a 50x20 frame is TURNED, so its rows run along Z and the grid
-- makes three stops at (0,-30), (0,0) and (0,30); a blade stuck at (25,0,0) is
-- 25, 25 and 39 studs off them — a miss every time, close enough to the ride to
-- stay "on the hitch" so the pass ends on the misses, not on a flung tool.
RIDE_POS = Vector3.new(0, 0, 0)
ATTPARENT.Position = Vector3.new(25, 0, 0)
TRAIL_STUCK, RIDE_JAMMED = true, true
longField()
resetState()
cj0 = seedRemote.invokeCalls
rf0 = rides
local tookJam = spudRadialFire(seedJob, field, hopRide, tool, "Cultivated",
    baseCF, baseSize, hopAtt)
check("a blade that never lands fires no calls",
    seedRemote.invokeCalls - cj0 == 0,
    (seedRemote.invokeCalls - cj0) .. " call(s)")
check("a blade that never lands says which block it left",
    loggedText():find("leaving this block") ~= nil)
check("three stops that never land end the grid, and the hop takes over",
    loggedText():find("not landed on 3 stop") ~= nil and tookJam == 0,
    tostring(tookJam))
check("a missed grid leaves every cell standing",
    #spudFieldCellIds(field, "Cultivated") == 27)
TRAIL_STUCK, RIDE_JAMMED = false, false
mode.atCell = false

-- 18. A BLOCK IS A SQUARE, NOT A SLICE (owner 2026-11-03: "why does it onyl do
--     half the field"). The live grid on a part-worked field reported
--       remote plow: fired 361 of 361 cell(s) from 57 stop(s), 3x3 per stop — 180 took, 181 left
--       remote cultivate: fired 368 of 368 cell(s) … — 165 took, 203 left
--     361 cells over 57 stops is 6.3 per stop, where a 3x3 is 9 — and NOT ONE
--     `the blade is N off stop` line appeared, because the miss test compares the
--     blade to the stop, and the stop is the MEAN of whichever cells the INDEX
--     slice landed in. On a ragged field the rows hold different cells, so a
--     "block" is an L and its mean can sit past the band from its own corners:
--     the calls are refused, the stop reads as landed, and half the field waits
--     for the per-cell hop. Every fixture above is a FULL rectangle, where index
--     slicing and lattice slicing are the same thing — which is why this never
--     showed up in the harness. RAGGED = the missing cells are in the middle
--     columns; APART = the present cells are two strips with a 40-stud gap.
local function raggedField()
    fieldState[field] = {}
    for _, id in ipairs({ 1 * 128 + 1, 2 * 128 + 1, 4 * 128 + 2, 5 * 128 + 2,
        1 * 128 + 3, 2 * 128 + 3, 4 * 128 + 3, 5 * 128 + 3 }) do
        fieldState[field][id] = { Stage = "Cultivated" }
    end
end
local function apartField()
    fieldState[field] = {}
    for _, x in ipairs({ 1, 5 }) do
        for y = 1, 3 do
            fieldState[field][x * 128 + y] = { Stage = "Cultivated" }
        end
    end
end
-- the blade parks EXACTLY on the stop in this fixture (the park is aimed from the
-- tool's own reading and spudPivotRig carries it), so the only thing a stop can
-- be judged on is where its cells are — which is the point of the two cases.
local function raggedRun(who, builder, cells, stops)
    RIDE_POS = Vector3.new(0, 0, 0)
    ATTPARENT.Position = Vector3.new(0, 0, 0)
    TRAIL_REST, TRAIL_STUCK, RIDE_JAMMED = nil, false, false
    mode.seed = "all"
    mode.atCell = true
    acceptR = 20                     -- the band that took; 30 was refused live
    capVal.Value = 50
    builder()
    resetState()
    local calls0, rides0, lg0 = seedRemote.invokeCalls, rides, #logs + 1
    local took = spudRadialFire(seedJob, field, hopRide, tool, "Cultivated",
        baseCF, baseSize, hopAtt)
    local line = table.concat(logs, "|", lg0)
    check(who .. " field: every cell called",
        seedRemote.invokeCalls - calls0 == cells,
        (seedRemote.invokeCalls - calls0) .. " call(s) for " .. cells)
    check(who .. " field: every cell TAKES the grid",
        took == cells, tostring(took) .. " took of " .. cells)
    check(who .. " field: it plans that many tight stops",
        line:find("from " .. stops .. " stop") ~= nil,
        line:match("from %d+ stop%s*") or "no stop line")
    check(who .. " field: no block abandoned",
        line:find("leaving this block") == nil)
    check(who .. " field: nothing left standing",
        #spudFieldCellIds(field, "Cultivated") == 0)
    return rides - rides0
end
raggedRun("ragged", raggedField, 8, 2)
raggedRun("apart", apartField, 6, 2)

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
    # the band this harness pins its checks to is the measured one in the script
    if not re.search(r"^    spudFieldReach = 24\b", src, re.M):
        print("spudFieldReach is no longer 24 — update this harness")
        return 2
    for const in ("spudToolSwing = 3", "spudToolFar = 90", "spudFieldTaken = 20",
                  "spudFieldPitch = 10", "spudBlockPause = 100"):
        if not re.search(r"^    " + const + r"\b", src, re.M):
            print("the tow-settle gate no longer declares " + const
                  + " — update this harness")
            return 2
    # ▸ the burst block is an EQUAL square sized against the band that actually
    #   took (spudBlockSide), and a stop whose blade never landed fires NO calls
    #   (the old "firing anyway" line spent the whole seeder on refusals).
    radial = extract(src, "spudRadialFire")
    if "spudBlockSide(spudFieldTaken)" not in radial:
        print("the grid no longer sizes its block from the equal-square rule")
        return 2
    if "3 + spudToolExtraTiles(impl)" in radial:
        print("the grid still widens the block with the implement — that is the cross")
        return 2
    if "firing anyway" in radial:
        print("the grid still bursts at a blade it measured off the block")
        return 2
    # ▸ AND THE BLOCK IS CUT BY DISTANCE, NOT BY LIST POSITION (owner
    #   2026-11-03: "why does it onyl do half the field"). `rows[k].cells[col]`
    #   and the mean of the block's own cells are exactly the two lines that made
    #   a part-worked field into L-shaped blocks whose centre sat past the band
    #   from their own corners — `fired 361 … from 57 stop(s), 3x3 per stop —
    #   180 took`, with no miss line, because the miss test measured the blade
    #   against that same centre.
    for gone in ("(idx - 1) * side + 1", "sx / #block", "sz / #block",
                 "math.ceil(ncols / side)"):
        if gone in radial:
            print("the grid cuts blocks by index again (" + gone + ") — "
                  "a ragged field makes L-shaped blocks and half of them is refused")
            return 2
    if "spudFieldPitch" not in radial:
        print("the grid does not size its block from the game's own cell pitch")
        return 2
    # the gate has to sit BEFORE each teleport, and the teleport has to be the
    # carrying one — a bare `ride:PivotTo` leaves the implement on the ground
    for fn in ("spudRadialFire", "spudHopCells"):
        body = extract(src, fn)
        if "spudWaitTool(ride, att" not in body:
            print(fn + " teleports without waiting for the tow to settle")
            return 2
        if "spudPivotRig(ride," not in body:
            print(fn + " jumps the ride without carrying the implement")
            return 2
        if body.index("spudWaitTool(ride, att") > body.index("spudPivotRig(ride,"):
            print(fn + " waits for the tow only AFTER its first teleport")
            return 2
        if re.search(r"\b(?:ride|tr):PivotTo\(", body):
            print(fn + " still has a bare ride:PivotTo — that is the tow-tearing bug")
            return 2
    # the arc hop moves the rig too, and the tour hands it the hitched implement
    hop = src[src.index("    local function hopTo("):]
    hop = hop[:hop.index("\n    end\n") + len("\n    end\n")]
    if "spudPivotRig(tr," not in hop:
        print("hopTo teleports the ride without carrying the tow")
        return 2
    if not re.search(r"hopTo\(ride, goal, SELL_HOP_SPEED, impl\)", src):
        print("the field-to-field arc hop is not given the implement to carry")
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
