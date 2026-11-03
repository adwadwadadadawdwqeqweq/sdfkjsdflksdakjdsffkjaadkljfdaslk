# SPUD FARM — the one-file brief

Everything an agent (or a person) needs before touching this repo: the owner's
rules, the game facts we have actually **verified**, the history of what was
asked and fixed, and the exact loop to prove a change works.

**Read this file first. Then read [README.md](README.md)** for the user-facing
description — it is the long-form manual and it is kept in sync with behaviour.

- Main script: [SpudFarm_Full.lua](SpudFarm_Full.lua) — one paste-and-run Luau
  file for the Roblox game *Farming and Friends*, currently `rebuild v1.133 ·
  fluent gui` (`VERSION`, line 15). ≈13k lines.
- Target: Windows + Git Bash. Luau toolchain lives in
  `%LOCALAPPDATA%\Temp\opencode\luau\` (`luau.exe`, `luau-compile.exe`,
  `luau-analyze.exe`).
- Nothing here is a library or a build system. There is no bundler, no package
  manager, no CI. Validation is a compile check plus thirty-one harness scripts in
  `tools/` (`python tools/run_all.py` runs the whole gate).

---

## 1. The owner's rules (non-negotiable)

### 1.1 UI

1. **No text under anything.** Every element gets a **title only**: no window
   subtitle, no description line under a button/toggle, no helper text, no
   placeholder sub-text. This applies to every future feature. (Recorded in the
   README as rule #1 and it has been violated and re-fixed before.)
2. **The window must stay comfortably large** on mobile/emulator screens:
   `Resize = true` and a generous base `Size`.
3. The HUD pattern is fixed: **RIGHT SHIFT** toggles the menu, **📡** opens the
   webhook window, **🥔** (draggable, left edge) hides/shows every window and
   stays visible while the rest is hidden.

### 1.2 Never guess a game field

4. **Probe before implementing.** If a behaviour depends on a live game
   structure, run the matching read-only probe and paste its report; do not
   invent a path, attribute or remote name. The probes exist precisely because
   guesses were wrong: the documented `Spots.<n>.Filth` shape was **not** what
   one live build exposed.
5. **Probes are read-only.** A probe presses nothing, teleports nothing, writes
   nothing. The only exceptions are the scripts that are *about* writing
   (`SpudFarm_Full.lua`) and the remote probe's own stop/upload buttons.
6. **Never derive "clean" from a trip.** Asking "is this stall dirty?" must be a
   read you can do **from where the character stands**. The teleport tour (visit
   all twelve) cost 12 hops / 6.00 s per pass on a clean barn and is banned.
7. **Unreadable is not empty.** An unreadable farm is not `0 cows`; an
   unreadable stall is not `clean`; a streamed-out plot is not `no farm`.
   Unreadable means: name it in the log, make no decision that depends on it,
   never teleport on the guess.

### 1.3 Timing and motion

8. **Wait on the game's own signal**, not a flat sleep. A clean takes ~**2 s**
   in this game (owner's number), so the script watches the Clean offer switch
   off rather than sleeping a guessed 0.96 s and pressing mid-clean.
9. **`task.wait(t)` is frame-quantised** — it sleeps *at least* `t` and resumes
   on the next Heartbeat, so at 60 FPS `task.wait(0.2)` costs 200–216 ms. Do not
   build stand-still loops out of it.
10. **Poll at the frequency the read deserves**: every frame only when the read
    is a cheap property that the game already updates (jug left the world, hand
    filled, tank label). **50 ms** for GUI-shaped reads (`milkMenuFor`,
    `milkStallGui`). `milkDrops` walks a world folder, so it is read at **4 Hz**
    (250 ms), only counts jugs near the stall being milked, and never per frame.
11. **A CFrame teleport needs ~50 ms to reach the server** (physics replication
    ~20 Hz): wait three frames after one, not 150–250 ms.
12. **No teleport just to look.** A hop is for an action the script is about to
    take, and only when the action is not already offered where it stands.

### 1.4 Script limits (these have broken the build before)

13. **Luau's 200-local limit is real** (it was 2 away from the practical
    ceiling until the path engine was deleted in v1.81). Run
    `python tools/local_budget.py`. As of v1.133:
    `4-space locals before milkCycle: 179 (practical ceiling 185)`,
    whole body `186 / 200`, **headroom 6** (v1.129's four `*_STEMS` word tables
    are four build-closure locals — every name the equipment rewrite, the tow
    carry and the v1.133 weld and seed arithmetic needed is a global for exactly
    this reason). Do **not**
    add a `local` inside the main build closure. Reuse an existing local,
    convert the feature to a **global** (the established pattern), or
    restructure — and re-run the budget.
14. **A bare global assignment silently clobbers.** That is exactly how
    `function milkDrops(...)` overwrote `milkDrops = {}` (the three farm
    dropdowns), so every later `milkDrops[slot]` indexed a function. Run
    `python tools/name_audit.py` before/after adding any global.
    That gate now also reads **order**: a 4-space `function NAME(...)` is a
    global, so its body sees only the `local`s declared **above** it, and the
    live v1.129 run died with `642: attempt to call a nil value` when
    `spudEquipHereText` (line 641) called `equipmentFolder` (line 841). No
    harness can see that class of bug — it slices the function out and stubs the
    callee — so the source tie in `name_audit.py` is the only guard.
15. **The file must load first try.** A syntax error means the user sees a
    dead script; `SpudBoot.lua` exists so the error is at least visible.

### 1.5 Scope and process

16. **Do what was asked, nothing more.** No unrequested refactors, features,
    dependencies or polish. A bug report gets a fix, not a redesign.
17. **The version string and the README move with behaviour.** Bump
    `VERSION` (`rebuild vX.YY · fluent gui`) and update the affected README
    paragraph in the same change. Commits are focused and message-first, e.g.
    `Keep cows out of dirty stalls and clean above the meter's clean baseline`.
18. **Never claim in-game verification you did not do.** "Harness green" and
    "tested in game" are different statements. Say which one it is.
19. **One barn per farm per session.** When a plot has more than one barn, the
    first cycle locks one (nearest the plot centre) and it is held as
    **name + position**, never as the model instance (a streamed-out barn
    returns as a *new* instance). Falling back to "the first model named
    `AutoWoodenBarn` in the map" herds other players' cows into the wrong barn —
    that was a real bug.
20. **Never put a cow into a stall that reports dirt.** The cleaner and the herd
    gate must read dirt the same way, or they disagree about what "dirty" means.

### 1.6 Working tree state (read before editing)

`HEAD` is the latest committed build (v1.72, the sweep runs a row every 20 studs and reaches 20),
`main`
tracks `origin/main`, and the tree is clean. Keep it that way: make the change,
run the gates, and commit only the files the change touches. `git add -A` is
banned here. **Commit and push after every completed change** (owner's standing
rule, 2026-10-28) unless the owner says they will do it themselves.

---

## 2. The verification loop

### 2.1 Compile

```bash
LC="$LOCALAPPDATA/Temp/opencode/luau"
"$LC/luau-compile.exe" --binary SpudFarm_Full.lua > /dev/null && echo "SYNTAX OK"
```

### 2.2 The full suite

```bash
for t in tools/*_test.py; do
  printf '%-30s ' "$(basename "$t")"
  PYTHONIOENCODING=utf-8 python "$t" >/dev/null 2>&1 && echo OK || echo FAILED
done
PYTHONIOENCODING=utf-8 python tools/test_doctor.py
```

All of these must exit 0 (29 `*_test.py` harnesses + `test_doctor.py`, which
does not match `*_test.py`). A plain `for` loop is **not** enough on its own:
most harnesses print `FAIL` but still exit 0, so the output has to be read.
The one command that runs everything — compile, budget, name audit and every
harness, checking both the exit code and the text — is:

```bash
python tools/run_all.py        # 34/34 checks on v1.133
```

Last full run (v1.133): **34/34 checks passed** (31 harnesses + 3 gates).
The compile row is judged by the **exit code and stderr only**: `luau-compile
--binary` writes the bytecode to stdout, so the old `"FAIL" not in stdout` scan
called a build broken the moment the script contained a string with those three
letters in it (v1.124 live: `the cell read FAILED` in a log line). Every
harness row still reads its stdout, because a harness printing `FAIL` and
exiting 0 is exactly what that scan exists to catch.

| Script | What it actually proves |
|---|---|
| `barn_lock_test.py` | The barn lock survives a stream-out/stream-in (matched by name + position, not identity). |
| `clean_visit_test.py` | Dirt is read without moving: clean barn = 0 hops, one dirty stall = 1, unreadable = 0, attribute/nested/visible-mesh/nested-value shapes all found, the meter line learns and stops, a 2.0 s clean is waited for exactly once, and a refusing stall is backed off on the next pass. |
| `cow_in_stall_test.py` | The per-cow clean path: a nil first read of the Clean offer still cleans (the poll fix), a clean stall is never pressed again, and an unreadable offer costs ≤0.5 s and no key — then the milk and gate still happen. |
| `lifecycle_test.py` | The generation guard: a reload stops the old build's loops, Unload stops the current ones, and a later build cannot revive them (captures the global-vs-local `spudAlive` trap). |
| `webhook_test.py` | A webhook URL must be Discord's own host + `/api/webhooks/` path; "contains the word discord" is rejected, and blank means off. |
| `drop_scope_test.py` | A jug appearing elsewhere in the world during the 10 s milk wait is not counted as "this cow gave milk". |
| `farm_batch_test.py` | Herd-batch arithmetic: who fills a batch, who hands over. |
| `farm_hop_test.py` | The go-to-the-farm hop: no plot or no position answers with a reason, a plot within 60 studs is left alone, a far plot targets its centre +5 Y, and the reported distance is the real one. |
| `farm_rotate_test.py` | Three-farm rotation order and wrap-around. |
| `farm_switch_test.py` | The under-herd-amount hand-over: `ready + parked` compared, fullest other wins, equal counts do not swap, unreadable never a target, no self-hand-over, no ping-pong. |
| `gate_visit_test.py` | Gate opened from where we stand (0 hops when the door is offered); an already-open gate is never pressed again. |
| `herd_arm_test.py` | Arming a cow is fast when the menu is up, and the no-menu timeout is bounded. |
| `herd_order_test.py` | Cows nearest the barn go first; a dirty free stall is skipped and an all-dirty barn arms nobody. |
| `herd_send_test.py` | The wrong-barn regression: no fallback to a stranger's `AutoWoodenBarn`. |
| `hitch_anchor_test.py` | The tow weld (v1.133): `spudAnchorTool` makes **no** weld for a nil pair or a tool that IS the ride, refuses when either side has no hitch part, and refuses **every** non-settled verdict — `far` says "off the hitch", `swinging` / `gone` / `none` name the verdict and leave the tow on the game's own constraint — while `stop` logs nothing. On `settled` it makes exactly one `WeldConstraint` named `SpudTowAnchor` with `Part0` = the ride's hitch part and `Part1` = the tool's, parented to `Part0`, claims network ownership once, and a second call for the same pair is idempotent (no second weld, no second claim, no second wait). A new tool destroys the old weld first; `spudUnanchorTool` releases it, logs the reason, and is silent on the second call; a refused `Instance.new` leaves `spudAnchor` **empty** (no phantom anchor) and a later weld still works, and a refused `SetNetworkOwner` still welds. Ties pin the anchor **after** `hitchTool`'s gave-up branch, the seven game-facing `spudUnanchorTool("<reason>")` sites (the eighth is inside `spudAnchorTool` and makes way for a different tool), that the settle is read before the weld, that `if v ~= "settled" then` is in the source, that no classic `Instance.new("Weld")` was used, and that `spudAnchor =` is assigned in exactly two places (weld, release). |
| `hop_test.py` | The arc hop's landing height: **the landing is the target's own height** (v1.122), so a return leg from the lower pad lands ON the field and a trip *down* to the pad lands ON the pad instead of hovering 28 studs above it; the arc clears the landing by ~12 studs and arrives from above in both directions, a level hop stays level, a target with no Y keeps the takeoff height, a zero-length hop is one move, and stopping aborts without landing. **The tow** (v1.131): the fake ride's `PivotTo` moves **only the ride**, so a hop handed an implement must carry it — 24 carries over 25 moves, the hitch still exactly 20 studs after the landing, no implement costs no carry, and the control (a bare `ride:PivotTo`) opens the 286-stud gap the live v1.130 run reported; a source tie refuses to run the harness if `hopTo` loses `spudPivotRig(tr,` or keeps a bare `tr:PivotTo(`. |
| `milk_arrivals_test.py` | The arrival wait watches stall `Occupant` values and scans a handful of times, not five times a second. |
| `farm_width_test.py` | Working width and row plan: studs→tiles rounding, oriented-box union width, rotated bars, 1/2/3-wide plans (step, headland, row half-extent) and an interval-coverage proof on 100/200-stud and narrow fields; owner match rules. |
| `equip_owner_test.py` | Whose tractor/tool is picked: the farm being worked first, mine next, an unreadable owner after that, a stranger's never; stored machines are reported for spawning; the implement distance/basis stay honest — and **what** a machine is comes from the game's own data (v1.129): the harness pulls the real `*_STEMS`/`TYPE_STEMS`/`TYPE_MODEL` tables out of the build, so `EquipmentType` is matched by **stem** (`Forage Harvester` = `harvest`), a model name is only ever the no-attribute fallback and the `basis` names which rule won, `PDRILL22` still reads as a Planter, a driver-seat + `Components.Hitchable` ride is accepted **only** when nothing the game calls a Tractor is out (and a Truck / Transport / Harvester / seat-without-a-Hitchable never is), and `spudEquipHereText()` prints the `Name=Type (stored)` world inventory the refusal lines quote. |
| `field_soil_test.py` | Tree/wood field types and names are never crop-harvest targets; a successful cell read with 0 cells is empty (skipped), while a failed read stays unknown (never a skip reason). |
| `early_cut_test.py` | The one harvest predicate: with `spudEarlyCut` off a `Seeded` cell is not standing (the old behaviour, byte for byte) and with it on `Seeded` + every unknown stage are; the other jobs still aim at their own stage either way; a nil/0-cell read stays unknown; and the source ties that the growth wait restarts on a cuttable field, bounds the restart with `spudCutWatch`, the census renames the column `cuttable`, the Settings toggle remembers the pick, and **Get coords** logs/copies the position. |
| `field_remote_test.py` | The field remotes: ids come from the game's own `GetCells` dict (numeric keys only, sorted, failed read = unknown), the tool's RaycastPart attachment is the one sent, one call per remaining cell carries `(field, {id}, {attachment})`, a full batch reports done, a partial batch hands back the remainder, an ignored batch switches that job back to driving (and fires nothing again), and `FillSeeder` falls back to V on a refusal. The Tests-tab batch: one call carries every id, a full/partial/ignored id list is judged by the stage re-read, and an ignored list never switches the job off. The single-spot fire takes a whole field from one teleport when the blade reaches 60 studs, fires one call per cell, respects the seeder budget, and takes nothing when the reach is small (4 of 8 cells called, the far ones handed to the blocks, no call at all when nothing is in reach, no frame = no filter). **The tow** (v1.129): `spudWaitTool` is `none` with no readable attachment, `settled` behind the ride, `far 300` when flung off the hitch, and `swinging` after exactly **30** beats — and a flung implement makes the grid fire **0 calls over 0 jumps** with `not on the hitch any more`; source ties pin the gate sitting **before** the first rig move in `spudRadialFire` and `spudHopCells`. **The carry** (v1.131): the fixture ride now moves **only itself**, exactly like the game, so a bare teleport is proven to abandon the blade (`gap became 286.0`), and every grid stop and cell hop carries it — `1 jump(s), 1 carry(ies)` for a stop, `15 jump(s), 15 carry(ies)` for a 15-cell field, the blade left on the hitch in both passes, no carry and still 15 jumps for a nil tool, `tool == ride` moving the ride **once** (the harvest job tows itself), and both passes still take their cells; ties assert `spudPivotRig(ride,` in each function and **no** bare `ride:PivotTo(`/`tr:PivotTo(` left in them. **The tool-sized burst**: `spudToolExtraTiles` = width past one tile (3 for a 40-stud tool, **0** for no tool or a `partBoxes` that throws), and the constants stay the measured `spudToolSwing = 3` / `spudToolFar = 90`. **The equal square** (v1.132): a wide implement now gets **`3x3 per stop`, not `6x6`** — that old check was the cross-pattern defect written down — and `spudBlockSide` is pinned at the corner arithmetic (20 → 3, 21 → 3 but 22 → 4, 29/35 → 5, 400 → 7, 0/nil → 3), with ties that `spudFieldTaken = 20` is the constant, that the grid reads `spudBlockSide(spudFieldTaken)`, that `3 + spudToolExtraTiles(impl)` is gone from `spudRadialFire` and so is `firing anyway`. **The re-aim** (v1.132): a fixture whose tool settles at a real 5-stud trail but starts 46 studs behind (what a 288-stud arc leaves) must still land — 15 calls, 15 took, more than 2 pivots for its 2 stops, and no `leaving this block` line — while a blade that never lands (stuck 25 studs off all three stops of a 9×3 field on a turned 50×20 frame, with the ride itself jammed so `spudWaitTool` can never call it `far`) fires **0 calls**, names `leaving this block's N cell(s)`, ends on `not landed on 3 stop(s)`, and leaves all 27 cells standing. |
| `equip_remote_test.py` | The equipment remotes: the seven captured calls resolve on `Modules.Larry`; spawn/store are proven by `InStorage` (or a >100-stud move for a rebuilt spawn) and fall back to the UI when ignored; enter is proven by the seat; hitch/unhitch use the captured `Components.Hitchable` + `Chassis.HitchableSocket` pair; carry/drop are proven by the hands; three misses switch one action off for the session. |
| `row_steer_test.py` | The row decision in the wide band: `spudRowNeedsAlign` asks for ONE snap only past `spudRowAng` (15°) or `spudRowTol` (6 studs); `spudRowSteer` presses nothing inside the band; `spudRowEase` takes a step off the throttle after three steering flips (×0.7, floor 30 %) and gives one back per steady 3 s. |
| `foreign_respawn_test.py` | `spudMayRespawn()` is false while a Farm owner is picked, and `ensureToolNearby` then never calls `respawnTool`: a stored or far-away tool is named and the pass is skipped, while `(mine)` still respawns. |
| `dropoff_test.py` | The full-tank gate follows the Farm tab's Drop-off pick: a full tank unloads with Fulfillment or Sell chosen, a half tank works on, an unknown/nil destination never moves; the Fulfillment pad is read from `Stores.DropOffs` (Deposit_Warehouse preferred over Withdraw_Warehouse), aimed at its top surface, and — when that folder is empty, which is what the live game now does — **found by name anywhere in the world** with its real path in `what`, a Model pad giving a park spot but no fire part, and a refusal that names the folder's state and the number of instances read. An unstreamed/empty folder with no pad anywhere returns no pad instead of a guess, and a **goto marker is never the pad** (it comes back as the waypoint to hop to, with the pad re-read once that hop streams the area). **A walk match that is not AT the deck is refused too** (v1.128): the harness rebuilds the live `Ugc.CompanyArea.WarehouseArea` and asserts 0 pads, a log naming the **142-stud** miss, and the marker still returned as the waypoint — while an in-band match is still taken and logs no refusal, and the game's own `Stores.DropOffs` folder is never gated. **No pad instance and no waypoint still unloads** (v1.122, both picks since v1.126): the trip parks at the owner's 📍 Get coords readings — `spudFulfillPadSpot()` = `-353, 141, -92` and `spudCropSellSpot()` = `125, 142, -150` — fires no sell call it has no part for, and logs the spot as remembered rather than as a world part. Fulfillment presses **nothing** (auto pad); the remembered **Sell** board must keep `autoPad` false so `trySellAt`'s Q/E menu path still runs there, which is pinned. `trySellAt` itself runs on a virtual clock: the Fulfillment pad drops the load while pressing **zero** keys and making **zero** calls, a working Sell call presses nothing, and an ignored Sell call falls back to Q and E without claiming a sale. |
| `seed_refill_test.py` | A crate's own seed count is read from `Configurations.Capacity` (0 is empty, a failed read is NOT empty), an empty box is never poured as "seed", the run's shop-trip cap is at least the seed pass's `refill N/M` promise + 1 — the latch that made refills 2 and 3 unreachable is pinned out — and a shelf price dearer than the balance blocks the **next** trip locally (unreadable price or balance blocks nothing; the gate must sit before the trip is counted). **The full tank** (v1.133): `spudSeedTripsNeeded` is pinned at the arithmetic (600 empty at 50 a crate, 2 crates a trip → **6** trips; a 50-slot tank → 1; room left, not capacity; a partial crate rounds **up**; full/over-full → 0; 1 crate a trip doubles the visits; a nil cap/crate size is **unknown**, not one trip; a nil `have` reads as empty) and `spudSeedTripCeiling` **only ever raises** the floor (unknown keeps 4, 6 trips → 6, a 1-trip tank never lowers the 4); `spudSeederWantsMore` stops the pour at the machine's own `MaxCapacity` and reads an unreadable pair as "no room", never "hungry"; `spudCratesInHand` counts `CarryLinks` children (0/1/2, no character = 0, no folder = 0). Ties: the refill ceiling scales, the run's trips cover that promise, no once-per-run latch came back, the shelf price is stored, the trip gate reads the **scaled** ceiling (not the constant) with the price gate still **before** it, the fill is a loop to the cap, `spudSeedsPerCrate` is never given a literal, the second crate is proven by `CarryLinks`, an unpaid crate calls `spudDropRemote()`, crates-per-trip is one setting, and a held crate is still gated by `spudCrateHasSeed`. |
| `stall_probe_test.py` | The stall probe's report shape (it must name every dirt candidate and count visible stains). |
| `stall_stream_test.py` | The stall scan after a milk teleport, on a virtual clock: a pass that did **not** hop reads once and sleeps zero (the old behaviour), a pass that hopped re-reads until the game actually has stalls and hands those back, each try costs 0.25 s, the wait is **bounded** at 12 tries (3 s), Stop ends it between tries, the skipped count and the same plot/owner are carried through every re-read, and a barn that never streams is logged as **not streamed** (naming the farm, saying the plot reads, saying this is not "no barn") rather than as an empty answer. Plus the ties: `milkCycle` scans through `spudStallScan`, its two plot teleports each report whether they moved, and the timing stamp is taken after the scan. |
| `fulfill_probe_test.py` | The fulfillment probe's **company-order** sections on a fake tree: every order-named instance with its value tree, the board's text read from **PlayerGui as well as workspace**, what `Stores` holds, each seed crate's `Configurations`, one field cell's full key list, and the honest grow-time verdict — a cell with only `PlantGrowth`/`GrowthMultiplier` must **not** be called a readable duration. Also pins the probe's read-only claim (no key press, no `FireServer`/`InvokeServer`, no `CFrame`/`PivotTo`, no metatable hook) and that the report reaches the panel, the multiline box and the clipboard. |
| `test_doctor.py` | The in-script 🩺 DOCTOR report runs on stubbed world objects and reports, not crashes. |

Plus the two non-test gates:

```bash
python tools/local_budget.py   # headroom must stay >= 1 (currently 6)
python tools/name_audit.py     # no top-level name collisions, and no global
                               # that calls a `local` declared later (365 names)
```

Measurement harnesses (run when you touch the thing they measure, quote the
numbers in the README):

- `cow_scan_bench.py` — instance calls per cow scan (cache effect).
- `stall_scan_bench.py` — calls/name reads to find 12 stalls (narrow scan).
- `store_timing.py` — milk store pass on a virtual clock with latency.

### 2.3 What green does **not** prove

The harness slices the **real** functions out of `SpudFarm_Full.lua` and runs
them under the real Luau interpreter against fake world objects. That catches
logic, arithmetic, and "did I break the shape" — it does **not** prove the live
game exposes those fields, that a GUI appears, or that an action is accepted.
Anything touching the game's own menus must be confirmed in game after a reload.

Known gaps: the **store deposit** and **feed top-up** paths have no harness (they
need a fake carrier + dispenser), and nothing in the suite proves the live game
exposes these fields. The per-cow clean path is covered by
`cow_in_stall_test.py`.

### 2.4 Reading a live run from the emulator (no copy-paste)

The game runs in **MuMu Player** (instance `Android Device-1`, adb
`127.0.0.1:16416`), and every `log(msg)` reaches Roblox's CreatorOutput, so
Android's logcat already carries the whole farm console:

```bash
MGR="/c/Program Files/Netease/MuMuPlayer/nx_main"
"$MGR/adb.exe" connect 127.0.0.1:16416
"$MGR/adb.exe" -s 127.0.0.1:16416 logcat -d | grep -F "[spud]" | sed 's/.*\[spud\] //'
"$MGR/adb.exe" -s 127.0.0.1:16416 exec-out screencap -p > screen.png   # what is on screen
```

The owner's executor fetches the latest build from the repo, so the loop is
**push → reload in game → read logcat**: no pasting needed. A screenshot also
shows the Tests panel, the HUD and the tank label.

---

## 3. The game, as measured (not guessed)

### 3.1 Where things are

```
Workspace.Objects.Buildings.<barn model>          -- barns live in Objects.Buildings
  AnimalContainer.Spots.<n>                       -- one folder per stall; 12 stalls seen
    (attributes) AnimalMask, FilthLevel, FilthPercentage
    Center                    Part (transparent) · child MilkContainerSpawn [Attachment]
    Adornee_BarnStallMenu     Part (transparent) · child AlwaysInvisible, LinkedGui
    Filth                     Folder
      Stain  Part (1×2×0 / 2×2×0, Transparency 1 when clean) with a Decal child
      Level1..Level4  MeshPart (the four drawn dirt levels)
    Occupant                  ObjectValue (the cow parked here, or nil)
    NodeLink                  ObjectValue -> <barn>.AnimalContainer.Nodes.Stall<n>
    Gate                      Model {Enabled, Moving, Opened, OpenedAngle}, parts +
                              ProximityPart + GateHinge
    Hay                       Part · child FilthEffect [ParticleEmitter]
  Other.Dirt                  Part (18×1×70) -- scenery, never a stall's dirt
```

A probe report, verbatim, is the source of truth. `SpudStallProbe.lua` prints
one complete stall folder — every descendant, value, attribute, part
transparency/position, the visible-stain count, every dirt-sounding instance in
stall/barn/plot with its full path, and the game's own `CleanAnimalContainer`
billboard.

### 3.2 The dirt model

- **`FilthLevel`** (attribute on the stall folder, 0–4) = how many of the four
  stain levels are showing. **`FilthLevel > 0` is the primary trigger.** It is
  readable from the plot centre.
- **`FilthPercentage`** is the meter behind it. The probe found **`24` on a stall
  whose every stain was invisible** — 24 is the *clean* baseline, not "24 units
  of dirt". The script's line is `milkDirtLine = 24` and the meter is a trigger
  **only above it** (the owner's "over 20/24 dirtyness").
- The line **only ever moves up**, and only when the game itself says a stall it
  pointed at is clean:
  `milk: stall 1 reads 60% but the game offers no Clean there - the dirty line moves to 60%`.
  The rest of the stalls at that reading are dropped from that pass, so a wrong
  baseline costs one hop, once. It learns `max(trigger reading, re-read)`, only
  from a stall with **no fresh stain** (a stain that appeared since the scan is
  dirt whatever the meter says), and a reading above 100 teaches nothing. The
  line resets to 24 on every Reload (it is learned state, not a setting).
- Fallback read, no teleport needed: count the `Filth/Level1..Level4` MeshParts
  whose `Transparency < 1`. Clean stall = all four hidden. The folder is trusted
  only when it actually holds `Level` parts; any other `Filth` shape falls
  through instead of answering "0".
- Older shapes are also read: a direct `Filth` child, a nested value, an
  attribute named `Filth` / `Dirt` / `Grime`, or a dirty-named child.
- **No shape at all is not a reason to move.** The old "12 of 12 need a visit
  (no readable dirt)" fallback is gone; an unreadable stall is cleaned at the
  stall while its cow is milked, and the console lists what the stall actually
  holds, once per session.

### 3.3 Cleaning

- The game's own action is the `CleanAnimalContainer` billboard (text
  `V | Clean`), adorned to a stall's `Center` part. It is only offered while
  standing in that stall, so a clean is inherently in-stall.
- **A clean takes ~2 s.** Three waits, all on the game's own signal:
  - pre-pass, waiting for the offer to point at the stall: `24 × 40 ms` =
    **0.96 s ceiling**;
  - pre-pass, waiting for the clean to finish: `44 × 50 ms` = **2.2 s ceiling**;
  - per-cow clean first polls the Clean offer for up to **0.5 s** (10 × 50 ms) —
    a single nil read right after the no-settle teleport used to skip the clean
    entirely and milk a dirty stall;
  - per-cow clean: `45 × 50 ms` = **2.25 s ceiling** (it used to give up at
    0.96 s and press for milk *mid-clean* — a press the game ignores, and one
    way a cow came back unmilked).
