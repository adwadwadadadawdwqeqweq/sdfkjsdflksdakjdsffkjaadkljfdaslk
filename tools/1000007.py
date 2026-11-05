"""The early cut: a Seeded cell is a harvest target (grownStage / whichNeed).

Proven live by Tests → Grow now on v1.124:

    test: growth: early cut — Seeded → Empty, tank 0 → 1 — TAKEN AND IT PAID

The harvest call does not want a ripe crop, so the growth wait is a choice.
With `spudEarlyCut` on, a Seeded cell counts as a standing crop in every place
the harvest job decides — the census, the cell ids, the field tour and the
growth wait all read the SAME predicate, so they cannot disagree about what
"cuttable" means. That agreement is what this pins, plus the bounds the pick
must not break:

  * with the pick OFF the behaviour is exactly the old one (unknown stage =
    standing, the four known stages = not);
  * a failed or 0-cell read stays UNKNOWN (owner rule 7), pick or no pick;
  * the other jobs aim at their own stage name and are not moved by the pick;
  * the growth wait restarts on a cuttable field but stops restarting when the
    restarts take nothing (spudCutWatch), so a blocked harvester cannot spin.

    python tools/1000007.py [path-to-luau.exe]
"""

import os
import pathlib
import re
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "1000051.lua"

# KNOWN_STAGES + grownStage + whichNeed are one block, and they only mean
# something together: whichNeed sums through grownStage, so slicing one of them
# out alone would test a copy instead of the real decision.
START = "    local KNOWN_STAGES = {"
STOP = "    -- world points of the cells still needing"


def extract_block(text: str) -> str:
    a, b = text.find(START), text.find(STOP)
    if a < 0 or b < 0 or b <= a:
        return ""
    body = text[a:b]
    return "\n".join(line[4:] if line.startswith("    ") else line
                     for line in body.splitlines())


PRE = "spudEarlyCut = false\n\n"

POST = r"""
local fails = 0
local function check(name, ok, detail)
    if not ok then fails = fails + 1 end
    print(string.format("%-56s %s%s", name, ok and "PASS" or "FAIL",
        detail and ("  " .. detail) or ""))
end

local HARVEST = { grown = true, verb = "harvest" }
local SEEDJOB = { stage = "Cultivated", verb = "seed" }
local PLOWJOB = { stage = "Empty", verb = "plow" }

-- ── 1. the pick off is the old behaviour, exactly ──────────────────────────
spudEarlyCut = false
local seeded50 = { total = 50, Cultivated = 0, Seeded = 50 }
check("off: a Seeded cell is not standing", whichNeed(HARVEST, seeded50) == 0,
    tostring(whichNeed(HARVEST, seeded50)))
check("off: grownStage(Seeded) is false", grownStage("Seeded") == false)
check("off: an unknown stage stands", grownStage("Harvestable") == true)
for _, s in ipairs({ "Empty", "Plowed", "Cultivated" }) do
    check("off: grownStage(" .. s .. ") is false", grownStage(s) == false)
end

-- ── 2. the pick on makes a planted cell a crop to cut ──────────────────────
spudEarlyCut = true
check("on: all 50 Seeded cells read cuttable", whichNeed(HARVEST, seeded50) == 50,
    tostring(whichNeed(HARVEST, seeded50)))
check("on: grownStage(Seeded) is true", grownStage("Seeded") == true)
check("on: bare/plowed/cultivated still are not standing",
    grownStage("Empty") == false and grownStage("Plowed") == false
    and grownStage("Cultivated") == false)

-- ── 3. a mixed field counts what the predicate says, both ways ─────────────
local mix = { total = 50, Empty = 10, Plowed = 10, Cultivated = 10,
              Seeded = 10, Harvestable = 10 }
spudEarlyCut = false
check("off: only the ripe column stands", whichNeed(HARVEST, mix) == 10,
    tostring(whichNeed(HARVEST, mix)))
spudEarlyCut = true
check("on: Seeded + ripe both stand", whichNeed(HARVEST, mix) == 20,
    tostring(whichNeed(HARVEST, mix)))

-- ── 4. the other jobs are untouched by the pick ────────────────────────────
for _, on in ipairs({ false, true }) do
    spudEarlyCut = on
    check("seed job still aims at Cultivated (cut=" .. tostring(on) .. ")",
        whichNeed(SEEDJOB, mix) == 10, tostring(whichNeed(SEEDJOB, mix)))
    check("plow job still aims at Empty (cut=" .. tostring(on) .. ")",
        whichNeed(PLOWJOB, mix) == 10, tostring(whichNeed(PLOWJOB, mix)))
end

-- ── 5. unreadable is not empty (owner rule 7), pick or no pick ─────────────
spudEarlyCut = true
check("a failed read is still unknown", whichNeed(HARVEST, nil) == nil)
check("a 0-cell read is still unknown", whichNeed(HARVEST, { total = 0 }) == nil)
-- the old harvest count was `total minus the four known names`, which threw on a
-- table with no total; summing the names it does have cannot.
check("a stage table without total sums what it can see",
    whichNeed(HARVEST, { Seeded = 3 }) == 3, tostring(whichNeed(HARVEST, { Seeded = 3 })))

-- ── 6. the census column is named for the pick it ran under ────────────────
spudEarlyCut = true
check("on: the label the census uses is cuttable",
    (spudEarlyCut and "cuttable" or "standing") == "cuttable")
spudEarlyCut = false
check("off: the label the census uses is standing",
    (spudEarlyCut and "cuttable" or "standing") == "standing")

print(fails == 0 and "ALL OK" or (fails .. " FAILED"))
"""


