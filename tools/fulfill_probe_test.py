"""Run the real SpudFulfillProbe.lua on a fake game tree.

The probe is the evidence step for the Company-order feature, so it has to do
three things without a real client: find the order data by name and dump its
whole value tree, read the board's TEXT from workspace AND PlayerGui (the first
version only walked workspace), and print one field cell's keys so the grow-time
question is answered instead of guessed. All of that is checked here, plus the
read-only claim: no key press, no CFrame, no remote fired, no metatable hook.

    python tools/fulfill_probe_test.py [path-to-luau.exe]
"""

import os
import pathlib
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "SpudFulfillProbe.lua"

PRE = r"""
local V = {}
function V.__sub(a, b) return setmetatable({ X = a.X - b.X, Y = a.Y - b.Y, Z = a.Z - b.Z }, V) end
V.__index = function(t, k)
    if k == "Magnitude" then return math.sqrt(t.X * t.X + t.Y * t.Y + t.Z * t.Z) end
    return nil
end
local function vec(x, y, z) return setmetatable({ X = x or 0, Y = y or 0, Z = z or 0 }, V) end

-- typeof answers "Vector3" for the vec tables so the probe's size/position
-- lines run the same branch they will run in game.
typeof = function(v)
    if type(v) == "table" then
        if v._inst then return "Instance" end
        if v.X and v.Y and v.Z then return "Vector3" end
    end
    return type(v)
end

local function node(name, cls, kids, extra)
    local o = { Name = name, ClassName = cls, _kids = {}, _attrs = {}, _inst = true }
    for k, v in pairs(extra or {}) do o[k] = v end
    for _, c in ipairs(kids or {}) do
        c.Parent = o
        o._kids[#o._kids + 1] = c
    end
    function o:FindFirstChild(n, rec)
        for _, c in ipairs(self._kids) do
            if c.Name == n then return c end
        end
        if rec then
            for _, c in ipairs(self._kids) do
                local hit = c:FindFirstChild(n, true)
                if hit then return hit end
            end
        end
        return nil
    end
    function o:GetChildren() return self._kids end
    function o:GetDescendants()
        local out = {}
        local function walk(x)
            for _, c in ipairs(x._kids) do out[#out + 1] = c; walk(c) end
        end
        walk(self)
        return out
    end
    function o:IsA(c) return self.ClassName == c end
    function o:GetPivot() return { Position = self.Position or vec(0, 0, 0) } end
    function o:GetAttributes() return self._attrs end
    function o:GetFullName()
        if self.Parent then return self.Parent:GetFullName() .. "." .. self.Name end
        return self.Name
    end
    return o
end

-- ── the fake area: a Company order tree, a pad, crates and one field ────────
local order1 = node("Order1", "Folder", {
    node("Crop", "StringValue", nil, { Value = "Wheat" }),
    node("Wanted", "NumberValue", nil, { Value = 40 }),
    node("In", "NumberValue", nil, { Value = 12 }),
    node("Coins", "NumberValue", nil, { Value = 900 }),
    node("BoardLabel", "TextLabel", nil, { Text = "Deliver 40 Wheat - 900 coins" }),
})
local orders = node("Orders", "Folder", { order1 })
local company = node("Company", "Folder", { orders })
local pad = node("Deposit_Warehouse", "Part", nil, {
    Position = vec(-353, 138, -90), Size = vec(30, 4, 30), Transparency = 0.6,
})
local drops = node("DropOffs", "Folder", { pad })
local stores = node("Stores", "Folder", {
    company, drops, node("Milk", "IntValue", nil, { Value = 24 }),
})

local crateCfg = node("Configurations", "Folder", {
    node("Capacity", "NumberValue", nil, { Value = 50 }),
    node("CostBillboard", "NumberValue", nil, { Value = 100 }),
    node("SeedType", "StringValue", nil, { Value = "Wheat" }),
})
local crate = node("SeedBox", "Model", { crateCfg })
local draggable = node("DraggableObjects", "Folder", { crate })
local field = node("Field", "Model", nil, { Position = vec(0, 170, 0) })
local fields = node("Fields", "Folder", { field })
local objects = node("Objects", "Folder", { draggable, fields })

workspace = node("Workspace", "Workspace", { stores, objects })

-- the board as a ScreenGui: only reachable through PlayerGui
local boardTitle = node("Title", "TextLabel", nil, { Text = "Company Orders" })
local boardGui = node("OrderBoard", "Frame", { boardTitle })
local cpa = node("PCGP_ContextActions", "Folder", { node("Billboards", "Folder", {}) })
local hud = node("HUD", "ScreenGui", { node("MainHUD", "Folder", { cpa }) })
local guiviews = node("GuiViews", "Folder", { hud, boardGui })
local pg = node("PlayerGui", "PlayerGui", { guiviews })

local char = node("Character", "Model", {
    node("HumanoidRootPart", "Part", nil, { Position = vec(-353, 141, -90) }),
})

CREATED, CLIP = {}, nil
setclipboard = function(t) CLIP = t end
task = { delay = function(_, fn) fn() end }
UDim2 = setmetatable({}, { __index = function() return function(...) return { args = { ... } } end end })
Color3 = setmetatable({}, { __index = function() return function(...) return { args = { ... } } end end })
Enum = setmetatable({}, { __index = function() return setmetatable({}, { __index = function() return {} end }) end })
Instance = {
    new = function(cls)
        local o = { ClassName = cls, _kids = {} }
        CREATED[#CREATED + 1] = o
        return setmetatable(o, {
            __index = function(_, k)
                if k == "Destroy" then return function() end end
                return { Connect = function() end }
            end,
        })
    end,
}

-- the game's own field reader, with NO time-shaped key on a cell — the honest
-- answer the probe has to say out loud instead of leaving the pick to guess
local CELLS = {
    [641] = {
        Stage = "Empty", PlantGrowth = 0, GrowthMultiplier = 1,
        IsWatered = false, SeedType = "Wheat", Position = vec(0, 170, 0),
    },
}
local FIELD_HELPER = { GetCells = function() return CELLS end, GetField = function() return nil end }
require = function(m)
    if m.Name == "FieldHelper" then return FIELD_HELPER end
    error("unexpected require of " .. m.Name)
end
local fieldHelper = node("FieldHelper", "ModuleScript", nil, {})
local mods = node("Modules", "Folder", { fieldHelper })
local repl = node("ReplicatedStorage", "Folder", { mods })

local LP = node("Me", "Player", { char })
LP.Character = char
function LP:FindFirstChildOfClass(c) if c == "PlayerGui" then return pg end end
PLAYERS = { LocalPlayer = LP }
game = {
    PlaceId = 12345,
    JobId = "fake-job",
    GetService = function(_, n)
        if n == "Players" then return PLAYERS end
        if n == "ReplicatedStorage" then return repl end
    end,
}
"""

