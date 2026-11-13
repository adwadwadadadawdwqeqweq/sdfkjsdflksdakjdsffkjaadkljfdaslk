"""Run the REAL auto-contract chooser on a fake Company board.

Owner 2026-11-12: "we need to find a way to make auto contracts for seeds", and
when asked whether the script should also answer the Company back: *"only steer
what is planted for now"*. So this feature READS one door — `FNCGetCompany()` —
and turns the answer into the next seed. It accepts no order, claims nothing and
fires nothing else, and the harness is the thing that keeps that promise.

What is pinned here is the part a live run cannot show in one glance: WHICH order
wins, and what the chooser refuses to guess.

  * the board is the door's answer, not a walk — §3.18 walked 20 004 world nodes
    and 386 PlayerGui labels and found no order-shaped instance anywhere, so a
    reader that looked in `workspace` would find nothing and call it "no orders"
    (rule 7). The live answer is `.activeOrders.<n>{product,total,deposited,
    progress,completed,claimed}`, read off this client on 2026-11-05;
  * a `product` the seed list has no name for is skipped AND NAMED. The only
    sample that read ever printed was `EggBox`, which no field grows, so the
    crop vocabulary is the genuinely unknown half of this feature;
  * "easiest" is `units owed × the crate price the shelf last showed`. Time left
    the ranking when v1.124 proved a `Seeded` cell cuts and pays — with early
    harvest on, no crop is slower than another. An unpriced crop is ranked after
    the priced ones rather than mixed into a number that would silently favour
    whichever shop visit happened first;
  * a crop this run cannot afford is skipped for a cheaper one — the owner's
    "if it dont got enough money to buy 1 single seed mox it skips", using the
    SAME predicate the shop trip itself gates on (`spudSeedPriceBlocks`), so the
    chooser and the trip can never disagree about what the wallet covers;
  * a name matched only as a prefix counts when exactly one seed starts that way,
    and two candidates is a refusal, not a coin flip.

    python tools/1000042.py [path-to-luau.exe]
"""

import os
import pathlib
import re
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "1000051.lua"
SRC_TEXT = SRC.read_text(encoding="utf-8")

WANTED = ["spudNameKey", "spudSeedPriceBlocks", "spudContractPick",
          "spudCompanyBoard", "spudContractSteer"]


def extract(text: str, name: str) -> str:
    m = re.search(r"^    (?:local )?function " + name + r"\(", text, re.M)
    if not m:
        return ""
    tail = text[m.start():]
    end = re.search(r"\n    (?:local function |function |-- )", tail[10:])
    block = tail[: end.start() + 10] if end else tail
    return "\n".join(l[4:] if l.startswith("    ") else l for l in block.splitlines())


# the state block, verbatim, so a shape change here is this harness's problem
STATE = re.search(r"^    spudContract = \{.*?^    spudContractTtl = \d+$",
                  SRC_TEXT, re.M | re.S).group(0)
STATE = "\n".join(l[4:] if l.startswith("    ") else l for l in STATE.splitlines())

PRE = r"""
-- ── the fake world ─────────────────────────────────────────────────────────
-- One clock for the whole harness: `os.clock` is the ONLY thing the deadline and
-- the cache read, so "never parked on" and "once a minute" are testable numbers
-- instead of a promise about wall time.
CLOCK = 1000
local realOS = os
os = setmetatable({ clock = function() return CLOCK end }, { __index = realOS })
task = {
    spawn = function(f) coroutine.resume(coroutine.create(f)) end,
    wait = function() CLOCK = CLOCK + 0.05 end,
}

LOGGED, INVOKED = {}, {}
function log(s) LOGGED[#LOGGED + 1] = tostring(s) end
function coinBalance() return BALANCE end

-- the kit seam: 1000010.py owns "does the door resolve", this owns what the
-- build does once it has it
KIT = nil
function spudEquipRemoteKit() return KIT end
function spudEquipRemoteResolve(key) return KIT and KIT[key] or nil end

local function door(answer, throws, never)
    return { remote = { InvokeServer = function()
        INVOKED[#INVOKED + 1] = "FNCGetCompany"
        if never then coroutine.yield() end
        if throws then error(throws) end
        return answer
    end }, method = "InvokeServer" }
end

-- the game's own seed vocabulary, the way FieldHelper.SEED_TYPE hands it over
SEEDS = { "Wheat", "Corn", "Rice", "Soybean", "Tomato", "Sugar Cane", "Cocoa" }
seedIdOf = {}
for _, n in ipairs(SEEDS) do seedIdOf[n] = #seedIdOf + 1 end

local function board(t)
    return { ordersShipped = 12, activeOrders = t }
end

--[[STATE]]

local fails = 0
local function check(name, ok, detail)
    if not ok then fails = fails + 1 end
    print(string.format("%-58s %s%s", name, ok and "PASS" or "not passing",
        detail and ("  " .. detail) or ""))
end
local function saysWith(word)
    for _, l in ipairs(LOGGED) do if l:find(word, 1, true) then return true end end
    return false
end
"""

