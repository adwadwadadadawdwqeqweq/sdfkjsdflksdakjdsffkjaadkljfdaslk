"""Where does a full harvester unload? (spudSellNow + spudFulfillSpots)

The Farm tab now carries a Drop-off pick: FULFILLMENT (the warehouse drop pad,
measured by the owner standing on it at -353,141,-92) or SELL (the crop board,
125,142,-150). Two things must hold:

  * spudSellNow answers "is this tank full AND is a destination chosen?" —
    a full tank with an unknown destination still must not drive anywhere;
  * spudFulfillSpots names the Fulfillment pad from the world, aims at its
    top surface, prefers Deposit_Warehouse over Withdraw_Warehouse, and
    returns nothing (with a log line) when the folder is not streamed;
  * trySellAt presses NO key on the Fulfillment pad (the pad unloads a parked
    harvester by itself), while the Sell pads still try the captured call and
    then Q/E, and the tank dropping is the only proof of either;
  * when the world hands back NO pad instance and no waypoint, the trip still
    parks at the coordinates the owner stood on and read with 📍 Get coords
    (spudFulfillPadSpot = -353,141,-92, spudCropSellSpot = 125,142,-150),
    because a position alone is enough for a pad that drains by contact — and it
    never fires a sell call it has no part for. A skipped unload is what leaves
    50 ripe cells standing, and it now cannot happen for either pick;
  * a pad the walk matched BY NAME has to be AT that measured pad
    (spudFulfillPadNear). Live 2026-11-02 it scored
    Ugc.CompanyArea.WarehouseArea — a district whose name says warehouse — and
    the trip parked on its centre 142 studs from the drop deck, tank unchanged.
    A name match that far off is a landmark: it is refused, the marker waypoint
    still comes back, and the measured deck is what the trip ends up parking on.

    python tools/dropoff_test.py [path-to-luau.exe]
"""

import os
import pathlib
import re
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "SpudFarm_Full.lua"
WANTED = ["spudSellNow", "spudHarvestFull", "spudFulfillSpots", "findSellSpots", "trySellAt", "sellHarvester", "spudFulfillPadSpot", "spudCropSellSpot"]

PRE = r"""
local V = {}
function V.__add(a, b) return setmetatable({ X = a.X + b.X, Y = a.Y + b.Y, Z = a.Z + b.Z }, V) end
function V.__sub(a, b) return setmetatable({ X = a.X - b.X, Y = a.Y - b.Y, Z = a.Z - b.Z }, V) end
V.__index = function(t, k)
    if k == "Magnitude" then return math.sqrt(t.X * t.X + t.Y * t.Y + t.Z * t.Z) end
    return nil
end
Vector3 = { new = function(x, y, z)
    return setmetatable({ X = x or 0, Y = y or 0, Z = z or 0 }, V)
end }

local NODE = {}
NODE.__index = NODE
function NODE:FindFirstChild(name) return self.kids[name] end
function NODE:GetChildren() return self.list end
function NODE:GetDescendants()
    local out = {}
    local function walk(n)
        for _, k in ipairs(n.list) do
            out[#out + 1] = k
            walk(k)
        end
    end
    walk(self)
    return out
end
function NODE:IsA(cls) return cls == self._cls end
function NODE:GetBoundingBox()
    return { Position = self.Position }, self.Size or Vector3.new(10, 1, 10)
end

GRID = setmetatable({ Name = "Workspace", kids = {}, list = {}, _cls = "Workspace" }, NODE)
workspace = GRID
local logged = {}
function log(s) logged[#logged + 1] = tostring(s) end
function loggedText() return table.concat(logged, "\n") end

local function folder(name, parent)
    local n = setmetatable({ Name = name, kids = {}, list = {}, _cls = "Folder",
        ClassName = "Folder", Parent = parent }, NODE)
    if parent then parent.kids[name] = n parent.list[#parent.list + 1] = n end
    return n
end
local function part(name, parent, x, y, z, sx, sy, sz)
    local n = setmetatable({ Name = name, kids = {}, list = {}, _cls = "BasePart",
        ClassName = "Part", Parent = parent,
        Position = Vector3.new(x, y, z), Size = Vector3.new(sx or 10, sy or 1, sz or 10) }, NODE)
    if parent then parent.kids[name] = n parent.list[#parent.list + 1] = n end
    return n
end
local function model(name, parent, x, y, z, sx, sy, sz)
    local n = setmetatable({ Name = name, kids = {}, list = {}, _cls = "Model",
        ClassName = "Model", Parent = parent,
        Position = Vector3.new(x, y, z), Size = Vector3.new(sx or 10, sy or 1, sz or 10) }, NODE)
    if parent then parent.kids[name] = n parent.list[#parent.list + 1] = n end
    return n
end
"""