- The log states the measured duration: `OK milk: stall 3 cleaned in 1.94s
  (2 stain(s) -> 0)`.

### 3.4 Cows and milk

- A cow's owner is found via `Configurations.Owner` (walking up to eight parents
  when absent); the instance walk is cached per model in a weak table, and an
  animal is **never** cached as untagged (it can gain an owner a moment later).
- Happiness decides the jug: **<60 % spoiled, 60–89 % regular, 90 %+ free-range.**
  Only **free-range** jugs are loaded into the carrier
  (`store: leaving N non-free-range jug(s)`); the rest are left for selling.
- 12 stalls per barn, herd batch typed 1–12, per-farm teleport to a remembered
  plot centre (plots stream out when far away).
- **A plot is not its barn** (v1.127). `Workspace.Plots` is a folder of
  lightweight models that stays in the world at any distance, so the milk pass
  can read `desbiens1235 is 868 studs away - teleported to its plot` and 17 ms
  later `no stall found for desbiens1235` — while the same pass counts 32 cows.
  A barn is a full 3D building and streams with the camera, and `milkTp`'s 0.2 s
  settle is the ~50 ms a CFrame needs to reach the **server**, not the seconds a
  distant building takes to arrive. So `spudStallScan(owner, cf, size, hopped)`
  re-reads until the game has stalls (0.25 s a try, **12 tries** = 3 s), and the
  hop is what licenses the wait: a pass that did not teleport reads once and
  sleeps zero, exactly as before. An answer that never comes is logged as
  `still no stall after 3.0 s - <farm>'s plot reads but its barn has not
  streamed in; this pass reads nothing here, which is not "no barn"` — rule 7,
  never an empty list dressed up as an empty barn.
- Arrival detection watches the plot's stall `Occupant` values (~30 reads over
  12 stall parts) and only scans when an un-milked cow turns up parked.

### 3.5 Which farm gets the next pass

The owner's rule: *"before it brings the cows inside make it check for over
20/24 dirtyness"* and *"it does not switch the plot/players field when it gets
under the herd amount"*. The implemented rule, in one sentence:

> **Compare every cow waiting on each farm — ready in the field plus already
> parked in a stall — and hand the next pass to the farm with the most of them,
> as long as that is more than here.**

Consequences that are deliberate and tested:

- A farm whose cows are all parked reads `0 ready`; leaving it out was the
  "it's missing sometimes bro" miss. `ready + parked` fixes it, and milking
  parked cows is also faster than herding.
- The comparison is **not** a demand for a full batch — two alts rarely have
  twelve cows at 300 % at the same moment.
- **Equal counts never swap** (that would ping-pong two equal alts).
- **No other farm readable → work this one**; a small farm cannot stall the loop.
- A farm that **cannot be read** (streamed out, not built) is **never** a target
  and is named as unreadable in the stay line.
- Cleaning happens first, always; a dirty stall is never skipped or filled.
- The stay line explains a skipped switch:
  `milk: desbiens1235 has 6 ready cow(s) - under the 12 per herd, but the fullest other is Miou2251: 4 ready - working this one`.

### 3.6 Travel: arcs and teleports, no pathfinding

The A* engine (a top-level `SpudPath` module: heap Lazy Theta*, clearance
field, Bézier smoothing, obstacle caches, the `driveRoute` follower) was
**removed in v1.81** at the owner's call: *"i want to remove the a* pathfinding
and have it tp fast untill the whole fielld is done"*. Nothing in a tour needs
a route any more.

- **Field to field** is `hopTo(ride, fieldCornerTarget(...), SELL_HOP_SPEED)` —
  a 140-stud/s sine arc that lands on the plate's corner. Every job takes it;
  `driveToField`/`driveRoute`/`pathfindAround` are gone.
- A field with **no readable frame** (`fieldFrame` → nil) is named
  (`SKIP <field> — no readable field frame`) and the pass stops there instead
  of driving at it — that field cannot be swept by the remotes either.
- **On the field** the work is the field remotes (§3.12), all teleports: the
  call pass, the stop-and-burst grid, the **per-cell hop** (a teleport per
  cell), then **grid → hop again, round after round**, until the field reports
  none of that stage left (v1.83 — Stop ends it), and two rounds that take
  nothing end the pass with
  `<verb>: N cell(s) never took a call even with the blade on them — leaving
  them for the next pass` (v1.94). **Nothing drives and nothing tweens** (the
  serpentine sweep was deleted in v1.95), so every move in a field pass is a
  teleport. **No row is ever driven**
  (v1.82) — a pass that refuses everything says
  `<verb>: every call on <field> was refused — N cell(s) left, no rows driven`. The old row driver (`keyRow`,
  `alignDriveLeg`, `driveLegKeys`, `throttleRow`) is now unreferenced code;
  `spudRowSteer`/`spudRowEase` are still pinned by `row_steer_test.py`.
- Deleting the planner also freed the 200-local budget: **headroom 2 → 10**
  (175 before `milkCycle`, 182 whole body).

### 3.7 Whose tractor and tool

A farming pass used to take the **nearest** machine in `Objects.Equipment`,
whoever owned it — on a foreign field that borrowed a stranger's ZM80 whenever
one was closer. The probe proved every machine carries
`Configurations.Owner` (`ZM80`/`SRC6` = `oksimba_1`, `LH150`/`MTS`/`UH` =
`Miou2251`), so `equipOwnerRank(m)` now ranks each machine.

With a **foreign farm picked** the order is: that farm's machines (rank 0), my
own machines (1), a machine with no readable owner (2), and another account's
**never**. With **`(mine)`** it is: mine (0), no readable owner (1), another
account's never. `findTractor` and `findImplement` scan the ranks low-first
and, inside a rank, keep the old nearest-wins rule. A stored machine of the
chosen rank is reported for the Equipment Manager instead of taking a spawned
machine from a lower rank. `logEquipment` prints each machine's owner, and the
"not found" lines name the farm the pass was looking for.