POST = r"""
-- ══ 1. the board as it was actually read (2026-11-05) ══════════════════════
spudSeedPrices = { wheat = 120 }
BALANCE = 900000
local r = spudContractPick(
    board({ [1] = { product = "EggBox", total = 750, deposited = 0, progress = 255 } }),
    SEEDS, spudSeedPrices, BALANCE, nil)
check("a board of one non-crop order steers nothing", r.seed == nil, tostring(r.seed))
check("… and the non-crop is NAMED, not swallowed", r.skipped == "EggBox", r.skipped)
check("… with the reason it chose nothing", r.why == "no open order is a crop this run can afford"
    or r.why == "the board holds no open order", r.why)

r = spudContractPick(board({
    [1] = { product = "Wheat", total = 750, deposited = 255 },
    [2] = { product = "EggBox", total = 900, deposited = 0 },
}), SEEDS, spudSeedPrices, BALANCE, nil)
check("the crop order wins and the EggBox is still reported",
    r.seed == "Wheat" and r.skipped == "EggBox", tostring(r.seed) .. " / " .. r.skipped)
check("the owed count is total minus what is already in",
    r.open:find("495 owed", 1, true) ~= nil, r.open)

-- ══ 2. cheapest to FINISH, not smallest order, not the old two-key sort ═════
spudSeedPrices = { wheat = 120, corn = 900 }
r = spudContractPick(board({
    [1] = { product = "Wheat", total = 500, deposited = 0 },   -- 60 000
    [2] = { product = "Corn", total = 60, deposited = 0 },     -- 54 000
}), SEEDS, spudSeedPrices, BALANCE, nil)
check("a big cheap order beats a small dear one", r.seed == "Corn", tostring(r.seed))
check("  the log line says which order and what it costs",
    r.why:find("Corn, 60 owed at 900 a crate", 1, true) ~= nil, r.why)

-- a price is only known for a crate the run has stood next to: unpriced crops
-- are ranked AFTER priced ones, never on a made-up number
r = spudContractPick(board({
    [1] = { product = "Rice", total = 5, deposited = 0 },      -- no price read
    [2] = { product = "Wheat", total = 500, deposited = 0 },   -- 60 000, priced
}), SEEDS, spudSeedPrices, BALANCE, nil)
check("an unpriced crop never outranks a priced one", r.seed == "Wheat", tostring(r.seed))
check("  and it is still offered, named as unpriced",
    r.open:find("Rice 5 owed (no shelf price read)", 1, true) ~= nil, r.open)

spudSeedPrices = {}
r = spudContractPick(board({
    [1] = { product = "Wheat", total = 500, deposited = 0 },
    [2] = { product = "Rice", total = 40, deposited = 0 },
}), SEEDS, spudSeedPrices, BALANCE, nil)
check("with no shelf price read at all it ranks on units left",
    r.seed == "Rice", tostring(r.seed))
check("  and says the price is what it did not have",
    r.why:find("no shelf price read yet", 1, true) ~= nil, r.why)

-- ══ 3. the owner's money rule: skip dear, take the next ════════════════════
spudSeedPrices = { wheat = 120, corn = 900 }
BALANCE = 500
r = spudContractPick(board({
    [1] = { product = "Corn", total = 10, deposited = 0 },
    [2] = { product = "Wheat", total = 400, deposited = 0 },
}), SEEDS, spudSeedPrices, BALANCE, nil)
check("a crate the wallet cannot buy is skipped for a cheaper one",
    r.seed == "Wheat", tostring(r.seed))
check("  the dear one is reported with its reason",
    r.skipped:find("crate costs more than the wallet", 1, true) ~= nil, r.skipped)
BALANCE = 100
r = spudContractPick(board({
    [1] = { product = "Corn", total = 10, deposited = 0 },
    [2] = { product = "Wheat", total = 10, deposited = 0 },
}), SEEDS, spudSeedPrices, BALANCE, nil)
check("nothing affordable is nothing steered, with no seed invented",
    r.seed == nil and r.why == "no open order is a crop this run can afford", r.why)

-- ══ 4. what is NOT an open order ═══════════════════════════════════════════
r = spudContractPick(board({
    [1] = { product = "Wheat", total = 100, deposited = 100 },
    [2] = { product = "Corn", total = 100, deposited = 40, completed = true },
    [3] = { product = "Rice", total = 100, deposited = 40, claimed = true },
    [4] = "not even a table",
}), SEEDS, { wheat = 1, corn = 1, rice = 1 }, 999999, nil)
check("filled, completed, claimed and junk are none of them orders",
    r.seed == nil and r.why == "the board holds no open order", r.why)
r = spudContractPick(board({}), SEEDS, {}, 999999, nil)
check("an empty board is an answer, not a fault",
    r.seed == nil and r.why == "the board holds no open order", r.why)
r = spudContractPick({ ordersShipped = 3 }, SEEDS, {}, 999999, nil)
check("a board with no activeOrders names the half that is missing",
    r.why == "the board carries no activeOrders", r.why)
r = spudContractPick(nil, SEEDS, {}, 999999, nil)
check("no answer at all is called that", r.why == "the Company gave no board", r.why)
r = spudContractPick(board({ [1] = { product = "Wheat", total = 9, deposited = 0 } }),
    {}, {}, 999999, nil)
check("no seed list means no decision (FieldHelper unreadable)",
    r.seed == nil and r.why == "no seed list was read from the game", r.why)

-- ══ 5. names: the board's word against the game's vocabulary ═══════════════
r = spudContractPick(board({ [1] = { product = "tomatoes", total = 50, deposited = 0 } }),
    SEEDS, {}, 999999, nil)
check("a plural and a case change are still the same crop", r.seed == "Tomato", tostring(r.seed))
r = spudContractPick(board({ [1] = { product = "Sugar", total = 50, deposited = 0 } }),
    SEEDS, {}, 999999, nil)
check("a board word that starts a seed's name takes it when it is alone",
    r.seed == "Sugar Cane", tostring(r.seed))
r = spudContractPick(board({ [1] = { product = "Be", total = 50, deposited = 0 } }),
    { "Bean", "Beet" }, {}, 999999, nil)
check("a short word is never guessed at", r.seed == nil, tostring(r.seed))
r = spudContractPick(board({ [1] = { product = "Corn", total = 50, deposited = 0 } }),
    { "CornSeed", "CornHub" }, {}, 999999, nil)
check("two seeds behind one prefix is a refusal, not a coin flip",
    r.seed == nil, tostring(r.seed))

-- ══ 6. anti-churn: the crop already chosen stays if the Company wants it ═══
spudSeedPrices = { wheat = 120, corn = 900 }
BALANCE = 900000
r = spudContractPick(board({
    [1] = { product = "Wheat", total = 10, deposited = 0 },    -- cheaper
    [2] = { product = "Corn", total = 400, deposited = 0 },
}), SEEDS, spudSeedPrices, BALANCE, "Corn")
check("a crop with an open order is kept even when another is cheaper",
    r.seed == "Corn" and r.why:find("kept Corn", 1, true) ~= nil, r.why)
r = spudContractPick(board({ [1] = { product = "Wheat", total = 10, deposited = 0 } }),
    SEEDS, spudSeedPrices, BALANCE, "Cocoa")
check("a crop nobody ordered is switched", r.seed == "Wheat", tostring(r.seed))

-- ══ 7. the read: bounded, and it says which half broke ═════════════════════
local b, why = spudCompanyBoard()
check("no door in this build is named as no door",
    b == nil and why == "no FNCGetCompany door in this build", tostring(why))
KIT = { company = door(board({ [1] = { product = "Wheat", total = 5, deposited = 0 } })) }
b = spudCompanyBoard()
check("an answering door gives the board back", type(b) == "table" and b.activeOrders ~= nil)
KIT = { company = door(nil) }
b, why = spudCompanyBoard()
check("a door answering nothing is called nothing", b == nil and why:find("answered nothing", 1, true) ~= nil, tostring(why))
KIT = { company = door(nil, "want a farm slot") }
b, why = spudCompanyBoard()
check("a refusal prints the server's own words", b == nil and why:find("want a farm slot", 1, true) ~= nil, tostring(why))
KIT = { company = door(nil, nil, true) }
INVOKED = {}
b, why = spudCompanyBoard()
check("a door that never replies costs the run its budget and no more",
    b == nil and why:find("never answered", 1, true) ~= nil, tostring(why))
check("  the wait is bounded by the constant, not by the server",
    why:find(tostring(spudContractWait), 1, true) ~= nil, tostring(why))

-- ══ 8. the cache: once a minute, and one line per read ═════════════════════
KIT = { company = door(board({ [1] = { product = "Wheat", total = 500, deposited = 0 } })) }
spudSeedPrices = { wheat = 120 }
seedIdOf = {}
for _, n in ipairs(SEEDS) do seedIdOf[n] = n end
LOGGED, INVOKED = {}, {}
spudContract.at, spudContract.seed, spudContract.survey = nil, nil, nil
local s1 = spudContractSteer(nil)
CLOCK = CLOCK + 5
local s2 = spudContractSteer(nil)
check("the first ask reads the board and the next one does not",
    s1 == "Wheat" and s2 == "Wheat" and #INVOKED == 1, "invoked " .. #INVOKED)
check("a fresh read is its verdict plus the board it saw", #LOGGED == 2, tostring(#LOGGED))
CLOCK = CLOCK + spudContractTtl
local s3 = spudContractSteer(nil)
check("a minute later it asks again", s3 == "Wheat" and #INVOKED == 2, "invoked " .. #INVOKED)
check("the same board is not re-printed every minute", #LOGGED == 3, tostring(#LOGGED))

-- the survey comes back when the board actually moved
KIT = { company = door(board({
    [1] = { product = "Wheat", total = 500, deposited = 0 },
    [2] = { product = "EggBox", total = 90, deposited = 0 },
})) }
CLOCK = CLOCK + spudContractTtl
spudContractSteer(nil)
check("a board that moved is named again", #LOGGED == 6 and saysWith("contracts skipped"), tostring(#LOGGED))
check("the non-crop reaches the log, not only the return value",
    saysWith("EggBox"), LOGGED[#LOGGED])

-- a read that stops working stops steering
spudContract.at = nil
KIT = { company = door(nil, "gone") }
s1 = spudContractSteer("Wheat")
check("a board that goes away stops the steer and says so",
    s1 == nil and saysWith("refused"), tostring(s1))
check("  and the run keeps the dropdown's seed (logged, not silent)",
    saysWith("planting the Farm tab"), "")

print(fails == 0 and "ALL OK" or (fails .. " CHECKS FAILED"))
if fails > 0 then realOS.exit(1) end
"""