POST = r"""
local fails = 0
local function check(name, ok, detail)
    if not ok then fails = fails + 1 end
    print(string.format("%-58s %s%s", name, ok and "PASS" or "FAIL",
        detail and ("  " .. detail) or ""))
end

-- the band is a script-level global; the extracted slice of spudFulfillSpots
-- does not carry its assignment, so the harness supplies the number that
-- main() asserts is in the source.
spudFulfillPadNear = spudFulfillPadNear or 35

-- 1. the full-tank gate follows the destination pick
spudDropOff = "Fulfillment"
check("fulfillment: a full tank unloads", spudSellNow(50, 50) == true)
check("fulfillment: an over-full tank unloads", spudSellNow(60, 50) == true)
check("fulfillment: a half tank keeps working", spudSellNow(25, 50) == false)
check("fulfillment: an unreadable load never unloads", spudSellNow(nil, nil) == false)
check("fulfillment: a zero capacity never unloads", spudSellNow(0, 0) == false)
spudDropOff = "Sell"
check("sell: a full tank sells", spudSellNow(50, 50) == true)
check("sell: a half tank keeps working", spudSellNow(25, 50) == false)
spudDropOff = ""
check("no destination: a full tank stays put", spudSellNow(50, 50) == false)
spudDropOff = nil
check("nil destination: a full tank stays put", spudSellNow(50, 50) == false)

-- 1b. a tank that cannot cover the standing cells is full too (live 49/50
--     against 46 cells fired one call a round for ever)
check("space: a full tank needs no second opinion", spudHarvestFull(50, 50, 46) == true)
check("space: one free slot against 46 cells unloads", spudHarvestFull(49, 50, 46) == true)
check("space: one free slot against 1 cell keeps working", spudHarvestFull(49, 50, 1) == false)
check("space: an empty tank never unloads", spudHarvestFull(0, 50, 46) == false)
check("space: an unreadable load never unloads", spudHarvestFull(nil, nil, 46) == false)
check("space: a zero capacity never unloads", spudHarvestFull(0, 0, 46) == false)
check("space: no standing cells means no excuse", spudHarvestFull(25, 50, 0) == false)

-- 2. the Fulfillment pad is named from the world
local stores = folder("Stores", workspace)
local drops = folder("DropOffs", stores)
local deposit = part("Deposit_Warehouse", drops, -353, 138, -90, 30, 4, 30)
part("Withdraw_Warehouse", drops, -286, 138, -217, 30, 4, 30)
part("DropOff", drops, 68, 138, -289, 12, 2, 12)

local spots = spudFulfillSpots()
check("fulfillment: one pad comes back", type(spots) == "table" and #spots == 1,
    type(spots) == "table" and ("got " .. #spots) or nil)
local s = spots and spots[1]
check("fulfillment: it is the deposit pad", s and s.what == "DropOffs.Deposit_Warehouse",
    s and tostring(s.what) or nil)
check("fulfillment: it aims at the top surface", s and s.p and math.abs(s.p.Y - 140) < 0.01,
    s and s.p and string.format("y=%.2f", s.p.Y) or nil)
check("fulfillment: x/z are the pad's centre", s and s.p and math.abs(s.p.X + 353) < 0.01
    and math.abs(s.p.Z + 90) < 0.01, nil)

-- 3. a lone withdraw pad is still better than refusing to move
drops.kids["Deposit_Warehouse"] = nil
drops.list = { drops.list[1], drops.list[3] } -- withdraw + plain dropoff
local spots2 = spudFulfillSpots()
check("no deposit pad: still returns a pad", type(spots2) == "table" and #spots2 >= 1,
    type(spots2) == "table" and ("got " .. #spots2) or nil)

-- 4. an unstreamed / empty folder is named, never guessed
local empty = folder("EmptyDrops", stores)
GRID.kids["Stores"] = stores
stores.kids["DropOffs"] = empty
stores.list = { empty }
local spots3 = spudFulfillSpots()
check("empty DropOffs: no pad", type(spots3) == "table" and #spots3 == 0, nil)
check("empty DropOffs: it says so", loggedText():lower():find("dropoff") ~= nil
    or loggedText():lower():find("unload") ~= nil, loggedText())

GRID.kids["Stores"] = nil
GRID.list = {}
local spots4 = spudFulfillSpots()
check("no Stores at all: no crash, no pad", type(spots4) == "table" and #spots4 == 0, nil)

-- 4b. THE FOLDER IS NOT WHERE THE PAD LIVES (v1.118, live): Stores.DropOffs
--     exists with 0 children at the field AND 0 children again after the
--     store hop — the same folder an older world dump called empty. So the
--     pad is looked for BY NAME wherever the game actually has it.
local storesB = folder("Stores", workspace)
local dropsB = folder("DropOffs", storesB)      -- present and empty, like the live build
local objectsB = folder("Objects", workspace)
local buildingsB = folder("Buildings", objectsB)
local companyB = folder("CompanyArea", buildingsB)
local depositB = part("Deposit_Warehouse", companyB, -353, 138, -90, 30, 4, 30)
local spots5 = spudFulfillSpots()
check("empty folder: the pad is found by name", type(spots5) == "table" and #spots5 == 1,
    type(spots5) == "table" and ("got " .. #spots5) or nil)
local s5 = spots5 and spots5[1]
check("empty folder: the path names where it really is",
    s5 and s5.what and s5.what:find("CompanyArea") ~= nil, s5 and tostring(s5.what) or nil)
check("empty folder: it still aims at the top surface",
    s5 and s5.p and math.abs(s5.p.Y - 140) < 0.01,
    s5 and s5.p and string.format("y=%.2f", s5.p.Y) or nil)
check("empty folder: the part is the pad to fire at", s5 and s5.part == depositB)

-- the documented folder still wins when it does hold the pad
part("Deposit_Warehouse", dropsB, 10, 138, 20, 30, 4, 30)
local spots6 = spudFulfillSpots()
check("both places: the DropOffs folder is still first",
    spots6[1] and spots6[1].what == "DropOffs.Deposit_Warehouse",
    spots6[1] and tostring(spots6[1].what) or nil)

-- a Model pad still gives a place to park — the CLASS is what no build has
-- ever printed, and the pad may well be a model rather than a part. It sits on
-- the measured deck because a name match that is NOT there is refused (4e).
local function detach(node, name)
    node.kids[name] = nil
    for i = #node.list, 1, -1 do
        if node.list[i].Name == name then table.remove(node.list, i) end
    end
end
detach(dropsB, "Deposit_Warehouse")
detach(companyB, "Deposit_Warehouse")
model("Deposit_Warehouse", companyB, -353, 138, -90, 30, 4, 30)
local spots7 = spudFulfillSpots()
check("model pad: a place to park comes back", #spots7 == 1, #spots7 .. " spot(s)")
check("model pad: the park spot is the model's own top",
    spots7[1] and math.abs(spots7[1].p.Y - 140) < 0.01,
    spots7[1] and string.format("y=%.2f", spots7[1].p.Y) or nil)
check("model pad: no part means no in-place call, only the park",
    spots7[1] and spots7[1].part == nil)

-- nothing anywhere: it says so instead of naming a pad that is not there
GRID.kids["Stores"] = nil
GRID.list = {}
logged = {}
local spots8 = spudFulfillSpots()
check("no pad anywhere: no pad", type(spots8) == "table" and #spots8 == 0, nil)
check("no pad anywhere: the line names the world read",
    loggedText():find("no unload pad") ~= nil, loggedText())

-- 4c. A GOTO MARKER IS NOT A PAD (live 2026-11-02). The world-walk scored
--     Ugc.Markers.GotoLocations.Warehouse as the pad, the run hopped 838 studs
--     onto it and parked: load 50, coins 14459 -> 14459 after 16 s. Then the
--     same trip again every 60 s, so 50 Harvestable cells were never picked.
--     A marker is a place to TRAVEL to (the seed shop does exactly that with
--     Markers.GotoLocations.FarmCo), so it comes back as the waypoint to hop
--     to and the pad is re-read once the area is streamed.
local ugc = folder("Ugc", workspace)
local mkNode = folder("Markers", ugc)
local gtNode = folder("GotoLocations", mkNode)
part("Warehouse", gtNode, -367, 138, -108, 8, 1, 8)
logged = {}
local spots9, wp9, wpWhere9 = spudFulfillSpots()
check("marker: a goto marker is never the pad", #spots9 == 0, #spots9 .. " spot(s)")
check("marker: the marker comes back as the waypoint to hop to",
    wp9 ~= nil and math.abs(wp9.X + 367) < 0.01,
    wp9 and string.format("x=%.0f", wp9.X) or "nil")
check("marker: the waypoint names its real path",
    wpWhere9 ~= nil and wpWhere9:find("GotoLocations") ~= nil, tostring(wpWhere9))
check("marker: it still says no unload pad was found",
    loggedText():find("no unload pad") ~= nil, loggedText())
-- and a real pad elsewhere still wins over refusing
part("Deposit_Warehouse", folder("CompanyArea", folder("Buildings", folder("Objects", workspace))),
    -353, 138, -90, 30, 4, 30)
local spots10, wp10 = spudFulfillSpots()
check("marker: a real pad beside the marker is the one returned",
    #spots10 == 1 and spots10[1].what:find("CompanyArea") ~= nil,
    spots10[1] and tostring(spots10[1].what) or "no pad")
check("marker: with a pad found no waypoint is needed", wp10 == nil)

-- 4e. A NAME MATCH IS NOT THE PAD UNLESS IT IS AT THE PAD (owner 2026-11-02:
--     "when it does the farm look and i put it to furfillement it brought me to
--     the wrong place"). Live: the walk admitted Ugc.CompanyArea.WarehouseArea —
--     a Model whose NAME says warehouse, so it scored 2 — the trip hopped 860
--     studs onto its centre (-278, 138, -212) and parked 142 studs from the drop
--     deck the owner stood on; the tank stayed at 50 and the same trip came back
--     every 60 s. So a walk candidate outside spudFulfillPadNear of
--     spudFulfillPadSpot() is refused, the marker waypoint still comes back, and
--     the trip ends on the measured deck. The game's own Stores.DropOffs folder
--     is never second-guessed — that is check 3.
GRID.kids["Stores"] = nil GRID.kids["Ugc"] = nil GRID.kids["Objects"] = nil
GRID.list = {}
local ugc2 = folder("Ugc", workspace)
local ca2 = folder("CompanyArea", ugc2)
model("WarehouseArea", ca2, -278, 137, -212, 60, 2, 60)
local gt2 = folder("GotoLocations", folder("Markers", ugc2))
part("Warehouse", gt2, -367, 138, -108, 8, 1, 8)
logged = {}
local spots11, wp11 = spudFulfillSpots()
check("far name match: a district is not the pad", #spots11 == 0,
    #spots11 .. " spot(s)")
check("far name match: the line names what was refused",
    loggedText():find("WarehouseArea") ~= nil, loggedText())
check("far name match: the line names the miss distance",
    loggedText():find("studs from the measured pad") ~= nil, loggedText())
check("far name match: the marker waypoint still comes back",
    wp11 ~= nil and math.abs(wp11.X + 367) < 0.01,
    wp11 and string.format("x=%.0f", wp11.X) or "nil")
-- a walk candidate ON the measured deck is still the pad the trip uses
detach(ca2, "WarehouseArea")
model("Deposit_Warehouse", ca2, -353, 139, -93, 30, 4, 30)
logged = {}
local spots12 = spudFulfillSpots()
check("in-band name match: the pad is still taken from the world",
    #spots12 == 1 and spots12[1].what:find("CompanyArea") ~= nil,
    spots12[1] and tostring(spots12[1].what) or "no pad")
check("in-band name match: nothing is refused",
    loggedText():find("not the drop pad") == nil, loggedText())

-- 5. the pad behaviour itself: Fulfillment presses nothing, Sell calls then
--    falls back to Q/E, and the tank dropping is the only proof
local vtime = 0
task = { wait = function(t) vtime = vtime + (t or 0) end }
os = { clock = function() return vtime end }
Enum = { KeyCode = { Q = "Q", E = "E" } }
local keys, calls = {}, {}
local function resetPad()
    vtime, keys, calls = 0, {}, {}
    logged = {}
end
function pressKey(k) keys[#keys + 1] = tostring(k) end
function stopping() return false end
function coinBalance() return 100 end
function sellMenuOpen() return false end
function sellMenuGui() return nil end
function closeSellMenu() return true end
local drainAt, remoteTakes = 2.4, true
function spudSellRemote(ride, pad) calls[#calls + 1] = { ride = ride, pad = pad } return remoteTakes end
function harvesterLoad(ride) return vtime >= drainAt and 0 or 50 end

-- fulfillment: parked, the pad drains it, no key ever pressed
resetPad() drainAt = 2.4 remoteTakes = true
local okPad = trySellAt("ride", "Deposit_Warehouse", nil, true)
check("fulfillment pad: the tank dropping counts as unloaded", okPad == true)
check("fulfillment pad: no key is pressed", #keys == 0, #keys .. " key(s)")
check("fulfillment pad: no sell call is made", #calls == 0, #calls .. " call(s)")
check("fulfillment pad: the log says it presses nothing",
    loggedText():lower():find("pressing nothing") ~= nil)

-- sell: the captured call takes it inside the grace window, still no key
resetPad() drainAt = 3.4 remoteTakes = true
local okSell = trySellAt("ride", "DropOff", "padpart", false)
check("sell pad: the remote unloads it", okSell == true)
check("sell pad: the call carries (ride, pad)",
    calls[1] and calls[1].ride == "ride" and calls[1].pad == "padpart")
check("sell pad: a working remote presses no key", #keys == 0, #keys .. " key(s)")

-- sell: an ignored remote falls back to Q and E, and never claims a sale
resetPad() drainAt = 999 remoteTakes = false
local okIgnored = trySellAt("ride", "DropOff", "padpart", false)
local pressed = table.concat(keys, ",")
check("sell pad: an ignored remote is not a sale", okIgnored == false)
check("sell pad: it falls back to Q and E", pressed:find("Q") ~= nil and pressed:find("E") ~= nil, pressed)
check("sell pad: the failure line names the pad", loggedText():find("DropOff") ~= nil)

-- 5b. a tank that ARRIVES ALREADY EMPTY is not a failed unload. sellHarvester
--     watches its in-place call for only 1.5 s; a sale that lands a beat later
--     leaves the pad trip running against an empty harvester, where
--     `cur < cap0` can never be true at cap0 = 0. Live v1.138 printed
--     `no unload at DropOffs.Deposit_Warehouse after 16 s (load 0, coins
--     644584 → 923235) — the pad didn't take it while parked` and then
--     `⚠ still full`, about a tank that had been emptied and paid out 278k.
resetPad() drainAt = 0 remoteTakes = true
local okEmpty = trySellAt("ride", "Deposit_Warehouse", nil, true)
check("already empty: the park trip is not a failure", okEmpty == true)
check("already empty: it presses nothing", #keys == 0, #keys .. " key(s)")
check("already empty: it makes no sell call", #calls == 0, #calls .. " call(s)")
check("already empty: the line names the empty read as the proof",
    loggedText():find("already reads empty") ~= nil, loggedText())
check("already empty: nothing calls the pad a failure",
    loggedText():find("didn't take it") == nil, loggedText())

-- 6. a full tank still finds the store when no pad is streamed yet
local realFindSellSpots = findSellSpots -- keep the extracted one for section 7
local hops = {}
function hopTo(ride, target, speed)
    hops[#hops + 1] = { X = target.X, Y = target.Y, Z = target.Z }
    return true
end
local soldAt = nil
function trySellAt(ride, what, pad, autoPad)
    soldAt = { what = what, pad = pad, autoPad = autoPad }
    return true
end
local tank, soldPad, remoteFired = 50, nil, 0
function harvesterLoad(ride) return tank, 50 end
function spudSellRemote(ride, pad)
    remoteFired += 1
    soldPad = pad
    tank = 0 -- the server takes it at once, like the live run
    return true
end
local ride = { GetPivot = function() return { Position = Vector3.new(10, 170, 10) } end }
local scanPad = { what = "SellArea.Pad", part = "padpart", p = Vector3.new(40, 170, 20) }
local scanState = "pad"
function findSellSpots()
    if scanState == "pad" then return { scanPad } end
    if scanState == "none" then return {} end
    return scanPad -- "late": empty first scan, pad after the store hop
end
function spudFulfillSpots() return {} end
function storeAnchors() return { FarmCo = Vector3.new(-900, 140, -900) } end
spudDropOff = "Sell"
spudSellNow = function() return true end

-- 6a. a pad already streamed: it sells in place, no hop at all
scanState = "pad"
tank, soldPad, remoteFired = 50, nil, 0
hops, soldAt = {}, nil
local okSell = sellHarvester(ride, nil, nil)
check("sell: a streamed pad sells with NO hop",
    okSell == true and #hops == 0, #hops .. " hop(s)")
check("sell: the call fired at that pad", remoteFired == 1 and soldPad == "padpart")
check("sell: the in-place sale never falls back to trySellAt", soldAt == nil)

-- 6b. nothing streamed, then the store hop makes the pad appear
local scans = 0
function findSellSpots()
    scans += 1
    if scans == 1 then return {} end
    return { scanPad }
end
tank, soldPad, remoteFired = 50, nil, 0
hops, soldAt = {}, nil
local fieldStub = { Parent = true, Name = "Field" }
local okLate = sellHarvester(ride, nil, fieldStub)
check("sell: no pad -> it hops to the store first", #hops >= 1 and hops[1].X == -900,
    #hops .. " hop(s)")
check("sell: after the hop it sells in place", okLate == true and remoteFired == 1)
check("sell: the trip back returns to the field, not the store",
    hops[#hops].X == 10 and hops[#hops].Z == 10,
    hops[#hops] and string.format("%.0f,%.0f", hops[#hops].X, hops[#hops].Z) or "no hop")

-- 6c. nothing streamed and no marker at all, on a SELL pick: the measured crop
--     board is still a place to park (owner 2026-11-02: the four spots read with
--     📍 Get coords). No part means no EVTSellAtStore — and a sell board is NOT
--     an auto pad, so the trip must still allow trySellAt's Q/E menu path.
function findSellSpots() return {} end
function storeAnchors() return {} end
tank, soldPad, remoteFired = 50, nil, 0
hops, soldAt = {}, nil
local okSellNone = sellHarvester(ride, nil, nil)
local cropSpot = spudCropSellSpot()
check("sell: the measured board is the crop-sell spot",
    cropSpot.X == 125 and cropSpot.Y == 142 and cropSpot.Z == -150,
    string.format("%.0f,%.0f,%.0f", cropSpot.X, cropSpot.Y, cropSpot.Z))
check("sell: no board anywhere still takes the trip", okSellNone == true)
check("sell: remembered spot: it hops to the measured crop board",
    hops[1] and hops[1].X == 125 and hops[1].Z == -150,
    hops[1] and string.format("%.0f,%.0f", hops[1].X, hops[1].Z) or "no hop")
check("sell: remembered spot: it fires NO sell call (no part to fire at)",
    remoteFired == 0 and soldAt ~= nil and soldAt.pad == nil)
check("sell: remembered spot: a sell board is NOT an auto pad (Q/E still allowed)",
    soldAt ~= nil and soldAt.autoPad == false)
check("sell: remembered spot: the log says the board was unreadable",
    loggedText():find("no pad instance is readable") ~= nil
    and loggedText():find("measured spot") ~= nil)
check("sell: remembered spot: the trip names it as remembered, not as a world part",
    soldAt ~= nil and soldAt.what:find("remembered Sell spot") ~= nil,
    soldAt and tostring(soldAt.what) or "no trip")

-- 6d. Fulfillment tries the same in-place call first (owner 2026-10-31:
--     "didnt you say we could just call the sell bro?") — no hop when the
--     tank drops, and the park trip only when the call does nothing
spudDropOff = "Fulfillment"
function spudFulfillSpots()
    return { { p = Vector3.new(40, 170, 20), what = "DropOffs.Deposit_Warehouse",
        store = "Fulfillment", part = "warehousePart" } }
end
tank, soldPad, remoteFired = 50, nil, 0
hops, soldAt = {}, nil
local okFul = sellHarvester(ride, nil, nil)
check("fulfillment: the in-place call empties the tank with NO hop",
    okFul == true and #hops == 0, #hops .. " hop(s)")
check("fulfillment: the call fired at the warehouse pad",
    remoteFired == 1 and soldPad == "warehousePart")

function spudSellRemote(ride, pad) remoteFired += 1 return true end
tank = 50
hops, soldAt = {}, nil
local okPark = sellHarvester(ride, nil, nil)
check("fulfillment: a refused call still takes the park trip",
    okPark == true and soldAt ~= nil and soldAt.autoPad == true)

-- 6f. the call is fired at ANY distance (owner 2026-10-31: "why isnt it
--     calling the sell function from anywhere") — the tank not moving in
--     1.5 s is what starts the trip
function spudSellRemote(ride, pad) remoteFired += 1 return true end
function spudFulfillSpots()
    return { { p = Vector3.new(-353, 140, -90), what = "DropOffs.Deposit_Warehouse",
        store = "Fulfillment", part = "warehousePart" } }
end
tank, remoteFired = 50, 0
hops, soldAt = {}, nil
local okFar = sellHarvester(ride, nil, nil)
check("fulfillment: a far pad is still called first",
    remoteFired == 1, remoteFired .. " call(s)")
check("fulfillment: a far pad still takes the trip",
    okFar == true and soldAt ~= nil and #hops >= 1)
check("fulfillment: the log names the distance it fired from",
    loggedText():find("didn't move the tank at") ~= nil)

-- 6g. no pad streamed, but the world read named a WAREHOUSE WAYPOINT: the trip
--     goes there (that is what a marker is for), lets the area stream and looks
--     again — instead of parking on the waypoint and hammering it every 60 s
local fulfills = 0
function spudFulfillSpots()
    fulfills += 1
    if fulfills == 1 then
        return {}, Vector3.new(-367, 138, -108), "Ugc.Markers.GotoLocations.Warehouse"
    end
    return { { p = Vector3.new(-353, 140, -90),
        what = "Objects.Buildings.CompanyArea.Deposit_Warehouse",
        store = "Fulfillment", part = "realPad" } }
end
function storeAnchors() return { FarmCo = Vector3.new(-900, 140, -900) } end
function spudSellRemote(ride, pad) remoteFired += 1 soldPad = pad return false end
spudDropOff = "Fulfillment"
tank, soldPad, remoteFired = 50, nil, 0
hops, soldAt = {}, nil
fulfills = 0
local okWp = sellHarvester(ride, nil, fieldStub)
check("waypoint: it hops to the warehouse marker, not to FarmCo",
    hops[1] and math.abs(hops[1].X + 367) < 0.01,
    hops[1] and string.format("%.0f,%.0f", hops[1].X, hops[1].Z) or "no hop")
check("waypoint: the pad is re-read once the hop has streamed it", fulfills == 2,
    fulfills .. " read(s)")
check("waypoint: the real pad then takes the load",
    okWp == true and soldAt ~= nil and soldAt.autoPad == true
    and soldAt.what:find("CompanyArea") ~= nil,
    soldAt and tostring(soldAt.what) or "no trip")
check("waypoint: the trip back returns to the field",
    hops[#hops].X == 10 and hops[#hops].Z == 10,
    hops[#hops] and string.format("%.0f,%.0f", hops[#hops].X, hops[#hops].Z) or "no hop")

-- 6h. no pad instance ANYWHERE and no waypoint either, on a FULFILLMENT pick:
--     the trip still goes to the coordinates the owner stood on (📍 Get coords,
--     2026-11-02: -353, 141, -92) — Fulfillment drains a parked harvester with
--     no call and no key, so a position alone is enough, and skipping the unload
--     is what leaves 50 ripe cells standing
local padSpot = spudFulfillPadSpot()
check("the remembered pad is the owner's standing reading",
    padSpot.X == -353 and padSpot.Y == 141 and padSpot.Z == -92,
    string.format("%.0f,%.0f,%.0f", padSpot.X, padSpot.Y, padSpot.Z))
function spudFulfillSpots() return {} end
function storeAnchors() return {} end
tank, soldPad, remoteFired = 50, nil, 0
hops, soldAt = {}, nil
local okRemembered = sellHarvester(ride, nil, nil)
check("remembered spot: the unload is not skipped", okRemembered == true)
check("remembered spot: the hop goes to the measured coords, not to FarmCo",
    hops[1] and hops[1].X == -353 and hops[1].Z == -92,
    hops[1] and string.format("%.0f,%.0f", hops[1].X, hops[1].Z) or "no hop")
check("remembered spot: it parks and fires NO sell call (no part to fire at)",
    remoteFired == 0 and soldAt ~= nil and soldAt.pad == nil)
check("remembered spot: the park is the auto pad (no key pressed)",
    soldAt ~= nil and soldAt.autoPad == true)
check("remembered spot: the log says the pad instance was unreadable",
    loggedText():find("no pad instance is readable") ~= nil
    and loggedText():find("measured spot") ~= nil)
check("remembered spot: the trip names it as remembered, not as a world part",
    soldAt ~= nil and soldAt.what:find("remembered Fulfillment spot") ~= nil,
    soldAt and tostring(soldAt.what) or "no trip")

-- 6i. THE LAST LINE OF A TRIP CANNOT CONTRADICT THE TANK IT JUST READ.
--     Every pad below the loop was tried and none returned a drop-baseline,
--     which used to print `⚠ still full` unconditionally. The load is re-read
--     now, so a sale that landed late ends the trip as the sale it was, and a
--     tank that really is still loaded names its own number.
local tank9 = 50
function harvesterLoad(ride) return tank9, 50 end
function spudSellRemote(ride, pad) remoteFired += 1 return false end
function spudFulfillSpots()
    return { { p = Vector3.new(-353, 140, -90), what = "DropOffs.Deposit_Warehouse",
        store = "Fulfillment", part = "warehousePart" } }
end
spudDropOff = "Fulfillment"
function trySellAt(ride, what, pad, autoPad) tank9 = 0 return false end
remoteFired, hops, soldAt = 0, {}, nil
logged = {}
local okLateEmpty = sellHarvester(ride, nil, nil)
check("empty after the trip: the run is not called still full",
    okLateEmpty == true and loggedText():find("still full") == nil, loggedText())
check("empty after the trip: the line reports the empty read as the proof",
    loggedText():find("reads empty after the pad trip") ~= nil, loggedText())
function trySellAt(ride, what, pad, autoPad) return false end
tank9, hops, soldAt, logged = 50, {}, nil, {}
local okStillLoaded = sellHarvester(ride, nil, nil)
check("still loaded: the failure names the real number",
    okStillLoaded == false and loggedText():find("still reads 50") ~= nil, loggedText())
check("still loaded: it never claims an empty tank",
    loggedText():find("reads empty") == nil, loggedText())

-- 7. every sell spot carries the part the sell call fires at
local gvNode = folder("GameplayVisuals", GRID)
local saNode = folder("SellArea", gvNode)
part("Pad", saNode, 20, 100, 20, 10, 1, 10)
local markersNode = folder("Markers", GRID)
local gotosNode = folder("GotoLocations", markersNode)
part("FarmCo", gotosNode, 0, 100, 0, 8, 1, 8)
part("SellBoardSeeds", gotosNode, 0, 100, 0, 8, 1, 8)
function storeAnchors() return { FarmCo = Vector3.new(0, 100, 0) } end
local sellSpots = realFindSellSpots()
check("sell spots: pads are found", #sellSpots > 0, #sellSpots .. " spot(s)")
local missingPart = 0
for _, s in ipairs(sellSpots) do
    if not s.part then missingPart += 1 end
end
check("sell spots: every spot carries the part to fire at", missingPart == 0,
    missingPart .. " without part")

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
    parts = []
    for name in WANTED:
        code = extract(src, name)
        if not code:
            print("missing " + name)
            return 2
        parts.append(code)
    if not re.search(r'spudDropOff\s*=.*"Fulfillment"', src):
        print("missing the Fulfillment default (spudDropOff)")
        return 2
    band = re.search(r"spudFulfillPadNear\s*=\s*(\d+)", src)
    if not band:
        print("missing the pad band (spudFulfillPadNear)")
        return 2
    if band.group(1) != "35":
        print(f"the pad band is now {band.group(1)} — the live miss distances say whether that is right")
        return 2
    for tie, why in [
        ("local bestFromWalk = false", "the walk no longer records that its pad came from a name match"),
        ("bestWhere, bestFromWalk = k, score, where, true", "the walk no longer flags the candidate it matched by name"),
        ("if bestFromWalk then", "a walk candidate is no longer checked against the measured deck"),
        ("local pad = spudFulfillPadSpot()", "the deck the walk is measured against is not the owner's reading"),
        ("return out, waypointSpot(), wpWhere", "a refused name match no longer hands back the marker waypoint"),
    ]:
        if tie not in src:
            print("source tie broken: " + why)
            return 2
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
