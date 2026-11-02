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
Two rules are pinned here:

  * a crate that READS zero seeds is not seed - an empty box cannot fill a
    seeder, and using one burns the trip. A crate that cannot be read at all
    is still used (owner rule 7: unreadable is not empty);
  * the seed pass promises "refill 1/3", so a run must be able to make more
    than one shop trip. The old once-per-run boolean made refills 2 and 3
    unreachable dead code;
  * a price learned standing at the shelf is remembered, so a seed that costs
    more than the balance cannot cost a second 1,000-stud hop to town. The
    balance is re-read every time, so the cache remembers the PRICE and never
    the verdict.

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
          "spudSeedPriceBlocks"]


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

    # the numbers must agree with what the seed pass PROMISES in its own log
    # line ("refill 1/3"): the run has to afford the entry trip plus the refills.
    cap = re.search(r"if refills >= (\d+) then", src)
    declared = re.search(r"^    (?:local )?spudSeedTripsMax = (\d+)", src, re.M)
    fails = []
    if not cap:
        fails.append("the seed pass no longer caps its refills - the tie is unmeasurable")
    else:
        refill_cap = int(cap.group(1))
        if not declared:
            fails.append("spudSeedTripsMax is missing")
        else:
            trips = int(declared.group(1))
            if trips < refill_cap + 1:
                fails.append(f"spudSeedTripsMax={trips} cannot reach refill {refill_cap}/"
                             f"{refill_cap} (needs at least {refill_cap + 1} trips)")
            else:
                print(f"{'run trips cover the refill promise':<56} PASS  "
                      f"{trips} trips vs {refill_cap} refills")
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

    # ... and consulted in seedCheck BEFORE the run commits a trip.
    sc = re.search(r"^    local function seedCheck\(", src, re.M)
    body = ""
    if sc:
        rest = src[sc.start():]
        e = re.search(r"\n    (?:local function |function )", rest[10:])
        body = rest[: e.start() + 10] if e else rest
    if not body:
        fails.append("seedCheck was not found - the price gate cannot be placed")
    elif "spudSeedPriceBlocks" not in body:
        fails.append("seedCheck does not consult spudSeedPriceBlocks - "
                     "an unaffordable seed still hops to town every trip")
    elif body.index("spudSeedPriceBlocks") > body.index("spudSeedTripAllowed"):
        fails.append("the price gate runs after the trip is already counted - "
                     "it costs a trip to be refused")
    else:
        print(f"{'the price is checked before the trip is spent':<56} PASS")

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