POST = r"""
local box, multiline
for _, o in ipairs(CREATED) do
    if o.ClassName == "TextBox" then box = o multiline = o.MultiLine end
end
print("PROBE-CHECK box=" .. tostring(box ~= nil and type(box.Text) == "string"
    and box.Text:find("COMPANY ORDERS", 1, true) ~= nil))
print("PROBE-CHECK multiline=" .. tostring(multiline == true))
print("PROBE-CHECK clipboard=" .. tostring(CLIP ~= nil
    and CLIP:find("COMPANY ORDERS", 1, true) ~= nil
    and CLIP:find("one field cell", 1, true) ~= nil))
"""


def main() -> int:
    base = pathlib.Path(os.environ.get("LOCALAPPDATA", ".")) / "Temp" / "opencode" / "luau"
    exe = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else base / "luau.exe"
    src = SRC.read_text(encoding="utf-8")

    fails = 0
    banned = ["pressKey", "FireServer", "InvokeServer", "hookmetamethod",
              "getrawmetatable", "CFrame", "PivotTo"]
    hits = [b for b in banned if b in src]
    if hits:
        fails += 1
        print("read-only: FAIL  file mentions " + ", ".join(hits))
    else:
        print(f"{'read-only: no key press, no CFrame, no remote fired':<56} PASS")

    with tempfile.NamedTemporaryFile("w", suffix=".lua", delete=False, encoding="utf-8") as fh:
        fh.write(PRE + "\n" + src + "\n" + POST)
        path = fh.name
    out = subprocess.run([str(exe), path], capture_output=True, encoding="utf-8", errors="replace")
    text = out.stdout
    if out.returncode != 0:
        print(text.strip()[-2000:])
        print(out.stderr.strip()[-2000:])
        return out.returncode

    def has(needle, label):
        nonlocal fails
        ok = needle in text
        if not ok:
            fails += 1
        print(f"{label:<56} {'PASS' if ok else 'FAIL'}")

    has("== COMPANY ORDERS: instances whose name says order", "it looks for the order data by name")
    has("Workspace.Stores.Company.Orders.Order1", "the order folder is found and named")
    has("matched 'order'", "it says which word matched")
    has("Crop  [StringValue]  =Wheat", "the whole order tree is dumped, not just the name")
    has("Wanted  [NumberValue]  =40", "the wanted count is printed")
    has("In  [NumberValue]  =12", "how much is already in is printed")
    has("Coins  [NumberValue]  =900", "the reward is printed")
    has("== COMPANY ORDERS: the words on the board (workspace + PlayerGui)",
        "the board text walks both trees")
    has("Deliver 40 Wheat - 900 coins", "a workspace board label is read")
    has("Company Orders", "a PlayerGui board label is read too")
    has("(under an order-named parent)", "a label under an order parent counts")
    has("order-sounding label(s) read", "it counts what it found")
    has("== what we hold that could fill an order ==", "it reads the inventory values")
    has("Milk  [IntValue]  =24", "a store value is printed with its number")
    has("== seed crates: every Configuration, looking for a grow time ==",
        "the crates are dumped whole")
    has("cfg.Capacity [NumberValue=50]", "a crate's own capacity is named")
    has("cfg.CostBillboard [NumberValue=100]", "the shelf price is named")
    has("seed kinds seen: Wheat", "the crop names are collected")
    has("FieldHelper exports:", "the field module's exports are listed")
    has("one field cell, every key", "one cell is dumped key by key")
    has("Stage              = Empty", "the cell's stage is printed")
    has("Position           = (0, 170, 0)", "a Vector3 key prints as a position")
    has("NO time-shaped key on a cell", "it says grow time is NOT readable")
    has("PROBE-CHECK box=true", "the report reaches the on-screen panel")
    has("PROBE-CHECK multiline=true", "the panel shows the whole report, not one line")
    has("PROBE-CHECK clipboard=true", "the report is copied to the clipboard")
    if "!!" in text:
        fails += 1
        print(f"{'no guarded section failed (!!) on a normal area':<56} FAIL")
    else:
        print(f"{'no guarded section failed (!!) on a normal area':<56} PASS")
    if "PROBE ERROR" in text:
        fails += 1
        print(f"{'the run itself never errors':<56} FAIL")
    else:
        print(f"{'the run itself never errors':<56} PASS")

    if fails:
        print(f"\n{fails} FAILED")
        print(text)
        return 1
    print("\nALL OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
