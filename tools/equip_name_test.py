"""The game writes display names the model names do not have — and the script
compared them with ==.

Reported live (v1.134 console, 2026-11-03), one run, three symptoms, one cause:

  equipment manager: looking for 'TempoL16' — 2 card(s) showing right now: KADL · Tempo L16
  equipment manager: no card for TempoL16 — it is not among the cards listed above
  ✅ seeder hitched — staying hitched
  hitch target: TempoL16 (31 studs, by EquipmentType Planter)
  a different tool is hitched (Tempo L16) — unhitching it first

The planter's MODEL is TempoL16. Its card and its HUD slot both read
"Tempo L16" — a space the model name has no. So:

  * the Equipment Manager refused a card it had just listed, and every spawn
    that fell through to the UI gave up ("the Equipment Manager wouldn't drive
    for this vehicle");
  * the wrong-tool guard pressed X against the implement this very pass had
    just hitched, then had to re-hitch it — and on the respawned instance,
    creep-align from 1,120 studs for nothing;
  * the stale-label check `folder:FindFirstChild("Tempo L16")` found no model,
    so a stored implement kept reporting itself as attached;
  * the park pass compared the same two strings, so a tool under the hitch was
    not recognised and got stored from under it.

One key fixes all four: a serial suffix (`#9`) out, every non-letter-and-digit
out, lowercased. The card match stays a PREFIX match on that key, so a card
that merely mentions a name still cannot win.

The same run also had the ride answer `tractor=none` on a machine that had
answered `HitchRoot` minutes earlier (and `plow=none` on one that had answered
`Hitch`), so the line-up lost its only measurement and the creep took over. Two
things pin that here: the game's own socket pair — `Components.Hitchable` on the
ride, `Chassis.HitchableSocket` on the tool, the exact instances the captured
FNCAttemptHitch takes — is the second source, and the refusal now names the
model and how much of it the client actually has (rule 7: name what is
unreadable instead of guessing past it).

    python tools/equip_name_test.py [path-to-luau.exe]
"""

import os
import pathlib
import re
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "SpudFarm_Full.lua"

WANTED = ["spudNameKey", "spudSameEquipName"]

POST = r"""
local fails = 0
local function check(name, ok, detail)
    if not ok then fails = fails + 1 end
    print(string.format("%-58s %s%s", name, ok and "PASS" or "FAIL",
        detail and ("  " .. detail) or ""))
end

-- the model name and the label the game draws are ONE machine
check("Tempo L16 and TempoL16 are one key",
    spudNameKey("Tempo L16") == "tempol16" and spudNameKey("TempoL16") == "tempol16",
    spudNameKey("Tempo L16"))
check("a serial suffix is not part of the name",
    spudNameKey("ZM80\n#9") == "zm80", spudNameKey("ZM80\n#9"))
check("spaced multi-word names fold together",
    spudNameKey("Horsch Joker 30 MT") == spudNameKey("HorschJoker30MT"),
    spudNameKey("Horsch Joker 30 MT"))
check("a hyphen or a dot is not a different machine",
    spudNameKey("KQF-3000") == spudNameKey("KQF3000"), spudNameKey("KQF-3000"))
-- the digits ARE the machine: a key that strips them (the %A class) would fold
-- TempoL16 and TempoL20 into one, and a build would park a card on the wrong rig.
check("digits survive the fold — L16 and L20 are not one key",
    spudNameKey("TempoL16") == "tempol16"
    and spudSameEquipName("Tempo L16", "TempoL20") == false,
    spudNameKey("Tempo L16"))

check("same name, spaced or not",
    spudSameEquipName("Tempo L16", "TempoL16") == true
    and spudSameEquipName("TempoL16", "Tempo L16") == true)
check("different machines never match",
    spudSameEquipName("KADL", "TempoL16") == false
    and spudSameEquipName("S4204", "KQF3000") == false)
check("a card that only mentions the name is not a prefix match",
    spudNameKey("My Trailer Box"):sub(1, #spudNameKey("Trailer")) ~= spudNameKey("Trailer"))
check("the card match itself still wins on a real card",
    spudNameKey("Tempo L16\n#3"):sub(1, #spudNameKey("TempoL16")) == spudNameKey("TempoL16"))

-- nothing is ever "the same" because both sides read empty
check("empty and nil never match anything",
    spudSameEquipName("", "") == false
    and spudSameEquipName(nil, "KADL") == false
    and spudSameEquipName("   ", "") == false)
check("a label of only punctuation has no key", spudNameKey("—/#") == "", spudNameKey("—/#"))

print(fails == 0 and "ALL OK" or (fails .. " FAILED"))
if fails > 0 then error("name-key checks failed") end
"""


def extract(text: str, name: str) -> str:
    m = re.search(r"^( +)(?:local )?function " + name + r"\(", text, re.M)
    if not m:
        return ""
    indent = m.group(1)
    tail = text[m.start():]
    end = re.search(r"\n" + indent + r"(?:local function |function |-- )",
                    tail[len(indent):])
    block_src = tail[: end.start() + len(indent)] if end else tail
    return "\n".join(l[len(indent):] if l.startswith(indent) else l
                     for l in block_src.splitlines())


