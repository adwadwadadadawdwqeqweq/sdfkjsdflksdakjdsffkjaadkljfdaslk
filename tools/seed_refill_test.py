"""The seed trip must not spend its only shop visit on a crate with no seeds.

Reported: "some times it missed some tiles while seeding and it fuckes the
whole thing up". The live console (v1.115) shows the chain:

  the seeder is empty — going to buy Wheat (50 cell(s) need seed right now)
  seed crate: you already own a Wheat crate 80 studs away — using it instead of buying one
  ✅ seeder now holds 23/50 seeds (Wheat)          <- the crate was HALF empty
  remote seed: fired 23 of 50 ... 23 took, 27 left
  seeder EMPTY with 27 cell(s) ... refill 1/3: buying Wheat and filling
  the seeder is still empty and the shop was already tried this run — not teleporting again
  the refill put no seeds in the seeder — stopping this pass

So 27 tiles stayed unseeded for the whole growth cycle, and the run ended.
Three rules are pinned here:

  * a crate that READS zero seeds is not seed - an empty box cannot fill a
    seeder, and using one burns the trip. A crate that cannot be read at all
    is still used (owner rule 7: unreadable is not empty);
  * the trip budget is a COUNT, and since v1.133 it is the TANK'S arithmetic:
    "if a seeder has like 600 capasity, make it fill up the seeder fully" →
    "fill to max, trips scales to fix. by the way you can carry to seed crates
    at once". A 600-slot seeder with 50-seed crates needs twelve crates, two a
    trip, six town visits — the constant 4 silently called that "loaded" at
    200/600;
  * a price learned standing at the shelf is remembered, so a seed that costs
    more than the balance cannot cost a second 1,000-stud hop to town. The
    balance is re-read every time, so the cache remembers the PRICE and never
    the verdict;
  * and the TANK SIZE is remembered too (owner 2026-11-03: *"when it puts seeds
    back in the seeder it isnt filling it up to 600 only about 100"*). The live
    console had both halves of the lie on screen at once:

        ✅ seeder now holds 50/600 seeds (Rice)      <- one crate, tank hungry
        seeder EMPTY with ... refill 1/6: buying Rice and filling
        the seeder is still empty and this run already made 4 shop trip(s) (the cap is 4)

    `refill 1/6` and `the cap is 4` are the same machine read twice: the 6 comes
    from a read that returned MaxCapacity 600, the 4 from one that returned nil.
    An unreadable cap is `nil` trips and `spudSeedTripCeiling` answers nil with
    the floor — so a 600-slot tank was planned as a 50-slot one. A cap this
    build has ever READ is what the next plan uses, and the line says
    "(the cap read from earlier this build)" rather than pretending a failed
    read answered 600 (rule 7).

    python tools/seed_refill_test.py [path-to-luau.exe]
"""

import os
import pathlib
import re
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "SpudFarm_Full.lua"

WANTED = ["spudCrateSeedCount", "spudCrateHasSeed", "spudSeedTripAllowed",
          "spudSeedPriceBlocks", "spudSeedTripsNeeded", "spudSeedTripCeiling",
          "spudSeederWantsMore", "spudCratesInHand", "spudSeederCapFor",
          "spudCratesTripActual", "spudCrateSize"]


def extract(text: str, name: str) -> str:
    m = re.search(r"^    (?:local )?function " + name + r"\(", text, re.M)
    if not m:
        return ""
    tail = text[m.start():]
    end = re.search(r"\n    (?:local function |function |-- )", tail[10:])
    block = tail[: end.start() + 10] if end else tail
    return "\n".join(l[4:] if l.startswith("    ") else l for l in block.splitlines())


def block_of(text: str, pattern: str) -> str:
    """A 4-space function's body, up to the next definition or comment block."""
    m = re.search(pattern, text, re.M)
    if not m:
        return ""
    rest = text[m.start():]
    e = re.search(r"\n    (?:local function |function |-- )", rest[10:])
    return rest[: e.start() + 10] if e else rest


def region(text: str, start: str, end: str) -> str:
    """From one marker to the next — for a function nested inside another."""
    a = text.find(start)
    if a < 0:
        return ""
    b = text.find(end, a + len(start))
    return text[a:b] if b > a else text[a:]