def main() -> int:
    base = pathlib.Path(os.environ.get("LOCALAPPDATA", ".")) / "Temp" / "opencode" / "luau"
    exe = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else base / "luau.exe"

    fails: list[str] = []

    def tie(pattern: str, why: str, present: bool = True) -> None:
        found = re.search(pattern, SRC_TEXT, re.M) is not None
        if found == present:
            print(f"{why:<58} PASS")
        else:
            fails.append(why)

    parts = [PRE.replace("--[[STATE]]", STATE)]
    for name in WANTED:
        code = extract(SRC_TEXT, name)
        if not code:
            print("missing " + name)
            return 2
        parts.append(code)
    parts.append(POST)

    pick = extract(SRC_TEXT, "spudContractPick")
    board_read = extract(SRC_TEXT, "spudCompanyBoard")
    steer = extract(SRC_TEXT, "spudContractSteer")

    # ── the scope the owner set: read the board, write nothing else ──────────
    for needle, why in (
        ("Accept", "no order is accepted"),
        ("Claim", "no order is claimed"),
        ("Refresh", "no board is refreshed on the server"),
        ("FireServer", "no RemoteEvent is fired"),
        ("pressKey", "no key is pressed"),
        ("PivotTo", "nothing is teleported"),
        ("Mouse", "no control is clicked"),
    ):
        blob = board_read + "\n" + steer + "\n" + pick
        if needle in blob:
            fails.append(why + f" — `{needle}` appears in the contract code")
        else:
            print(f"{why:<58} PASS")

    # ── one door, and it is the one that was actually read live ──────────────
    tie(r'company = \{ "FNCGetCompany", "InvokeServer" \}',
        "the board is one getter on Modules.Larry")
    if board_read.count("InvokeServer") != 1:
        fails.append("spudCompanyBoard invokes " + str(board_read.count("InvokeServer"))
                     + " time(s) — one door call per read is the whole design")

    # ── the deadline and the cache are the two things that protect the loop ──
    if "os.clock() < deadline" not in board_read:
        fails.append("the board read lost its deadline — a door that never replies "
                     "would park the planting loop")
    else:
        print(f"{'the read is bounded by a deadline, not by the server':<58} PASS")
    if "task.spawn" not in board_read:
        fails.append("the read is no longer on its own thread, so a blocking "
                     "InvokeServer still parks the caller")
    tie(r"if st\.at and now - st\.at <", "a board read is cached, not asked per tick")

    # ── the steer reaches the ONLY place a seed is chosen ────────────────────
    tie(r"if spudAutoContracts then", "the switch decides whether the board is asked")
    tie(r"local plantSeed = seedChoice", "the dropdown is the default it falls back to")
    trip = SRC_TEXT[SRC_TEXT.index("local plantSeed = seedChoice"):]
    trip = trip[:trip.index("\n    local function seedHitchStep")]
    if trip.count("buySeedAndFill(plantSeed)") != 2:
        fails.append("the trip buys plantSeed " + str(trip.count("buySeedAndFill(plantSeed)"))
                     + " time(s) — the fill-to-the-top loop must not go back to town "
                     "for the dropdown's seed")
    else:
        print(f"{'both the first trip and every refill buy the steered seed':<58} PASS")
    if "buySeedAndFill(seedChoice)" in trip:
        fails.append("a buy of seedChoice survived inside the steered trip")
    if "spudSavedContracts" not in SRC_TEXT:
        fails.append("the pick is not remembered across a reload")
    tie(r'spudAutoContracts = \(spudSavedContracts == true\)',
        "auto contracts start OFF: a fresh build never changes the crop by itself")

    # ── the two honesty rules this feature lives or dies on ──────────────────
    if "no shelf price read" not in pick:
        fails.append("an unpriced crop no longer says it was ranked on units alone")
    if "skipped" not in steer or 'log("contracts skipped' not in steer:
        fails.append("a non-crop order is dropped in silence instead of named")

    lua = "\n\n".join(parts) + "\n"
    with tempfile.NamedTemporaryFile("w", suffix=".lua", delete=False,
                                     encoding="utf-8") as fh:
        fh.write(lua)
        path = fh.name
    try:
        out = subprocess.run([str(exe), path], capture_output=True,
                             encoding="utf-8", errors="replace")
        print(out.stdout.strip())
        if out.returncode != 0:
            print(out.stderr.strip()[-1500:])
        for f in fails:
            print("CHECK FAILED  " + f)
        if fails:
            return 1
        return out.returncode
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