def block(text: str, name: str) -> str:
    """A function's source, indentation kept, for the tie checks. Any depth —
    managerAction and lineUpHitch sit at 4 spaces, seedPasses sits inside the
    farm loop at 8."""
    m = re.search(r"^( +)(?:local )?function " + name + r"\(", text, re.M)
    if not m:
        return ""
    indent = m.group(1)
    body = text[m.end():]
    again = re.search(r"\n" + indent + r"(?:local )?function " + name + r"\(", body)
    nxt = re.search(r"\n" + indent + r"(?:local )?function \w+\(", body)
    stops = [x.start() for x in (again, nxt) if x]
    return text[m.start(): m.end() + (min(stops) if stops else len(body))]


def main() -> int:
    base = pathlib.Path(os.environ.get("LOCALAPPDATA", ".")) / "Temp" / "opencode" / "luau"
    exe = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else base / "luau.exe"
    src = SRC.read_text(encoding="utf-8")

    missing = [n for n in WANTED if not extract(src, n)]
    if missing:
        print("MISSING from the build: " + ", ".join(missing))
        return 2
    lua = "\n".join(extract(src, n) for n in WANTED) + "\n" + POST
    with tempfile.NamedTemporaryFile("w", suffix=".lua", delete=False, encoding="utf-8") as fh:
        fh.write(lua + "\n")
        path = fh.name
    out = subprocess.run([str(exe), path], capture_output=True, encoding="utf-8", errors="replace")
    print(out.stdout.strip())
    if out.returncode != 0:
        print(out.stderr.strip()[-1200:])
        return out.returncode

    # ▸ the wiring, so a later edit cannot quietly go back to a raw ==
    ties = []

    def tie(name, ok, detail=""):
        ties.append((name, bool(ok), detail))

    tie("the fold strips non-alphanumerics, not non-letters",
        'gsub("%W", "")' in extract(src, "spudNameKey")
        and 'gsub("%A", "")' not in src)

    manager = block(src, "managerAction")
    tie("the card lookup folds the name",
        "spudNameKey(t):sub(1, #key) == key" in manager
        and "t:sub(1, #vehicleName) == vehicleName" not in manager)
    tie("the expanded-card proof folds the name too",
        "and tk:sub(1, #key) == key" in manager)

    hud = block(src, "hitchedImplementName")
    tie("the stale-label check finds a spaced label",
        "spudNameKey(m.Name) == key" in hud and "FindFirstChild(t)" not in hud)

    hitch = block(src, "hitchTool")
    tie("the wrong-tool guard never unhitches the tool it wants",
        "spudSameEquipName(attached, impl.Name)" in hitch
        and "attached ~= impl.Name" not in hitch
        and "got ~= impl.Name" not in hitch)

    park = block(src, "storeUnusedTools")
    tie("the park-everything pass recognises a spaced label",
        "spudSameEquipName(hitched, m.Name)" in park
        and "hitched == m.Name" not in src)

    point = block(src, "hitchPoint")
    tie("the hitch point asks the game's own socket second",
        "findHitchPart(model)" in point
        and 'a:IsA("Attachment")' in point and "a.WorldCFrame" in point)
    line = block(src, "lineUpHitch")
    tie("the line-up uses the ride's Hitchable and the tool's socket",
        'hitchPoint(tr, "Components", "Hitchable")' in line
        and 'hitchPoint(plow, "Chassis", "HitchableSocket")' in line)
    tie("a line-up with nothing to measure NAMES the model it could not read",
        "spudHitchMissText(tr" in line and "spudHitchMissText(plow" in line)
    tie("the pre-park line-up carries the tow, the pre-hitch arc does not",
        "spudPivotRig(tr, newPivot, airborne and nil or plow)" in line
        and "tr:PivotTo(" not in line)
    tie("the miss line says whether the instance is still in the world",
        "IsDescendantOf(workspace)" in extract(src, "spudHitchMissText"))
    at = src.rfind("hitch gap at arrival")  # rfind: the phrase is quoted in a comment first
    arrive = src[at - 700:at]
    tie("the arrival gap reads the same two points",
        'hitchPoint(ride, "Components", "Hitchable")' in arrive
        and 'hitchPoint(impl, "Chassis", "HitchableSocket")' in arrive)

    tie("the standing seed pick asks the game's own crop word",
        'spudNameKey(n2) == "tomato"' in src
        and '" (the crop you are planting)"' in src)

    seed = block(src, "seedPasses")
    tie("a seed round that takes nothing cannot run for ever",
        "leftStuck >= 2" in seed
        and "after >= leftWas" in seed
        and "still need seed after 2 round(s) that took nothing" in seed)
    tie("a refill is a fresh start for that count",
        "leftWas, leftStuck = nil, 0" in seed)

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