PRE = r"""
local logs = {}
function log(msg) logs[#logs + 1] = tostring(msg) end
task = task or {}
task.wait = function(_) end

local function newInst(name, class)
    local o = { Name = name, ClassName = class, kids = {} }
    function o:IsA(c) return self.ClassName == c end
    function o:FindFirstChild(n)
        for _, k in ipairs(self.kids) do
            if k.Name == n then return k end
        end
        return nil
    end
    return o
end

-- a crate model with a Configurations.Capacity of `value` (nil = no such field)
local function crateWith(value, class)
    local m = newInst("SeedBox", "Model")
    if value == "noconf" then return m end
    local conf = newInst("Configurations", "Folder")
    conf.Parent = m
    m.kids[#m.kids + 1] = conf
    if value ~= "nocap" then
        local cap = newInst("Capacity", class or "IntValue")
        cap.Value = value
        cap.Parent = conf
        conf.kids[#conf.kids + 1] = cap
    end
    return m
end

-- the game's carry rig: CarryLinks holds ONE child per item in hand
LocalPlayer = { Character = nil }
local function setCratesInHand(n)
    local links = { Name = "CarryLinks", n = n }
    function links:GetChildren()
        local t = {}
        for _ = 1, self.n do t[#t + 1] = { Name = "Link" .. _ } end
        return t
    end
    local ch = { Name = "Character" }
    function ch:FindFirstChild(nm)
        if nm == "CarryLinks" then return links end
        return nil
    end
    LocalPlayer.Character = ch
end
"""