**WHAT a machine is — the game says it, and since v1.129 that is the only thing
the pick reads** (owner: *"now it's not detecting my new harvesters and
traotrs, make it use the games build in scripts to know what is a harvester and
what is what"*). The live DOCTOR dump names an `EquipmentType` attribute on
**every** model in `Objects.Equipment`: `ZM80=Tractor`, **`JDS790=Harvester`**
(MaxCapacity 600 — the new machine the name tables had never heard of),
`KADL=Planter`, `KQF3000=Cultivator`, `S4204=Plow`, `R150=Truck`,
`Trailer=Transport`; `SRC6` is gone from this build. So:

- `spudEquipTypeKey(m)` is the game's own word **lowercased and stripped to
  letters**, and `spudEquipIs(m, STEMS)` asks whether that key contains a
  **stem** — not one exact spelling learned from one dump. `HARVEST_STEMS =
  {harvest, combine, forage}`, `TRACTOR_STEMS = {tractor}`, `HAULER_STEMS =
  {truck, transport, trailer, hauler, cart}`, `TOOL_STEMS = {plow, plough,
  cultivat, plant, seed, drill, sower, spray, sprinkler, irrig, mower, baler,
  tine, harrow}`. `"Forage Harvester"` and `"Harvester"` are one machine.
- **A model name can never veto what the game says.** It is consulted only when
  `GetAttribute("EquipmentType")` returns **nil** on that build (`isHarvester`,
  `findTractor`'s `zm80` fallback, `findImplement`'s `TYPE_MODEL`), and
  `findImplement`'s `basis` now reports which rule won —
  `EquipmentType Cultivator` vs `model name KADL` — because a check that pinned
  the model name was the old name-wins defect written down.
- **Structure is the second source, still the game's own**: `spudEquipSeat(m)`
  (a `VehicleSeat`/`Seat` descendant = "you can drive this") and
  `spudEquipTows(m)` (`Components.Hitchable` — the exact instance the captured
  `FNCAttemptHitch` takes). With **nothing** in the world carrying the word
  Tractor, `findTractor`'s loose pass takes a model the game built with a
  driver seat **and** a Hitchable, excludes anything it calls a Truck /
  Transport / Harvester / tool, and logs which machine it settled on and why.
- `equipInStorage(m)` (`InStorage == true` = parked in the garage: no seat, no
  live position, hitching to it fails) is skipped by the lookups, and every
  "none found" line now ends with `spudEquipHereText()` — up to eight
  `Name=Type (stored)` entries actually in `Objects.Equipment` — so the next run
  names the game's own words instead of this build guessing them (rule 4/7).

**On a picked farm nothing is spawned or respawned** (v1.34). User: *"when it's
on someone elses plot make it not try to respawn things bro."* Bringing a
machine out of storage or respawning a far one drives the game's Equipment
Manager — the owner's call, not ours. `spudMayRespawn()` is the single rule
(false while a pick is active) and it is checked at all three places that used
to spawn: a **stored tractor** (log + stop), a **tractor beyond
`RESPAWN_RANGE`** (log + stop), and every **implement** through
`ensureToolNearby` (log + skip that pass). Each line names the machine, why
(stored / N studs away) and that `(mine)` is how to bring it out.

**The fields follow the same picker, one owner at a time** (v1.29):
`SpudFarm.ownerWanted` now means *exactly* the picked owner when a pick is
active, not "mine **or** the pick". Before that, picking Miou2251 hitched that
farm's plow (rank 0) and then toured **my** fields as well — user: *"it's using
the player it's working for's equipment then going on it's own field."* With
`(mine)` it is still exactly my fields. The tour and per-field log lines now
carry the owner (`Field · Miou2251`), so a mixed tour can never look anonymous.

### 3.8 Trees and wood soil

User: *"it's trying to harvest my trees but i don't want to."* The harvest job
(`JOBS[4]`, `grown = true`) counts **any cell stage it does not recognise** as
"a crop is standing" — because the real grown-stage name was never in a dump.
A tree/wood field's cells therefore look like a ripe crop and the harvester is
sent over standing trees.

The guard is `spudTreeField(typeName, modelName)`: a field whose
`Configurations.FieldType` or model name contains **wood, tree, log, forest,
timber, lumber, sawmill or stump** is never a crop-harvest target. It is applied
everywhere harvest work is decided (`probeWork`, `runPass`'s `anyNeed`,
`runPass`'s per-field loop, `needLeft`, `grownLeft` and the growth wait) and the
skip is logged with the real type, so a build that names the soil differently is
visible in one run instead of silently harvesting trees.

The second rule is the owner's "unreadable is not empty" (rule 7) applied to
cells: `spudNoCells(st)` is true only when the game's cell read **succeeded**
and returned `total = 0`. Such a field is skipped for every job. A `nil` read
(failed API, streamed-out field) stays *unknown* and is still never a reason to
skip work.

The full crop↔soil mapping (a crop seed works normal soil, a tree seed works
wood soil) still needs the live `FieldType` values and the seed categories —
that is what `SpudFieldProbe.lua` answers; the harvest guard is independent of
it and needs no mapping.

### 3.9 Row driving and speed

User: *"when you drive there is like a game helper that auto re steers the
tractor on course"* + *"it does not re-center"* + *"make it go faster"*. The
game has its own steering assist on a field; the align mover fought it, and its
pure-pursuit aim corrected **heading only** — a tractor parallel to the row but
2–6 studs beside it had zero heading error, pressed no key, and never came back.

- Rows are now driven on **real W** (`keyRow`, the driver the harvester already
  used), so the game's controller does the steering. `keyRow(tr, seat, from,
  goal, who)` gained the `who` label so the log says `tractor:` as well.
- **v1.35 — snap once, then go straight** (user: *"it is still going back and
  fourth bro like side to side, make it force the alignement then jus tgo
  straight and let the game do the ajustments"*). The per-tick cross-track A/D
  nudge was fighting the game's steering, which is the side-to-side. Now, at
  the start of a **row** (leg ≥ 20 studs) `keyRow` snaps the ride onto the row
  line with `CFrame.lookAt` when `spudRowNeedsAlign(angDeg, cross, tol)` says
  it is off, waits 0.15 s for the move to reach the server, and then holds
  **W only** for the rest of the leg. `spudRowSteer(angDeg, crossY)` is
  heading-only: A/D is pressed to swing the nose onto a row, and **nothing**
  while the heading is fine. Short Omega turn legs (< 20 studs) keep the
  swing-through from v1.30.
- **v1.36 — the band is WIDE** (user: *"widen the steering range it takes bro
  it's like still going side to side yo"*). The thresholds were 8° / 2.5 studs,
  close enough to the game's own corrections that they kept trading places. They
  are now globals `spudRowAng = 15` and `spudRowTol = 6`, and the row loop has
  **hysteresis**: steering starts past 15° and only stops once the nose is back
  inside half that band, so a nose wobbling around one threshold can no longer
  flip A/D/A/D.
- **v1.37 — a swinging row slows itself down** (user: *"if it keeps going back
  and fourth with the seering make it slowly go slower bro"*). `keyRow` counts
  steering **direction changes**; three of them take a step off the row's
  throttle through `spudRowEase(level, flips, steadyFor)` (×0.7, never below
  **0.3**), and every steady **3 s** earns +0.1 back (never above 1). A reduced
  throttle is a duty cycle on W (4 pulses a second), because the key API has no
  analogue input. So an oscillating row converges to a slow, steady pass instead
  of a fast wobble.
- Travel speed `ALIGN_MAXVEL` is **34 studs/s** (was 24). The align mover is now
  only the row **fallback** (`math.min(HARVEST_TWEEN_SPEED + 8, ALIGN_MAXVEL)` =
  18), so a plow doesn't snag at travel speed; the old 10-stud/s mover cap no
  longer governs a normal row.

`row_steer_test.py` pins the steering decision. The real-W row speed is the
game's own, so it is faster than the old 10-stud mover by construction.

### 3.10 A full harvester unloads at the chosen drop-off

User: *"im telling you i ON the pad to furfull bro, make a option in the farm to
either furfull or sell bro."* The Farm tab now carries **Drop-off** with two
values, and the full tank always ends in a real trip:

- global `spudDropOff` (default **Fulfillment**, remembered across a reload in
  `spudSavedDropOff`); `spudSellNow(cur, max)` is true only for a readable
  `cur >= max` **and** one of the two known destinations — an unknown or nil
  pick still stops the run rather than driving nowhere.
- **A tank that cannot cover the standing cells is full** (`spudHarvestFull(cur,
  max, need)`, v1.86). Live: `49/50` against 46 standing crops gave a budget of
  **1**, fired one call, the server refused it, and the sell gate demanded
  `cur >= max` — so the harvest loop ran round after round for ever and nothing
  unloaded. The rule is `cur >= max` **or** `max − cur < need` (a readable pair,
  `max > 0`, `need > 0`); `harvestSellIfFull` takes the standing count at every
  call site and checks the destination pick itself. Its budget line now says
  `remote harvest: the tank has N free slot(s) …` instead of reusing the
  seeder's wording.
- **Fulfillment** → `spudFulfillSpots()` reads `Stores.DropOffs` and prefers
  `Deposit_Warehouse` (the owner's standing reading: `-353, 141, -92`) over
  `Withdraw_Warehouse` and the plain `DropOff`s, aiming at the pad's **top
  surface**.
  **That folder is empty in the live game** (v1.118, 2026-11-01: 0 children at
  the field and 0 children again after the 1,133-stud hop to the store — the
  same folder an older world dump called empty), so when it holds nothing one
  bounded walk over `workspace:GetDescendants()` looks for the pad **by name**
  wherever the game actually has it, scores it the same way, and logs the path
  it found (`fulfillment pad: Objects.Buildings.CompanyArea.Deposit_Warehouse
  at (…)`). A `BasePart` is both a place to park and the part `EVTSellAtStore`
  fires at; a `Model` gives a place to park only (`part = nil`), which is all a
  pad that drains a parked harvester by itself needs. A refusal is never a
  guess: it names the folder's state, how many instances were read, and up to
  eight world names that sound like a pad **with their class and full path**,
  because the class is what no build has ever printed.
  **A goto marker is never a pad** (v1.121, live): that walk first matched
  `Ugc.Markers.GotoLocations.Warehouse`, the run hopped 838 studs onto it and
  parked — `load 50, coins 14459 → 14459` after 16 s — then took the same trip
  every 60 s, so 50 `Harvestable` cells were never picked. Anything whose path
  contains `Marker`/`GotoLocation` is now returned as the **waypoint** to hop to
  instead of the place to park, and the pad is re-read once the hop has
  streamed the area (the marker sits ~20 studs from the probed pad position).
  **A name match has to be AT the pad, not merely named like it** (v1.128,
  live): the next build's walk admitted `Ugc.CompanyArea.WarehouseArea` — a whole
  district whose name says *warehouse*, a `Model`, so it scored 2 — and the trip
  hopped 860 studs onto its centre at `-278, 138, -212` and parked **142 studs
  from the deck the owner stood on**, `load 50` unchanged after 16 s. So a
  candidate the walk matched by name is only the pad when its park point is
  within `spudFulfillPadNear = 35` studs of `spudFulfillPadSpot()` (the two
  readings of that deck — the dump's part centre and the standing one — agree
  within 3.6 studs, while the withdraw side of the yard is 143 off); anything
  further is a landmark: the refusal names its real miss distance, the waypoint
  still comes back, and the trip ends the way it does when the world has no pad
  at all — marker hop → re-read → park on the measured spot. The game's own
  `Stores.DropOffs` folder is **not** gated: whatever it holds is a drop-off by
  the game's own grouping.
- **Sell** → the old `findSellSpots()` crop sell-board scan, unchanged.
- **The call goes first, for both picks** (v1.87, owner: *"didnt you say we
  could just call the sell bro?"*). `sellHarvester` fires `EVTSellAtStore` from
  where the harvester stands at the chosen destination's own pad part
  (Fulfillment → `Deposit_Warehouse`, Sell → the board) and watches the tank
  for 3.5 s. A tank that drops logs
  `✅ sold in place — load N → M, coins … (no pad trip)` and the ride **never
  moves**; only a call that leaves the tank alone falls through to the trip
  below.
- **The call is fired at ANY distance, then the trip** (v1.93, owner: *"why
  isnt it calling the sell function from anywhere? it was there before"*). The
  v1.88 range gate is gone: `sellHarvester` fires `EVTSellAtStore` from wherever
  the harvester stands, logs the distance it fired from, and watches the tank
  for **1.5 s** — a take logs `✅ sold in place at N studs … (no pad trip)` and
  the ride never moves; a no-op logs `<dest>: the in-place call didn't move the
  tank at N studs — taking the pad trip`. The take is real (a full tank sold
  in place 46 studs off the board); the distance in that line is what teaches
  the real band from runs instead of a guessed constant.
- The trip itself is the existing arc hop (`hopTo`, `SELL_HOP_SPEED`) plus
  `trySellAt(ride, what, pad, autoPad)`, which differs by destination:
  - **Fulfillment** (`autoPad = true`) presses **nothing** — user: *"the
    fulfillment you dont gotta do anything just go to the location and it does
    it"*. The pad unloads a parked harvester on its own; the trip only waits
    (16 s ceiling) and logs `fulfillment pad …: parked — this pad unloads by
    itself, pressing nothing`.
  - **Sell** (`autoPad = false`) fires the captured `EVTSellAtStore(ride, pad)`
    first, then falls back to Q (menu) / E (confirm) after a 3 s grace.
  **The tank dropping is the only proof** a pad took the load, in both cases. A
  failed trip backs off 60 s and the harvest carries on with the load it has.
- **The hop lands on the target's own height, from above** (v1.42 → v1.122).
  `hopTo` used to keep the **takeoff** height at both ends, so the return leg
  from the Fulfillment pad (~140) flew the whole way **under** the field (~172)
  and only surfaced on the last frame. v1.42's fix was
  `max(takeoff, target.Y)`, which cured that leg and quietly broke the other
  one: the outbound trip to a lower pad kept the field height, so the ride
  parked **28–34 studs above** the pad (live: `arc hop: 837 studs … (Y 166 →
  166)` next to a marker at Y 138, `load 50 … coins 14459 → 14459` after 16 s).
  It now lands at **`target.Y`** (a target with no height keeps the takeoff),
  and the lift is always enough to clear both ends by ~12 studs, so every
  arrival is a descent. The log names both heights:
  `arc hop: 412 studs, lifting 70 studs (Y 172 → 140)`.
- **A pad that is not in the world is still a place to park** (v1.122, owner:
  *"didnt i tell you the coords to do the fufillement"*). `Stores.DropOffs` is
  empty in the live build and the world-walk has only ever turned up a goto
  marker, so `sellHarvester` ends with `spudFulfillPadSpot()` — a
  **park-only** spot (`part = nil`, so no sell call is fired at an imaginary
  part, and Fulfillment needs no key: the pad drains a parked harvester by
  itself, v1.41 rule). A position alone is enough for a contact trigger, and
  "no pad instance" was never a good reason to leave 50 ripe cells in the tank.
  **Both picks have one now** (v1.126): the numbers are the owner's 📍 Get
  coords readings of 2026-11-02 — standing **on** each spot, so the Y is the
  deck a vehicle parks on rather than a part's centre — and a Sell trip with no
  board streamed anywhere no longer skips the unload, it parks at the crop
  board and lets `trySellAt` use its Q/E menu path (a sell board is **not** an
  auto pad, so `autoPad` stays false there). The line says which spot it used:
  `fulfillment: no pad instance is readable — parking on the measured spot
  (-353, 141, -92)`.
- **The four town spots the owner measured (2026-11-02, 📍 Get coords).** These
  are in-world positions read by standing on them, and they are the fallback
  addresses for anything the script cannot stream:

  | Spot | Position | What uses it |
  |---|---|---|
  | Fulfillment (warehouse drop pad) | `-353, 141, -92` | `spudFulfillPadSpot()` — the park-only Fulfillment fallback |
  | Sell crops (FarmCo board) | `125, 142, -150` | `spudCropSellSpot()` — the park-only Sell fallback |
  | Sell liquid | `86, 141, -288` | **no consumer yet** — the milk loop fills a carrier and only reports `store: <carrier> is FULL (n/m) — empty it or pick another`; a drain trip to this spot is the unbuilt half of that |
  | Sell logs and planks (LumberCo) | `232, 141, -232` | **no consumer yet** — the script harvests no wood (§3.8 refuses tree soil outright) |

  The old `-353, 138, -90` came from the `Deposit_Warehouse` **part centre** in
  the owner's 2026-10-30 dump; the standing reading agrees on X exactly, so it
  is the same pad, 3 studs higher and 2 along Z. The hop lands at the target's
  own Y (§3.10), so the deck number is the one a parked harvester wants.
- `SpudFulfillProbe.lua` reads the game's **live** offer billboards
  (`PCGP_ContextActions.Billboards`, with key + adornee), what the character is
  standing on, everything within 30 studs, `DropOffs` by distance, and nearby
  equipment. `PCGP_ContextActions.Buttons` is the whole action registry (70
  entries, no keys) and must not be used to answer "what is offered here".
  It now also answers the **Company-order** questions: every instance whose name
  says order / contract / request / company / cargo / shipment (with its whole
  value tree), the board's **visible text in both `workspace` and `PlayerGui`**
  (a ScreenGui board is invisible to a workspace-only walk), what `Stores`
  actually holds, every seed crate's `Configurations`, and one field cell's full
  key list plus `FieldHelper`'s exports — so "is a crop's grow time readable
  anywhere?" gets an answer instead of a guess. Each section is `pcall`-wrapped:
  one shape it did not expect prints `!! <section> FAILED` rather than eating the
  report.

### 3.11 A picked farm is reached before anything is read

User: *"also make it teleport to the spesific farm, find the tools then run."*
The start of a run with a **Farm owner** picked now hops to that owner's plot
before the equipment scan:

- `spudFarmHop(here, plotPos)` returns `nil, "no plot"`, `nil, "no position"`,
  `nil, "close"` (≤60 studs — no teleport for nothing), or
  `Vector3(plot.X, plot.Y + 5, plot.Z), distance`.
- The plot is `milkStorePlotOf(pick)` — the same owner lookup the milk store
  uses (`Configurations.Owner`, else the `PlotBillboard.Owner` label).
- A **seated** character is stood up first (`milkStandUp("farm")`, the game's F
  key), because a CFrame write on a seat does not replicate; if it cannot get
  out it stays put and says so instead of teleporting nowhere.
- After the hop it waits **0.5 s** so the fields and that farm's machines
  stream in, then `findTractor` / `findImplement` pick **that owner's** gear
  (§3.7), and the run logs `farm: using <tool> (<owner>) N studs away`.
- An unstreamed plot is not a guess: the run says
  `farm owner: <who>'s plot is not streamed — working from here`.

`farm_hop_test.py` pins the helper's decisions (7 checks).

### 3.12 Field work fires the game's own cell remotes

User: *"i want to make the seeding and planting and things use remotes."*
`SpudRemoteProbe.lua` was extended to capture field calls, and one manual
cultivate pass recorded the shape (2026-10-30):

```
ReplicatedStorage.Modules.Larry.EVTCultivateFieldCell:FireServer(
    Workspace.Objects.Fields.Field, {1=641},
    {1=Workspace.Objects.Equipment.KQF3000.Components.Cultivator.RaycastPart.Attachment})
ReplicatedStorage.Modules.Larry.FNCFillSeeder:InvokeServer(Workspace.Objects.Equipment.KADL)
```

- **Cell ids are the game's own keys.** `FieldHelper.GetCells(field)` is a dict
  keyed `x*128+y` (the same key `cellsAtStage` already decodes), so
  `spudFieldCellIds(field, stage)` returns exactly the numbers the call wants.
  A failed read returns **nil** (unknown), never an empty list.
- **The attachment is the tool's own.** `spudToolAttachment(impl)` prefers a
  `RaycastPart` attachment (the captured shape), falls back to a Seed/Detect
  one, and returns nil otherwise — nil means "drive".
- **The batch is verified, never trusted.** `spudFieldRemotePass(job, field,
  impl, baseCF, baseSize)` fires one call per remaining id **that is within
  `spudFieldReach = 24` studs of the tool's own attachment** (40 ms apart),
  then re-reads the
  stages: 0 left = `✅ remote seed: 50 cell(s) in 2.4s — the field is done
  without driving` and the sweep is skipped; some left = the sweep drives the
  remainder; none taken = the job is switched off **for the session** and the
  sweep drives (`remote seed: the game ignored 50 call(s) … — driving for this
  session`). A missing remote or attachment also disables that job once.
  **The reach filter is what killed the dead 10 s** (v1.120 — see §5): seed and
  harvest are `InvokeServer`, so every call waits for the server, and firing at
  the 44 cells a corner pose can never take cost 11 s per field for nothing. No
  field frame, no readable cell position or no numeric id = **no filter** (rule
  7); nothing in reach = no call at all, straight to the blocks.
  **The band grows with the implement** (v1.129, owner: *"if the tool is bigger
  cant the burst things also be bigger?"*): the corner pass filters at
  `spudFieldReach + spudToolExtraTiles(impl) * 5`, because the measured 20–24
  studs is the band around the **blade** and a wide tool's own ground is inside
  it. `spudToolExtraTiles(impl)` is the implement's measured width **past one
  tile** (`SpudFarm.partBoxes` → `widthFromParts` on both step axes →
  `widthTiles − 1`, clamped 0–6) and **0 whenever the build will not answer** —
  so a nil tool, a missing `SpudFarm` or a throwing `partBoxes` keeps the
  measured 24 and the 3×3 (rule 7). The stage re-read stays the judge: an
  over-generous reach costs a refused call, never a missed cell.
- **Stop-and-burst grid** (v1.71 single spot, **grid since v1.76**) — the band
  the lift probe measured (20 studs to the side at +8 taken, 30 refused; +80
  straight up taken) means the server takes a cell whose ground is within ~2
  tiles of the blade's, so a parked blade clears the disc around it. Between
  the call pass and the sweep, `spudRadialFire(job, field, ride, impl, stage,
  baseCF, baseSize, att)` walks the remaining cells as **3×3 blocks** (v1.90,
  owner: *"i wanted it to tp to a spot, do the closest 9 areas then go forwards
  then so on"*): cells are grouped into rows, three rows at a time are cut into
  three-column blocks, and each block gets one stop at its own centre, in
  serpentine order (each band alternates direction, so the ride always moves
  forward). Every cell belongs to exactly one block, so nothing is skipped and
  nothing is fired twice. At each stop it parks the **blade** on the stop — the tool trails
  behind the tractor, so the ride goes to `stop − (blade.Position −
  ride.Pivot)` with the ride's own rotation kept — waits (0.5 s for the first
  stop after the long ride, 0.5 s for the short hops; a call fired before the
  pose reaches the server is refused, the artifact every lift run hit) and
  fires **that block's nine cells**, 40 ms apart, **one call per cell**, capped by
  the seeder/tank budget. Height is free (+80 was taken), so the grid runs 10
  studs above the cells. **One stop = one EQUAL square** (v1.132, replaces
  v1.129's wide block): `spudBlockSide(spudFieldTaken)` sizes the side so the
  square's own **corners** stay inside the band that was measured to take. A
  square of `n` cells on the game's 10-stud grid puts a corner at
  `√2 × (n−1) × 5` studs out from its centre — 14.1 (3×3), 21.2 (4×4), 28.3
  (5×5) — and `spudFieldTaken = 20` is the sideways reading the lift probe
  recorded (20 taken, 30 refused), so this build gets **3×3 for every implement,
  wide or not**. A wide tool still grows the *corner pass*
  (`spudFieldReach + spudToolExtraTiles(impl) * 5`), because that leg filters one
  cell at a time against the blade, but the block earns no diagonal credit: the
  call carries a single attachment point. The stop's arrival tolerance
  (`4 * side`) and its off-block warning (`20 + (side − 3) * 10`) still derive
  from the side. **The stop waits for its blade, then re-aims** (v1.97 → v1.132):
  a hitched tool follows the ride through physics and settles at the ride's own
  rest trail, so the pass polls the attachment's position until the blade is on
  the block and only then fires. v1.97's single re-park was not enough — the
  trail is read *before* the jump, and after a 288-stud arc it is stale, so the
  **first** stop of every grid landed off its own block and fired "anyway". Live:
  `the blade is 32 studs off stop 1 — firing anyway` on the grid that spent its 48
  seeds with `36 took, 2362 left`, then — after a refill —
  `the blade is 41 studs off stop 1` and
  `fired 9 of 2362 cell(s) from 276 stop(s), 3x3 per stop — 0 took, 2362 left`,
  where `fired 9` is exactly one block: the honesty gate read those 0 takes after
  stop 1 and gave up the whole grid. Now the
  park is re-made **from the blade's fresh position** until it arrives (three
  aims for the first stop, one for the rest), a block whose blade demonstrably
  is **not** on it fires **no** calls, three such misses in a row end the grid
  and hand the field to the per-cell hop, and an unreadable blade still gets its
  burst (rule 7 — unreadable is not a miss). The per-cell hop waits the same way
  (was a flat 0.1 s). The stage re-read after the **first stop that actually
  fired** is the honesty gate: nothing taken = the server refuses a parked blade,
  the grid ends there and the hop drives. The final re-read is the proof:
  `remote seed: fired 46 of 46 cell(s) from 8 stop(s), 9 per stop — 46 took,
  0 left`; anything it misses is still hopped, so it can only add speed. Pinned by 18 `field_remote_test.py` checks
  (a 40×20 field is covered by 2 stops with 15 calls, a 9×3 field
  by 3 stops with 27 calls, a 4-seed seeder fires 4 and hands back dry, a
  5-stud reach takes nothing and leaves every cell standing, and a server that
  takes nothing ends the grid after **one** stop).
- **The tow settles before the next jump** (v1.129, owner: *"when it tp's the
  tools make the whole thing glitch and it falls out the map, make it wait for
  the tool to be behind the tractor before tping again bro"*). A hitched
  implement is pulled by its own constraint, so a **second** teleport while it is
  still swinging adds velocity to it instead of turning it — that is what threw
  the tool off the map. `spudWaitTool(ride, att, who)` (globals
  `spudToolSwing = 3`, `spudToolFar = 90`) reads the tool's **flat** distance
  from the ride twice, 50 ms apart: ≤3 studs of movement = `settled`; the first
  read past 90 = `far`; 30 beats later it says `swinging`; an unreadable
  attachment is `none` — nothing to wait for, and never a reason to skip the
  work (rule 7). It runs **before** every `PivotTo`: at each grid stop, before
  each per-cell hop, and before the field-to-field arc hop in the tour (that one
  bails out of the field entirely — `the JDS790 is N studs from the ride — it is
  not on the hitch any more, leaving the field alone rather than dragging it off
  the map`). A `far` tool ends the grid/hop pass where it stands (one log line,
  no more jumps); a `swinging` tool is named **once** per pass and the pass
  continues, because 1.5 s a cell is all the wait will ever give. The re-park
  after a missed arrival now takes a **fresh** settle rather than firing
  immediately. `field_remote_test.py` pins `none` / `settled` / `far 300` /
  `swinging` (bounded at exactly 30 beats), and that a flung implement makes the
  grid fire **0 calls and 0 jumps of its own** and log `not on the hitch any more`.
- **Every teleport carries the implement too** (v1.131, owner: *"we need to
  anchor the tractor when it tps because the tool drags it, also the tractor tps
  before the tool can get back in place"*). The v1.129 wait made the swing
  visible; it could not make the hitch keep up, because `Model:PivotTo` moves
  **only that model** — the implement is a separate model joined to the ride by
  the game's own constraint, so each hop left the tool on the old ground and put
  the constraint under the whole length of the trip. The live v1.130 console
  measured it: a 286-stud arc hop → **`hitch gap at arrival: 277.7 studs`**, then
  `the S4204 is 210 studs from the ride — it is not on the hitch any more` on
  every pass and `fired 0 of 2398 cell(s) … 0 took`. A taut tow is both reported
  symptoms: it drags the ride, and the settle wait (≤1.5 s) can never close it,
  so the next jump fires while the tool is still catching up.
  `spudPivotRig(ride, cf, tool)` (a **global**, so it costs no build-closure
  register) pivots the ride and then translates the implement by the **same
  position delta**, keeping the tool's own rotation — a ride turn must not spin
  the plow. **A self-propelled job's `tool` IS the ride** (the harvest tour sets
  `impl = ride`), so the `tool ~= ride` guard is not decoration: without it the
  delta is applied twice and the harvester lands **twice the trip away** — both
  harnesses pin that case. Every teleport goes through it: the **grid** stops and their
  re-parks (`spudRadialFire`), the **per-cell hop** and its re-park
  (`spudHopCells`), and every pivot of the **arc hop** (`hopTo`, which gained the
  `towed` parameter; the field tour passes the hitched implement — or the ride
  itself, which the guard turns into a plain hop — and the unload trips pass
  `nil`). The gap is then only the tool's own
  trailing distance, so the settle wait reads `settled`, the `far` bail stays as
  the backstop for a tool that comes off the hitch anyway, and the whole field
  gets called at instead of refused. `field_remote_test.py`'s fixture is now
  honest about the game — a ride `PivotTo` **does not** move the fake implement —
  and asserts the carry in both passes (a 15-cell field makes 15 jumps **and**
  15 carries) plus ten tie checks that no bare `ride:PivotTo` survives in them;
  `hop_test.py` pins the arc (24 carries over 25 moves, the hitch still exactly
  20 studs, and a control that a ride-only hop opens a 286-stud gap).
- **The tow is welded while it is hitched** (v1.133, owner: *"bro make it anchor
  te tool permanantly behind the tractor while it's hitched"*). Carrying the
  implement through the jump fixed the *gap* but not the *pose*: the tool still
  hangs on the game's own constraint, so what arrives behind the ride is whatever
  the solver managed in the frames available, and every grid stop has to re-aim
  from a fresh reading. `spudAnchorTool(ride, impl)` puts a client
  **`WeldConstraint`** (`SpudTowAnchor`, `Part0` = the ride's hitch **part**,
  `Part1` = the tool's, parented to `Part0`) — the same two `BasePart`s
  `findHitchPart` already ranks for the physical line-up (`Hitch` > `HitchRoot` >
  `HitchKnob` > `HitchTip`), **not** the `Components.Hitchable` /
  `Chassis.HitchableSocket` pair the captured `FNCAttemptHitch` takes, because a
  `WeldConstraint` joins parts and those are attachments —
  after claiming `SetNetworkOwner(LocalPlayer)` on the implement — a server-owned
  part rubber-bands straight through a client weld. Ride + implement are then
  **one assembly**: the tool is where the ride put it, there is no swing to
  refuse, and nothing drags. Three rules, all pinned by
  `tools/hitch_anchor_test.py`:
  - **Only after a proven hitch.** The call sits at the bottom of `hitchTool`,
    *below* the `if not didHitch then … return false` branch, so a weld is never
    the reason a failed hitch looked like a success.
  - **Only on a settled tow.** The weld is permanent for the whole hitch, so a
    mid-swing frame would hold the plow at an angle the game never rests it at.
    `spudWaitTool` is asked first and `far` ("off the hitch") / `swinging` /
    `gone` / `none` each refuse with a line; `stop` is silent.
  - **Released before anything unhitches.** `spudUnanchorTool(why)` runs at each of
    the seven sites that face the game — the park, the unhitch path, the blind X at
    attempt 3, the wrong-tool grab, loop end, loop stop, `destroyUI` — plus one
    inside `spudAnchorTool` itself (a different tool on the ride makes the old weld
    go first). An X press against a welded tow is a tug-of-war the script wins and
    the server loses, and "the tool stayed put" would then be a lie about the park.
  A refused weld (no hitch part, no readable attachment, the build rejecting the
  instance) costs **the anchor and nothing else** — v1.131's carry and v1.132's
  re-aim still work — so it cannot regress a field pass. `spudAnchor` is assigned
  in exactly two places (the weld, the release) and a rejected `Instance.new`
  leaves it **empty** rather than holding a phantom joint. Whether the live server
  accepts a client-created weld at all is **not yet measured**; the verdict is
  `anchor: <tool> welded to the <ride>'s <part> — the tool is part of the ride
  while it is hitched` followed by grid stops that need no re-aim, versus the
  honest `the tow stays on the game's own constraint`.
- **Teleports only** (v1.95, owner 2026-10-31: *"during the plowing it
  started doing the fast tp and then kinda strafing the ground"*). Between
  the grid and the hop there used to be a **serpentine tween sweep**
  (`spudSweepCells`, 45 studs/s with a burst every 0.5 s) — the one thing
  that slid the ride along the ground. It is **deleted** with its harness
  checks: a field pass is the call pass → the 3×3 block grid →
  `spudHopCells` (one teleport per cell) → grid → hop, round after round,
  and a cell neither takes is named and left for the next pass. Nothing
  in a field pass touches a movement key or a tween.
- **It runs from the field, hitched and seated** — the same state the game fires
  the call from: the attempt sits at the top of `sweepField`, after the ride has
  arrived and the tool is hitched.
- **Plow / seed / harvest are siblings.** Only cultivate was recorded; the other
  three use the same `(field, {id}, {attachment})` shape at the same path
  (`EVTPlowFieldCell` FireServer, `FNCSeedFieldCell` / `FNCHarvestFieldCell`
  InvokeServer). If a build disagrees, the verification disables just that job
  instead of corrupting the pass.
- **Seeder fill** — `spudFillSeederRemote(seeder)` calls the captured
  `FNCFillSeeder(seeder)`; `buySeedAndFill` still presses V when the seed count
  does not rise, so a refusal costs one extra press, not a failed trip.
- **Fill to the machine's OWN capacity** (v1.133, owner: *"if a seeder has like
  600 capasity, make it fill up the seeder fully"* → *"fill to max, trips scales
  to fix. by the way you can carry to seed crates at once"*). A seeder is no
  longer topped up with one crate: the pour loop runs while
  `spudSeederWantsMore(count, cap)` (i.e. `count < cap`, and **false** when either
  number is unreadable — an unknown pair is never "hungry") and the hands still
  hold a crate, so a 600-slot machine gets 600 seeds instead of the first box's
  50. Three globals carry the arithmetic (all **pure**, so the harness can slice
  them; the loop they drive is nested inside `buySeedAndFill` and is pinned by
  source ties instead):
  - `spudCratesPerTrip = 2` — the game's own carry limit, so one town visit buys
    **two** crates. After the first purchase is proven the run prices and carries
    a second crate, proven by the `CarryLinks` **child count**
    (`spudCratesInHand()`) rather than by `carrying()`, which is already true with
    one box in hand. A second crate dearer than the *post-first-buy* balance is
    left on the shelf, and anything bought-but-unpaid is put back down
    (`spudDropRemote` until the hands read empty) before the fill, so a shelf box
    can never reach the seeder.
  - `spudSeedTripsNeeded(cap, have, perCrate, cratesPerTrip)` =
    `ceil(ceil(room / perCrate) / cratesPerTrip)`, and **nil** when the capacity or
    the crate size is unreadable (rule 7 — that is unknown, not one trip).
    `spudSeedsPerCrate` is **learned** from a real pour (the count a rise actually
    gave), never guessed at 50, so until a crate has been poured the ceiling stays
    at the old constant.
  - `spudSeedTripCeiling(needed, floorMax)` only ever **raises** the floor — 4 for
    the entry check, 3 for a mid-field refill — so a big tank gets the trips it
    needs (`refill 1/6`, not the unreachable `refill 1/3`) and a 50-slot seeder
    behaves exactly as before. Both call sites read it; the price gate still sits
    **before** the trip is counted.
- **Buying seeds from anywhere is NOT a thing** (owner: *"in earlier explot check
  diddnt you say that we could buy seedcs from anywhere? if no then drop it"*).
  It was never measured — the only answered shop questions are **Fill from afar**
  (refused at 963 studs) and **Spawn from afar** (works from anywhere), so no
  remote here is assumed to ignore proximity and nothing is wired for it.
- **Tests tab · batch field remote** (v1.43, user: *"can we just abuse bugs to
  plow and harvest"*). The captured call already carries a **list** of ids
  (`{1=641}`), so with the Tests toggle on (`spudBatchRemotes`) the pass first
  fires **one call with every remaining id** via `spudFieldRemoteCallMany` and
  re-reads the stages: all gone = `✅ batch test: N cell(s) in ONE call` and the
  sweep is skipped; some taken = the rest go one call per cell; none taken =
  `batch test: the server ignored the id list … — one call per cell` and the
  normal per-cell pass runs. It is **on by default** since v1.88 (owner: *"can
  you turn batch remotes on by default"*), session-only, and an
  ignored list never switches a job off. The batch's own takes are counted into
  the final `✅ remote …` line.
- **Tests tab · live probes** (trimmed in v1.60 and again in v1.74, user:
  *"remove any tool we arenet using anymore in the bugs tab becuase it's
  getting crowsed"*). The tab now holds the **Batch field remote** toggle and
  one probe (`spudTestRun`, `spudTestWork`, `spudTestSay`; lines land in the
  Tests paragraph and as `test:` lines, and `spudTestCopy` puts place id +
  build + player + the whole `spudTestLog` on the clipboard with
  `setclipboard`):
  - **Remote list** (v1.59, user: *"we need to find another way of forcing the
    seeding and plowing"*) — read-only. Walks `ReplicatedStorage` (Modules
    first, depth 4, 3000 nodes — v1.124: the cap was 600, so the v1.123 report's
    "339 found (601 nodes walked)" was a **truncated** list that did not say so;
    it now names `CAP 3000 REACHED` when it runs out). The per-cell field calls
    are only the ones the game fired by hand; a bulk/field door that was never
    fired would show up here and nowhere else.
  - **Field remotes** (v1.66) — the three field calls the capture never fired.
    `FNCSprayFieldCell(field, {id}, {att})` is tried with the plow/seed shape and
    judged on `IsWatered` / `PlantGrowth` / `Stage`; `FNCEditField()` and
    `FNCConvertRundownField()` are invoked with **no arguments** purely to read
    the shape they demand — an error names it, and nothing that could rebuild
    the field is handed to them. Live (2026-10-31, twice): the spray call runs
    and the cell does **not** change (Empty and Plowed both), `FNCEditField()`
    returns a **table** (a reader, not a setter — still just an address, which is
    what v1.124's config read inside **Grow now** exists to dump) and
    `FNCConvertRundownField()` refuses with
    `ConstructionHandler:686: attempt to index nil with 'Name'` — it wants an
    instance, so it is not a free field reset. **The spray leg was lying (v1.124).**
    The v1.123 run reached a real crop (`cell 518 is Seeded, watered false,
    growth 1170 (tool none)`) and still said `no change from here`, because
    `spudToolAttachment` had found no implement, the third slot got a bare `nil`
    instead of the captured `{att}` **list**, and an empty request was reported as
    a verdict. It now sends `{ att }`, names the attachment it sent (or says no
    implement exists and that a `no change` **answers nothing**), and points at
    **Grow now** for the sprayer-by-name test. So **water on a growing cell is
    still unmeasured.**
  - **Grow now** (v1.123, owner: *"is there a exploit that we can make the croops
    grow instalntly"*) — the instant-growth question, asked of the four things
    that were never measured. It (0) walks `Modules` for a `ModuleScript` named
    **grow / crop / config** and requires each inside `pcall`, printing the table
    one level deep (v1.124, because the v1.123 remote list names
    `EVTUpdateCropGrowthConfig` — a broadcast config means a client copy may
    exist, and the per-crop **grow time** is the number both this question and the
    owner's order-ranking rule need); (1) prints **every stage name on one of our
    fields with the cell's own `PlantGrowth` / `GrowthMultiplier` / `IsWatered` /
    `SeedType`**, which is also the only way to see whether the harvest job's
    "any stage we do not know is a standing crop" rule is being handed an
    immature name; (2) **gets INTO the harvester** (spawned out of storage if it
    is parked — the Tool-apart answer says a loose implement takes nothing, so a
    refusal read from outside the seat would be a false answer), parks the blade
    on a **Seeded** cell with the grid's own settle-poll and fires
    `FNCHarvestFieldCell` at it, then reads the **stage and the tank**: a take
    that raises `Capacity` is the exploit (the wait can be skipped), a take that
    raises nothing is a bare cut, a refusal means the server wants a ripe cell;
    (3) writes the cell's `PlantGrowth` to the **ripe number the game itself
    just printed** (never tried — Force a tile forged `Stage`) and distinguishes
    "a fresh `GetCells` dropped the write" (the cell table is a copy, nothing to
    patch) from "the mirror now reads ripe" (re-fire the cut and see whether the
    server consults it); (4) fires `FNCSprayFieldCell` with the **sprayer's own**
    attachment at that cell — neither the v1.66 run (an *Empty* tile) nor the
    v1.123 one (a `Seeded` tile, but `(tool none)` — the call carried **no**
    attachment) measured water-vs-growth on a growing crop — and finds the
    sprayer by walking `Objects.Equipment` for a spray/sprinkler/water/irrig
    name, printing every machine with its real `EquipmentType` when none
    matches (no guessed type name). It is **not** in Run all, which stays the two
    read-only probes; this one sits in a machine and cuts a cell. No harness —
    the live re-read is the verdict, and `Copy report` carries it.
    **ANSWERED (the owner's run, v1.124):** `early cut — Seeded → Empty, tank
    0 → 1 — TAKEN AND IT PAID`, so the wait is skippable and the harvest call
    does **not** want a ripe crop. The behaviour is §3.14 (**Early harvest**,
    on by default from v1.125); the same run named the working attachment
    (`HarvesterAxle.AxleAttachment` — the SRC6 has no `RaycastPart`, so the
    harvest-sounding rank wins), read `CropGrowthConfigClient → GetConfig=fn
    SetConfig=fn`, and showed **no sprayer on this plot**, so steps (4)'s water
    question cannot be answered here at all.
  **Copy report** (`spudTestCopy`) now also appends the last **60 farm-log
  lines** from `_G.SPUD_TRACE` (v1.85) — a Tests-only copy cannot answer "why is
  harvesting silent", and the console is the place the owner does not want to
  dig in. **Copy console** (`spudTestCopyConsole`, v1.86) is the same clipboard
  without the test run — the last **150** farm-log lines — for a run that is
  stalling and needs no experiment (owner: *"you should add a copy consol line
  bro"*).
  **Run all** runs the two remaining probes (remote list, field remotes); both
  refuse while `loopThread` is live and touch no animals or other plots.
  There is **no harness** for them — the live read is the only verdict.
  **Removed once answered** (v1.44–v1.80; every result is in §5 and the console):
  From here / Wrong stage / No attachment / All at once (seat, stage and
  attachment are checked, and a multi-id list is only partly taken), Sell abuse
  (`EVTSellAtStore` ignores distance; an empty tank never pays twice), Grab from
  afar (carry works at 35 studs), Spawn from afar (works from anywhere), Fill
  from afar (refused at 963 studs), Field API (the module exports **no setter**;
  `UpdateCell`/`UpdateCells` are the client's own writers), Force a tile,
  **Wrong tool** (v1.69): a plow's own attachment firing cultivate on a Plowed
  cell the blade had been hopped onto stayed `Plowed → Plowed — IGNORED`, so
  the server checks *which implement* the attachment belongs to — one sweep
  cannot run every stage, and each verb keeps its own tool — and **Lift test**
  (v1.74): three runs returned the same band, a call TAKEN with the blade
  **20 studs to the side at +8** (30 refused) and from **+80 studs straight
  above**, so the sweep's 20-stud reach and rows are measured, not guessed, and
  **Tool apart** (v1.80): a plow taken off the tractor with its blade **0.0
  studs** from an Empty cell still came back `IGNORED`, so a field call also
  needs the implement on the ride the player is driving — position is not the
  only check, and a loose tool can never be used.

**Remote inventory (v1.60, owner's report 2026-10-30).** 334 remotes under
`ReplicatedStorage`, all on `Modules.Larry`. Field: `EVTPlowFieldCell`,
`EVTCultivateFieldCell`, `FNCSeedFieldCell`, `FNCHarvestFieldCell`,
`FNCSprayFieldCell`, `EVTFieldPacket`, `FNCEditField`,
`FNCConvertRundownField`. **Never wired, and now named**: `EVTHerdRequest`,
`EVTAnimalAction`, `EVTCollectAnimalProduction`, `EVTFilthCleaning`,
`EVTFillFeeder`, `EVTFillFeedDispenser`, `EVTOpenBarnGate`, `EVTToggleDoor`,
`EVTDepositWarehouse`, `EVTWithdrawWarehouse`, `EVTFulfillOrder`,
`EVTTeleportToFarm`, `FNCCutTree`/`EVTToppleTree`, `EVTSellObjects`,
`EVTSellAtAnimalCo`, `FNCForceRespawnEquipment`, `FNCSetEquipmentHome`. Those
are the next candidates for the milk/barn/feed/gate/deposit steps that still
press keys or drive the UI.

**v1.124 re-read (the 339 that came back after the cap was raised).** Same
`Modules.Larry` home, and it names two doors the open questions were waiting on.
**Growth**: `EVTUpdateCropGrowthConfig` (the server broadcasts a crop-growth
config — so a client copy may be readable, which is what **Grow now**'s config
walk asks), plus `EVTWatered`, `EVTHireCropduster` / `EVTHireFreeCropDuster` /
`EVTUsedFreeCropDuster` (a hired duster waters a whole field — never probed) and
`EVTSendOfflineGrowthSummary`. **Company orders** (task #6, and this is the first
time the game has named them): `FNCGetOrderProgress`, `FNCAcceptOrder`,
`EVTRefreshOrders` / `EVTFreeRefreshOrders`, `EVTOrderDepositProgress`,
`EVTOrderFulfilledFX`, `EVTWithdrawOrderFX`, `EVTDepositIntoTrainCar`,
`EVTTrainOrderDeposited`, `EVTCompleteTask` / `EVTLoadNewTasks` / `EVTRefillTasks`
/ `EVTSendTasksToPlayer` / `EVTUpdateTasks` / `FNCSelectGoal`, and
`FNCGetAvailableBoxes`. None is wired and none has been fired — **rule 4 still
applies: the arguments are unknown until a probe reads them**, which is what
`SpudFulfillProbe.lua` was built to answer.

**Is a tile forceable?** No — and the last candidate is closed too.
`EVTFieldPacket` is the server telling clients which cells changed: live packets
are a **4-byte header + 6-byte cell records** (`CellToBuffer` is the 6 bytes; the
stage is one byte — live `04` Cultivated, `08` Plowed, `0c` Seeded, `20` on a
standing crop). Forging one was tested twice: a bare record (v1.62) and then a
**real** packet with only its stage byte patched (v1.64) — both ended with **no
packet back and no cell moved**, so there is no client→server handler. The live
dump also shows no setter, and Force a tile (2026-10-30) ended `the client cell table is writable — UpdateCell kept the
forged Cultivated for 2 s` then `reads Cultivated — IGNORED: no update arrived`:
the server never reads the client's copy. A cell only holds `Alternate,
GrowthMultiplier, IsWatered, PlantGrowth, Position, SeedType, Stage` (50 cells,
`Stage=Plowed` on the live field). `spudSweepCells` therefore forces *position*,
not state — and position has far more slack than assumed. Measured live
(2026-10-31, every reading retried): a cell was TAKEN with the blade **20
studs to the side at +8** (30 refused) and with the blade **+80 studs straight
above** it, so the check is the ground under the blade within ~2 tiles — not
that it is over the cell — and a parked blade clears the block around it
(`spudRadialFire`, v1.71). The three untouched field calls are
readers/no-ops live (`FNCSprayFieldCell` changes nothing, `FNCEditField()`
returns a table, `FNCConvertRundownField()` wants an instance) and the **tool
identity is checked** (cultivate fired from a plow's own attachment at a
Plowed cell the blade was over stayed `Plowed → Plowed — IGNORED`), so one
sweep cannot run every stage.

`field_remote_test.py` pins the ids, the attachment pick, the call shape, the
full/partial/ignored outcomes, the session switch-off, the fill fallback, the
hop, the sweep (a 15-cell field taken in one tween, the budget cutting it
short, and an ignored sweep leaving every cell standing) and the single-spot
fire (a 60-stud reach taking all 15 cells from one teleport and 15 calls, a
4-seed seeder firing 4 and handing back dry, a 5-stud reach taking nothing).

### 3.13 Equipment actions fire the captured calls

User: *"use remoted for everything."* The same probe pass recorded the
equipment/action calls, so the loop now fires them instead of pressing keys or
driving the Equipment Manager UI. All live under `Modules.Larry`:

```
FNCEnterEquipment(vehicle, seat)
FNCAttemptHitch(tractor.Components.Hitchable, tool.Chassis.HitchableSocket)
FNCUnhitch(tractor.Components.Hitchable)
FNCSpawnEquipment(model) / FNCStoreEquipment(model)
EVTRequestToCarry(draggable) / EVTRequestToDrop()
```

- **Fired only where the game offers the action**: mount after the walk-up,
  hitch/unhitch at the same line-up pose the key needs, carry at the crate,
  spawn/store for a machine that is actually stored/out.
- **The effect is the proof** — the seat holding the humanoid
  (`spudEnterRemote`), the existing hitch/unhitch tug (`attemptHitch`,
  `dropImplementAtOrigin`), `InStorage` flipping (or a >100-stud move for a
  spawn that rebuilds the model) in `spudEquipRemoteAct`, and `carrying()`
  turning over for carry/drop.
- **Sell and buy** — `EVTSellAtStore(ride, pad)` is fired for the **Sell**
  destination (the tank dropping is the proof; Q/E after a 3 s grace), and
  `FNCRequestStorePurchase({crate})` is fired at the buy popup (balance or a
  new crate is the proof; the menu click is the fallback). **Fulfillment**
  makes no call and presses no key: the pad unloads a parked harvester itself
  (v1.41), so the trip only waits on the tank.
- **The shop closes itself after a buy** (v1.96, owner 2026-10-31: *"after it
  buys a seed can you make it close the ui"*). The old close step searched the
  whole `GuiViews` tree for a "close" button and then pressed F whenever **any**
  GuiButton was on screen — the HUD and top bar always are — so F fired every
  time and the shop menu stayed up. `buySeedAndFill` now reads the actual open
  menus (`GuiViews.Menus` plus any `*Menu` layer beside it, by
  `LayerCollector.Enabled`), clicks that menu's own close control **inside** it
  (text/name close/exit/back/cancel/dismiss, or an `X`), re-reads `Enabled`, and
  only presses F if it is still up. It only closes what the trip **raised**: the Enabled layer set is
  recorded just before F, so the always-enabled layers (`SettingsMenu`,
  `BuildMode`, `FarmerPass`, `PalletStorage`…) are never touched (v1.99 — the
  first cut tried to close those and only logged warnings). The buy dialog is
  closed **by its own container** (v1.100): that screen is a frame inside an
  always-enabled layer, so Enabled alone reported "no shop menu is open" while
  the dialog sat on screen — a shown **Purchase/Buy** control now names the
  container GuiViews holds it in, and that container's own close (the red X) is
  clicked before the layer pass runs. Every run logs
  `seed shop: <Menu> closed (handler)` or the honest
  `<Menu> is still open after F — close it by hand once`; a run with nothing
  new open says `seed shop: no shop menu is open — nothing to close`.
- **The old path always remains**: F for a mount, X for hitch/unhitch, E for a
  crate, the Equipment Manager UI for spawn/store. `spudEquipRemoteMiss` counts
  ignored calls; three switch that one action back to keys/UI for the session.
- **Not wired yet**: cleaning a stall, milking, herding, feeders and gates.
  Their shapes were never
  captured — `SpudRemoteProbe.lua` now has an **ACTION CALLS** section and a
  checklist for them (run it, or let one normal milk/barn cycle record while it
  runs), and `EQUIPMENT CALLS` confirms those above.

`equip_remote_test.py` pins the kit, the call shapes, the effect proofs, the
UI/key fallbacks and the three-miss switch-off.

### 3.14 A crop does not have to be ripe to be cut (the early harvest)

**Answered live by the owner's own run of Tests → Grow now (v1.124):**

```
test: growth: early cut — Seeded → Empty, tank 0 → 1 — TAKEN AND IT PAID:
a crop can be harvested before it is ripe — the wait can be skipped
```

So the growth wait is optional, and the farm loop now takes it. Global
`spudEarlyCut` (**on** by default, remembered in `spudSavedEarlyCut`, Settings
toggle **Early harvest**) makes a `Seeded` cell count as a standing crop in the
**one** predicate every harvest decision reads — `grownStage(s)`, used by
`whichNeed(JOBS[4])`, `whichCells`, `spudFieldCellIds` and the per-field census —
so the tour, the cell ids, the tank gate and the wait cannot disagree about what
"cuttable" means. A cycle is then: plow → cultivate → seed → harvest (the same
field, minutes later) → sell → replant, and an hour of standing in
`🌱 growing: 50/50 cell(s) still Seeded` becomes one restart line,
`🌱 early cut: 50 cell(s) are cuttable now — restarting the loop instead of
waiting`.

Three things this deliberately does **not** change:

- **Off means the old build.** With the toggle off, `Seeded` is again not
  standing, the wait waits, and the census column reads `standing` instead of
  `cuttable` — `early_cut_test.py` pins both halves, plus that the plow,
  cultivate and seed jobs aim at their own stage name either way.
- **Unreadable is still not empty** (rule 7): a nil read or a `total = 0` read
  returns `nil` from `whichNeed`, so no pick turns an unreadable field into a
  finished one. (`whichNeed` used to compute `total − the four known names`,
  which threw on a table with no `total`; it now sums the stage names through
  the predicate, which cannot.)
- **The restart is bounded.** `spudCutWatch` (a global table) remembers the last
  cuttable count: the **same number twice in a row** means the harvest pass took
  nothing — no harvester on a picked foreign farm, a refused call — so from the
  third read on `waitForGrowth` waits like a normal cycle instead of restarting
  on a dime and hammering `GetCells` in a hot loop.

The attachment that made this measurable is also the one the loop now uses:
`spudToolAttachment(SRC6)` ranks **RaycastPart → harvest-sounding part →
Seed/Detect → any**, and the SRC6 has no `RaycastPart` at all, so it picks
`HarvesterAxle.AxleAttachment` (the probe prints `attachment: SRC6 →
HarvesterAxle.AxleAttachment (harvest)`). That is the v1.89 wheel-strut failure
closed with a live take, not with another guess.

**Get coords** (Settings, 📍) exists because the pad positions this build parks
on came out of the owner standing somewhere and typing the numbers into the chat.
It reads `HumanoidRootPart.Position`, logs `(x, y, z)` rounded to whole studs and
puts the same text on the clipboard (`coords: (…) — copied, paste it in the
chat`, or the honest `the copy was refused, read it above`). Stand on a pad, press
it, paste it here: that is how a spot the script cannot stream becomes a spot it
can drive to. Its first four readings (2026-11-02) are the table in §3.10 — and
because a standing reading is the **deck**, not the part centre, it corrected the
Fulfillment pad's Y from the dump's 138 to 141.

---

## 4. Code map (names, not line numbers — they move)

| Area | Function / thing |
|---|---|
| Build identity | `VERSION` at the top of the file (`rebuild vX.YY · fluent gui`) |
| Farm width / owner | top-level `SpudFarm` (`widthTiles`, `widthFromParts`, `rowPlan`, `ownerWanted`, `workTiles`, `partBoxes`, `declaredWidth`), `spudOwnerChoices`, global `farmOwnerPick`, `spudFarmOwnerDrop`; `sweepField` plans rows from `rowPlan` |
| Go to the farm | global `spudFarmHop(here, plotPos)` (nil+reason, or centre +5 Y and distance), `milkStorePlotOf(who)`, `milkStandUp(who)` (default `"milk"`); wired at the top of `runFarmingBody` |
| Whose machine | global `equipOwnerRank(m)` (farm being worked → mine → no readable owner → never another account), used by `findTractor` / `findImplement`; owner tag read by `milkStoreOwnerOf`. **What** it is: globals `spudEquipTypeKey(m)` (the game's `EquipmentType`, letters only), `spudEquipIs(m, STEMS)` (stem match), `spudEquipSeat(m)` (`VehicleSeat`/`Seat`), `spudEquipTows(m)` (`Components.Hitchable`), `spudEquipHereText()` (the world's `Name=Type (stored)` list); build-closure tables `HARVEST_STEMS` / `TRACTOR_STEMS` / `HAULER_STEMS` / `TOOL_STEMS` / `TYPE_STEMS` / `TYPE_MODEL` |
| Tree soil | global `spudTreeField(typeName, modelName)` (wood/tree/log/forest/timber/lumber/sawmill/stump → no crop harvest) and `spudNoCells(st)` (successful 0-cell read is empty, `nil` read is unknown); used in `probeWork`, `runPass`, `needLeft`, `grownLeft`, growth wait |
| Field remotes | global `spudFieldRemoteKit()` (Modules.Larry: plow/cultivate/seed/harvest/fillSeeder), `spudFieldCellIds(field, stage)` (GetCells keys), `spudToolAttachment(impl)`, `spudFieldRemoteCall`, `spudFieldRemoteCallMany` (Tests batch), `spudFieldRemotePass` (fires, re-reads, self-disables a job), `spudRadialFire` (one EQUAL square per stop, sized by global `spudBlockSide(spudFieldTaken)` — the blade re-aims until it lands, fires that block's cells and skips a block it demonstrably missed, serpentine order), `spudHopCells` (one teleport per cell — the tween sweep was deleted in v1.95), `spudFillSeederRemote`; the tow gate `spudWaitTool(ride, att, who)` + `spudToolTrail` (constants `spudToolSwing = 3`, `spudToolFar = 90`) runs before **every** move, and the move itself is global `spudPivotRig(ride, cf, tool)` — pivot the ride, then translate the implement by the same delta (§3.12); the width helper `spudToolExtraTiles(impl)` scales **only** `spudFieldReach` (the block sizes off `spudFieldTaken = 20`, the band that was measured to take); state `spudFieldRemoteState`, `spudBatchRemotes` (Tests toggle, **default true** since v1.88); wired at the top of `sweepField` and in `buySeedAndFill` |
| Tow anchor | globals `spudAnchorTool(ride, impl)` / `spudUnanchorTool(why)` and the state `spudAnchor` (v1.133, §3.12) — a client `WeldConstraint` (`SpudTowAnchor`) joining the two hitch **parts** `findHitchPart` ranks (`Hitch` > `HitchRoot` > `HitchKnob` > `HitchTip`) — **not** the `Components.Hitchable` / `Chassis.HitchableSocket` attachments the captured hitch call takes — after `SetNetworkOwner` on the implement; welded **only** after the tug test and **only** on a `settled` read, released before any unhitch (7 sites) at the two loop exits and in `destroyUI`; call sits at the bottom of `hitchTool` |
| Seed fill | globals `spudCratesPerTrip` (**2** crates a town visit), `spudSeedsPerCrate` (**learned** from a real pour, nil until then), `spudCrateSeedCount(crate)`, `spudCrateHasSeed(n)`, and the pure arithmetic `spudSeedTripsNeeded(cap, have, perCrate, cratesPerTrip)` / `spudSeedTripCeiling(needed, floorMax)` / `spudSeederWantsMore(count, cap)` / `spudCratesInHand()` (`CarryLinks` children) — v1.133: the pour runs to the machine's own `MaxCapacity` and the trip budget scales to it instead of the constant 4; wired in `seedCheck`, the `seedCrateIntoSeeder` loop, the second-crate block and `seedPasses`' `refillsMax` |
| Tests tab | `spudTestRun(kind)` (busy guard + pcall), `spudTestWork(kind)` (`remotes` / `fieldremotes` / `growth` / `shop`), `spudTestRunAll`, `spudTestCopy` (`setclipboard`, test run + last 60 farm lines), `spudTestCopyConsole` (`setclipboard`, last 150 farm lines only), `spudTestSay`, `spudTestLog`, `spudTestPara`/`spudTestShow`; buttons **Remote list**, **Field remotes**, **Grow now** (v1.123), **Shop counter** (v1.103), **Run all**, **Copy report**, **Copy console** (the settled one-shots were removed in v1.60, **Wrong tool** in v1.69, **Lift test** in v1.74, **Tool apart** in v1.80) |
| Equipment remotes | global `spudEquipRemoteKit/State` (enter/hitch/unhitch/spawn/store/carry/drop/sell/purchase), `spudEquipRemoteCall`, `spudEquipRemoteMiss`, `spudEquipRemoteAct` (spawn/store proof), `spudEnterRemote`, `spudHitchParts`, `spudHitchRemote`, `spudUnhitchRemote`, `spudCarryRemote`, `spudDropRemote`, `spudSellRemote`, `spudPurchaseRemote`; wired in `managerAction`, `mountTractor`, `attemptHitch`, `dropImplementAtOrigin`, `carryCrate`, the two held-item drops, `trySellAt` and `buySeedAndFill` |
| Row driving | `keyRow(tr, seat, from, goal, who)` drives rows on real W (the game auto-steers); global `spudRowSteer(angDeg, crossY, cross, tol)` (heading > 8°, cross-track > 2.5 studs → re-center); travel `ALIGN_MAXVEL = 34`, fallback row speed 18; **field-to-field travel is `hopTo` (the arc) for every job**; the A* planner was deleted in v1.81 and the row driver in v1.82, so a field pass never touches a movement key |
| Dirt line | global `milkDirtLine = 24`; `milkDirtHigh(spot)` (the single "is this dirty?" answer) |
| Drop-off | global `spudDropOff` (**Fulfillment** / **Sell**, remembered in `spudSavedDropOff`), `spudSellNow(cur,max)` (full tank + a chosen destination), `spudHarvestFull(cur,max,need)` (full tank **or** room less than the cells still standing), `spudFulfillSpots()` (Deposit_Warehouse top; a world-walk match has to sit within `spudFulfillPadNear` of the measured deck or it is refused and only its marker comes back), `spudFulfillPadSpot()` (the measured `-353,141,-92` — the park-only fallback *and* the point the band is measured from), global `spudFulfillPadNear = 35`, `spudCropSellSpot()` (the measured `125, 142, -150` crop board, park-only fallback for the Sell pick), `findSellSpots()` (crop sell board), `sellHarvester` (arc hop + `trySellAt`), `harvestSellIfFull`; Farm tab dropdown `dropOffChoice` |
| Early harvest | globals `spudEarlyCut` (**on**, remembered in `spudSavedEarlyCut`) and `spudCutWatch` (the wait's spin guard); the one predicate `grownStage(s)` (v1.125, §3.14) read by `whichNeed`/`whichCells`/`spudFieldCellIds`/the census and by `waitForGrowth`, Settings toggle **Early harvest** |
| Coordinates | Settings **📍 Get coords** (v1.125) — logs `(x, y, z)` from `HumanoidRootPart.Position` and copies the same text, so a pad the script cannot stream can still be named by the owner |
| Clean pass | pre-pass offer watch (0.96 s) → clean watch (2.2 s); per-cow clean `≤2.25 s` |
| Herd | `milkHerdBatch(stalls, cows)`, `milkHerdTargets`, `milkHerdSend`, ordering nearest-barn-first, `milkHerdArm` |
| Farm choice | `milkFarmReadyCount(who)`, `milkFarmSwitch(want, owner, readyHere, parkedHere)` |
| Barn lock | name + position, resolved by spot — see `milkBarnLive` / `milkBarnFor` |
| Stall scan | `milkStalls` (narrow walk + whole-map fallback), global `spudStallScan(owner, cf, size, hopped)` (the re-read that waits for a just-hopped barn to stream — §3.4); `milkFarmReadyCount` reads `milkStalls` directly, no wait, since it is looking at a farm it is NOT standing on |
| Cow reads | `milkCows`, `milkOwnerOf`, `milkPercentOf`, `milkStateOf`, `milkDrops` |
| Store | `milkStoreAmount`, `milkStoreDeposit`, `milkPollFor`, `milkFrame`; remotes `EVTRequestToCarry`, `EVTFillLiquidCarrier` (key path is the fallback) |
| GUI | Fluent shell, RIGHT SHIFT, 📡 webhook, 🥔 overlay; `spud-gui-preview.html` is a browser mock |

**Read-only probes** (run in game, paste the report): `SpudStallProbe.lua`
(stalls/dirt), `SpudDump.lua` (world structure, run twice: town + farm),
`SpudFieldProbe.lua` (every field's `FieldType`, its cells, what is planted
where, seed boxes and FieldHelper's tables), `SpudFulfillProbe.lua`
(Fulfillment / Shipment area: candidate models, unload pad parts, prompts,
signs, live context actions, the old sell-pad targets, and the **company-order**
sections: order-named instances with their value trees, board text in workspace
*and* PlayerGui, what we hold, seed-crate configs and whether a cell carries a
grow duration), `SpudRemoteProbe.lua` (remotes
while you act by hand — milk calls plus the FIELD CALLS section for
plow/cultivate/seed/harvest/FillSeeder), `SpudBarnProbe.lua`,
`SpudCrateProbe.lua`, `SpudEquipProbe.lua`, `SpudFeedProbe.lua`,
`SpudSellProbe.lua`, `SpudCapture.lua`. `SpudBoot.lua` is the error-reporting
loader. `FarmingAndFriends_Main.lua` is the older generic script; superseded.

---

## 5. The conversation, condensed

Chronological, oldest → newest. Each entry: what was reported, what was actually
wrong, what changed.

**Early arcs (from the git history).** Build string v1.9 → clean rebuild in
progress. `2ae3d37` fixed the **200-local limit** that broke loading; `22992d1`
added the on-screen loader so failures are visible without a console; `8fd16d5`
and `831728e` cut fixed sleeps out of the milk loop and milked each cow as it
landed; `129fbf3` restricted carrier loading to free-range jugs; `d154efe` used
the game's own carry/fill remotes as a fast path with key-press fallback.
`2586443` herds the cows nearest the barn first. `7693ef3` added the three-farm
rotation. `84da366` locked one barn per farm for the session. `1a4b243` made
farm changes a teleport to the remembered plot centre instead of a walk (a
distant plot is streamed out, so the pass used to see "no farm").
`a150ffe` narrowed the stall scan to `Objects.Buildings` (95,517 → 73 calls).
`f5a2b51` added `SpudBarnProbe.lua` for the herd-not-sending bug.

**"It does not switch the plot/players field when it gets under the herd
amount"** → `f2c3e19`. The switch demanded a whole batch from the other farm,
which almost never exists at that moment. It now hands over to the **fullest
other** farm. The README keeps the owner's quote and the reasoning.

**"It's missing sometimes bro"** → `c193909`. The chooser counted only cows
*ready in the field*; a farm whose cows were already parked in its stalls read
as `0` and was skipped, so its milk sat there. Now compares `ready + parked`,
and the stay line names the reason. The test suite also caught a real bug in
that edit: early exits returned the reason as the farm-name slot, so a parked
farm would log `farm nil (full)`.

**"Btw it takes 2 seconds to clean a stall"** → `a6a5034`. The per-cow clean gave
up after 0.96 s and pressed for milk **mid-clean** — a press the game ignores,
which is one concrete way a cow comes back unmilked. It now holds until the
Clean offer clears (2.25 s ceiling), both clean paths log the real duration, and
the pre-pass polls every 40–50 ms instead of overshooting.

**"Like bro, before it brings the cows inside make it check for over 20/24
dirtyness"** → `e58935e`. The meter was read but not used as a trigger; it is now
a trigger above the 24 % clean baseline (`milkDirtLine`), and **no cow is put in
a stall that reports dirt** — the herd step tests every free stall with the same
three readings the cleaner uses, skips dirty ones, and arms nobody in an
all-dirty barn. The line self-corrects upward from the game's own answer, so it
cannot become the old twelve-stall tour.

**"Add a read-only probe that dumps one complete stall folder"** → `7901c2f`
(the probe) and `5e29ff4` (an on-screen panel with COPY REPORT). It is what
named `FilthLevel`/`FilthPercentage`, showed every stain `Transparency = 1` on a
clean stall, and found `Other.Dirt` (scenery) — the field the clean pass should
*not* read.

**"Can you explain how the A* pathfinding works?"** — answered, no code change:
grid from trip length, `CanCollide` footprints, octile heuristic, no corner
cutting, the clearance hug penalty, string-pull with a 2-cell margin, quintic
Bézier corners, three-attempt fallback, replanning while driving. Summary is in
§3.6 above.

**"Look for bugs. let me know what to improve" → "js do it all"** → v1.24
(uncommitted). The review found: Unload/Reload leaked every loop (the FPS that
kept getting worse), the per-cow clean read the offer once right after an
un-settled teleport (a dirty stall could be milked), `milkDrops` counted the
whole world (another player's jug read as "milked"), learned state survived
Reload, a crashed growth-wait left `farmResting = true`, and a global
`milkDrops` counter clobbered the dropdown table. Fixed: session generation
guard, clean-offer poll, 4 Hz plot-scoped jugs, strict webhook validation
(pasted **and** remembered), per-stall clean backoff, per-pass timing in the
status line and Doctor, persisted farm/batch/seed/movement choices,
Start/Stop-all + verbose-log controls, pinned `FLUENT_TAG`, reload payload
check, and the `name_audit` + `run_all` gates. New harnesses:
`lifecycle_test`, `cow_in_stall_test`, `drop_scope_test`, `webhook_test`. All
harness-green; **not reloaded in game**.

**"first you need to make the pathfinding MUCH better with online resources"**
→ v1.25 (uncommitted). The diagnosis: the old A* scanned its open array **and**
`table.remove`d from it on every pop (O(frontier) twice), with no closed set, so
on a cluttered map it burned its pop budget on duplicate entries and returned
**no path** — `path_bench` reproduces that (252 ms / 103 ms spent, then nil).
Obstacle marking ignored height (roofs and raised pad edges were phantom
walls) and re-walked seven folders every second; line-of-sight sampled
half-cells (a thin fence post could slip between samples); and the Bézier
control factor `0.55` overshot the corner, so the nominal "22-stud radius"
measured ~4 studs. Now: a top-level `SpudPath` module with a binary heap +
closed set, **Lazy Theta\*** (A* fallback), exact DDA line-of-sight, a 1 s/0.5 s
cached, height-banded obstacle map, a 6–16-stud grid (90k-cell cap, finer-first
retries), and clearance/curvature-gated arcs (`0.30` factor, margin 2,
0.08 rad/stud). `path:` prints mode, pops, ms and minimum clearance. New
`tools/path_test.py` (32 checks) and `tools/path_bench.py`; suite **20/20**.

**"i want the farming features to also work on another field ... they will be
3 wide instead of 1" → "make the farming be able to work on someone elses
farm"** → v1.26 (uncommitted). The sweep hard-coded one 10-stud tile (rows
every 10, headland 10), so a 3-wide tool would overlap three times. Now
`SpudFarm.workTiles` measures the implement's whole ground union across the
step axis (oriented boxes, rotated tools included), rounds it to 10-stud tiles,
and `SpudFarm.rowPlan` spaces rows by that width with a matching headland band;
the touch-up groups missed cubes by row instead of visiting each. A declared
attribute/Config width is logged next to the measurement but only used when no
part is readable. The Farm tab also has a **Farm owner** picker (mine + owners
seen in streamed fields, plus **Refresh farm list**): `findMyFields` now uses
`SpudFarm.ownerWanted`, so the same tour/growth/touch-up runs on that owner's
fields. Equipment was still found **without** an owner filter at that point
(nearest tractor/tool — fixed in v1.27 below), and a pass that changes nothing
on a foreign field says `check worker permissions`. New
`farm_width_test.py` (30 checks); suite **21/21**. Green but **not reloaded in
game**.

**"make it use the farm owners tools then commit and push"** → v1.27. The
owner picker changed which **fields** were worked, but the machines still came
from "nearest in `Objects.Equipment`" — a stranger's ZM80 was borrowed whenever
it happened to be closer. `equipOwnerRank` now ranks machines: the farm being
worked first, then mine, then one with no readable owner; another account's is
never used. `findTractor` and `findImplement` scan the ranks in order (nearest
wins inside a rank, and the implement still prefers the model name over
`EquipmentType`); a stored machine of the chosen rank goes to the Equipment
Manager for a spawn rather than taking a lower rank's spawned machine.
`logEquipment` prints every machine's owner, and the not-found lines name the
farm. New `equip_owner_test.py` (23 checks); suite **22/22**.

**"it isnt farming in the right field … when it's wood it should work on the
wood soil" → "it's trying to harvest my trees but i dont want to"** → v1.28.
The tour still returns every field of the selected owner and `FieldType` was
only logged, so the full crop↔soil mapping is waiting on the read-only
`SpudFieldProbe.lua` report. The tree cut is fixed independently: the harvest
job treats any unknown stage as a standing crop, so `spudTreeField` now refuses
a harvest on a field whose type/name says wood/tree/log/forest/timber/lumber/
sawmill/stump (logged with the real type). `spudNoCells` applies rule 7 to cell
reads: a successful read with `total = 0` is an empty non-field and is skipped;
a `nil` read stays unknown. Applied in `probeWork`, both `runPass` decisions,
`needLeft`/`grownLeft` and the growth wait. New `field_soil_test.py`
(22 checks); suite **23/23**.

**"no but it's using the player it's working for's equipment then going on it's
own field"** → v1.29. Picking a farm did not replace my fields: `ownerWanted`
returned true for `ownerName == mine` *or* the pick, so the tour mixed both
owners — the pass hitched Miou2251's plow and then plowed my field. It is now
**one owner at a time** (`pick or mine`), so the machinery and the soil always
match. `(mine)` still means exactly mine. The tour line and each per-field line
now include the owner (`Field · Miou2251`), which is what made the mismatch
visible in the console. `farm_width_test.py` gained the two pick-vs-mine checks.

**"when it's on the field just let the game's thing that focuses is on the field
do its thing … it does not re-center … make it go faster"** → v1.30. The game
auto-steers a tractor on its field; the align mover fought it, and its aim
corrected heading only — a tractor parallel to the row but 2–6 studs beside it
had no heading error and never re-centered. Rows now run on real W (`keyRow`,
the harvester's proven driver) so the game steers; `spudRowSteer` nudges A/D
only for a heading error > 8° or a cross-track offset > 2.5 studs. Travel rose
from 24 to **34 studs/s**; the align mover is now only the row fallback (18),
so rows no longer run at its old 10-stud/s cap. New `row_steer_test.py`
(9 checks); suite **24/24**.

**"once the harvester is full just make it stop because we dont have the spot
yet … the place is called furfullement next to the shippement"** → v1.31. A full
tank used to start a sell trip against guessed pads (`SellArea` / `DropOffs`).
`spudSellWired = false` + `spudSellNow(cur,max)` now gate that: while unwired, a
full harvester logs
`stopping the run: the Fulfillment drop-off isn't wired yet`, clears
`loopThread` and switches the Farm toggle off, so the run ends instead of
driving somewhere wrong. `SpudFulfillProbe.lua` was added to dump the
Fulfillment / Shipment area (models, pad parts, prompts, signs, live context
actions, old pad targets). New `sell_gate_test.py` (7 checks); suite **25/25**.

**"also make it teleport to the spesific farm, find the tools then run"** →
v1.32. A picked farm was worked from wherever the character stood, so the far
plot's fields and machines had not streamed in when the scan ran. The run now
hops to the owner's plot first (`milkStorePlotOf` → `spudFarmHop`, >60 studs
only, centre +5 Y), standing the character up first because a seated CFrame
write does not replicate, waits 0.5 s for streaming, then finds **that
owner's** tractor/tool (§3.7) and logs `farm: using <tool> (<owner>) N studs
away`. `milkStandUp` takes a caller label now (`farm:` instead of `milk:`).
New `farm_hop_test.py` (7 checks); suite **26/26**. The Fulfillment dump the
owner pasted is useful (CompanyArea with Fulfillment/Shipment titles,
`Deposit_Warehouse` at -353,138,-90, `Withdraw_Warehouse` at -286,138,-217,
`UnloadTrailer` / `PullFactoryLever` / `TogglePipe` actions) but **not enough
to wire the unload**: the probe was run from the start point, not the pad, so
which action/key the pad offers with a full harvester is still unknown.

**"im telling you i ON the pad to furfull bro, make a option in the farm to
either furfull or sell bro"** → v1.33. The probe upgrade went in first: it now
reads `PCGP_ContextActions.Billboards` (only what is offered here, with each
action's key and adornee) instead of `Buttons` (the whole 70-action registry,
which is why two runs answered nothing). Then the Farm tab got **Drop-off**:
**Fulfillment** (default) drives the full harvester to the probed
`Stores.DropOffs.Deposit_Warehouse` top surface; **Sell** keeps the old crop
sell-board scan. The tank dropping is the only proof a pad took the load; a
failed trip backs off 60 s. `spudSellWired` is gone, so is `sell_gate_test.py` —
`dropoff_test.py` (17 checks) replaces it. Suite **26/26**.

**"when it's on someone elses plot make it not try to respawn things bro"** →
v1.34. Spawning/respawning goes through the game's Equipment Manager, which is
the owner's call: on a picked farm the run no longer brings anything out. The
shared `spudMayRespawn()` rule guards all three spawn sites (stored tractor, a
tractor past `RESPAWN_RANGE`, and `ensureToolNearby`); each one now logs the
machine, why (stored / N studs away) and that `(mine)` is how to spawn it.
New `foreign_respawn_test.py` (14 checks); suite **27/27**.

**"it is still going back and fourth bro like side to side, make it force the
alignement then jus tgo straight and let the game do the ajustments"** → v1.35.
The cross-track A/D nudge added in v1.30 was re-centering every 100 ms and
fighting the game's own steering — a visible side-to-side on every row. Now the
row is **snapped onto its line once** (`spudRowNeedsAlign`: heading > 8° or
offset > 2.5 studs, rows ≥ 20 studs only) and then driven with **W alone**;
`spudRowSteer` is heading-only, so a straight tractor presses no key. Short
Omega turns keep swinging through. `row_steer_test.py` rewritten (15 checks).

**"widen the steering range it takes bro it's like still going side to side
yo"** → v1.36. Still oscillating, so the band itself was too narrow for the
game's steering: 8° / 2.5 studs. It is now `spudRowAng = 15` and
`spudRowTol = 6`, and the row loop steers with **hysteresis** (engage past 15°,
release inside 7.5°) so the boundary cannot flip A/D back and forth. Both are
globals, so they can be retuned without touching the loop.

**"if it keeps going back and fourth with the seering make it slowly go slower
bro"** → v1.37. The throttle now eases itself: `spudRowEase` counts steering
flips, drops the row's duty to 70 % of what it was on the third flip (floor
30 %), and restores 10 % per steady 3 s. W is pulsed at 4 Hz when the duty is
below 100 %, so "slower" is real rather than a no-op. `row_steer_test.py` grew
to 23 checks.

**"i want to make the seeding and planting and things use remotes"** → v1.38.
The probe was extended for field captures; one manual cultivate pass recorded
`EVTCultivateFieldCell:FireServer(field, {cellId}, {raycastAttachment})`, and a
V at the seeder recorded `FNCFillSeeder:InvokeServer(seeder)`. A pass now fires
the game's own call for every remaining cell id (read from `FieldHelper.GetCells`)
with the hitched tool's RaycastPart attachment, re-reads the stages, and drives
only what the server did not take; a job that ignores the batch switches itself
back to driving for the session. Plow/seed/harvest reuse the captured shape
(siblings on the same path) behind the same verification. The seeder fill calls
the remote first and keeps V. New `field_remote_test.py` (24 checks); suite
**28/28**.

**"use remoted for everything"** → v1.39. The equipment calls the probe had
already recorded were wired with the same verify-then-fall-back rule:
`FNCEnterEquipment(vehicle, seat)` for a mount (the seat is the proof, F stays
the fallback), `FNCAttemptHitch(hitchable, socket)` / `FNCUnhitch(hitchable)`
inside the existing line-up + tug attempts (X stays the fallback),
`FNCSpawnEquipment` / `FNCStoreEquipment` in `managerAction` (the `InStorage`
flip or a >100-stud move is the proof; the Equipment Manager UI is the
fallback — this is where the old UI flow was slowest),
`EVTRequestToCarry` / `EVTRequestToDrop` for crates and held items. Three
ignored calls switch that one action off for the session. Cleaning, milking,
herding, fulfillment, feeders and gates are **not** wired yet: their shapes
were never captured, so the probe gained an ACTION CALLS section and a checklist
for them. New `equip_remote_test.py` (26 checks); suite **29/29**.

**Two more capture runs** → v1.40. The plow report confirmed the field shape
(`EVTPlowFieldCell(field, {id}, {plow RaycastPart})`), so plow is no longer an
inferred sibling. The sell/buy report added two actions: a **Sell** drop-off now
fires `EVTSellAtStore(harvester model, pad part)` before touching Q/E (the tank
dropping is the proof), and the seed buy fires
`FNCRequestStorePurchase({crate})` before clicking the popup (the balance or a
new crate is the proof). The two reports also showed no clean/milk/herd/fulfill/
feed/gate call, so those are still waiting on one targeted run.

**"the furfillement you dont gotta do anytihng just go ot the location and it
does it bro"** → v1.41. The Fulfillment pad unloads a parked harvester by
itself, so `trySellAt` gained the `autoPad` flag and the Fulfillment trip now
parks, logs `fulfillment pad …: parked — this pad unloads by itself, pressing
nothing`, and watches the tank for up to 16 s **without pressing Q or E**. The
Sell destination is unchanged (captured call, then Q/E after a 3 s grace), and
the tank dropping is still the only proof in both cases. `dropoff_test.py`
grew 9 checks that run `trySellAt` itself on a virtual clock: the Fulfillment
pad drops the load with **zero** keys and **zero** calls, a working Sell call
presses nothing, and an ignored Sell call still falls back to Q and E without
claiming a sale.

**"i found a but. when the harvester is coming back from somewhere it should
drop from higher, becuase right not it is coming from under"** → v1.42. The
arc hop kept the takeoff height at both ends, so the return leg from the
Fulfillment pad (~140) travelled under the field (~172) and popped up only at
the last frame. `hopTo` now lands at `max(takeoff, target.Y)` and lifts enough
to clear that landing by ~12 studs, so an upward trip arrives from above; a
downward trip is unchanged. New `hop_test.py` (15 checks) pins the landing
height, the clearance, the descent, level hops, a missing target Y, the
zero-length case and the stop; suite **30/30**.

**"wait can we just abuse bugs to plow and harvest and stuff bro" → "add it in a
new section called 'Tests'"** → v1.43. A new **Tests** tab (off by default)
holds the experiments. Its first entry, **Batch field remote**, abuses the fact
that the captured call already carries a *list* of ids: one call with every
remaining id, judged only by the stage re-read — all taken = the whole field in
one call, some taken = the rest go one call per cell, none taken = the list is
ignored and the normal per-cell pass runs (nothing is switched off). The
`field_remote_test.py` batch checks were added (8 more). Live result (the
owner's console, 2026-10-30): the 1-cell field took the list, the 48-cell field
logged `batch test: the server ignored the id list (48 still need it) — one call
per cell` — so the server takes **one id per call**.

**"maybe you can make a dump to try to find bugs to abuse"** → v1.44. The Tests
tab gained a four-button **bug finder** (`spudTestRun`/`spudTestWork`): **From
here** (one cell call with nobody seated, no hitch), **Wrong stage** (seed a
cell that is not cultivated), **No attachment** (empty attachment table) and
**All at once** (every id with no 40 ms spacing). Each writes one cell of our
own field, re-reads it, and prints `test: … TAKEN/IGNORED` plus the before/after
stage — manual experiments with no harness, since the live field is the only
judge.

**"i wnat to find ingame bugs we can abuse bro not the scripts bufgs" → "add a
button to test ALL bugs you can think of … and add a copy button"** → v1.45.
The bug finder grew to eight questions and two report buttons: **Sell abuse**
(`EVTSellAtStore` twice off-pad, then again on the emptied tank — distance and
double-sell, judged by the tank and `coinBalance`), **Grab from afar**
(`EVTRequestToCarry` on a distant SeedBox, dropped back afterwards), **Spawn
from afar** (`FNCSpawnEquipment` on a stored machine), **Fill from afar**
(`FNCFillSeeder` on a distant seeder, seeds and coins read), **Run all** and
**Copy report** (`setclipboard` of place id + build + player + every line).
The live answers so far (owner's report, 2026-10-30): seat, stage and
attachment are **IGNORED**, and a 48-id list is ignored — the field door is
closed — but **carry worked from 35 studs** (`SeedBox` grabbed and dropped
back) and **spawn worked from anywhere** (`S4204` rebuilt >100 studs away). The
fill and sell tests reported no seed field / no streamed pad, which is what
v1.46 fixes.

**First live bug report from the Tests tab** → v1.46. The user ran **Run all**
and copied the report: ride/stage/tool IGNORED (seat, stage and attachment are
checked), carry **TAKEN at 35 studs**, spawn **TAKEN from anywhere**; fill said
`seeds nil` and sell said `no sell pad found`, so both tests could not measure.
Fixes: sell pads now fall back to `spudFulfillSpots()` and a raw scan of
`SellArea`/`DropOffs`, and no streamed pad is stated instead of fired; the
seeder read accepts IntValue/NumberValue/attributes and, when still nil, dumps
the seeder's `Configurations` and attributes so the real seed field can be
named next run.

**"the harverster's contents arente getting sold vbro"** → v1.47. The v1.45
reports showed `sell: no sell pad found in the world` at three different spots:
`GameplayVisuals.SellArea` and `Stores.DropOffs` are streamed **with distance**,
so a full tank at the farm got an empty list and `sellHarvester` skipped the
unload entirely. It now hops the harvester to the store's own waypoint
(`storeAnchors`, then any `GotoLocations` marker named fulfil/ship/store/market),
waits 1.2 s for the area to stream, and looks again; `back` (the return target)
is captured before that hop so the trip back goes to the field, not the market.
Two more bugs from the same report: the `SellBoardSeeds` candidate had no `part`,
so `EVTSellAtStore` was never fired at the crop board (and the test crashed on
`s.part.Position`) — it now carries `part = g`; and the seeder's seeds are
`Capacity`/`MaxCapacity` (live dump: 0/50), not a "seed"-named value, so the
fill test read nil — it now reads that pair and reports `seeds s/m`.
`dropoff_test.py` grew 7 checks (streamed pad = one hop, no pad → store hop →
sell, trip back to the field, no marker = honest skip).

**v1.48** — the very next v1.47 report said `sell: the pads found carry no part
to fire at`. The rebuilt output list in `findSellSpots` copied `p/what/store/
dist/board` but **dropped `part`**, so every spot the trip used had no part for
`EVTSellAtStore`. Fixed (`part = c.part`), and `dropoff_test.py` now asserts
every returned spot carries a part (2 spots in the fixture). The same report
confirmed the fill reads `seeds 0/50` and the fill from 965 studs left it at
0/50 — the seeder fill needs proximity too.

**"ok, now we need to try to make it seed the wqhole fields" → "i meant
seeding plowing and all and harvesting bro"** → v1.49–v1.51. Every job got the
whole-field treatment. A **Sell** drop-off is fired from where the harvester
stands (`EVTSellAtStore` checks no distance: a full tank sold 46 studs away,
+150 coins, no double-sell on an empty one), so the pad trip is gone. Each job
is capped by the machine's own load — the seeder fires at most `Capacity`, the
harvester at most `MaxCapacity − Capacity` — and a cap that runs out hands the
field back instead of driving: the seeder refills (up to 3 shop trips in one
pass), the harvester sells and comes back. A refused tail gets **one retry of
just those** before any row is driven.

**"it wont do it all bor help fix it"** → v1.52. The live console showed the
ceiling: `batch test: 2 of 46 cell(s) took the id list` and
`remote plow: 6 of 46 cell(s) took the call in 3.9s — driving the last 40`.
**The server only accepts a cell whose blade is over it**, so one call per id
from the field edge can never finish a field. `spudHopCells` moved the ride
onto each remaining cell with the tool's attachment lined up and fired that one
id (`remote plow: hopped the ride over 46 cell(s) — 46 took`).

**"why dont we just make it tween and do that every 500ms so it's super fast"**
→ v1.53 (the owner picked **sweep + fire every 500 ms**). `spudSweepCells`
replaces the hop as the first fallback after the call pass: one serpentine
tween over the remaining cells at 20 studs/s, a burst every 0.5 s at the cells
the blade is passing (6 studs), a second lap offset by half a row for the ones
a burst skipped, then the hop for whatever is still standing, then the drive.
The seed/tank budget is enforced inside the sweep too (dry hands the field
back). `field_remote_test.py` gained the sweep checks; suite **30/30**.

**"it does not work so well with the plow bro"** → v1.55. The burst at 14
studs fired at every cell in reach and marked it done — the server refused the
far calls, so those cells were never called again with the blade over them,
and the plow came back with a field of leftovers while seeding (which the
server takes more readily) looked fine. Now the very tick a cell comes within
**4 studs** fires it, a wide burst can never block that close fire, and
seed/harvest skip the burst entirely so their budget is spent only on cells
the server takes. `field_remote_test.py` pins it with a blade-over server (all
15 cells taken, one call each) and a refused burst followed by a close fire.

**"that tween NEEDS to be faster, and have more range like before bro"** →
v1.54. The sweep ran at 20 studs/s and only fired at cells within 6 studs —
the old per-cell pass had fired at every id whatever the distance, so the
field took 12–15 s and skipped cells off the row. It now runs at **45 studs/s**
with a **14-stud** catch range, and the second lap slows to 70 % to aim; a
whole field crosses in 5–7 s. Same verification: the server decides, the hop
and the drive still take whatever it refuses.

**"isnt there a way we can force a tile to become tiles and stuff"** → v1.56.
The stage lives on the server — the owner's own Wrong-stage test answered
IGNORED — so writing `Stage` in `FieldHelper.GetCells` only edits a local
copy. Two Tests entries settle it for any build: **Field API** (read-only:
`FieldHelper`'s exports, what one cell holds, whether an export is a setter)
and **Force a tile** (forge an Empty cell to Cultivated, re-read after 2 s,
then fire seed on it — TAKEN would mean the server trusts the mirror). The
sweep therefore forces *position*, not state, since position is the only input
the server checks.

**"we need to find another way of forcing the seeding and plowing"** → v1.59–
v1.65. The remote inventory (334, all `Modules.Larry`) named `EVTFieldPacket`,
the only door that could carry a whole field. Packet watch captured it as
`buffer(10)` — one cell's worth — so Forge packet builds the same buffer from a
forged cell and sends it back. The patch test then flipped that byte inside a
real packet and sent it: **nothing came back and no cell moved** (v1.64–v1.65),
so `EVTFieldPacket` is server→client only and the tile cannot be forced. The two
packet tools were retired like the other settled experiments.

**The v1.68 band run (2026-10-31)** — the first report after the lift rewrite:
the plow was hitched and the field had **no Empty cell**, so the probe fell
back to a Plowed cell and fired **plow at it** — a no-op at any distance
(`+8 studs above cell 129 — Plowed → Plowed — ignored`), and the ladder ran out
of cells after one reading (`tallest take none, widest take none (1 cell(s)
used)`). The same run finally answered the wrong-tool question: cultivate fired
from the plow's own attachment at a Plowed cell the blade had been hopped onto
stayed `Plowed → Plowed — IGNORED`. **→ v1.69** rewrites the lift probe to
measure only cells the hitched tool can stage (in the field with the most of
them), reuses a cell until a take spends it, walks each ladder far → near and
stops at the first take (80/40/20/8/0 up, 0 as the control; 60…4 to the side
at +8), and retires **Wrong tool** with its verdict recorded.

**The band, measured (v1.69 run, 2026-10-31).** With the plow hitched and one
Empty cell left on the whole farm: `+80 studs above — ignored`, `+40 studs above
— Empty → Plowed — TAKEN` → `tallest take +40 studs, widest take none (1 cell(s)
spent)`. So the blade may sit **40 studs above** a cell (the check is not a flat
ground gate and not an unlimited column either — 80 was refused), which matches
the 8-stud take from the first run. The sideways band never ran: the take spent
the only usable cell, so the far → near lateral ladder had nothing left to fire
at. **→ v1.70** runs the **lateral ladder first** (80/60/45/30/20/14/8/4 at +8)
so a one-cell farm still gets the number a sweep depends on, keeps the height
ladder second, and marks a dimension `not measured` when no cell is left.

**The band, second run (v1.70, 2026-10-31).** A cultivator on a field with 3
Plowed cells: `80 studs to the side at +8 — ignored`, `60 studs to the side at
+8 — Plowed → Cultivated — TAKEN`, then `+80 studs above — Plowed →
Cultivated — TAKEN` → `tallest take +80 studs, widest take 60 studs to the
side (2 cell(s) spent)`. Two things fell out. **The reach is a radius, not a
column**: the server takes a call from 60 studs away and from 80 studs up, so
the blade only has to be *near* the cell. And the **first reading of every
run so far was a false ignore** (v1.67's `0 studs`, v1.69's `+80`, this run's
`80 to the side`), because the call is fired before the long teleport has
reached the server — the probe now re-reads and retries an ignored reading
once. **→ v1.71** adds `spudRadialFire`: after the call pass, the blade parks
10 studs above the middle of the remaining cells and every id is fired from
there (one teleport instead of a serpentine), verified by the stage re-read
and backed by the unchanged sweep/hop/drive.

**The band, third run (v1.71, 2026-10-31).** A planter on a field with 50
Cultivated cells, every reading retried: `80 → ignored`, `60 → ignored`,
`45 → ignored`, `30 → ignored`, `20 → Plowed… Cultivated → Seeded — TAKEN`,
then `+80 studs above → TAKEN` → `tallest take +80 studs, widest take 20
studs to the side`. So the reach is **~2 tiles horizontally at any height** —
the cultivator's `60 to the side` from the previous build was a late take
credited to the wrong reading (that build had no retry). **→ v1.72** raises the
sweep's burst from 14 to **20 studs** and its row spacing from 10 to **20** (a
pass covers three rows; bursts 22 studs apart along the path leave every cell
at most ~15 studs from one), and lays the lap path on the **field's own box** —
re-reading the bounds from the leftover cells had moved lap 2's half-row offset
off a single leftover row.

**The band confirmed (v1.72 run, 2026-10-31).** The same probe on the next
build returned the identical verdict — `30 → ignored`, `20 → TAKEN`, `+80
up → TAKEN` — so the two-tile reach is stable, not one lucky reading. **→
v1.73** stops the single-spot fire at **24 studs**: a cell past the reach can
never take that call, so firing it only spent 40 ms. The pass now logs
`fired N of M … (reach 24)` and leaves the rest to the sweep.

**The band retired (v1.74).** With a third identical run behind it (20 to the
side TAKEN, 30 refused, +80 up TAKEN), the Lift test came off the Tests tab
like every other answered probe — it spent two of your cells per run and had
nothing left to say. The verdict and the numbers it produced live in §3.12 and
in `spudRadialFire`/`spudSweepCells`' comments, so the sweep's 20-stud reach
and 20-stud rows stay justified if the question ever comes back.

**Seeding at range (v1.75).** Owner: *"why cant we make it seed/plant etc in
a larger range because when we ran testes it did and then can we eliminate
driving cuz now we can just use tp/tween"*. The tests did prove the range —
the sweep was the part not using it: seed and harvest fired **close-only**
(4 studs) so the rows between the passes waited for the second lap. They now
burst at **20** like the plow, and the budget counts cells instead of calls so
a burst call plus a close call on the same cell is one seed. Driving is
already the last resort: the finish is remote-call → single-spot fire →
tween → **hop (a teleport per remaining cell, live 46/46)** and only a cell
the server refuses even with the blade over it is driven.

**Stop, burst, move on (v1.76).** Owner: *"cant we just make it tp and burst
plant very fast? wouldnt that work, by the way you have to keep in mind that
the tools are behind the tractor"*. One spot only cleared the disc around the
field's middle, so the rest still waited for the 7 s serpentine. The fire is
now a **grid**: stops spaced 1.35 reaches apart cover the remaining cells'
box (a 50×100 field = 8), the blade is parked on each (the ride goes to
`stop − blade offset`, so the tractor keeps the tool behind it), and every
cell within 20 studs is fired — one call per cell, across all stops. The first
stop's re-read ends the grid if the server takes nothing from a parked blade,
so a refusing build still falls straight through to the sweep. Harness green;
the live check is the new log line
`fired N of M cell(s) from K stop(s), 9 per stop` and whether
a field finishes with **no** sweep at all.

**No driving, and can the tool go alone? (v1.77).** Owner: *"bro why is it
driving to the field i dont want that, by the way can we abuse the power that
the tools can like be seperated from the tractor to make it like so that the
tool get's used but the tractor does not move"*. Two answers. (1) The arc hop
was the harvester's alone, so every other job still pathfound to each field —
now **every job arcs to the field corner**, and `driveToField`/`driveRoute`
only run when a field has no readable corner (`fieldCornerTarget` → nil). A
tour is teleports, arcs and bursts. (2) Whether the tractor is needed at all
became the **Tool apart** probe — answered **IGNORED** in v1.80 (below), so the
stop-and-burst grid's teleports stay.

**The probe's first run (v1.78).** The report came back
`toolapart: need a plow/cultivator/seeder and a field with the right cell` —
two real gaps, not a refusal: the field was fully grown (`Harvestable`, so
nothing a towed tool can stage) and all three implements were in storage, and
`findImplement` skips stored ones by design. The probe now scans **every**
streamed field, prints each field's stage counts when it finds no usable cell,
and spawns a stored tool through the captured call (`managerAction(name,
"Spawn")`), storing it again at the end.

**The probe's second run (v1.79).** It found a cell (`Empty`, cell 518) and
brought the S4204 plow out, but the plow was **still on the tractor**: the
`PivotTo` moved its blade from 81 to 43.7 studs off the cell and the hitch
pulled it back, so `Empty → Empty — IGNORED` answered a distance question, not
the hitch one. The owner saw **one tile get plowed** during the move — the
game's own drive-over staged a cell under the displaced blade — which is the
first live hint that a tool's own position is what matters. The probe now
unhitches first (HUD = no secondary is the proof), retries the placement once,
and refuses to fire when the blade is more than 10 studs off, so the next
report is a clean verdict either way.

**Tool apart is answered: the implement has to be on a ride (v1.80).** The
clean run: `S4204 (plow), free of a ride — blade was 79 studs off cell 518, now
0.0`, then `Empty → Empty — IGNORED`. So with the blade **exactly** on the cell
and the tool's own attachment in the call, the server still refuses it, which
means the check is not just where the blade is — the implement must be hitched
to the vehicle the player is driving. The v1.79 run's single plowed tile was
the game's own drive-over while the tool was still HITCHED and being shoved
across the field, which is consistent: staging needs the implement on a ride.
The probe was retired with the verdict; the practical answer is that the
tractor must be there, it just never has to *drive* (arc hop + stop-and-burst
grid). One caveat recorded for honesty: the test changed hitched-ness and
seated-ness together (the player stood on the ground), so a build that ever
accepts a loose implement would need the probe re-run.

**The A* engine comes out (v1.81).** Owner: *"ok, no i want to remove the a*
pathfinding and have it tp fast untill the whole fielld is done bor"*. The
planner had one caller left — `driveToField`, the fallback for a field with no
readable corner — so the whole engine went: the `SpudPath` module (~600 lines:
heap, Lazy Theta*, clearance BFS, DDA line of sight, Bézier smoothing, obstacle
caches), `obstacleCells`, `clearanceField`, `pathfindAround`, `towMargin`,
`driveRoute` (~350 lines), `driveToField`, the route-preview debug studs
(`dbgRoute`/`dbgRouteClear`), and the `path_test.py`/`path_bench.py` harnesses
(**29/29** now, was 30/30). Every job already arc-hopped to the field, so the
only behaviour change is honest: a field whose plate has no readable frame is
named `SKIP <field> — no readable field frame` instead of being pathfound to.
The field itself now finishes on teleports — call pass → grid → **one more
grid** for leftovers → per-cell hop — and rows are driven only when every
single call was refused (`<verb>: N cell(s) left after the teleport passes —
leaving them, no rows driven` otherwise). The 200-local budget went from
headroom **2 to 10**.

**Rows are gone too (v1.82).** Owner: *"it's still driving"*, one line after
the A* came out. Two things were left that moved the ride along the ground:
the **row driver** behind a failed field pass, and the **tween sweep** before
the hop. Both are answered now. (1) The row block (~316 lines: headland lap,
skip-row passes, Ω turns, the tank diagnostics) is deleted outright — a field
pass no longer touches a movement key, and a field whose calls all fail logs
`<verb>: every call on <field> was refused — N cell(s) left, no rows driven`.
(2) The **hop runs before the tween**, so the leftover cells are teleported
onto and the smooth serpentine is the last resort. The real reason the sweep
kept running was the **first-call artifact**: the grid gave the whole field
away after one stop when the server refused the first burst (the pose had not
replicated yet) — it now settles 0.5 s and fires **that same stop once more**
before believing a parked blade is refused, which is pinned by
`field_remote_test.py` (`mode.seed = "retryOnce"`).

**Harvest first, retry forever (v1.83).** Owner: *"it was detecting plowing
when only one of the tiles needed plowing, i want that when the script starts
it sees the field … if it detects even 1 tile … at the fully grown stage i want
it to harvest before going to the next stage. also if it misses some thing i
want it to infinitly keep retrying untill there is none of the last stage it
was on"*. Three changes. (1) **Harvest outranks the other stages**: it was
already checked first, but a run that could not enter the harvester used to
log one line and carry on to the plow — it now **stops** there
(`crops are standing and the harvester couldn't be entered — stopping before the
plow/cultivate/seed passes`), because a single standing crop outranks a bare
tile. (2) The harvest loop's **4-round cap and "didn't change" break are gone**:
it re-reads after every pass and goes back until `grownLeft()` is 0 (Stop still
ends it). (3) The field pass no longer says "leaving them, no rows driven": a
leftover cell now loops **grid → hop** round after round, logging
`<verb>: N cell(s) still need <prog> — teleport round N`, until the field
reports none of that stage left; the seeder loop's 6-round cap went the same
way (its 3-refill coin guard stays). All three loops watch `stopping()` and
`task.wait(1)` between rounds.

**Harvesting fired nothing (v1.84).** Owner: *"harvesting does not work? it is
not harvesting anything"*. Two ways the harvest pass could go silent on a live
build, both closed. (1) **The attachment picker was too picky**: the captured
call's third argument was only ever taken from a part named `Raycast*` or
`Seed`/`Detect`, and the harvester's head may be named anything — with no match
`spudFieldRemotePass` switched the whole job off for the session
(`no raycast attachment … — driving instead`) and, since rows are gone, nothing
harvested at all. The pick now ranks **RaycastPart → harvest-sounding part**
(head/header/cutter/blade/gather/reel/knife/scythe/combine/pickup) →
Seed/Detect → any attachment (v1.89), logs the class of the pick
(`attachment: <tool> → <part>.<attachment> (harvest)`), and a non-raycast
pick also logs **every attachment path and every part name** on the machine, so
one live run names the harvesting point instead of another guess. The v1.89
evidence: the SRC6 sent `EquipmentRoot.L0StrutAttachment` — a wheel strut —
and the server refused **all 46** harvest calls from 8 stops, from a hop onto
every cell and from the sweep. (2) **A 0/0 tank read posed as a full tank**: `budget = MaxCapacity −
Capacity` was `0` when both values were unreadable, and the pass bailed as
`the tank is full` before firing a call. The budget is only used when
`MaxCapacity > 0` now, in both `spudFieldRemotePass` and `spudRadialFire`, so an
unreadable pair means "unknown, no cap", never "full".

**A console copy, and a tank that never emptied (v1.86).** Owner: *"you should
add a copy consol line bro"*, sent with a screenshot of a run stuck in harvest
rounds 19–21 at `49/50`. Two things. (1) **Copy console** — a Tests-tab button
(`spudTestCopyConsole`) that puts the last **150** `_G.SPUD_TRACE` lines on the
clipboard with the place/build/player header and shows the tail in the Tests
panel, so a stalling run answers itself without running an experiment first.
(2) **The stall was the sell gate**: a `49/50` tank against 46 standing crops
gave a budget of **1**, fired one call, the server refused it, `dry` handed the
field back, and `harvestSellIfFull` declined because `cur < max` — every round
repeated that, for ever. The new `spudHarvestFull(cur, max, need)` treats a tank
whose free space cannot cover the cells still standing as full, `harvestSellIfFull`
takes the standing count at all eleven call sites, and the dry line now names the
machine it belongs to (`remote harvest: the tank has N free slot(s) …` instead of
"the seeder holds N seed(s)"). `dropoff_test.py` pins the rule with seven checks
(49/50 against 46 sells, 49/50 against 1 keeps working, unreadable/zero capacity
never sells, no standing cells is no excuse).

**Call the sell, don't drive it (v1.87).** Owner: *"didnt you say we could just
call the sell bro?"* — the capture had already proved `EVTSellAtStore` sells a
full tank from 46 studs off the board, but only the **Sell** pick fired it in
place; **Fulfillment** still arc-hopped to the pad first. Now both picks fire
the captured call from where the harvester stands (at their own pad part) and
watch the tank for 3.5 s: a drop logs `✅ sold in place … (no pad trip)` and the
ride never moves. A call that leaves the tank alone still takes the destination's
own trip (Fulfillment parks and lets the pad drain it, Sell falls back to Q/E).
`dropoff_test.py` gained three checks: a Fulfillment pad emptied in place costs
**0 hops**, the call carries the warehouse part, and a refused call still takes
the park trip (`autoPad = true`).

**Batch on by default, and the sell call is proximity-checked (v1.88).** The
owner pasted the whole console of a v1.86 run: the harvest loop sat at
`49/50` with 46 crops standing, fired **one** call at the field corner every
round (out of reach — refused), sold, came back, and did it again; and the
in-place sell call fired from the field did nothing, while the same call at the
board then sold `49 → 0`. Three fixes. (1) **`spudBatchRemotes` is ON by
default** (owner: *"can you turn batch remotes on by default"*) — one id list
per field pass, proven ignored by the live server, so it costs one call and its
1.2 s read and can never switch a job off. (2) **The sell call is
proximity-checked**: `spudSellCallRange = 60`, so `sellHarvester` only fires it
in place when the pad is that close and otherwise logs
`<dest>: the pad is N studs away — the sell call needs it close, taking the
trip` and hops straight away (no 3.5 s wait for a call that cannot land). The
v1.87 claim "it checks no distance" was wrong — 46 studs was one lucky
reading. (3) **A tank that cannot cover the field sells first and fires
nothing**: `spudFieldRemotePass` returns dry on `spudHarvestFull(cur, max,
#ids)` with `remote harvest: N free slot(s) cannot cover M standing cell(s) —
selling first, then coming back`, instead of spending the single slot on a
refused call at the corner. `field_remote_test.py` and `dropoff_test.py` pin
all three (one free slot against two cells fires **no** call; a far pad is not
called; a close pad is).

**Harvest never lands: the strut (v1.89).** Owner: *"you know bro why dont you
just use mumumplayer to debug bro"* — and the emulator answered it. MuMu
(instance `Android Device-1`, adb `127.0.0.1:16416`) runs the game with the
executor fetching the latest build, and **every `log()` reaches Roblox's
CreatorOutput**, so `adb logcat | grep "[spud]"` is the whole farm console (the
loop is documented in §2.4). The v1.88 run it read: `attachment: SRC6 →
EquipmentRoot.L0StrutAttachment`, then `batch test: the server ignored the id
list`, `remote harvest: the game ignored 92 call(s)`, and **0 took** from 8
stops, from a hop onto every cell and from the sweep — 46 crops untouched. So
the tank/sell fixes were never the harvest fault: the picker's last-resort "any
attachment" chose a **wheel strut**. It now ranks RaycastPart → a
harvest-sounding part (head/header/cutter/blade/gather/reel/knife/scythe/
combine/pickup) → Seed/Detect → any, logs the class, and on a non-raycast pick
logs **every attachment path and every part name** on the machine, so the next
live run names the real harvesting point. `field_remote_test.py` pins the rank
(a `HarvestHead` point beats a `EquipmentRoot.Bolt`).

**Nine cells a stop, then forward (v1.90).** Owner: *"i spotted a bug, it tps
too fast. i wanted it to tp to a spot, do the closest 9 areas then go forwards
then so on and so fourth"*. The grid used to fire **every** remaining id within
20 studs of each stop, so stops overlapped heavily and the ride jumped around
the field. Now the remaining cells are grouped into **rows**, three rows at a
time are cut into **three-column blocks**, and each block gets one stop at its
own centre in **serpentine** order (each band alternates direction), where the
blade fires exactly that block's nine cells and moves forward. Blocks partition
the cells, so nothing is skipped and nothing is fired twice; the settle before
each stop went back to 0.5 s. `field_remote_test.py` pins the shape (a 15-cell
field = 2 stops / 15 calls, a 27-cell 9×3 field = 3 stops / 27 calls, an ignored
grid = one stop and 18 calls, the retry still 3+3 on a one-row field) and the
log line is now `fired N of M cell(s) from K stop(s), 9 per stop — K took, L
left`. The previous grid took 46/46 live in the emulator that day; this block
version had not been run live when it was committed.

**A hitch that never ends (v1.91).** The first live run of the 3×3 grid never
reached a field: the seeder's Hitch prompt never appeared and `hitchTool`'s
`while not stopping()` loop ran **27+ attempts** while the toggle stayed ON — a
run that looks alive and does nothing. Two changes: the loop now stops after
ten attempts and logs `hitch: gave up on KADL after 10 attempt(s) — this pass
runs without it`, and attempt 3 presses **X** once in case another tool is
still on the hitch even when the HUD label reads empty (the cultivator from the
previous pass was still attached in that run). Neither is pinned by a harness
(the hitch path needs a live prompt), so the next live run is the verdict.

**A small budget is spent by the blocks (v1.92).** The first live seed pass
with the 3×3 grid never reached a block: the seeder held **28 seeds against 46
cells**, fired all 28 from the field corner — nearly all out of reach — and
handed the field back (`remote seed: the seeder holds 28 seed(s) — 28 call(s)
sent, 40 cell(s) still need it`). `spudFieldRemotePass` now returns before
firing when `budget < #ids` and logs `N cell(s) need it but the machine holds M
— going straight to the blocks`, so the blade is over every cell it spends a
seed on. `field_remote_test.py` pins it (one seed against two cells fires
**nothing** at the corner and is not dry; one seed against one cell still fires
one call). The reload button also fetches the **newest commit sha** now
(`reload: newest commit is <sha>`): three reloads in a row served the previous
build from the client's HTTP cache even with a query buster, and an immutable
SHA path cannot be stale.

**The sell call has no gate (v1.93).** Owner: *"why isnt it calling the sell
function from anywhere? it was there before ive seen it with my eyes"*. v1.88 had
put a 60-stud gate in front of the in-place call after one far attempt did
nothing; that gate is removed. Every unload now fires `EVTSellAtStore` from
where the harvester stands, names the distance, and watches the tank for 1.5 s
before taking the trip. `dropoff_test.py` pins it (a pad 300+ studs away is
still called once; a call that moves nothing takes the trip; the log carries
the distance).

**A retry loop that never moved (v1.94).** The live run showed the 3×3 blocks
working (`remote harvest: fired 43 of 43 cell(s) from 7 stop(s), 9 per stop` and
`48 of 48 from 8 stop(s)`), but the **cultivator** then sat in `teleport round
1..10` on **2 cells** that never took a call even with the blade on them — the
owner's *"it wont do the 3x3 tp bro"* was that hang, not the grid. A round that
leaves the same count twice now ends the pass with `N cell(s) never took a call
even with the blade on them — leaving them for the next pass`, and the harvest
loop got the same rule (`… leaving them for the next cycle`), so neither can
spin for ever with the toggle on. The earlier "retry until none is left" rule
still holds while a round makes progress.

**The last slide goes too (v1.95).** Owner: *"no but during the plowing it
started doing the fast tp and then kinda strafing the ground bro"*. The
teleports were not the complaint — the **serpentine tween** between the grid
and the hop was: it slid the ride along the field at 45 studs/s, which reads as
strafing the ground right after a fast teleport. `spudSweepCells` is deleted
(207 lines) along with its eight harness checks, so a field pass is **grid →
hop, round after round** and nothing else; a cell both refuse is named
(`N cell(s) never took a call even with the blade on them — leaving them for
the next pass`) instead of being tweened over.

**Purchase, not Buy, and an empty hand (v1.102).** Two live finds. The
dialog pass matched any shown "Buy" control, and the shop LIST behind the
dialog keeps its Buy buttons on screen — so a close that had worked read as
"still open", pressed F and re-opened the shop. It now matches the dialog's own
**Purchase** control only, and a second click replaces the F retry. And a trip
that started with a crate already in hand made the till answer *"You must place
items on the counter to buy them"*, so every trip now drops what it is holding
before picking a fresh crate.

**Open means visible, not Enabled (v1.101).** The v1.100 run named the
container — `GuiViews.Stores` — and reported it "still open after handler then
F", then pressed F. `Stores` stays `Enabled` with its contents hidden, so that
verdict was wrong and the F **re-opened** the shop. Every judge is now a
visible button (`layerShown`), so a click that worked ends the step with
`Stores closed (handler)` and no key is pressed; a real failure names up to
eight of the buttons still on screen so the next run does not guess.

**The dialog is not a layer (v1.100).** v1.99's layer diff reported `no shop
menu is open — nothing to close` on the next live trip while the purchase
dialog was plainly on screen: it is a frame inside an always-enabled layer, so
its `Enabled` never changes. The close step now finds a shown **Purchase/Buy**
control first, walks up to the container GuiViews holds it in, and clicks that
container's own close; the enabled-layer pass stays as the backstop.

**Only the shop the trip opened (v1.99).** The first live run of the close step
turned up five layers that are `Enabled` but not on screen — `CompanyDashboard`,
`SettingsMenu`, `FarmerPass`, `PalletStorage`, `BuildMode` — and it dutifully
reported each as "still open". The set of enabled layers is now recorded just
before F, and only a layer that the trip switched on is closed afterwards, so
the always-enabled screens are left alone.

**The shop stays shut (v1.96).** Owner: *"after it buys a seed can you make it
close the ui"*. The close step that ran after a purchase looked for a "close"
button anywhere in `GuiViews` and then pressed F whenever any GuiButton was on
screen — which is always, since the HUD and top bar live in that tree — so F
fired every buy and the shop menu stayed up. It now reads the open menus
(`GuiViews.Menus`, plus any `*Menu` layer beside it, by `Enabled`), clicks that
menu's own close control inside it, re-reads `Enabled`, and presses F only if it
is still up; the log says `<Menu> closed (handler)` or names the menu it could
not shut. No harness (the live GUI is the only judge) — the next shop trip's
line is the verdict.

**The blade, not the beat (v1.97).** Owner: *"IT JUST USED THE FAST TP BRO"*
with a crop of `fired 50 of 50 cell(s) from 8 stop(s), 9 per stop — 17 took, 33
left` and `hopped the ride over 33 cell(s) — 5 took`. The teleports were right;
what was wrong was the clock. `hitch gap at arrival: 26.9 studs` says the plow
was still catching up, and both passes fired on a flat wait (0.5 s per stop,
0.1 s per hop) long before the blade arrived — so the server, which judges the
ground under the blade, refused most calls. Both now poll the attachment's own
position until the blade is on the target (12 studs for a stop, 8 for a cell),
re-park once from the measured offset if it is still swinging, and refresh the
offset so the next jump starts from the settled trail. A stop that still ends
more than 20 studs off logs `the blade is N studs off stop K — firing anyway`.
No harness (the stub moves the blade with the ride) — the next live grid is the
verdict: `took` should climb towards `fired`. The first live run of the
settle alone lifted the cultivate grid from **17/50 to 29/41** and the hop from
**5/33 to 11/12**, but the client's blade position runs ahead of the server's,
so both passes now also take a short beat (**0.25 s** after a stop lands,
**0.2 s** after a cell) before firing — v1.98.

**Where does the crate go? (v1.103 — probe).** The purchase still does not land
and the game is explicit: *"You must place items on the counter to buy them"*.
Both live trips read `F at the owner (InteractWithNPC)` and then the **general
shop** came up (`Shop · Farmer's Club · Equipment Manager · Buy · 200 · 520`),
`FNCRequestStorePurchase` changed nothing, and the balance stayed at 53,577 —
so the script's model ("carry the crate to the clerk and buy") is the part that
has to be measured, not the clicking. The Tests tab gained **Shop counter**
(`spudTestRun("shop")`): it repeats the real trip and prints, at the shelf, at
the clerk and at anything named counter/till/checkout/register/cashier, the
game's own visible context actions and prompt billboards — then puts the crate
down, re-reads, presses F, and reports which layer F raised, the toast text and
the visible buttons. One run names the counter and its prompt instead of
guessing them.

**The counter is in the building (v1.104).** The first live run of the probe
answered two things and never got to the crate: every helper it uses asks
`stopping()`, which is **true whenever no farm loop is running**, so
`carryCrate` gave up after one attempt — the probe now lends itself the loop
slot for its own run and hands it straight back. And the shop's own geometry is
in `Stores.Buildings.FarmCo.Persistent.CounterAttachments` (the counters the
first run found near the clerk were LumberCo's at 31 studs and AnimalCo's at
56), while every seed box carries `Primary.LinkedCounterAttachment`. The second
run prints FarmCo's children and parts, every counter attachment with its world
position, the crate's own linked attachment, then carries the crate onto that
attachment, drops it, and reads the prompt there (plus the toast and the layer F
raises) — the placement is what the till is asking for.

**The toast says it out loud (v1.105).** The second live probe run named the
block in the game's own words — the notification read *"You must place items on
the counter to buy them"* — and showed why the counter stayed invisible: each
store keeps its slots in `Stores.Buildings.<store>.Persistent.CounterAttachments`,
which is a **folder of folders**, so a scan for instances named
`CounterAttachment` found three empty containers and no world position. The crate
itself carries `Primary.LinkedCounterAttachment`. The probe now lists what is
*inside* each store's `CounterAttachments`, lists every FarmCo part within 25
studs of the clerk (so a counter not named "Counter" shows up by position), and
prints the crate's link with its class and value.

**The counter is real, and the crate has its own slot (v1.106).** The slots
are attachments: FarmCo's are six `Attachment`s at x=-166, y=142, z=85…100, and
`SeedBox.Primary.LinkedCounterAttachment` is an **ObjectValue** that points
straight at the one this crate belongs on. The probe placed the crate 1.1 studs
from its slot — the toast *"You must place items on the counter to buy them"*
disappeared with the crate down — but it then pressed F where it stood, 7.6
studs from the clerk, and raised nothing. The next run places the crate on its
own linked slot and walks to the **clerk** before pressing F, then clicks a
shown Purchase control and reports the balance, so the answer is the whole
transaction rather than one step of it.

**The clerk sells pallets, not seeds (v1.107).** F at the FarmCo clerk with
the crate on its slot raised `GuiViews.Stores.PalletStoreMenu` — a pallet till
whose Purchase button answered *"You need to own the Forklift License!"*, and
whose label dump (`CapacityLabel`, `PalletAmount`, `PalletInfo`, `Price`) is
exactly the "buy popup" every earlier trip had been reading as the seed dialog.
So the clerk was never the seed till: the seed box on its counter slot is. The
probe now prints the crate's own attributes and `Configurations` before, in hand
and after the drop (so "placed" is a readable state, not a guess), the counter
slabs under the slot with their sizes, and what E and F do from the counter.

**It was carrying my own box (v1.108).** The crate every trip carried read
`Configurations.Owner = Players.oksimba_2` on the shelf — it is the player's own
seed box, sitting in `Objects.DraggableObjects`, so putting it on the counter
could never buy anything. `findSeedCrate` prefers a tagged match and then the
nearest, and the nearest tagged Wheat box was mine. The shop's stock is the
**unowned** crates in `GameplayVisuals.LockedDraggables`. The probe now groups
every seed-tagged crate by the folder it lives in and prints the nearest with its
owner, picks the nearest **unowned** one with the chosen seed, places it on its
linked slot and then talks to the clerk. The counter itself measured 3.5 × 0.5 ×
18.5 studs at y=142.2 on x≈-165.6, and a teleport onto the slot pushes the
character out of it, so the drop has to be made from beside it.

**The shelf is GameplayVisuals (v1.109).** Grouping the 61 seed-tagged crates
by home split them 30 in `Workspace.GameplayVisuals` and 31 in
`Workspace.Objects`; the unowned crate the probe then took was a loose one under
Objects with **no** `LinkedCounterAttachment`, so it had no slot to be placed on
and the trip ended with the crate still in hand. The shelf set is the one the
till sells from, so the pick now prefers an unowned `GameplayVisuals` crate with
the chosen seed, and the run places it on its own linked slot, presses F at the
clerk, clicks a Purchase control if one is shown and reports the balance.

**The shelf sells pallets, the floor sells seeds (v1.110).** `GameplayVisuals.
LockedDraggables` is pallet stock: standing at one of those boxes offers
**nothing**, the nearest shelf crates are Potato and Grape (the Wheat ones are
farther), and F at the clerk raised `PalletStoreMenu` — *"You need to own the
Forklift License!"*. The boxes with a `Carry` prompt are the unowned
`Objects.DraggableObjects` ones, and F at the clerk while carrying one raises
the real till: **"Are you sure you want to buy 1 item? — Wheat Seeds, 100 —
Purchase"**. That dialog is a frame inside an always-enabled layer, which is why
every `Enabled`-layer check read "nothing raised" while it sat on the screen. The
probe now finds it by its own words, prints its container and buttons, clicks its
Purchase control and reports the balance and the crate's owner.

**The crate goes on the counter first (v1.111).** The dialog is real — live it
priced Wheat Seeds at **100** and, with a Potato crate in hand, Potato Seeds at
**120,000** — so the buy is: carry a floor crate to the clerk, put it on the
counter, F, Purchase. Clicking Purchase with the crate still in hand is the
"place items on the counter" answer. The probe places the crate on the counter
slab (3.5 × 0.5 × 18.5 at y=142.2, the slab under the slots) and only then
talks to the clerk, reads the dialog by its own words, clicks its Purchase and
reports the balance and the crate's owner.

**Placed means no dialog (v1.112).** A crate put on the counter (1.4 studs
from its top, live) makes the clerk offer only `F Talk` and raise nothing, so
the "Are you sure you want to buy" panel belongs to the crate **in hand** — the
computer till reads the box you are carrying and prices it (Wheat 100, Potato
120,000). The next run therefore carries the crate to the clerk, presses F and
clicks the dialog's own Purchase straight away, reporting the balance and the
crate's owner, to see whether the hand-held buy is the whole transaction.

**The confirm panel is drawn, not typed (v1.113).** F with the crate in hand
puts the panel on screen, yet no `TextLabel` under `GuiViews` carries "Are you
sure you want to buy" — the title and the green Purchase control are images. The
probe now dumps the shown controls under `GuiViews.HUD.Notifications` (class,
name, text, is-it-a-button) and clicks the one whose **name** says
purchase/buy/confirm, then reports the balance.

**Never buy the seed that is already in hand (v1.114).** Owner: *"it's trying
to buy seeds when it has the exact seed it already bought in it's hands — before
it tries to buy a seed it should see if it has any"*. A crate an interrupted
trip left carried is already paid for, and the shop trip bought a second one.
`buySeedAndFill` now reads the hands from the crate's own
`Configurations.CurrentHolder` before anything else: a held crate of the picked
seed skips the shop completely and goes straight to the seeder. The
"carry the crate to the seeder and pour it in" leg became one helper
(`seedCrateIntoSeeder`) shared by that path and the bought path, so both end the
same way — `FNCFillSeeder` first, V second, the seeder's count rising as the
only proof. The crate stays **in hand** rather than being put down, because
FillSeeder consumes the crate you are holding.

**A crate you own on the plot is seed too (v1.115).** Owner: *"i also wnat it
to see if i have that seed in my plot so it usees it"*. The hand check grew into
a hands-and-owned scan in one pass over `Objects.DraggableObjects`: a crate whose
`Configurations.Owner` is you and whose seed is the picked one counts as already
bought, nearest first, and the trip teleports to it, drops whatever else is in
hand, carries it and pours it into the seeder — no shop trip, no coins.

**Half a crate is not a full field (v1.116).** Owner: *"now some times it missed
some tiles wheile seeding and it fuckes the whole thing up"*. The live console
named the chain, and it was **not** the server refusing calls — every call the
grid made took:

```
the seeder is empty — going to buy Wheat (50 cell(s) need seed right now)
seed crate: you already own a Wheat crate 80 studs away — using it instead of buying one
✅ seeder now holds 23/50 seeds (Wheat)
remote seed: fired 23 of 50 cell(s) from 8 stop(s), 9 per stop — 23 took, 27 left
seeder EMPTY with 27 cell(s) … refill 1/3: buying Wheat and filling
the seeder is still empty and the shop was already tried this run — not teleporting again
the refill put no seeds in the seeder — stopping this pass
```

Two defects, both real. **(1)** The v1.114/v1.115 short-circuit asked only *which
seed* a crate held, never *how much*: a crate left half-full (23 of 50) made the
trip report "loaded", the field has 50 cells, and 27 tiles stayed Cultivated for
the whole growth cycle (the next loop read `27 cultivated, 0 seeded, 23
standing`). An owned crate that **reads** 0 seeds is now skipped outright; the
count comes from the crate's own `Configurations.Capacity` (the same field the
seeder uses) and a crate that cannot be read is still used — rule 7, unreadable
is not empty. **(2)** `seedShopTried` was a once-per-**run** boolean, so the seed
pass's own promise (`refill 1/3`, `seedPasses`) was dead code from the second
trip on: any run that started with an empty seeder spent its only trip at the
start and could never refill mid-field. It is now a counter `seedShopTries`
against the global `spudSeedTripsMax = 4` — the entry trip **plus** the pass's
three refills — and the refusal line names the number it hit. New
`seed_refill_test.py` (19 checks) pins both the crate read and the arithmetic tie
between the two counters, and asserts `seedShopTried` never comes back. Suite
**30/30**.

**A price read in town is not re-read by hopping back (v1.117).** The first live
run of v1.116 (owner's emulator, 2026-11-01) never reached the half-crate case —
the Farm tab was on **Cabbage** and the town till is expensive:

```
the seeder is empty — going to buy Cabbage (50 cell(s) need seed right now)
seed shop: FarmCo at Markers.GotoLocations.FarmCo (1097 studs) — tp'ing there for Cabbage
seed crate: the Cabbage crate (SeedBox) costs 57600 coins — balance 54159
seed crate: that is more than the balance — not buying it (pick a cheaper seed or sell something first)
✅ back in the tractor — the planting stage runs next
no seed was bought this run (the shop lines above say why) — the planting stage can't run
Field: 0 bare, 0 plowed, 50 cultivated, 0 seeded, 0 standing, 50 total cells
check-back 1: still to do — plow:no cultivate:no seed:yes
… the same 1,097-stud hop again …
check-back 2: still to do — plow:no cultivate:no seed:yes
```

So the "fuckes the whole thing up" half of the report is a **repeat**: a 50-cell
field stays Cultivated for ever while the run pays a 1,097-stud teleport, a
dismount, a mount and a store trip to rediscover a number it had already read.
The crate's own `CostBillboard` is the only price source and it is only readable
in town, so the **first** hop is kept and its answer is cached in the global
`spudSeedPrices` (keyed by the lowercased seed name); `seedCheck` then asks
`spudSeedPriceBlocks(spudSeedPrices, seedChoice, coinBalance())` **before** it
spends a trip, and says
`the Cabbage crate was 57600 coins at the shelf and the balance is 54159 — not
hopping to town for a price this run has already read`. The balance is re-read at
every check, so the cache holds the price and never the verdict — sell a load and
the same seed is buyable again — and an unreadable price or balance blocks
nothing (rule 7). `seed_refill_test.py` grew 10 checks for that predicate (no
cache / cheaper / exactly payable / dearer / unreadable balance / unreadable
price / nil table / another seed / case-insensitive / nil name) plus two source
ties: the shelf price must actually be stored, and the gate must sit **before**
`spudSeedTripAllowed` so a refusal costs no trip. Local budget unchanged
(headroom 10), name audit clean (341). Suite **30/30**.

**Both halves watched live (v1.117, owner's emulator, 2026-11-01).** The gate
line appeared on every seed check after the first, and the whole run made
**one** 1,097-stud hop — the one that had to read the price:

```
the Cabbage crate was 57600 coins at the shelf and the balance is 54159 — not hopping to town for a price this run has already read (sell a load or pick a cheaper seed)
check-back 2: still to do — plow:no cultivate:no seed:yes
the Cabbage crate was 57600 coins at the shelf and the balance is 54159 — not hopping to town for a price this run has already read (…)
```

With the Farm tab moved to **Wheat** (affordable) the rest of the chain closed
the owner's original report end to end:

```
the seeder is empty — going to buy Wheat (50 cell(s) need seed right now)
✅ KADL respawned — it moved into the world
✅ Wheat bought via FNCRequestStorePurchase (balance 54159 → 54123)
✅ seeder now holds 50/50 seeds (Wheat) — the planting pass takes it from here
✅ hitched KADL (attempt 1)
remote seed: fired 44 of 44 cell(s) from 7 stop(s), 9 per stop — 44 took, 0 left
✅ seeding complete — no field is missing seed any more
Field: 0 bare, 0 plowed, 0 cultivated, 50 seeded, 0 standing, 50 total cells  [Seeded=50]
```

**`0 left`** is the number the report was about — no tile was missed, and the
later pass read the same field at `50 standing`, so the seeds took and grew.
The v1.116 empty-crate skip did NOT get observed (the plot's half Wheat crate
had already been poured out, so the scan found nothing to use and bought
straight away). **What the same run exposed instead is the unload**: the harvest
leg reached `harvester is FULL (1/50, after the remote pass)` — the v1.86
"room cannot cover the cells" rule, working as designed — and then

```
fulfillment: Stores.DropOffs holds no pad part — nothing to drive onto
no Fulfillment pad is streamed from here — arc hop to the store, then looking again
arc hop: 1133 studs, lifting 70 studs (Y 166 → 166)
⚠ no Fulfillment pad found (not even after a store hop) — unload skipped
```

so `Stores.DropOffs` is empty **even standing at the store**, while
`findSellSpots()` still returns four FarmCo boards. Uninvestigated — it is the
Drop-off area, not the seeding report.

**"look bro i found a bug, it's not going to harvest" (v1.118–v1.119).** That
uninvestigated half was the whole report, and the emulator console named it
before any guess was needed: the harvest pass fires **zero** calls, because the
unload it sends itself to can never happen.

```
remote harvest: 49 free slot(s) cannot cover 50 standing cell(s) — selling first, then coming back
harvester is FULL (1/50, after the remote pass) — unloading
harvester FULL (1/50) — going to Fulfillment
fulfillment: Stores.DropOffs holds no pad part — nothing to drive onto (0 child(ren): )
no Fulfillment pad is streamed from here — arc hop to the store, then looking again
arc hop: 1133 studs, lifting 70 studs (Y 166 → 166)
⚠ no Fulfillment pad found (not even after a store hop) — unload skipped
no unload landed — backing off for 60 s instead of hammering the pad (…)
50 cell(s) across 1 field(s) still standing — going back to harvest them (round 1)
```

**v1.118 was the instrument, not the fix.** The refusal now prints the folder's
child count and each child's `Name [ClassName]`, and the answer was **0
children** — the folder is there and empty at the field *and* again after the
1,133-stud hop, which is what an older world dump had already said about it. So
`Stores.DropOffs` is simply not where the pad lives any more, and rule 4
forbids guessing where it moved to. **v1.119** keeps the folder as the first
choice and, when it holds nothing, reads the world's own instances once and
uses whatever the game actually has: a `BasePart` (a place to park **and** the
part to fire at) or a `Model` (a place to park only — `part = nil`, which is all
a pad that drains a parked harvester by itself needs). A refusal is still never
a guess: it names the folder's state, how many instances were read, and up to
eight pad-sounding world entries with their class and full path. So the next
live run either logs `fulfillment pad: <real path> at (…)` and the harvest
unloads, or it logs the classes — which is the answer the real fix needs.
`dropoff_test.py` grew 10 checks (the pad found under
`Objects.Buildings.CompanyArea`, its real path in `what`, the top surface still
aimed at, the folder still winning when it does hold the pad, a Model pad
parking without a fire part, and a no-pad-anywhere refusal that names the world
read). Suite **30/30**, headroom 10, name audit clean (341). **Harness green —
not yet reloaded in game.**

**"before every tool use on the field it waits a bit like 10 seconds" +
"add a anti afk that is on be default" (v1.120).** Two asks, both from the
emulator console the owner was watching. **(1) The dead 10 s.** Timestamped
logcat pinned it exactly: the corner pass, not the travel.

```
03:04:17.957 batch test: 50 cell id(s) in ONE call — watching the field
03:04:19.185 batch test: the server ignored the id list (50 still need it)
03:04:30.051 remote seed: 44 cell(s) still need it — one retry of just those
03:04:39.123 remote seed: 6 of 50 cell(s) took the call in 11.0s — the blocks take the last 44
03:04:51.264 remote seed: fired 44 of 44 cell(s) from 8 stop(s), 9 per stop — 44 took, 0 left
```

Seed and harvest are **InvokeServer**, so every call waits for the server's
answer: ~0.2 s each, and 50 of them from the field corner cost 11 s to learn
what the measured band already says — only the cells within ~2 tiles of the
blade can take a call at all (20 studs taken, 30 refused), so 44 of those 50
could never land. The retry then spent another 9 s firing at the same
out-of-reach tail from the same pose. `spudFieldRemotePass` now takes the
field frame (`baseCF, baseSize`, supplied by `sweepField`) and fires only the
ids `cellsAtStage` maps inside `spudFieldReach = 24` studs of the tool's own
attachment (sideways only — height is free up to +80); the leftovers are not
retried at the corner and go straight to the blocks, which put the blade over
every one of them. A field with **nothing** in reach fires no call and says
`remote <verb>: N cell(s) need it but none is within 24 studs of the blade —
going straight to the blocks`, and no field frame, no readable cell position or
no numeric id means **no filter** (rule 7 — unreadable is never a skip). The
retry line now counts what it actually retried (`one retry of the N in reach`).
**(2) The Anti-AFK** (Settings toggle, **on by default**, remembered in
`spudSavedAntiAfk`): Roblox flags a client with no input for ~20 min and the
server drops it, which is exactly what a 60-minute Cabbage growth wait does to
a sleeping owner. `spudAfkNudge()` sends a **ScrollLock** press (no context
action in this game uses it) plus a **1-pixel mouse move** — whichever of the
two the client counts as activity restarts the idle timer, and neither can
touch the farm: no key the game binds, no button clicked. One beat every
40–50 s, silent (a startup line plus `anti-afk: the game flagged this session
idle — input sent` from the `LocalPlayer.Idled` hook), stopped by the same
`spudAlive()` generation guard and disconnected in `destroyUI` as
`spudAfkConn`. `field_remote_test.py` grew 10 reach checks (4 of 8 cells
called, the far ones handed over not dropped, no call when nothing is in
reach, an out-of-reach bail neither dry nor a session switch-off, and no field
frame firing all 8) plus a Python tie that `spudFieldReach` is still the
measured 24. Suite **30/30**, headroom 10, name audit clean (344). **Harness
green — neither half has been reloaded in game**, and the anti-AFK's real
verdict is a session that survives the night.

**"look rn all the crops are fully grown but it wont harvest" (v1.121).** The
emulator console answered before any guess: the harvest **did** start — the
field read `50 standing [Harvestable=50]`, the run spawned SRC6, mounted it and
hopped to the field — and then the tank blocked it, because the unload could
never happen:

```
remote harvest: the tank is full — 50 cell(s) still standing; the sell trip runs before the rest
harvester is FULL (50/50, after the remote pass) — unloading
fulfillment pad: Ugc.Markers.GotoLocations.Warehouse at (-367, 138, -108)
sell: EVTSellAtStore fired at 838 studs from the harvester — watching the tank
Fulfillment: the in-place call didn't move the tank at 838 studs — taking the pad trip
arc hop: 837 studs, lifting 70 studs (Y 166 → 166)
fulfillment pad Ugc.Markers.GotoLocations.Warehouse: parked — this pad unloads by itself, pressing nothing
no unload at Ugc.Markers.GotoLocations.Warehouse after 16 s (load 50, coins 14459 → 14459) — the pad didn't take it while parked
⚠ still full — none of the pads took the load
no unload landed — backing off for 60 s instead of hammering the pad
```

**Root cause: the v1.119 world-walk accepted a navigation marker as the pad.**
`scoreOf` gives `warehouse` +2, and `Ugc.Markers.GotoLocations.Warehouse` is a
`BasePart`, so it passed the `score >= 2` gate — but a marker is a *travel*
destination (the seed trip hops to `Markers.GotoLocations.FarmCo` for exactly
that reason), and parking a harvester on a waypoint 20 studs off the real
`Deposit_Warehouse` drains nothing. Because `#spots` was 1, the existing
"nothing streamed → hop to the store and re-read" branch never ran, so the run
repeated the 837-stud hop every 60 s while 50 ripe cells stood, and the growth
wait kept logging `🌱 no cell reads as Seeded yet (50 cell(s), 50 grown)` — the
field was never going to read Seeded again until it was harvested. Two changes:
`spudFulfillSpots()` now rejects any candidate whose path contains
`Marker`/`GotoLocation` and returns it as a **second value — the waypoint**, and
`sellHarvester` hops there (instead of FarmCo, which is on the other side of
town for a Fulfillment pick), waits for the stream and re-reads, so the pad is
found where the game actually keeps it. `dropoff_test.py` grew 10 checks (a
marker is never the pad, it comes back as the waypoint with its real path, the
refusal still says no pad, a real `CompanyArea` pad beside the marker still
wins, no waypoint when a pad is found; and on the trip side: the hop goes to
-367 not -900, the pad is re-read after the hop, the real pad takes the load,
the trip back returns to the field). Suite **30/30**, headroom 10, name audit
clean (344). **Harness green — not yet reloaded in game.** If the re-read after
the waypoint hop still finds no pad, the refusal line now names the pad-sounding
world entries with class and path, and the honest options are the **Sell**
boards (which `findSellSpots()` does return) or one hand-driven trip to name the
pad for good.

**"i want to add a feature that auto does the fufillements the company needs" →
"well start witht the prober" (probe only, no main-script change).** The owner
then answered the design questions: **crops only**; pick the **easiest** order by
**seeding time and cost**, and *"if it dont got enough money to buy 1 single seed
mox it skips and goes to a lower cost one"*; **only steer the next planting**
(never rip out what is growing); the delivery itself is **parking the vehicle on
the pad**, which the unload trip already does. Two more rules came out of the same
conversation: *"it should put the tihngs or sell them before planting again bro"*
(any load in the tank is unloaded at the stage boundary **before** planting) and,
when the Fulfillment pad will not drain, *"try 5 more times then go to sell"*.
None of it can be written yet, because rule 4 forbids guessing the two shapes it
depends on: **what an order actually is** in the world (no dump has ever named one)
and **whether a crop's grow time is readable anywhere** (the ranking key). So
`SpudFulfillProbe.lua` was upgraded to answer exactly those, read-only: order-named
instances with their whole value trees, the board's visible text from `workspace`
**and** `PlayerGui`, what `Stores` holds, every seed crate's `Configurations`, and
one field cell's full key list plus `FieldHelper`'s exports — each in a `pcall` so
one unexpected shape prints `!! <section> FAILED` instead of eating the report.
New `tools/fulfill_probe_test.py` (25 checks) runs the real probe against a fake
farm and pins the read-only claim (no key press, no `FireServer`/`InvokeServer`,
no `CFrame`/`PivotTo`, no metatable hook). It also caught its own first bug: the
grow-time verdict matched the substring `grow` over the joined key list, so
`PlantGrowth` and `GrowthMultiplier` made a cell with **no** duration read as
"a time-shaped key IS on the cell" — the check now tests each key name against
time / duration / unit / ripe / ready words. Suite **31/31** (the new harness is
auto-discovered), headroom **10**, name audit clean **344** — `SpudFarm_Full.lua`
was not touched, so `VERSION` stays at v1.121. **Harness green — the probe has not
been run in game**, and until its report comes back the order feature has no
reader.

**"what but in a earlier dump didnt i tell you the coords to do the
fufillement?" (v1.122).** Correct, and the probe ask was the wrong ask: the
Fulfillment pad's position has been in the record since the owner's v1.32-era
dump (`Deposit_Warehouse` at **-353, 138, -90**, `Withdraw_Warehouse` at
-286,138,-217). Reading the trip against those numbers exposed the real reason
the park never drained, on top of the v1.121 marker bug: `hopTo` lands at
`max(takeoff, target.Y)` (the v1.42 rule), the fields sit at Y 166–172 and the
pad at 138, so **every** outbound unload trip parked the harvester 28–34 studs
*above* the pad it was sent to — the live line `arc hop: 837 studs … (Y 166 →
166)` next to a target at 138, `load 50 → 50, coins 14459 → 14459`. Two changes:
the hop now lands at the **target's own height** (the lift formula already
clears both ends by ~12 studs, so the arrival is still a descent, and the return
leg from a lower pad is unaffected — it lands at the field either way), and
`sellHarvester` finishes with `spudFulfillPadSpot()` as a **park-only** fallback
(`part = nil`, so no `EVTSellAtStore` is fired at an imaginary part and no key is
pressed — a Fulfillment pad drains a parked harvester by itself, v1.41), logged
as `fulfillment: no pad instance is readable — parking on the probed spot
(-353, 138, -90)`. `hop_test.py`'s "a trip down still lands at the takeoff
height" check was the defect written down, so it is inverted (and its nil-Y case
now passes a bare table, because `Vector3.new` coerces a nil Y to 0 and could
never exercise the guard); `dropoff_test.py` gained 7 checks (the constant is the
dumped coordinate, the trip parks there instead of skipping, no call fires
without a part, the park stays key-free, the log names it as remembered). Suite
**31/31**, headroom **10** (the new `local` is inside a function, not the build
closure), name audit clean **345** (`spudFulfillPadSpot`). **Harness green — not
yet reloaded in game**, and the verdict is one log line: `✅` a tank that drops
while parked, or the honest `the pad didn't take it while parked` at the probed
spot, which would mean the pad needs something other than contact.

**"is there a exploit that we can make the croops grow instalntly" (v1.123).**
The honest starting point is that four doors are **already measured shut**, so the
question is not "can we hurry the clock" but "can we skip the wait":
`EVTFieldPacket` is server→client (a real packet with its stage byte patched moved
nothing), the client cell mirror is writable but the server never reads it (a
forged `Cultivated` sat there and read back `Cultivated`, no update arrived),
`FieldHelper` exports **no setter**, and `FNCSprayFieldCell` changed nothing on the
one cell the v1.66 run happened to aim at. (v1.124 note: that spray line is weaker
than it reads — the cell was an *Empty* tile **and** the call carried no
attachment, so water was never measured at all; see below.) What had never been
asked is the only
thing left, so the answer is a new Tests-tab probe rather than a guess: **Grow
now** (`spudTestWork("growth")`) prints the field's **stage census with each
cell's own `PlantGrowth` / `GrowthMultiplier` / `IsWatered` / `SeedType`** (which
also shows whether the harvest job's "any unknown stage is a standing crop" rule is
being fed an immature name, and what the ripe number even is), then **gets into
the harvester** — spawned out of storage if parked, because the Tool-apart answer
(§3.12) is that a loose implement takes *nothing*, so a refusal read from the
ground would be a false answer — parks the blade on a `Seeded` cell with the
grid's own settle-poll, fires `FNCHarvestFieldCell` and reads **both the stage and
the tank**: a take that raises `Capacity` is the exploit (plant, cut, repeat, no
wait), a take that raises nothing is a bare cut, a refusal is the server asking for
a ripe cell. Only then, and only after a refusal, does it write the cell's
`PlantGrowth` to the **ripe number the game just printed** and split "a fresh
`GetCells` dropped the write" (the table is a copy — nothing to patch) from "the
mirror now reads ripe" (re-fire the cut and see whether the server consults it —
the old tile test forged `Stage`, never the growth number). Last it fires
`FNCSprayFieldCell` with the **sprayer's own** attachment at that planted cell —
the earlier spray hit an *Empty* tile, so water-vs-growth was never measured on a
crop — finding the sprayer by walking `Objects.Equipment` for a
spray/sprinkler/water/irrig name and printing every machine with its real
`EquipmentType` when none matches, so the next run names it instead of this one
guessing it (rule 4). It is deliberately **not** in **Run all**, which stays the
two read-only probes; this one sits in a machine and cuts a cell. No harness (the
live re-read is the only verdict, same as the other Tests probes). Suite **31/31**,
headroom **10**, name audit clean **345** — no new global, every local is inside
`spudTestWork`'s own scope. **Harness green — not reloaded in game**, and the whole
answer is in the `growth:` lines of one `Copy report`.

**The v1.123 report, read (v1.124).** The owner ran **Run all** on the live build,
and the report corrected three things about our own evidence rather than about the
game. **(1)** `remotes: 339 found under ReplicatedStorage (601 nodes walked)` —
the walk's cap was **600**, so it aborted *inside* `Modules.Larry` and the list was
cut short while claiming to be complete. The cap is now 3000 and the line says
`CAP 3000 REACHED — this list is cut short` when it trips (the record had counted
334 before, so 339 was already the tail of a truncated read, not a growth). Even
truncated it named doors never probed: **`EVTUpdateCropGrowthConfig`** (the server
broadcasts a crop-growth config ⇒ a client copy of the per-crop times may exist),
and the Company-order family **`FNCGetOrderProgress` / `FNCAcceptOrder` /
`EVTRefreshOrders` / `EVTFreeRefreshOrders` / `EVTOrderDepositProgress` /
`EVTOrderFulfilledFX` / `EVTWithdrawOrderFX` / `EVTTrainOrderDeposited` /
`EVTDepositIntoTrainCar`** — which is the door task #6 was waiting on a probe to
name. **(2)** `fieldremotes: cell 518 is Seeded, watered false, growth 1170 (tool
none)` then `after spray — … no change from here`. `(tool none)` means
`spudToolAttachment` had nothing: the call went out with **no attachment at all**
(worse, in the third slot rather than the captured `{att}` **list**), so that
`no change` measured an empty request, not water — water on a growing cell is
**still unmeasured**, and the §5 line above that said "the v1.66 run happened to
aim at an Empty cell" was only half the reason. The leg now passes `{ att }`, prints
which attachment (`the call carries <part>.<attachment>`) or says outright that no
implement exists to spray with and that a `no change` below **answers nothing**, and
points at **Grow now**, which finds the sprayer by name. **(3)** A real growth
number is now on the record: a `Seeded` cell reads `PlantGrowth 1170`, so the
"census" line has something concrete to compare a `Harvestable` cell against — and
`FNCEditField()`'s returned table (live: `table: 0x2b526078eb43ec6f`) is still just
an address, which is why **Grow now** gained a reader: it walks `Modules` for a
`ModuleScript` named grow/crop/config, requires each inside `pcall` and prints the
table one level (`Wheat={…}` per key, values for scalars, `fn` for functions, 14
keys + a `(+N more)`), or says no such client copy is sitting there to read. That
serves the owner's order-ranking rule too (*"it chooses the easyest one by seeding
time and cost"* — the time half was never readable anywhere we looked). **Run all**
stays the two read-only probes; the config read lives inside **Grow now** with the
rest of the growth questions. No harness (a live read is the only verdict), no new
global, no new build-closure local: Suite **31/31**, headroom **10**, name audit
clean **345**. **Harness green — not reloaded in game**, and the instant-growth
verdict still needs the one button this run did not press: **Tests → Grow now**.

**"bro it havested" — the wait is optional (v1.125).** The owner pressed **Tests
→ Grow now** and pasted the console, which answered the instant-growth question
outright: `growth: early cut — Seeded → Empty, tank 0 → 1 — TAKEN AND IT PAID: a
crop can be harvested before it is ripe — the wait can be skipped`. Same report:
the census read `Field — Seeded ×50 [growth 2012, mult 1, watered false, seed
Tomato]` (so `PlantGrowth` counts **up** from planting; the ripe number stayed
unknown because nothing was standing to compare against), the picker named the
harvest point (`attachment: SRC6 → HarvesterAxle.AxleAttachment (harvest)` — the
SRC6 has no `RaycastPart`, so the harvest-sounding rank wins, which is the v1.89
wheel-strut failure closed with a live take), the equipment remotes worked from a
probe (`Spawn SRC6 via spawn (no UI)`, `✅ mounted SRC6 (FNCEnterEquipment)`,
`Store SRC6 via store (no UI)`), and **there is no sprayer on this plot**
(`KADL=Planter, Trailer=Transport, S4204=Plow, KQF3000=Cultivator, SRC6=Harvester,
R150=Truck, ZM80=Tractor`), so water-vs-growth cannot be measured here at all —
the run says so instead of leaving the v1.66 `no change` to be read as a verdict.

The follow-up is the behaviour, not another probe: **Early harvest** (Settings,
**on** by default, remembered in `spudSavedEarlyCut`, §3.14). One predicate —
`grownStage` — now treats a `Seeded` cell as a standing crop, and because the
census, `whichNeed`, the cell-id list, the field tour and the growth wait all read
that same predicate, a run plants and cuts the field on the same cycle instead of
sitting in `🌱 growing: 50/50 cell(s) still Seeded` for an hour. Off is the old
build, byte for byte. `waitForGrowth` restarts on a cuttable field, bounded by
`spudCutWatch`: the **same count twice in a row** means the harvest pass is taking
nothing (no harvester on a picked farm, a refused call), so the third read waits
like a normal cycle instead of spinning. The census column renames itself
(`%d cuttable` vs `%d standing`) so a log line never hides which mode produced it.
Two side fixes came out of the same report rather than a hunt: the growth leg now
calls a config **getter** with no arguments when a module exposes one (`GetConfig()`
— an error names the shape it wants instead of us inventing one; live it found
`CropGrowthConfigClient → GetConfig=fn SetConfig=fn`, a client crop-growth config
with a setter we have never called), and the ten-minute `🌱 no field readable yet`
silence the owner's own console showed at 87 studs now says **which** field could
not be read — the call failed, or `GetCells` answered 0 cells — with its distance
(rule 7: unreadable is never empty, so it gets named, not assumed away). New
`tools/early_cut_test.py` (21 checks + 12 source ties) pins the predicate
agreement and the ties; `tools/run_all.py`'s compile row was also lying — it
grepped `FAIL` out of the **bytecode** `luau-compile` writes to stdout, so the
build read broken the moment a log string contained those letters (the new
`the cell read FAILED` line was the first to hit it). The compile row is judged by
the exit code and stderr now; every harness row still reads its stdout, because a
harness printing `FAIL` and exiting 0 is exactly what that scan exists for. Also
**📍 Get coords** (Settings), at the owner's ask: it logs and copies
`(x, y, z)` from the character, so a pad the script cannot stream can still be
named by somebody standing on it. Suite **32/32** (the new harness is
auto-discovered), headroom **10** (no build-closure local: the pick and the spin
guard are globals), name audit clean **347**. **Harness green — not reloaded in
game**, and the first live run of the pick is the verdict: a field planted and cut
inside one cycle, or the honest `early cut: N cell(s) still read cuttable after 2
restart(s) that took nothing`, which would mean the single cell the probe cut does
not generalize to a whole field.

**The button's first four readings (v1.126).** The owner pressed **📍 Get coords**
standing on each town spot and pasted all four:
`furfullement=(-353, 141, -92)`, `sell crops=(125, 142, -150)`,
`sell liquid=(86, 141, -288)`, `sell logs and planks=(232, 141, -232)`. Two of
them are the addresses the unload trips have been missing: `spudFulfillPadSpot()`
is now the standing reading (X agrees with the old part-centre dump exactly, so
it is the same pad — 3 studs higher because a character stands *on* the deck, and
the hop lands at the target's own Y), and a **Sell** pick with no board streamed
anywhere no longer skips the unload — it parks at `spudCropSellSpot()` and lets
`trySellAt` run its Q/E menu path there, because a sell board is **not** the
auto-draining Fulfillment pad. That difference is pinned (`autoPad` must stay
false on the remembered Sell spot), and the old check asserting
`sell: no pad and no marker -> no sale, no hop` was the defect written down, so it
is replaced by the trip. The other two readings have **no consumer**: the milk
loop fills a liquid carrier and only reports `store: <carrier> is FULL — empty it
or pick another` (a drain trip to `86, 141, -288` is the unbuilt half of that
line), and the script harvests no wood at all (§3.8 refuses tree soil), so
`232, 141, -232` is recorded in §3.10 rather than wired. Suite **32/32**, headroom
**10**, name audit clean **348** (`spudCropSellSpot`). **Harness green — not
reloaded in game**, and the verdict is one of the two `✅` lines: a tank that drops
at the measured Fulfillment deck, or the honest
`still full — none of the pads took the load`, which would mean the Y needs a few
studs of tuning and only a live park can say how many.

**"i found a small bug, when the barns and cows are too far from where the player
tps' it just stalls there" (v1.127).** The v1.125 console the owner pasted named
the failure in two adjacent lines:

```
milk: desbiens1235 is 868 studs away - teleported to its plot
milk: no stall found for desbiens1235 in 17 ms (0 skipped)
0 stall(s) - 32 cow(s), 0 in a barn
herd: 31 ready cow(s) LEFT in the field - the next cycle takes them
milk: no dirty stall seen - next barn check in 60 s
```

**Root cause, from the code rather than a guess:** the plot branch of
`milkCycle` teleports and then reads the stalls *once*. `Workspace.Plots` is a
folder of lightweight models that stays replicated at any distance — that is why
the plot was readable from 868 studs away at all — while a barn is a full 3D
building inside `Objects.Buildings` that has to stream in around the camera. The
only settle between the two reads was `milkTp`'s 0.2 s, which exists for the
~50 ms a CFrame needs to reach the server (§11), not for area streaming, and the
branch that *does* wait for streaming (the plot-not-found one, up to 4 s) never
runs when the plot is the part that answered. So one pass concluded "no stalls",
herded nothing because there was no stall to send cows into, milked nothing, and
the loop rested 60 s — every 60 s repeating the same 17 ms read. The 32 cows in
the same line are the proof the farm was full: **animals stay networked when
buildings do not.**

The fix is `spudStallScan(owner, cf, size, hopped)` (§3.4): the scan is asked
again until the game answers with stalls, 0.25 s a try, **12 tries** — the scan
is the signal, not a guessed sleep (§8), and the bound keeps a genuinely
barn-less farm from costing more than 3 s a pass. The wait is licensed by the
hop: `milkCycle` now keeps the teleport's own answer (`hopped = milkTp(…)`, both
branches) and a pass that did not move reads once and sleeps zero, byte for byte
the old behaviour. When the answer never comes the line says what it is —
`still no stall after 3.0 s - desbiens1235's plot reads but its barn has not
streamed in; this pass reads nothing here, which is not "no barn"` — rather than
letting an empty list pose as an empty barn (§7). Stop ends the wait between
tries, the skipped count and the same plot/owner are carried through every
re-read, and the timing stamp moved to *after* the scan so the status line's
`clean` is the clean and not the streaming wait. New
`tools/stall_stream_test.py` (29 checks + 5 source ties) runs the real helper on
a virtual clock. Suite **33/33**, headroom **10** (`local stallAt` is inside
`milkCycle`, not the build closure; the helper is a global), name audit clean
**349**. **Harness green — not reloaded in game**, and the verdict is one line in
the next far-farm pass: `the barn streamed in 0.5 s after the hop - 12 stall(s)`
followed by real clean/herd/milk work, or the honest not-streamed line, which
would mean 3 s is not enough for that plot and the wait — not the diagnosis — is
what needs changing. The Trailer / Equipment-Manager lines in the same dump were
a test and are deliberately untouched.

**"when it does the farm look amd i put it to furfillement it brought me to the
wrong place" (v1.128).** The v1.126 console the owner pasted had the answer in
four lines:

```
fulfillment pad: Ugc.CompanyArea.WarehouseArea at (-278, 138, -212)
arc hop: 860 studs, lifting 70 studs (Y 166 → 138)
fulfillment pad Ugc.CompanyArea.WarehouseArea: parked — this pad unloads by itself, pressing nothing
⚠ still full — none of the pads took the load
```

**Root cause: the world-walk accepted a district as the pad.** `scoreOf` awards
`warehouse` +2 and the walk admits any `score >= 2` node that is a `BasePart`
**or a `Model`** (a pad may be a model, which is all a contact-draining pad
needs), so `Ugc.CompanyArea.WarehouseArea` — the whole yard, 60 × 2 × 60 of it —
beat "no pad", and the trip parked on its bounding-box centre. v1.121 closed the
same class of bug one step earlier (`Marker`/`GotoLocation` names come back as
the waypoint, not the pad); this was the other half of the same mistake — a name
that *sounds* like the pad is not a proof the instance **is** the pad. And the
place it chose is the yard's other side: 142 studs from the deck the owner stood
on, which is also the "it's going the the other pad close that deliver" symptom
reported before any of this was wired.

The fix is a distance gate keyed to the owner's own reading rather than to a new
vocabulary (rule 4 forbids inventing names): global `spudFulfillPadNear = 35`. A
candidate the **walk** matched by name is only the pad if its park point sits
within 35 studs of `spudFulfillPadSpot()`; the harness reproduces the live
`WarehouseArea` and gets **142** back. The band is not a guess either — the two
readings of that deck (the 2026-10-30 part centre `-353,138,-90` and the
2026-11-02 standing deck `-353,141,-92`) agree within **3.6 studs**, while the
withdraw pad across the yard is **143** off — and the refusal prints its real
distance, so a wrong band shows up in one run instead of becoming folklore. A
refusal answers exactly like an empty world: the marker waypoint still comes back
as the second value, the trip hops there, re-reads, and if the game still offers
nothing at the deck it parks on `-353, 141, -92` (v1.126's measured spot) — the
address the owner gave. `Stores.DropOffs` is deliberately **not** gated:
whatever that folder holds is a drop-off by the game's own grouping, and gating
it would mean rejecting the plain `DropOff` pad that `dropoff_test.py` check 3
exists to keep.

`dropoff_test.py` grew 6 checks (the far match returns no pad, the line names the
path and the 142-stud miss, the waypoint still comes back, an in-band match is
still taken and logs no refusal) plus 4 source ties, and the model-pad fixture
moved onto the measured deck — its old `-300, 138, -60` was a stand-in written
before 📍 Get coords existed and would itself now read as a name match 62 studs
off. Suite **33/33**, headroom **10** (the new name is a global assignment; every
new local is inside `spudFulfillSpots`' own prototype), name audit clean **350**
(`spudFulfillPadNear`). **Harness green — not reloaded in game**, and the verdict
is the next full tank on a Fulfillment pick: either
`fulfillment: Ugc.CompanyArea.WarehouseArea is 142 studs from the measured pad
(…) — … not the drop pad` followed by `parking on the measured spot (-353, 141,
-92)` and a tank that drops, or a real pad path inside the band. If it parks on
the measured deck and the tank *still* does not drop, the deck number itself is
what needs changing — and only a live park can say by how much.

**"not detecting my new harvesters and tractors" + "the tp's make the tool fall
out the map" + "if the tool is bigger cant the burst things also be bigger"
(v1.129).** Three asks in one build, all answered from the live DOCTOR dump the
owner's emulator printed (rule 4, no guessing): every model in
`Objects.Equipment` carries `EquipmentType`, and the set is now `ZM80=Tractor`,
**`JDS790=Harvester`** (MaxCapacity 600), `KADL=Planter`, `KQF3000=Cultivator`,
`S4204=Plow`, `R150=Truck`, `Trailer=Transport` — **`SRC6` is gone**, which is
exactly why a build whose pick leans on model names finds no harvester. **(1) The
pick reads the game's own data** (§3.7): `spudEquipTypeKey` strips the game's word
to letters and `spudEquipIs` matches a **stem**, so `"Forage Harvester"` and
`"Harvester"` are one machine; a model name is a last resort for a build that
ships no attribute and can **never veto** what the game wrote; with no machine
called a Tractor out, `findTractor`'s loose pass asks the game's **structure**
instead — a `VehicleSeat`/`Seat` **and** `Components.Hitchable`, excluding
anything the game calls a Truck / Transport / Harvester / tool — and logs the
machine it settled on. `findImplement`'s `basis` now says **which rule won**
(`EquipmentType Cultivator` vs `model name KADL`), so the old
`basis == "model name KQF3000"` check — the name-wins defect written down as a
passing assertion — was inverted, not preserved. Every "none found" line ends
with `spudEquipHereText()` (up to eight `Name=Type (stored)` entries actually in
the world), so a refusal names the game's words instead of this build guessing
them. **(2) The tow settles before the next jump** (§3.12): `spudWaitTool`
samples the tool's flat distance from the ride twice 50 ms apart and calls it
`settled` at ≤3 studs, `far` past 90, `swinging` after 30 beats, `none` when the
attachment can't be read — and it runs **before** every `PivotTo` (each grid
stop, each per-cell hop, and the field-to-field arc, which refuses the field
outright rather than dragging the implement 800 studs off the map). A flung tool
ends the pass where it stands with `not on the hitch any more`; a swinging one is
named once per pass. **(3) The burst is the tool's own size**:
`spudToolExtraTiles(impl)` (the implement's measured width past one tile, clamped
0–6, **0** if the build will not answer) is added to the corner reach
(`24 + extra*5`), to the block side (`3 + extra` → a 4-wide tool gets 6×6, and
the log says `%dx%d per stop`), and to the stop's arrival tolerance and off-block
warning. The stage re-read stays the judge, so a generous reach costs a refused
call, never a missed cell. `equip_owner_test.py` was rebuilt around the real
stem tables and structural parts (17 new checks, incl. `PDRILL22`/Planter beating
the old name table, a seat-without-a-Hitchable never being the ride, and the
`spudEquipHereText` shapes) and is **ALL OK**; `field_remote_test.py` gained the
settle and wide-tool sections plus source ties that the gate sits **before** the
first `:PivotTo` in both passes. Suite **33/33**, headroom **6** (the four
`*_STEMS` tables are four build-closure locals — every other new name is a
global for that reason), name audit clean **364**. **Harness green — not reloaded
in game**, and the verdicts are three lines: the harvester found by its
`EquipmentType` word (not a name), a grid whose `took` is no longer gutted by a
swinging plow, and a wide implement logging `6x6 per stop` — the last of those
three was **reversed in v1.132**: a 4×4 stop paints a cross, because its own
corners sit outside the band that was measured to take.

**"what did you do" — v1.129 killed the farm loop (v1.130).** The owner reloaded
`83fcf93` in game and pasted the console twice; both runs died the same place,
right after `— seed check —`, while the tractor spawned and stored cleanly
around it:

```
✅ ZM80 respawned — it moved into the world
equipment: Spawn ZM80 via spawn (no UI)
— seed check —
⚠ farming loop error: VLZaHJYekijBuWSfmfPhONRBw:642: attempt to call a nil value
```

**Root cause, read from the source rather than guessed:** the v1.129 helper
`spudEquipHereText` is a 4-space `function NAME(...)`, which in Luau is a
**global** assignment — so its body compiles every identifier that is not an
already-visible `local` as a `_G` lookup. It called `equipmentFolder`, a
`local function` declared 200 lines **below** it (line 841 vs 641), and at the
moment of the call that name was not in the global table. Every other v1.129
name was placed correctly, which is why the DOCTOR dump, the `EquipmentType`
classification and the equipment remotes all worked while the seed check died.
**No harness can see this class of bug:** the tests slice the function out of the
file and stub the callee, so the upvalue order never exists.

The fix is the relocation, not a new abstraction — `spudEquipHereText` now sits
immediately after `local function equipmentFolder()` (824 → 835) with a comment
naming this exact failure — plus a class-wide guard in `tools/name_audit.py`
(`later_local_calls`): for every 4-space global function it collects the calls
in its body and flags any name whose only declarations are `local`s that appear
**later** in the file. Validated against the shipped build, where it prints
`spudEquipHereText: line 641 calls local equipmentFolder declared at line 841`,
and clean on the fixed file. Compile OK, suite **33/33**, headroom **6** (the
move adds no build-closure local), name audit clean **364**. **ANSWERED — the
owner reloaded v1.130 and the loop ran**: the console opens `rebuild v1.130`,
prints `— seed check —` and then goes on to mount the tractor, hitch the plow and
work the field, with no `⚠ farming loop error` anywhere. What that same run
reported instead is the tow, and it is the next entry.

**"we need to anchor the tractor when it tps because the tool drags it, also the
tractor tps before the tool can get back in place" (v1.131).** The owner's own
v1.130 console is the whole diagnosis — no new probe, no emulator run needed:

```
arc hop: 286 studs, lifting 70 studs (Y 166 → 166)
hitch gap at arrival: 277.7 studs
remote plow: the S4204 is 210 studs from the ride — it is not on the hitch any
              more, stopping the grid instead of dragging it further
remote plow: fired 0 of 2398 cell(s) from 150 stop(s), 4x4 per stop — 0 took
remote plow: the blade is 514 studs off stop 1 — firing anyway
```

**Root cause:** `Model:PivotTo` moves **only that model**. The implement is a
separate model attached through the game's own hitch, so every ride teleport left
the tool on the ground and put the constraint under the length of the trip —
277.7 studs of tension after one arc hop. That is both reported symptoms at once:
the taut tow is what drags the ride, and a bound 1.5 s settle can never close a
277-stud gap, so the next jump fires while the tool is still catching up and the
v1.129 guard (correctly) refuses the pass. The run plowed **0 of 2398** cells and
ended `2396 cell(s) never took a call even with the blade on them`.
v1.129 measured the swing; only the teleport itself can fix it.

**The fix is one global:** `spudPivotRig(ride, cf, tool)` pivots the ride, then
translates the implement by the **same position delta** and leaves the tool's own
rotation alone (a ride turn must not spin the plow) — and does **nothing** extra
when `tool == ride`, because the harvest job's `impl` *is* the ride and a second
delta would land the harvester 572 studs from a 286-stud hop. It replaces the bare
pivots
in the four field sites (`spudRadialFire` stop + re-park, `spudHopCells` hop +
re-park) and all three in `hopTo`, which gained a `towed` parameter — the tour
passes the hitched `impl`, the self-propelled sell trips pass `nil` and change
behaviour not at all. The row-driver/align-mover pivots are unreferenced code and
were left alone (rule 16). The gap becomes the tool's own trailing distance, so
`spudWaitTool` reads `settled` instead of `far` and the field gets called at.
`tools/field_remote_test.py` had been hiding this: its fake ride moved the blade
with itself, which is not what the game does, so the fixture now moves **only the
ride** — and the old build fails that fixture (`a ride-only teleport leaves the
implement on the ground (like the game) PASS gap became 286.04`). Ten carry
checks in that harness (grid: carries per jump / blade on the hitch / cells still
taken; hop: the same three; direct `spudPivotRig`; nil tool = no carry;
`tool == ride` = one move, no double) plus ten
tie assertions — four per field pass (the settle gate, that it sits **before** the
first rig move, that the pass uses `spudPivotRig(ride,` and keeps **no** bare
`ride:PivotTo(`/`tr:PivotTo(`), and two that `hopTo` carries and the tour hands it
the `impl`. `hop_test.py` extracted `spudPivotRig` too and added the arc case
(24 carries over 25 moves, hitch exactly 20 studs, no implement = no carry, a
self-propelled hop lands the ride once) with
the same pair of ties. Compile OK, suite **33/33**, headroom **6** (a global
assignment costs no register), name audit clean **365**. **Harness green — not
reloaded in game**, and the verdict is the two lines the owner already has:
`hitch gap at arrival:` reading a **few** studs instead of `277.7`, and
`fired N of N … N took` instead of `0 took` next to `not on the hitch any more`.
**ANSWERED — the owner reloaded it.** The next console reads
`hitch gap at arrival: 5.0 studs` and, after the field hops, `1.0 studs`, and no
line says `not on the hitch any more`, so the carry is confirmed in game. What the
same run exposes instead is the shape of the leftovers (`4x4 per stop — 1793 took,
595 left`) and the first stop of a seed grid — the next entry.

**"if it cant do a equal 3x3 or 4x4 or 5x5 or 6x6 or 7x7 it should only do one of
those, if it make a cross pattern it goes back to a 3x3" + "the seeding is
bugging, probably because the tool is attatched tot he tractor" (v1.132).** Two
reports, both about `spudRadialFire`, both answered from the console rather than
theory.

**(1) The cross.** v1.129 had let a wide implement widen the *block* as well as
the corner pass, and the live arithmetic says why that paints a plus sign instead
of a square (the owner's emulator, v1.131 build):

```
remote plow: fired 2388 of 2388 cell(s) from 150 stop(s), 4x4 per stop — 1793 took, 595 left
remote cultivate: fired 2399 of 2399 cell(s) from 280 stop(s), 3x3 per stop — 2374 took, 25 left
```

595 of 2388 is **24.9%** refused, and the four corners of a 4×4 are 4 of 16 =
**25%** — the same field on a 3×3 grid loses 25 of 2399. A stop parks the blade on
the block's **centre**, and on the game's 10-stud grid a square of `n` cells puts
its corner at `√2 × (n−1) × 5` studs out (14.1 for 3×3, 21.2 for 4×4, 28.3 for
5×5). The server's band is the sideways reading the lift probe measured — **20
taken, 30 refused** — so a 4×4's corners sit 21.2 out and are the cells that never
take, and a ride that fires them anyway and moves on leaves exactly that shape
standing. `spudFieldTaken = 20` (the strict
"actually took" number, distinct from the `spudFieldReach = 24` compromise the
corner pass filters at) now sizes the block through global `spudBlockSide(band)`,
which grows the side only while the **next** square's own corner is inside that
band and caps at 7×7. On this build that is **3×3 for every implement**, which is
what the owner asked for; a wide tool still widens the corner pass, because that
leg checks one cell at a time against the blade and earns no diagonal credit — the
call carries a single attachment point.

**(2) The seed pass firing nothing.** The same run, the two grids that follow the
shop trip:

```
remote seed: the blade is 32 studs off stop 1 — firing anyway
remote seed: fired 48 of 2398 cell(s) from 280 stop(s), 3x3 per stop — 36 took, 2362 left
remote seed: the blade is 41 studs off stop 1 — firing anyway
remote seed: fired 9 of 2362 cell(s) from 276 stop(s), 3x3 per stop — 0 took, 2362 left
```

The owner's guess was *"probably because the tool is attatched tot he tractor"*,
and the code confirms it without a new theory: v1.131 made the teleport carry the
implement, so the tool now lands at the ride's **rest trail** — but the offset the
stop is aimed from is read **before** the jump, and after a 288-stud arc that
reading is stale. The first stop of every grid is precisely the one that arrives
out of a long ride, so it parks 32 studs off its own block, the old code logged
`firing anyway` and spent the burst there — the `fired 9` is exactly one 3×3
block's calls, i.e. the honesty gate gave up the pass after stop 1 took nothing —
while the 48-call grid before it had already spent a whole seeder load on cells
the blade was not over. v1.97's
single re-park could not close it either — it re-aims from the same pre-jump
offset once. The fix is to re-make the park **from the blade's own fresh position**
until it arrives (three aims for the first stop, one for the rest, each taking a
new `spudWaitTool` settle so a flung tool still ends the pass) and, when the blade
demonstrably is **not** on the block, to fire **nothing** there: the block's cells
are left for the per-cell hop, which puts the blade on each one. Three consecutive
misses end the grid with
`the blade has not landed on 3 stop(s) in a row — ending the grid here; the hop
pass puts it on each cell`, and the honesty gate now keys on the **first stop that
fired** rather than stop 1, so a miss cannot disprove the server. An **unreadable**
blade still gets its burst (rule 7 — unreadable is not a miss).

`tools/field_remote_test.py` was the place the old defects were written down as
passing: its `6x6 per stop` check asserted the cross, so it is inverted to
`3x3 per stop` and six `spudBlockSide` corner checks added. The fixture ride now
has a **rest trail** (`TRAIL_REST`) and can start a grid 46 studs behind it, like
the arc hop does — that case must still take all 15 cells, with more than two pivots
for its two stops and no `leaving this block` line. The jam case parks a blade that
never lands (`TRAIL_STUCK` + `RIDE_JAMMED`, so `spudWaitTool` can never report
`far` and the 3-miss rule is what ends it) and asserts **0 calls**, the refusal
line, `not landed on 3 stop(s)` and all 27 cells still standing. Writing it taught
me the geometry again: `cellsAtStage` **turns** the plate when the field frame's
axis counts match the other dimension, so a 9×3 field on a 50×20 frame lays its
stops along Z at (0,−30), (0,0), (0,30) — the first draft assumed X and its
"stuck" blade was legitimately on stop 1. Ties now refuse the build if
`spudRadialFire` still contains `3 + spudToolExtraTiles(impl)` or the words
`firing anyway`. Compile OK, suite **33/33**, headroom **6** (both new names are
global assignments; the three new locals are inside `spudRadialFire`), name audit
clean **367**. **Harness green — not reloaded in game**, and the verdicts are the
two lines above: a seed grid whose `took` climbs towards `fired` instead of
`0 took` next to `firing anyway`, and a plow field that ends with no cross of
leftover cells. If the first stop still misses after three aims, the honest
reading is that the rest trail is longer than the arc's own settle can absorb, and
the next number to measure is that trail.

**"make it anchor te tool permanantly behind the tractor while it's hitched" +
"if a seeder has like 600 capasity, make it fill up the seeder fully" (v1.133).**
Two asks, one build, both answered from the code the previous builds had already
proven — no new probe was needed for either.

**(1) The weld.** v1.131 closed the 277-stud gap and the owner's own next console
read `hitch gap at arrival: 5.0 studs`, so the tow arrives *near* the ride — but
"near" is still the game's solver answering whenever it gets around to it, which
is why v1.132 had to re-aim each stop from a fresh blade reading. `spudAnchorTool`
makes the join **rigid** instead: a client `WeldConstraint` between the ride's
hitch `BasePart` and the tool's — the pair `findHitchPart` already ranks for the
physical line-up, **not** the `Components.Hitchable` / `Chassis.HitchableSocket`
attachments the captured `FNCAttemptHitch` takes (a `WeldConstraint` joins parts) —
after `SetNetworkOwner(LocalPlayer)` on the
implement, because a server-owned part simply rubber-bands through a client weld.
Three gates, and the middle one was the only real code change this segment: the
weld is made **only after the tug test proves the hitch** (it sits below
`hitchTool`'s gave-up branch, so a failed hitch can never weld anything), **only on
a `settled` read** (`far` / `swinging` / `gone` / `none` each refuse with a named
line — freezing a mid-swing frame would hold the plow at an angle the game never
rests it at), and it is **destroyed before anything asks the game to unhitch**
(the seven sites that face the game — park, unhitch path, the blind X at attempt 3,
the wrong-tool grab, loop end, loop stop, `destroyUI`, plus one inside the anchor
itself when a different tool goes on the same ride) because an X press against a
welded tow is a tug-of-war the script wins and the server loses, and "the tool
stayed put" would be a lie about the park. Every refusal costs the anchor **and
nothing else**, so this cannot regress a field pass.
New `tools/hitch_anchor_test.py` (≈40 checks + 13 ties) stubs `Instance.new`,
`findHitchPart` and `spudWaitTool` and asserts the weld's class, name, `Part0`,
`Part1`, parent, one network claim, idempotence on a re-call, the old weld destroyed
by a new tool, an empty `spudAnchor` after a refused `Instance.new`, and that a
weld still lands when `SetNetworkOwner` is refused.

**(2) Fill to max.** The live arithmetic was already in the console
(`the seeder is empty — going to buy Wheat (50 cell(s) need seed right now)` against a
machine whose `MaxCapacity` the KADL may now read far above 50): one crate bought,
one crate poured, one trip spent, and the field still hungry. Now the pour is a
loop until `spudSeederWantsMore(count, cap)` says the machine is full, the trip
ceiling is `spudSeedTripCeiling(spudSeedTripsNeeded(...), floor)` — which **only
ever raises** the old 4 / 3, so a 50-slot seeder is untouched — and
`spudCratesPerTrip = 2` buys and carries two crates per town visit, proven by the
`CarryLinks` child count because `carrying()` is already true with one box in hand.
`spudSeedsPerCrate` is **learned** from a real rise, never guessed at 50, and nil
until a pour has happened (rule 7: an unknown crate size is unknown, and the old
ceiling stands). An unpaid second crate goes back on the shelf before the fill.
The three arithmetic globals are **pure and top-level** because the loops they drive
are nested locals the harness cannot slice — so `tools/seed_refill_test.py` runs the
functions directly (600 empty at 50 a crate, 2 a trip → **6** trips; 1-trip tank
never lowers the 4; nil cap/crate → nil, not 1) and pins the wiring with 12 ties,
including that the price gate still sits **before** the trip is counted. Its
`refills >= (<digit>)` tie was itself the defect written down — the constant it
asserted is exactly what v1.133 removes — so it now reads the
`local refillsMax = spudSeedTripCeiling(...)` block, and the `extract()` helper
gained a `region()` sibling for a function nested inside another
(`seedCrateIntoSeeder` lives inside `buySeedAndFill`).

**Also settled by the owner, and deliberately NOT built:** *"in earlier explot
check diddnt you say that we could buy seedcs from anywhere? if no then drop it"*.
We never said that. The Tests tab answered **Fill from afar → refused at 963
studs** and **Spawn from afar → works from anywhere**; a purchase at a distance has
never been probed, so nothing is wired for it and no shop call is assumed to ignore
proximity. The auto-Fulfillment ask is real and approved (the design is in the
v1.121 entry below and the questions are in `SpudFulfillProbe.lua`), but it is
**blocked by rule 4**: no world dump has ever named a Company order, and a crop's
grow time — the ranking key the owner asked for (*"it chooses the easyest one by
seeding time and cost"*) — has never been proven readable anywhere. `SpudFulfillProbe.lua`
is built to answer exactly those two questions and has not been run in game yet.

Compile OK, suite **34/34** (the new harness auto-discovered), headroom **6**
(every v1.133 name is a global assignment — `spudAnchorTool`, `spudUnanchorTool`,
`spudAnchor`, `spudCratesPerTrip`, `spudSeedsPerCrate`, `spudSeedTripsNeeded`,
`spudSeedTripCeiling`, `spudSeederWantsMore`, `spudCratesInHand` — and each new
`local` is inside its own function), name audit clean **375**. **Harness green —
not reloaded in game**, and the verdicts are four lines: `anchor: <tool> welded to
the <ride>'s <part>` (or the honest "nothing welded"), grid stops that need no
re-aim, a seed pass that logs `refill N/6`-style arithmetic rather than the dead
`refill 1/3`, and a 600-slot machine that reads `50/600 → 600/600` instead of
stopping at the first crate.

**Where it stands:** `rebuild v1.133 · fluent gui`, whole suite green (34/34),
harness verified, **and v1.117 was reloaded and run in game** (the seed chain
above). **v1.129 was reloaded in game and crashed** (the ordering bug above);
**v1.130 fixed that and was run in game** — the owner's console opens
`rebuild v1.130`, gets past `— seed check —` into the field, and never prints
`⚠ farming loop error`, so the crash verdict is closed. What that same run
opened is the tow: a 286-stud arc hop arriving with `hitch gap at arrival:
277.7 studs`, every later pass refusing itself and `0 took` on a 2 398-cell
field — which is what v1.131 answers, **and v1.131 was reloaded and confirmed**:
the same emulator now reads `hitch gap at arrival: 5.0 studs` (then `1.0`) and no
pass says `not on the hitch any more`, and a 2 399-cell cultivate grid took 2 374.
What that confirmed run then exposed is the grid's own shape — a 4×4 plow leaving
`595 left` in crosses and a seed grid whose first stop sits `32 studs off stop 1`
and fires `0 took` — which is what v1.132 answers. **v1.132 and v1.133 are
harness-green only: neither has been reloaded in game.** v1.133's four verdicts are
`anchor: <tool> welded to the <ride>'s <hitch part> — the tool is part of the ride
while it is hitched` (or the honest `nothing welded, the tow stays on the game's
own constraint`, which means the weld was refused and the field pass is unchanged),
grid stops that log no `the blade is N studs off stop` line at all, a seed trip that
refills to the machine's own `MaxCapacity` (`refill 1/6`-shaped arithmetic, not the
dead `refill 1/3`), and two crates carried per town visit.
**Not yet reloaded in game** after v1.22–v1.46 — the next real
test is a live pass watching the arc hop on **every** job (no `field corner
target:`/pathfinding line may appear), the
tool-width line (`tool KADL — 3-wide (…, 40 studs)`), the Farm owner picker
showing ONLY that owner's fields (`Field · Miou2251`), the equipment owner
column (`· ZM80 = Tractor [spawned] · oksimba_1`), a
`SKIP … — <type> soil, trees are left alone` line on the wood field, the
`remote <verb>: fired N of M cell(s) from K stop(s)` line with **no** row lap
after it, the
`farm owner: teleporting to …'s plot` hop followed by
`farm: using <tool> (<owner>)`, a full harvester taking the Drop-off trip
(`fulfillment pad: Deposit_Warehouse at (…` → `fulfillment pad … parked —
pressing nothing` → `✅ sold at …` or the honest
`still full — none of the pads took the load`), the milk lines
(`… read from here - none reports dirt`, `… cleaned in X.XXs`), the field
remote lines (`✅ remote seed: N cell(s) in X.Xs — the field is done without
driving`, or the honest `remote seed: the game ignored N call(s) … — driving
for this session`), and the equipment lines (`✅ mounted … (FNCEnterEquipment)`,
`equipment: Store KADL via store (no UI)`, `✅ carrying the … (EVTRequestToCarry)`,
`sell pad …: EVTSellAtStore(ride, pad)`,
`✅ <seed> bought via FNCRequestStorePurchase`) or their honest fallback lines
(`equipment: store didn't Store the KADL — using the Equipment Manager`,
`seed shop: FNCRequestStorePurchase didn't buy anything — clicking the menu`).
On top of all that, **Early harvest is now the default** (v1.125) and its live
verdict is one of two lines: a field that is planted **and** cut inside the same
cycle (`🌱 early cut: N cell(s) are cuttable now — restarting the loop instead of
waiting`, then a harvest pass that takes them), or the honest
`early cut: N cell(s) still read cuttable after 2 restart(s) that took nothing`,
which would mean the single tile **Grow now** cut does not generalize to a whole
field. **📍 Get coords** is the other new line: press it standing on a pad and
paste the `(x, y, z)` here, and a spot the script cannot stream becomes one it
can drive to — the owner did exactly that (v1.126), so both drop-off picks now
have a measured park address and the Fulfillment deck is at the standing height
rather than the part centre. **v1.127's** milk verdict is the far-farm pass: after
`teleported to its plot` the next line should be
`the barn streamed in N s after the hop - K stall(s)` and then real clean / herd /
milk work — not `no stall found … in 17 ms` with 32 cows standing. **v1.128's**
unload verdict is the same trip read against the owner's measurement: a
`fulfillment: Ugc.CompanyArea.WarehouseArea is 142 studs from the measured pad …`
refusal then `parking on the measured spot (-353, 141, -92)`, or a pad path that
really is at that deck — and either way a tank that **drops**, because `⚠ still
full` at a landmark 142 studs away is exactly what the owner reported. **v1.129's**
three verdicts are one run each: a harvester found by the **word the game wrote**
(`isHarvester` on `JDS790 [Harvester]`, and a `no … found` line that names the
`Name=Type` list it did see), a grid whose `took` no longer collapses because the
pass waited for the tow (`remote <verb>: the <tool> is still moving N studs
behind the ride …`, or no such line at all), and — with a wide implement hitched
— a `3x3` that became `NxN per stop`. If a tool is ever logged
`not on the hitch any more`, that pass stopped on purpose: the implement had been
flung off, and dragging it the rest of the way is what the owner reported.
**v1.132's and v1.133's verdicts are both still open — neither was reloaded.**
v1.132: a seed grid whose `took` climbs towards `fired` (not `0 took` next to
`firing anyway`) and a plow field with no cross of leftovers. v1.133 has **two
things the harness genuinely cannot know**, so say which of these the console shows:
**(a)** whether the live server accepts a **client-created `WeldConstraint`** on a
part it may not hand over — `anchor: … welded to …` and then grid stops that need no
re-aim, versus `the tow stays on the game's own constraint` (refused: the field pass
is then exactly v1.132's behaviour, which is the point of making every refusal
cost only the anchor); and **(b)** whether a **second** `FNCRequestStorePurchase`
while the first crate is still in hand buys the second box or answers the till's
"place items on the counter" toast — `✅ <seed> bought …` twice in one town visit
versus the second crate left on the shelf. **(c)** A 600-slot seeder should read a
`refill N/M` with `M > 3` and end at `600/600`; if it stops at the first crate the
`MaxCapacity` read is the thing to name.

---

## 6. Open questions / known limits

1. **In-game confirmation is pending** for v1.22 (2 s clean wait), v1.23
   (meter trigger + no-cow-in-dirt gate), v1.24 (unload/reload guard, drop
   scoping, clean backoff), v1.25 (new path engine: watch the first `path:`
   lines and whether the tractor stops hugging gear), v1.26 (wide tools:
   check the `tool … — N-wide` line matches the real tool, and that a picked
   foreign farm actually accepts the drive-overs), v1.27 (owner-first
   equipment: check the owner column in the equipment log, and that a picked
   farm's tractor/tool is the one mounted), v1.28 (tree soil: the wood field
   must log `SKIP … — <type> soil, trees are left alone`, and a normal pass must
   still harvest the crop field), v1.29 (one owner at a time: with a farm
   picked, the tour must list ONLY that owner's fields and never mine), v1.30
   (real-W row driving: watch for a `tractor: the W row drive handed back`
   fallback line and whether rows actually re-center after a drift), v1.31
   (a full harvester must stop the run and NOT drive to a sell pad), v1.32
   (a picked farm: `farm owner: teleporting to …'s plot` must appear once, the
   fields must stream in, and the mounted tool must be that owner's) and v1.33
   (the Drop-off pick: a full tank must hop to the chosen pad and the tank must
   drop; if it does not, the log names the pad and whether a menu opened) and
   v1.34 (a picked farm: no `Equipment Manager` line may appear for a stored or
   far machine — the run must name it and stop/skip instead), v1.35 (rows: no
   side-to-side — the tractor may snap once onto the row and must then run
   straight with the game's own steering holding it), v1.36 (the 15°/6-stud
   band: a row should now tolerate a visible drift without touching A/D) and
   v1.37 (a swinging row: watch for `steering is swinging — easing the row to
   N% throttle` and whether the wobble settles at the lower duty) and v1.38
   (field remotes: cultivate is the only recorded shape — a seed/plow/harvest
   job must log `✅ remote X: N cell(s) in X.Xs` and leave the field finished,
   or the honest `remote X: the game ignored N call(s) … — driving for this
   session`; the seeder fill must log `seeder fill: FNCFillSeeder(seeder)` and
   the count must rise, with V only on a refusal) and v1.39 (equipment remotes:
   watch `✅ mounted … (FNCEnterEquipment)`, `equipment: Store/Spawn … via …
   (no UI)`, `✅ carrying … (EVTRequestToCarry)`; a refused call must log its
   fallback and the old F/X/E/UI path must still complete the step) and v1.40
   (sell/buy: a **Sell** drop-off must log `sell pad …: EVTSellAtStore(ride,
   pad)` and the tank must drop; a seed buy must log `✅ <seed> bought via
   FNCRequestStorePurchase` with the balance falling — otherwise the Q/E and
   menu-click fallbacks must finish the step) and v1.41 (Fulfillment: the trip
   must log `fulfillment pad … parked — this pad unloads by itself, pressing
   nothing`, press **no** key, and the tank must still drop; if it does not, the
   log must say `the pad didn't take it while parked`) and v1.42 (the arc hop:
   the return trip from a lower pad must climb and **come down** onto the field
   — watch `arc hop: N studs, lifting N studs (Y 140 → 172)` — not fly under
   the ground; a trip to a lower pad must still land at the takeoff height) and
   v1.43 (Tests → **Batch field remote**: with the toggle on, a field job must
   log `batch test: N cell id(s) in ONE call` and then either
   `✅ batch test: … in ONE call` (one call finished the field) or
   `batch test: the server ignored the id list … — one call per cell` with the
   normal per-cell pass still finishing it) and v1.44 (Tests → bug finder: press
   each button once and read its `test: … TAKEN/IGNORED` line — the answer is
   the cell's own stage, so quote the before → after in the report) and v1.45
   (Tests → **Run all** then **Copy report**: the copy must carry place/build/
   player and every line; the sell test needs a FULL harvester, the fill test a
   spawned KADL, the spawn test a stored machine of mine) and v1.46 (the sell
   test must name the pad it picked or say no pad is streamed; the fill test
   must either read the seed count or dump the seeder's fields so the next run
   can name it) and v1.47 (a full harvester with no pad streamed must log
   `no Sell pad is streamed from here — arc hop to the store`, then sell at the
   board; the fill test must read `seeds 0/50` and say whether the fill took)
   and v1.48 (every sell spot the trip receives must carry a `part`; the test
   must fire `EVTSellAtStore` instead of saying "no part to fire at") and v1.49
   (a full tank with any sell pad streamed must log `sell: EVTSellAtStore fired
   from where the harvester stands` and then `✅ sold in place … (no pad trip)`
   with the ride never moving; a refusal must still take the pad trip) and v1.50
   (a seed pass must log the seeder's budget / `seeder EMPTY … refill 1/3`, the
   shop trip must refill, and the same pass must carry on until the field is
   seeded; a refill that puts nothing in must stop it) and v1.51 (harvest: a
   full tank must log `the tank is full … the sell trip runs before the rest`
   and fire no harvest call; any refused tail must log
   `one retry of just those` and then `the retry finished the field`) and v1.52
   (a field after the call pass must log `remote <job>: hopped the ride over N
   cell(s) — N took`; if the count reaches 0 the field ends with **no row
   driven**, otherwise the drive starts from the last hopped cell).
   and v1.53 (a field job must log `remote <job>: swept N cell(s) in X.Xs at
   45 studs/s, range 14 — N took, N left`; a taken sweep finishes the field
   with **no row driven**, and any leftover must still be hopped and then
   driven), v1.54 (the sweep must cross a field in ~5–7 s and catch cells
   well off the row; anything the server refuses must still be hopped) and
   v1.55 (a plow field must finish on the sweep: watch that its leftovers are
   not a row of missed cells, and that the log's `took` is close to `swept`)
   and v1.61–v1.65 (the packet door: live packets are a 4-byte header + 6-byte
   records and the stage is one byte (`04` Cultivated, `08` Plowed, `0c` Seeded);
   a real packet with that byte patched and re-sent was **IGNORED** — no packet
   back, no cell moved — so the bulk door is shut and the blade is the only
   input) and v1.59 (Tests → **Remote list**: paste it. A remote that looks
   like a field/bulk door names the next experiment. The wrong-tool question is
   answered — the tool identity IS checked, so each verb keeps its own
   implement) and v1.76 (a field job must log `remote <verb>: fired N of M
   cell(s) from K stop(s), 9 per stop — K took, L left`
   right after the call pass — N should equal the field's cells on a healthy
   run and the take should equal N, so the field ends with **no sweep line at
   all**; a `swept …` line means stops were refused, and a grid that ends
   after one stop means the server took nothing from a parked blade) and v1.77
   (a tour must log `arc hop to the <field> corner` for **every** job and no
   `path:` / `field corner target:` line may appear anywhere — the planner was
   deleted in v1.81, so any route line means an old build. The
   Tool apart question is answered **IGNORED** and its probe retired: a plow off
   the tractor with its blade 0.0 studs from an Empty cell still took nothing,
   so the implement must be on a ride — never fire a field call with the tool
   loose). Watch that a seed pass does **not** stop early with
   `seeder empty` before the field is seeded (that would mean the wide seed
   calls are being refused and eating the budget) and v1.57/v1.58 (Tests → **Force a tile**: the live FieldHelper dump has
   **no setter**, and the client cell table is **writable** (`UpdateCell` keeps
   a forged stage), so the remaining question is whether the server uses it —
   the verdict is `reads Seeded` = TAKEN (a real abuse) or `reads Cultivated`
   = IGNORED (client-only lie). Paste that one line).
   Harness green ≠ game green.
2. **The 24 % baseline may differ per build.** If stalls sit higher, the first
   pass logs `reads X% but the game offers no Clean there - the dirty line moves
   to X%` and then stops hopping. That is the designed self-correction, not a
   bug — report the number if you see it.
3. **The store deposit and feed top-up paths are untested** (they need a fake
   carrier + dispenser).
4. **"Modified client" is executor detection**, not movement or timing. No edit
   to this script changes it; the README's Stealth section says so explicitly
   and should keep saying so. The probes are louder than the farm script (they
   hook `__namecall`); don't run them on an account you care about.
5. **Codes are disabled** in-game (mid-2026); any "working codes" list is fake.
6. **The early cut is proven on ONE cell, not on a field.** **Grow now** took a
   `Seeded` tile and the tank paid (`0 → 1`), so `spudEarlyCut` (v1.125) plants
   and cuts on the same cycle — but one planted tile cut from inside the seat is
   not a 50-cell field swept by the blocks. The first live run answers it: either
   `🌱 early cut: N cell(s) are cuttable now — restarting the loop` followed by a
   harvest pass that takes them, or the bounded
   `still read cuttable after 2 restart(s) that took nothing`, which means the
   server pays only for the cell it was shown, not for the field.

---

## 7. Glossary

- **stall** — `<barn>.AnimalContainer.Spots.<n>`, one per cow slot; 12 per barn.
- **dirt line** — `milkDirtLine`, the `FilthPercentage` threshold above which a
  stall counts as dirty even with no level drawn (24 by default).
- **parked** — a cow already inside a stall (`Occupant` set), as opposed to
  **ready** in the field.
- **batch** — the typed herd size (1–12) for one pass.
- **lock** — the farm's chosen barn, held as name + position for the session.
- **probe** — a separate read-only script whose only job is to report live game
  structure so names and thresholds stop being guesses.
