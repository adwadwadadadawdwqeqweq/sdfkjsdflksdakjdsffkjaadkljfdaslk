"""Run the real Tests-tab Company-order probe on a fake game tree.

The probe is the evidence step for the auto-contract feature the owner approved,
and it lives INSIDE the shipped build (Tests → Company orders) rather than in a
second executor script — a second script is how the ghost build happened. So what
this harness has to pin is that the leg stays a reader while sitting in a script
that writes: no event fired, no key pressed, nothing moved, and the only network
call is a RemoteFunction the game itself named ``Get…``, bracketed by a coin-
balance read that flags a moved balance in the same report.

It also pins the two honesty lines the feature depends on: an empty world walk is
"the board is elsewhere", never "no orders" (rule 7), and a grow time the client
cannot read is named as unreadable instead of guessed (rule 4).

    python tools/order_probe_test.py [path-to-luau.exe]
"""

import os
import pathlib
import re
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "SpudFarm_Full.lua"
SRC_TEXT = SRC.read_text(encoding="utf-8")


def orders_block(text: str) -> str:
    """The real `if kind == "orders" then … end` leg of spudTestWork."""
    start = text.index('if kind == "orders" then')
    anchor = text.index("-- ▸ REMOTE LIST", start)
    seg = text[start:anchor]
    end = seg.rindex("end")          # the leg's own closing `end`
    return seg[:end + len("end")]


ORDERS = orders_block(SRC_TEXT)
# the fold the probe reads every name through — the build's own function
NAME_KEY = re.search(r"function spudNameKey\(s\)\n.*?\n    end", SRC_TEXT, re.S).group(0)

COMMON = r"""
local V = {}
function V.__sub(a, b) return setmetatable({ X = a.X - b.X, Y = a.Y - b.Y, Z = a.Z - b.Z }, V) end
V.__index = function(t, k)
    if k == "Magnitude" then return math.sqrt(t.X * t.X + t.Y * t.Y + t.Z * t.Z) end
    return nil
end
local function vec(x, y, z) return setmetatable({ X = x or 0, Y = y or 0, Z = z or 0 }, V) end
typeof = function(v)
    if type(v) == "table" then
        if v._inst then return "Instance" end
        if v.X and v.Y and v.Z then return "Vector3" end
    end
    return type(v)
end

-- FIRED / INVOKED / KEYS / MOVED is the read-only ledger: every fixture instance
-- carries a counting method, so "nothing was fired" is a number, not a reading
-- of the source.
FIRED, INVOKED, KEYS, MOVED = {}, {}, {}, {}

local function node(name, cls, kids, extra)
    local o = { Name = name, ClassName = cls, _kids = {}, _attrs = {}, _inst = true }
    for k, v in pairs(extra or {}) do o[k] = v end
    for _, c in ipairs(kids or {}) do
        c.Parent = o
        o._kids[#o._kids + 1] = c
    end
    function o:FindFirstChild(n)
        for _, c in ipairs(self._kids) do if c.Name == n then return c end end
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
    function o:GetAttributes() return self._attrs end
    function o:GetFullName()
        if self.Parent then return self.Parent:GetFullName() .. "." .. self.Name end
        return self.Name
    end
    function o:PivotTo() MOVED[#MOVED + 1] = self:GetFullName() return true end
    function o:FireServer(...) FIRED[#FIRED + 1] = self.Name end
    function o:InvokeServer(...)
        INVOKED[#INVOKED + 1] = self.Name
        if self._answer ~= nil then return self._answer end
        if self._throws then error(self._throws) end
        return nil
    end
    return o
end

local function label(name, txt)
    return node(name, "TextLabel", nil, { Text = txt })
end

--[[NAMEKEY]]

local SAY = {}
function spudTestSay(line) SAY[#SAY + 1] = tostring(line) end
function coinBalance() return COINS end

--[[FIXTURE]]

-- the leg exactly as the build defines it, driven directly
local function runOrders(kind)
__BODY__
end

local okRun, errRun = pcall(runOrders, "orders")
print("RUN " .. (okRun and "OK" or ("ERROR " .. tostring(errRun))))
for _, line in ipairs(SAY) do print("SAY " .. line) end
print("LEDGER fired=" .. #FIRED .. " invoked=[" .. table.concat(INVOKED, ",")
    .. "] keys=" .. #KEYS .. " moved=" .. #MOVED)
"""