POST = r"""
local fails = 0
local function check(name, ok, detail)
    if not ok then fails = fails + 1 end
    print(string.format("%-56s %s%s", name, ok and "PASS" or "FAIL",
        detail and ("  " .. detail) or ""))
end

-- ── 1. what a crate actually holds is readable, and unreadable is nil ──────
check("a full crate reads its seed count", spudCrateSeedCount(crateWith(50)) == 50,
    tostring(spudCrateSeedCount(crateWith(50))))
check("a half crate reads 23", spudCrateSeedCount(crateWith(23)) == 23)
check("an empty crate reads 0, not nil", spudCrateSeedCount(crateWith(0)) == 0,
    tostring(spudCrateSeedCount(crateWith(0))))
check("no Configurations folder is unreadable", spudCrateSeedCount(crateWith("noconf")) == nil)
check("no Capacity value is unreadable", spudCrateSeedCount(crateWith("nocap")) == nil)
check("a Capacity that is not an IntValue is unreadable",
    spudCrateSeedCount(crateWith("50", "StringValue")) == nil)
check("a nil model does not crash", spudCrateSeedCount(nil) == nil)

-- ── 2. unreadable is not empty (owner rule 7) ─────────────────────────────
check("a crate holding 50 seeds is usable", spudCrateHasSeed(50) == true)
check("a crate holding 23 seeds is usable", spudCrateHasSeed(23) == true)
check("a crate holding 0 seeds is NOT usable", spudCrateHasSeed(0) == false)
check("a crate holding -1 is not usable", spudCrateHasSeed(-1) == false)
check("an unreadable crate is still usable", spudCrateHasSeed(nil) == true)

-- ── 3. the trip budget is a count, not a once-per-run latch ───────────────
check("trip 1 of 4 is allowed", spudSeedTripAllowed(0, 4) == true)
check("trip 4 of 4 is allowed", spudSeedTripAllowed(3, 4) == true)
check("trip 5 is refused", spudSeedTripAllowed(4, 4) == false)
check("a runaway count is refused", spudSeedTripAllowed(9, 4) == false)
check("no trips left at all is refused", spudSeedTripAllowed(0, 0) == false)
check("a missing count still gets its trips", spudSeedTripAllowed(nil, 4) == true)

-- ── 4. a price read in town is reused before the next hop ──────────────────
local prices = { cabbage = 57600, wheat = 100 }
check("a seed with no cached price is not blocked",
    spudSeedPriceBlocks(prices, "Carrot", 54159) == false)
check("a seed cheaper than the balance is not blocked",
    spudSeedPriceBlocks(prices, "Wheat", 54159) == false)
check("a seed costing exactly the balance is payable",
    spudSeedPriceBlocks({ corn = 54159 }, "Corn", 54159) == false)
check("a seed dearer than the balance is blocked",
    spudSeedPriceBlocks(prices, "Cabbage", 54159) == true)
check("an unreadable balance never blocks",
    spudSeedPriceBlocks(prices, "Cabbage", nil) == false)
check("an unreadable cached price never blocks",
    spudSeedPriceBlocks({ cabbage = nil }, "Cabbage", 54159) == false)
check("no price table at all never blocks",
    spudSeedPriceBlocks(nil, "Cabbage", 54159) == false)
check("another seed's price does not block this one",
    spudSeedPriceBlocks(prices, "Cabbage", 90000) == false)
check("the seed name is matched case-insensitively",
    spudSeedPriceBlocks(prices, "cabbage", 54159) == true)
check("a nil seed name never blocks", spudSeedPriceBlocks(prices, nil, 54159) == false)

-- ── 5. the trip count is the TANK's arithmetic (600-slot seeder) ───────────
-- 600 slots, an empty seeder, a crate that gives 50, two crates a trip:
-- twelve crates is six town visits, and the constant 4 was a quarter of a fill.
check("600 empty slots need 6 trips at 2 crates of 50",
    spudSeedTripsNeeded(600, 0, 50, 2) == 6, tostring(spudSeedTripsNeeded(600, 0, 50, 2)))
check("a 50-slot seeder still needs 1 trip", spudSeedTripsNeeded(50, 0, 50, 2) == 1)
check("the room left is what counts, not the capacity",
    spudSeedTripsNeeded(600, 550, 50, 2) == 1, tostring(spudSeedTripsNeeded(600, 550, 50, 2)))
check("600 with 300 in needs 3 trips", spudSeedTripsNeeded(600, 300, 50, 2) == 3)
check("a partial crate rounds UP, never down",
    spudSeedTripsNeeded(600, 560, 50, 2) == 1, tostring(spudSeedTripsNeeded(600, 560, 50, 2)))
check("a full seeder needs no trip", spudSeedTripsNeeded(600, 600, 50, 2) == 0)
check("an over-full read is not a trip", spudSeedTripsNeeded(600, 640, 50, 2) == 0)
check("one crate a trip doubles the visits",
    spudSeedTripsNeeded(600, 0, 50, 1) == 12, tostring(spudSeedTripsNeeded(600, 0, 50, 1)))
check("a nil crates-per-trip means one", spudSeedTripsNeeded(600, 0, 50, nil) == 12)
check("a zero crates-per-trip is clamped to one",
    spudSeedTripsNeeded(600, 0, 50, 0) == 12, tostring(spudSeedTripsNeeded(600, 0, 50, 0)))
check("a nil crate size is UNKNOWN, not one trip",
    spudSeedTripsNeeded(600, 0, nil, 2) == nil)
check("a nil capacity is unknown", spudSeedTripsNeeded(nil, 0, 50, 2) == nil)
check("a zero capacity is unknown, not free", spudSeedTripsNeeded(0, 0, 50, 2) == nil)
check("a zero crate size is unknown", spudSeedTripsNeeded(600, 0, 0, 2) == nil)
check("no 'have' reading is treated as empty",
    spudSeedTripsNeeded(600, nil, 50, 2) == 6, tostring(spudSeedTripsNeeded(600, nil, 50, 2)))
check("a 600-seed crate fills it in one trip",
    spudSeedTripsNeeded(600, 0, 600, 2) == 1)

-- ── 5b. THE CRATE'S OWN NUMBER IS THE SIZE, not a pour's rise (live 2026-11-04)
--   The console taught this one the hard way: a two-crate trip raised the seeder
--   by 100 (`402/600` → `502/600` → `600/600`) and the build wrote down
--   `99 seed(s) a crate`, because the carry folder read ONE box. Every plan then
--   halved — 803 cells came out as `the cap is 5` after six trips had already
--   been spent, so the run refused to teleport and ended
--   `shop trip: the seeder is empty` with 803 cells unplanted.
check("a crate that can speak is the size — 50, not the 99 the rise taught",
    spudCrateSize(50, 99) == 50, tostring(spudCrateSize(50, 99)))
check("the crate's own number may CORRECT a bad lesson, up or down",
    spudCrateSize(50, 400) == 50, tostring(spudCrateSize(50, 400)))
check("a silent crate keeps what a pour taught", spudCrateSize(nil, 50) == 50)
check("an empty crate (0) is not a crate SIZE", spudCrateSize(0, 50) == 50)
check("a negative read is not a size", spudCrateSize(-50, 50) == 50)
check("neither read is unknown, never a guessed 50", spudCrateSize(nil, nil) == nil)
check("a numeric string still sizes a crate", spudCrateSize("50", nil) == 50)
-- the arithmetic the wrong size broke, written as the two plans:
check("803 cells at a 50-seed crate are NINE visits — the truth",
    spudSeedTripsNeeded(803, 0, 50, 2) == 9, tostring(spudSeedTripsNeeded(803, 0, 50, 2)))
check("the same field on the 99-seed lesson is the live cap of 5",
    spudSeedTripsNeeded(803, 0, 99, 2) == 5, tostring(spudSeedTripsNeeded(803, 0, 99, 2)))
check("so the wrong size is what refused the six already-made trips",
    spudSeedTripCeiling(spudSeedTripsNeeded(803, 0, 99, 2), 4) == 5
    and spudSeedTripCeiling(spudSeedTripsNeeded(803, 0, 50, 2), 4) == 9)

-- ── 6. the ceiling is the promise OR the work, whichever is bigger ─────────
check("an unknown crate size keeps the old 4", spudSeedTripCeiling(nil, 4) == 4)
check("6 trips raises the ceiling to 6", spudSeedTripCeiling(6, 4) == 6)
check("a 1-trip tank never LOWERS the 4", spudSeedTripCeiling(1, 4) == 4)
check("0 trips needed keeps the floor", spudSeedTripCeiling(0, 4) == 4)
check("no floor and no need is no trips", spudSeedTripCeiling(nil, nil) == 0)
check("a numeric string is still a number", spudSeedTripCeiling("6", 4) == 6)

-- ── 7. "is there room?" only answers for a readable pair ───────────────────
check("50 of 600 still wants seed", spudSeederWantsMore(50, 600) == true)
check("599 of 600 still wants seed", spudSeederWantsMore(599, 600) == true)
check("600 of 600 is full", spudSeederWantsMore(600, 600) == false)
check("more than the cap is full", spudSeederWantsMore(601, 600) == false)
check("no count read is NOT 'room left'", spudSeederWantsMore(nil, 600) == false)
check("no cap read is NOT 'room left'", spudSeederWantsMore(50, nil) == false)
check("a zero cap is unknown, not hungry", spudSeederWantsMore(0, 0) == false)

-- ── 8. the carry rig counts CRATES, which carrying() cannot ────────────────
setCratesInHand(0)
check("empty hands read 0 crates", spudCratesInHand() == 0)
setCratesInHand(1)
check("one crate reads 1", spudCratesInHand() == 1)
setCratesInHand(2)
check("two crates read 2", spudCratesInHand() == 2, tostring(spudCratesInHand()))
LocalPlayer.Character = nil
check("no character is 0 crates, not a crash", spudCratesInHand() == 0)
setCratesInHand(0)
local noLinks = { Name = "Character" }
function noLinks:FindFirstChild(_) return nil end
LocalPlayer.Character = noLinks
check("no CarryLinks folder is 0 crates", spudCratesInHand() == 0)

-- ── 9. the tank size a trip PLANS ON survives a failed read ────────────────
-- 600 read once is 600 for the build. The owner's "only about 100" is the
-- second half of this: a nil cap is nil trips is the floor of 4 (or 3), and a
-- 600-slot tank planned at the floor gets one crate's worth and is called loaded.
check("a readable cap is the plan", spudSeederCapFor(600, 600) == 600)
check("a fresh read wins over a remembered one",
    spudSeederCapFor(50, 600) == 50, tostring(spudSeederCapFor(50, 600)))
check("a failed read falls back to the remembered cap",
    spudSeederCapFor(nil, 600) == 600)
local planCap, planVia = spudSeederCapFor(nil, 600)
check("and SAYS it remembered", planCap == 600 and planVia == "remembered")
local freshCap, freshVia = spudSeederCapFor(600, 600)
check("a fresh read says nothing about remembering",
    freshCap == 600 and freshVia == nil)
check("a zero cap is not a cap", spudSeederCapFor(0, 600) == 600)
check("a negative cap is not a cap", spudSeederCapFor(-5, 600) == 600)
check("a cap string is still a number", spudSeederCapFor("600", nil) == 600)
local noneCap, noneVia = spudSeederCapFor(nil, nil)
check("neither read is unknown, not one trip", noneCap == nil and noneVia == nil)
check("an unknown remembered cap is not a cap either",
    spudSeederCapFor(nil, 0) == nil)
-- ── 9b. the plan uses the crates a trip ACTUALLY carried out of town ──────
-- The till is ASKED for two crates a visit. Live 2026-11-03 the second one
-- never lands — `seed crate: the second purchase did not land — putting the
-- crates back down and picking up only the one that is paid for` — so a 600
-- tank planned at 2 crates a trip gets 6 visits x 50 seeds = 300 and the
-- owner sees "only about 100" per trip. The plan reads what was bought.
spudCratesPerTrip = 2
spudCratesTripGot = nil
check("no trip finished yet: the ask stands", spudCratesTripActual() == 2)
spudCratesTripGot = 1
check("a one-crate trip plans on one crate", spudCratesTripActual() == 1)
spudCratesTripGot = 2
check("a two-crate trip plans on two", spudCratesTripActual() == 2)
spudCratesTripGot = 5
check("an over-reported delivery is not believed past the ask",
    spudCratesTripActual() == 2, tostring(spudCratesTripActual()))
spudCratesTripGot = 0
check("zero is not a delivery", spudCratesTripActual() == 2)
spudCratesTripGot = -1
check("a negative is not a delivery", spudCratesTripActual() == 2)
spudCratesTripGot = "2"
check("a string count is still a count", spudCratesTripActual() == 2)
spudCratesTripGot = nil
check("and unknown is the ask again, not one", spudCratesTripActual() == 2)
-- the arithmetic the owner's complaint turns on: 600 empty, 50 a crate.
spudCratesTripGot = 1
check("a one-crate till needs TWELVE visits, not six",
    spudSeedTripsNeeded(600, 0, 50, spudCratesTripActual()) == 12,
    tostring(spudSeedTripsNeeded(600, 0, 50, spudCratesTripActual())))
check("and the ceiling raises the floor to that",
    spudSeedTripCeiling(
        spudSeedTripsNeeded(600, 0, 50, spudCratesTripActual()), 4) == 12)
spudCratesTripGot = 2
check("a two-crate till still needs six",
    spudSeedTripsNeeded(600, 0, 50, spudCratesTripActual()) == 6)
-- ── 9c. the crate size is per CRATE, not per PRESS (v1.145) ───────────────
-- Live: the seeder read 1 seed, ONE FNCFillSeeder call ran, no pour round
-- followed, and the tank read 101/600 — the call drained both crates in hand.
-- Learning the crate size from that rise teaches 100, and a 499-seed shortfall
-- then plans 3 visits (3 x 2 x 100) when the game sells 50 a crate: the owner's
-- "still only putting 100 seeds in" is this arithmetic stopping early.
check("the same shortfall with a 50-seed crate needs FIVE visits",
    spudSeedTripsNeeded(600, 101, 50, 2) == 5,
    tostring(spudSeedTripsNeeded(600, 101, 50, 2)))
check("the two-crate rise read as one crate is the defect",
    spudSeedTripsNeeded(600, 101, 100, 2) == 3,
    tostring(spudSeedTripsNeeded(600, 101, 100, 2)))
check("and 5 visits x 2 crates x 50 really does cover the tank",
    5 * 2 * 50 >= 600 - 101)
check("3 visits x 2 crates x 50 does NOT - it stops at 401",
    101 + 3 * 2 * 50 < 600)
-- ── 9d. the FIELD sizes the budget, not the tank (v1.150) ─────────────────
-- Live: a 2400-cell field, a 600-slot tank, six trips planned to fill the
-- machine — and after those six visits the run had seeded 600 cells and every
-- later refill was refused by its own ceiling. The budget has to cover the
-- cells that need seed, which is four tanks, not one.
check("a 2400-cell field needs TWENTY-FOUR visits at 2 crates of 50",
    spudSeedTripsNeeded(2400, 0, 50, 2) == 24,
    tostring(spudSeedTripsNeeded(2400, 0, 50, 2)))
check("one tank's plan is the defect that left 1800 cells cultivated",
    spudSeedTripsNeeded(600, 0, 50, 2) == 6)
check("so the field number is the one that must win",
    spudSeedTripsNeeded(2400, 0, 50, 2) > spudSeedTripsNeeded(600, 0, 50, 2))
check("and the ceiling raises to it, never lowers",
    spudSeedTripCeiling(math.max(6, spudSeedTripsNeeded(2400, 0, 50, 2)), 4) == 24)
check("an unreadable field is unknown, not one visit",
    spudSeedTripsNeeded(nil, 0, 50, 2) == nil)
spudCratesPerTrip = 1
spudCratesTripGot = 2
check("a stray count never exceeds what the build asks the till for",
    spudCratesTripActual() == 1)
spudCratesPerTrip = 2
spudCratesTripGot = nil
-- the whole point: the plan feeds the trip arithmetic, so a tank that streams
-- badly still gets the visits its REAL size needs.
check("the remembered cap still sizes six trips",
    spudSeedTripsNeeded(spudSeederCapFor(nil, 600), 0, 50, 2) == 6,
    tostring(spudSeedTripsNeeded(spudSeederCapFor(nil, 600), 0, 50, 2)))
check("planning on unknown collapses to the floor - the defect",
    spudSeedTripCeiling(spudSeedTripsNeeded(nil, 0, 50, 2), 4) == 4
    and spudSeedTripCeiling(spudSeedTripsNeeded(600, 0, 50, 2), 4) == 6)

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

    # The refill ceiling used to be the literal 3 written into the loop. It is
    # now the same helper the trip gate uses, with 3 as its FLOOR — so a 50-seed
    # seeder behaves exactly as before and a 600-slot one gets its six trips.
    rm = re.search(r"local refillsMax = spudSeedTripCeiling\(([\s\S]{0,400}?)\n\s*while true do", src)
    if not rm:
        fails.append("seedPasses no longer scales its refill ceiling - the "
                     "600-slot seeder is back to three refills")
    else:
        inner = rm.group(1).strip()
        if "spudSeedTripsNeeded(" not in inner:
            fails.append("the refill ceiling does not come from "
                         "spudSeedTripsNeeded - it is a constant again")
        floor = re.search(r",\s*(\d+)\)\s*$", inner)
        if not floor:
            fails.append("the refill ceiling has no floor - an unreadable "
                         "seeder would get zero refills")
        else:
            floor_n = int(floor.group(1))
            if re.search(r"if refills >= refillsMax then", src) is None:
                fails.append("the refill loop no longer compares against "
                             "refillsMax - the ceiling is computed and ignored")
            else:
                print(f"{'the refill ceiling scales to the tank':<56} PASS  "
                      f"{floor_n} as the floor")
            # the run's trip budget must still be able to REACH that floor:
            # the entry trip plus `floor` refills.
            declared = re.search(r"^    (?:local )?spudSeedTripsMax = (\d+)", src, re.M)
            if not declared:
                fails.append("spudSeedTripsMax is missing")
            elif int(declared.group(1)) < floor_n + 1:
                fails.append(f"spudSeedTripsMax={declared.group(1)} cannot reach "
                             f"refill {floor_n}/{floor_n} (needs at least "
                             f"{floor_n + 1} trips)")
            else:
                print(f"{'run trips cover the refill promise':<56} PASS  "
                      f"{declared.group(1)} trips vs {floor_n} refills")

    if re.search(r"\bseedShopTried\b", src):
        fails.append("seedShopTried is still there - the once-per-run latch is the bug")
    else:
        print(f"{'no once-per-run shop latch left':<56} PASS")

    # the price has to be RECORDED where the shelf reads it, or the gate below
    # never has anything to work from.
    if re.search(r"spudSeedPrices\[", src):
        print(f"{'the shelf price is remembered':<56} PASS")
    else:
        fails.append("the crate price is never cached - the gate has nothing to read")

    # ... and consulted in seedCheck BEFORE the run commits a trip, and the
    # scaled ceiling must be what the trip gate compares against.
    body = block_of(src, r"^    local function seedCheck\(")
    if not body:
        fails.append("seedCheck was not found - the gates cannot be placed")
    else:
        for need, why in (("spudSeedPriceBlocks",
                           "seedCheck does not consult spudSeedPriceBlocks - "
                           "an unaffordable seed still hops to town every trip"),
                          ("spudSeedTripsNeeded",
                           "seedCheck does not size the trips to the tank - a "
                           "600-slot seeder is refused after the constant 4"),
                          ("spudSeedTripCeiling",
                           "seedCheck does not raise its own ceiling from the "
                           "arithmetic - spudSeedTripsNeeded alone changes nothing")):
            if need not in body:
                fails.append(why)
        if "spudSeedTripAllowed(seedShopTries, spudSeedTripsMax)" in body:
            fails.append("seedCheck still compares against the constant - the "
                         "scaled ceiling is computed and thrown away")
        elif "spudSeedTripAllowed(seedShopTries, tripsCeiling)" not in body:
            fails.append("seedCheck does not hand the scaled ceiling to "
                         "spudSeedTripAllowed")
        else:
            print(f"{'the trip gate reads the scaled ceiling':<56} PASS")
        if "spudSeedPriceBlocks" in body and "spudSeedTripAllowed" in body:
            if body.index("spudSeedPriceBlocks") > body.index("spudSeedTripAllowed"):
                fails.append("the price gate runs after the trip is already counted - "
                             "it costs a trip to be refused")
            else:
                print(f"{'the price is checked before the trip is spent':<56} PASS")

    # The pour is a LOOP now: one press is one crate and the tank may want
    # twelve. It must stop on a readable-full seeder, on empty hands, and on a
    # round that moved nothing - never on a guessed number of presses.
    fill = region(src, "local function seedCrateIntoSeeder(crate)",
                  "-- ▸ NEVER BUY A SEED THAT IS ALREADY IN HAND")
    if not fill:
        fails.append("seedCrateIntoSeeder was not found - the fill loop cannot be checked")
    else:
        for need, why in (("while rounds <",
                           "the pour is a single press again - the seeder is "
                           "called loaded at one crate's worth"),
                          ("spudSeederWantsMore",
                           "the pour loop does not ask the seeder if it still "
                           "has room - it would press V into a full tank"),
                          ("spudCratesInHand() > 0",
                           "the pour loop does not check the hands - it would "
                           "press at an empty box until the loop ran out")):
            if need not in fill:
                fails.append(why)
        if all(n in fill for n in ("while rounds <", "spudSeederWantsMore",
                                   "spudCratesInHand() > 0")):
            print(f"{'the fill pours to the machine\'s own cap':<56} PASS")

    # The crate size must be LEARNED from a rise, never guessed: a guessed 50
    # would size every trip ceiling for a crate the game may have filled with 12.
    # And since v1.145 the rise is divided by the crates the call CONSUMED —
    # live, one FNCFillSeeder drained both crates in hand (1 seed -> 101/600,
    # no pour round at all), so the raw rise taught the build that a 50-seed
    # crate holds 100, and every tank was planned at half the visits it needs.
    if re.search(r"spudSeedsPerCrate = \d", src):
        fails.append("spudSeedsPerCrate is given a literal number - the crate "
                     "size is guessed, not measured")
    elif re.search(r"spudSeedsPerCrate = gave2?\b", src):
        fails.append("the crate size is learned from the WHOLE rise again - one "
                     "FNCFillSeeder empties every crate in hand, so a two-crate "
                     "pour teaches 100 and the trip ceiling halves")
    elif "local own = crate and spudCrateSeedCount(crate) or nil" not in src or \
            "spudCrateSize(own, math.floor(gave / ate))" not in src:
        fails.append("the crate is never ASKED its own size - live 2026-11-04 a "
                     "two-crate trip whose carry folder read ONE box taught "
                     "`99 seed(s) a crate`, and 803 cells came out as a cap of 5 "
                     "visits after six had already been spent")
    elif "spudSeedsPerCrate = size" not in src or \
            "spudSeedsPerCrate = perCrate2" not in src:
        fails.append("a pour site no longer records the crate size it read")
    elif src.count("local hand0 = spudCratesInHand()") + \
            src.count("local beforeHand = spudCratesInHand()") < 2:
        fails.append("the pour does not count the crates it consumed - the "
                     "divider is a guess")
    else:
        print(f"{'the crate is asked first; a rise only fills a silence':<56} PASS")

    # A second crate is proven by the CarryLinks COUNT, and an unpaid one is
    # put back down - carrying() is already true with the first one in hand.
    if "spudCratesInHand() > links0" not in src:
        fails.append("the second carry is not proven by the link count - "
                     "carrying() cannot tell crate 2 from crate 1")
    else:
        print(f"{'the second crate is proven by CarryLinks':<56} PASS")
    second = src[src.find("the second purchase did not land"):] if \
        "the second purchase did not land" in src else ""
    if not second:
        fails.append("there is no unpaid-crate path - a refused second buy "
                     "would leave a shelf crate in hand")
    elif "spudDropRemote()" not in second[:1500]:
        fails.append("the unpaid crate is never put back down - the fill leg "
                     "would pour a box the till never sold")
    else:
        print(f"{'an unpaid crate goes back down':<56} PASS")
    if not re.search(r"while extraCrates < math\.max\(0, \(tonumber\(spudCratesPerTrip\)", src):
        fails.append("the second-crate loop is not driven by spudCratesPerTrip - "
                     "the owner's 'two crates at once' is hardcoded or gone")
    else:
        print(f"{'crates a trip is one setting':<56} PASS")

    # The held-crate short-circuit must prefer a crate that still HAS seed, not
    # merely the right kind (v1.116's half-poured box).
    if "spudCrateHasSeed(heldCount)" not in src:
        fails.append("the held-crate scan no longer checks what the box holds - "
                     "an empty crate is still 'seed'")
    else:
        print(f"{'a held crate is checked for seed':<56} PASS")

    # The cap has to be REMEMBERED at the one place it is read, and every plan
    # site has to read it back through the one helper. A plan computed from a
    # raw `cap` is the 4-vs-6 lie again, one call site at a time.
    if "spudSeederCap = cap" not in src:
        fails.append("the seeder's MaxCapacity is never remembered - a nil read "
                     "on the next pass is still an unknown tank")
    elif not re.search(r"if cap and cap > 0 then spudSeederCap = cap end", src):
        fails.append("the remembered cap is written unconditionally - a zero/nil "
                     "read would wipe the 600 it already saw")
    else:
        print(f"{'the read cap is remembered, a failed read is not':<56} PASS")
    for need, why in (
        ("spudSeederCapFor(cap, spudSeederCap)",
         "seedCheck's trip gate plans on the raw read again - an unreadable cap "
         "is '4 trips' for a 600-slot tank"),
        ("spudSeederCapFor(fillCap, spudSeederCap)",
         "the refill ceiling plans on the raw read again - `refill 1/6` beside "
         "`the cap is 4` is exactly this call site"),
    ):
        if need not in src:
            fails.append(why)
    if "spudSeederCapFor(cap, spudSeederCap)" in src and \
            "spudSeederCapFor(fillCap, spudSeederCap)" in src:
        print(f"{'both trip ceilings plan on the remembered cap':<56} PASS")

    # And the pour loop must SAY when the hands run dry on a hungry tank, rather
    # than logging "✅ seeder now holds 50/600" as though that were loaded.
    if "the hands are empty and the tank still wants" not in src:
        fails.append("a pour that stops on empty hands is not named - 50/600 is "
                     "still reported as a loaded seeder")
    elif "spudSeedTripsNeeded(capFor, n1" not in src:
        fails.append("the stop line does not do the town-visit arithmetic - it "
                     "says the tank is hungry without naming what would fill it")
    else:
        print(f"{'a short pour names the visits it still needs':<56} PASS")

    # ── v1.144: the visits are planned on the crates a trip ACTUALLY bought.
    # The till is asked for two and live answers with one, so a plan built on
    # the ASK under-counts the trips by exactly half (6 visits x 50 = 300 into
    # a 600 tank). Every plan site reads the helper; the ask stays only where
    # the run asks the till for a second crate.
    if "spudCratesTripGot = 1 + extraCrates" not in src:
        fails.append("the trip never records how many crates it bought - the "
                     "ceiling is still planned on the two-crate ask")
    elif len(re.findall(r"spudCratesTripActual\(\)", src)) < 4:
        fails.append("a plan site still passes spudCratesPerTrip to the trip "
                     "arithmetic - a one-crate till gets half the visits it needs")
    elif not re.search(r"while extraCrates < math\.max\(0, \(tonumber\(spudCratesPerTrip\)", src):
        fails.append("the second-crate loop no longer asks the till for the "
                     "constant - spudCratesTripGot is a result, not a request")
    else:
        print(f"{'the visit budget plans on crates actually bought':<56} PASS")

    # ── v1.148: FILL TO MAX BEFORE PLANTING (owner: "it should fill untill max
    # or there is not mroe moeny"). Two separate ways the build used to start
    # planting with a partly-full tank: it returned true on ANY seed in the
    # machine, and it made ONE town trip for an empty one and went anyway.
    check_region = region(src, "local function seedCheck(", "local function seedHitchStep(")
    if "local hungry = allowBuy and cap and cap > 0" not in check_region:
        fails.append("a seeder holding any seed is still 'full enough' — the "
                     "48/600 tank goes to the field and plants 48 cells")
    elif "spudSeederWantsMore(count, cap)" not in check_region:
        fails.append("the planting-stage check never asks the machine whether "
                     "it still reads room")
    elif "while bought and not stopping() do" not in check_region:
        fails.append("the trip is still a one-shot — an empty tank buys one "
                     "crate and goes planting instead of filling to the cap")
    elif check_region.count("seedShopTries += 1") < 2:
        fails.append("the fill loop does not count its own trips — the ceiling "
                     "cannot stop it and the wallet is hammered instead")
    elif "bought = buySeedAndFill(seedChoice)" not in check_region:
        fails.append("the fill loop does not re-run the proven trip — it would "
                     "loop on a read that never changes")
    else:
        print(f"{'the tank is filled to max before the field, or until the money stops':<56} PASS")

    # ── v1.150: the FIELD sizes the trip budget, not the tank. A 600-slot
    # machine needs six visits and a 2400-cell field needs twenty-four; planning
    # on the tank is what left `1800 cultivated, 600 seeded` and a run that
    # refused every later refill with its own ceiling.
    if "spudSeedTripsNeeded(needCells, 0," not in check_region:
        fails.append("the entry budget is still planned on one tank — the run "
                     "spends six visits on 600 cells of a 2400-cell field")
    elif "refillsMax = spudSeedTripCeiling(math.max(refillsMax," not in src:
        fails.append("the refill rounds never re-size the budget from the cells "
                     "still standing — the pass ends with 1800 cultivated cells")
    elif "for %s cell(s)" not in src:
        fails.append("the refusal line still names only the tank it planned on — "
                     "the number that grew is the field's, and it must say so")
    else:
        print(f"{'the trip budget is sized by the field, at both sites':<56} PASS")
    if re.search(r"after = after or coinBalance\(\)", src):
        fails.append("the purchase line still reports the FIRST balance read — "
                     "the HUD counter animates, so 129026 → 87069 was printed "
                     "for a buy that really left 9026")
    elif "local settled = coinBalance()" not in src:
        fails.append("no settled balance is read after a confirmed buy — the "
                     "report is a frame of the animation, not the wallet")
    else:
        print(f"{'the buy line reports the settled balance':<56} PASS")

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