def main() -> int:
    base = pathlib.Path(os.environ.get("LOCALAPPDATA", ".")) / "Temp" / "opencode" / "luau"
    exe = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else base / "luau.exe"
    src = SRC.read_text(encoding="utf-8")
    block = extract_block(src)
    if not block:
        print("missing the KNOWN_STAGES/grownStage/whichNeed block")
        return 2

    # ── source ties: the places that must consult the one predicate ────────
    ties = [
        ("the pick defaults on and is remembered",
         r"spudEarlyCut = \(spudSavedEarlyCut == nil\) or \(spudSavedEarlyCut == true\)"),
        ("the wait restarts on a cuttable field",
         r"if spudEarlyCut and grown > 0 then"),
        ("the wait says why it is not waiting",
         r"early cut: %d cell\(s\) are cuttable now — restarting the loop instead of waiting"),
        ("the restart is bounded so a blocked harvester cannot spin",
         r"if spudCutWatch.stuck < 2 then"),
        ("the bound is kept across waits (a global, not a per-call local)",
         r"spudCutWatch = \{ left = nil, stuck = 0 \}"),
        ("the census names the column for the pick",
         r'spudEarlyCut and "cuttable" or "standing"'),
        ("every harvest id list goes through grownStage",
         r"job\.grown and grownStage or job\.stage"),
        ("the Settings toggle carries the title only (rule 1)",
         r'Title = "Early harvest",'),
        ("the toggle remembers the pick across a reload",
         r"spudSavedEarlyCut = spudEarlyCut"),
        ("Get coords logs what it read",
         r'log\("coords: " \.\. text'),
        ("Get coords copies it",
         r"setclipboard\(text\)"),
        ("Get coords says so when the copy is refused",
         r"the copy was refused"),
    ]
    bad = [name for name, pat in ties if not re.search(pat, src, re.M)]
    print("source ties: %d/%d" % (len(ties) - len(bad), len(ties)))
    for name in bad:
        print("FAIL tie missing: " + name)

    with tempfile.NamedTemporaryFile("w", suffix=".lua", delete=False, encoding="utf-8") as fh:
        fh.write(PRE + block + "\n" + POST)
        path = fh.name
    try:
        out = subprocess.run([str(exe), path], capture_output=True, encoding="utf-8",
                             errors="replace")
        print(out.stdout.strip())
        if out.returncode != 0:
            print(out.stderr.strip()[-1500:])
        return out.returncode if out.returncode == 0 and not bad else (out.returncode or 1)
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