FIXTURE_RICH = r"""
-- a Company tree whose ORDER data is a CHILD of order-named folders: a walk that
-- stopped at the match would never see the shape this probe exists to report
local extras = {}
for i = 1, 15 do extras[#extras + 1] = node("Slot" .. i, "IntValue", nil, { Value = i }) end
local deal = node("Deal", "Folder", {
    node("Crop", "StringValue", nil, { Value = "Tomato" }),
    node("Wanted", "IntValue", nil, { Value = 240 }),
    node("Coins", "IntValue", nil, { Value = 3200 }),
})
local order1 = node("Order1", "Model", {
    node("Progress", "NumberValue", nil, { Value = 60 }),
    deal,
}, { _attrs = { Order = "Tomato", Wanted = 240 } })
-- 15 more values so the descendant list overflows the 16 the probe prints
for i = 1, 15 do
    order1._kids[#order1._kids + 1] = extras[i]
    extras[i].Parent = order1
end
local orders = node("Orders", "Folder", { order1 })
local company = node("Company", "Folder", { orders })

-- 16 more order-named instances elsewhere: only the first 14 hits may be printed
local notices = {}
for i = 1, 16 do
    notices[#notices + 1] = node("Request" .. i, "Folder", {
        node("Item", "StringValue", nil, { Value = "Cabbage" }),
    })
end
workspace = node("Workspace", "Workspace", {
    company,
    node("Objects", "Folder", { node("Notices", "Folder", notices) }),
})

-- the board as a ScreenGui: invisible to the walk above, so PlayerGui is read too
local pg = node("PlayerGui", "PlayerGui", {
    node("OrderBoard", "ScreenGui", {
        label("Title", "Company Orders — deliver 240 Tomato for 3200 coins"),
        node("Go", "TextButton", nil, { Text = "Accept" }),
    }),
    node("Chat", "Frame", { label("Msg", "hello there") }),
})
LocalPlayer = node("Miou", "Player", { pg })

-- the doors: two getters that may be read, one event and one accept that must not
local larry = node("Larry", "Folder", {
    node("FNCGetOrderProgress", "RemoteFunction", nil, {
        _answer = { Order1 = { Crop = "Tomato", Wanted = 240, Reward = 3200 } },
    }),
    node("FNCGetAvailableBoxes", "RemoteFunction", nil, { _answer = {} }),
    node("EVTRefreshOrders", "RemoteEvent"),
    node("FNCAcceptOrder", "RemoteFunction", nil, { _throws = "want an order id" }),
})
local growCfg = node("CropGrowthConfigClient", "ModuleScript")
local mods = node("Modules", "Folder", { larry, growCfg })
local repl = node("ReplicatedStorage", "Folder", { mods })
game = { GetService = function(_, n) if n == "ReplicatedStorage" then return repl end end }

-- the live shape this build answers with (v1.124 read GetConfig/SetConfig off the
-- same module): a table of per-crop tables AND a getter
local CONFIG = {
    Tomato = { GrowTime = 900 },
    Wheat = { GrowTime = 600 },
    GetConfig = function() return { Tomato = { GrowTime = 900 }, Count = 2 } end,
}
require = function(m)
    if m.Name == "CropGrowthConfigClient" then return CONFIG end
    error("unexpected require of " .. tostring(m.Name))
end

spudSeedPrices = { tomato = 140, wheat = 100 }
COINS = 54159
"""

FIXTURE_BARE = r"""
-- nothing order-named anywhere, no Larry, no config module, no remembered price
local mods = node("Modules", "Folder", {})
local repl = node("ReplicatedStorage", "Folder", { mods })
workspace = node("Workspace", "Workspace", {
    node("Objects", "Folder", { node("Fields", "Folder", { node("Field", "Model") }) }),
})
LocalPlayer = node("Miou", "Player", {
    node("PlayerGui", "PlayerGui", {
        node("HUD", "ScreenGui", { label("L", "fps 24") }),
    }),
})
game = { GetService = function(_, n) if n == "ReplicatedStorage" then return repl end end }
require = function() error("nothing to require") end
spudSeedPrices = {}
COINS = 700
"""

FIXTURE_BALANCE = r"""
-- a getter that TAKES money: the balance read before/after is the only proof
workspace = node("Workspace", "Workspace", {
    node("Orders", "Folder", {
        node("Order1", "Folder", { node("Crop", "StringValue", nil, { Value = "Wheat" }) }),
    }),
})
LocalPlayer = node("Miou", "Player", { node("PlayerGui", "PlayerGui", {}) })
local getter = node("FNCGetOrderProgress", "RemoteFunction")
function getter:InvokeServer(...)
    INVOKED[#INVOKED + 1] = self.Name
    COINS = COINS + 50
    return { paid = true }
end
local mods = node("Modules", "Folder", { node("Larry", "Folder", { getter }) })
local repl = node("ReplicatedStorage", "Folder", { mods })
game = { GetService = function(_, n) if n == "ReplicatedStorage" then return repl end end }
require = function() error("nothing") end
spudSeedPrices = {}
COINS = 500
"""


def build(fixture: str) -> str:
    return (COMMON.replace("--[[NAMEKEY]]", NAME_KEY)
                  .replace("--[[FIXTURE]]", fixture)
                  .replace("__BODY__", ORDERS))


def run(exe: pathlib.Path, fixture: str, label_: str):
    with tempfile.NamedTemporaryFile("w", suffix=".lua", delete=False, encoding="utf-8") as fh:
        fh.write(build(fixture))
        path = fh.name
    out = subprocess.run([str(exe), path], capture_output=True, encoding="utf-8", errors="replace")
    os.unlink(path)
    text = out.stdout
    if out.returncode != 0:
        print(f"{label_}: the harness itself did not run")
        print(text.strip()[-1500:])
        print(out.stderr.strip()[-1500:])
        return None
    return text


def says_of(text: str) -> str:
    return "\n".join(line[4:] for line in text.splitlines() if line.startswith("SAY "))


def main() -> int:
    base = pathlib.Path(os.environ.get("LOCALAPPDATA", ".")) / "Temp" / "opencode" / "luau"
    exe = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else base / "luau.exe"

    fails = 0

    def check(label_, ok, detail=""):
        nonlocal fails
        if not ok:
            fails += 1
        print(f"{label_:<58} {'PASS' if ok else 'FAIL'}" + (f"  [{detail}]" if detail and not ok else ""))

    # ── source ties: the leg must stay a reader ──────────────────────────────
    banned = ["FireServer", "pressKey", "setkeypress", "Mouse", "PivotTo", "CFrame",
              "Teleport", "HookFunction", "getrawmetatable", "hookmetamethod", "SetPrimaryPartCFrame"]
    hits = [b for b in banned if b in ORDERS]
    check("the orders leg mentions no write (no fire/key/move)", not hits, str(hits))
    check("names are folded by the game's own rule, not a new one", "spudNameKey(" in ORDERS)
    check("the walk names its own CAP when it is reached", "CAP 20000 REACHED" in ORDERS)
    check("an empty world walk is never called \"no orders\"",
          "that is not " in ORDERS and "no orders" in ORDERS)
    check("the getter list is a FNCGet allow-list, not every RemoteFunction",
          '"FNCGetOrderProgress"' in ORDERS and '"FNCGetAvailableBoxes"' in ORDERS
          and "FNCAcceptOrder" not in ORDERS and "EVTRefreshOrders" not in ORDERS)
    check("a moved balance is called out as a write", "the balance MOVED" in ORDERS)
    check("an unreadable grow time is named, not guessed",
          "NO client-side grow time is readable" in ORDERS)
    check("it recurses whether or not a node matched",
          "if why then" in ORDERS and "if depth < 8 then walk(c" in ORDERS)

    # ── RUN A: a world that does have orders ─────────────────────────────────
    rich = run(exe, FIXTURE_RICH, "rich") or ""
    says, ledger = says_of(rich), next((l for l in rich.splitlines() if l.startswith("LEDGER ")), "")

    check("the run itself never errors", "RUN OK" in rich, rich.strip()[-400:])
    check("the order folder is found and its full path printed",
          "Workspace.Company.Orders.Order1" in says)
    check("it recurses INTO an order-named parent (the deal is named)",
          "Order1.Deal.Crop" in says and "Tomato" in says)
    check("the wanted count and the reward are dumped",
          "Deal.Wanted" in says and "240" in says and "Deal.Coins" in says and "3200" in says)
    check("the attribute of a hit is printed, not skipped", "Order=Tomato" in says)
    check("it says which word matched", 'matched "order"' in says or 'matched "company"' in says)
    check("a descendant list over the cap is admitted", "more descendants on this one" in says)
    check("only 14 hits are printed and the rest is counted",
          "more order-named instance(s) not shown" in says)
    check("a ScreenGui board is read from PlayerGui, not only the world",
          "Company Orders — deliver 240 Tomato" in says)
    check("a label that says nothing about orders is not reported", "hello there" not in says)
    check("the door inventory lists each door with its real class",
          "FNCGetOrderProgress [RemoteFunction]" in says
          and "EVTRefreshOrders [RemoteEvent]" in says)
    check("the getter answer is dumped, two levels deep",
          ".Order1.Crop=Tomato" in says and "Wanted=240" in says)
    check("an empty table from a getter is an answer, not a failure",
          "it answered an EMPTY table" in says)
    check("a grow time the client CAN read is printed with its number",
          "GrowTime" in says and "900" in says)
    check("the remembered shelf prices come back in the report",
          "shelf price remembered: tomato = 140" in says)
    check("only the two FNCGet* doors were called",
          "invoked=[FNCGetOrderProgress,FNCGetAvailableBoxes]" in ledger, ledger)
    check("NOTHING was ever fired at the server", "fired=0" in ledger, ledger)
    check("no key press and no move came from the probe",
          "keys=0" in ledger and "moved=0" in ledger, ledger)

    # ── RUN B: a world with nothing order-named ──────────────────────────────
    bare = run(exe, FIXTURE_BARE, "bare") or ""
    bsays = says_of(bare)
    check("an empty world answers without erroring", "RUN OK" in bare, bare.strip()[-400:])
    check("0 order-named instances is stated as a count",
          "0 instance(s) in the streamed world named like an order" in bsays)
    check("… and never as \"the game has no orders\" (rule 7)",
          'that is not "no orders"' in bsays and "the board is elsewhere" in bsays)
    check("no board on screen is named as not-on-screen",
          "the board is not on screen from here" in bsays)
    check("no doors is a count, not a guess", "0 order/task/goal/box door(s)" in bsays)
    check("a getter this build does not have is reported, not called",
          "is not a RemoteFunction in this build" in bsays)
    check("no readable grow time is said out loud", "NO client-side grow time is readable" in bsays)
    check("no remembered price is said out loud too", "no shelf price read yet this build" in bsays)
    check("the bare world still costs no call", "fired=0 invoked=[]" in bare, bare[-200:])

    # ── RUN C: a getter that takes money ─────────────────────────────────────
    bal = says_of(run(exe, FIXTURE_BALANCE, "balance") or "")
    check("a getter that moved the wallet is caught in the same report",
          "the balance MOVED on a getter" in bal and "coins 500 → 550" in bal, bal[-300:])

    if fails:
        print(f"\n{fails} FAILED")
        return 1
    print("\nALL OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
