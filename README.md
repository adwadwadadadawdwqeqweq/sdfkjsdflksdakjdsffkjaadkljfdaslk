# 🥔 SPUD FARM — Farming and Friends scripts

> **Status: active build (see `VERSION` at the top of `SpudFarm_Full.lua`).**
> Farm, Presets, Milk, Player, Stealth and the Doctor report are implemented;
> this README describes the current behaviour. Harness-green is not
> in-game-green — the pending in-game checks are tracked in [AGENTS.md](AGENTS.md).

**Working on this repo, or handing it to an AI agent?** [AGENTS.md](AGENTS.md) is
the single-file brief: the owner's rules, the game facts we actually verified,
the session history, and the exact compile/test loop. Read it before editing.

## UI RULES (non-negotiable, per project owner)
1. **No text under anything.** Elements get a title and nothing else: no window
   SubTitle, no Description lines under buttons/toggles, no helper text, no
   placeholder sub-text. Titles only. This applies to every future feature.
2. The window must stay comfortably large on mobile/emulator screens (use
   `Resize = true` and a generous base Size).

## Quick start (using the script)
1. Copy the raw script link:
   `https://raw.githubusercontent.com/simba13231/spud-farm/main/SpudFarm_Full.lua`
2. Paste that link into your executor's script box (or open the file here, click
   **Raw**, copy everything) and execute.
3. In game: **RIGHT SHIFT** = menu · **📡** = webhook panel · **🥔** = hide/show all.

Free VIP servers (this game has them) + short sessions = far lower report risk.
Read the Stealth section below before farming in public servers.

## Files

### `SpudFarm_Full.lua` — THE MAIN SCRIPT (use this one)
Everything merged into one paste-and-run file:
- **Farm tab** — Farming auto-cycle (PLOW → CULTIVATE → PLANT → GROW → HARVEST → SELL).
  **Harvest outranks every other stage**: if even **one** cell is standing at the
  fully-grown stage the run harvests first and keeps going until nothing is
  standing — the old 4-round cap is gone. A run that cannot enter the harvester
  stops there instead of plowing around the crop.
  **crop selector** (Wheat, Corn, Rice, Oat, Sugar Cane, Soybeans, Tomatoes, Cabbage,
  Carrots, Potatoes, Cocoa, **Grape**, Custom) with auto set grow-time from wiki data,
  a **live crop info line** (grow time · seed cost/box · avg $/hr · equipment
  requirements · price-rotation tip), auto seed-loading during PLANT, Auto-Sell,
  Grow time slider, Skip Stage / Reset buttons, live status line,
  **live sell-price readout** (reads the in-game SellValueBoards every 3s)
- **No driving, and no pathfinding** — a field pass is arc hops and
  teleports: the ride arcs to the field corner, the calls fire from a grid of
  parked blades, then a teleport onto each remaining cell. Nothing touches a
  movement key: the old row driver is unreferenced and no row is ever driven,
  so a pass that cannot finish says
  `<verb>: every call on <field> was refused — N cell(s) left, no rows driven`
  instead of driving a lap. The arc lands on the field's own corner, the
  pathfinder is gone and so is the tween sweep, so **every move in a field
  pass is a teleport** — nothing slides the ride along the ground.
- **Field work on the game's own remotes** — before a pass drives a single row
  it fires the call the game itself fires on drive-over, once per cell still at
  the job's stage: `EVTPlowFieldCell` / `EVTCultivateFieldCell`
  (`FireServer(field, {cellId}, {raycastAttachment})`) and
  `FNCSeedFieldCell` / `FNCHarvestFieldCell` (`InvokeServer`, same arguments).
  The ids are the `FieldHelper.GetCells` keys the script already reads, and the
  attachment is the tool's own — the `RaycastPart` when it has one, otherwise a
  harvest-sounding point (`HarvestHead`, `Cutter`, `Blade`, `Gather`…), then a
  `Seed`/`Detect` one, and only then any attachment on the machine. The pick is
  logged once (`attachment: <tool> → <part>.<attachment> (raycast|harvest|seed|any)`),
  and a non-raycast pick also logs every point and part name on the machine —
  the live SRC6 sent `EquipmentRoot.L0StrutAttachment` (a wheel strut) and the
  server refused all 46 calls, so the point has to be the harvesting one. The
  stage re-read is the proof: a full batch logs
  `✅ remote seed: 50 cell(s) in 2.4s — the field is done without driving`, a
  partial batch drives the rest, and a batch the server ignores logs it and
  puts that job back on driving for the session. The seeder fill uses the
  captured `FNCFillSeeder(seeder)` first and presses V only when the seed count
  does not rise. Every job is capped by the machine's own load and hands the
  field back when that runs out instead of driving: the seeder fires at most
  its `Capacity` (empty = no call), the harvester at most its free tank space
  (`MaxCapacity − Capacity`, full = no call), and the planting stage buys and
  fills (up to 3 refills) or the harvest loop sells and comes back. A refused
  tail gets one retry. After the call pass there is a
  **3×3 block grid**: the remaining cells are grouped into rows, three rows at
  a time are cut into three-column blocks, and each block gets one stop at its
  own centre — the ride parks with the **blade** on it (the tool trails behind
  the tractor, so the ride goes to `stop − blade offset`), fires that block's
  **nine cells** 40 ms apart, then walks **forward** to the next block (each
  band alternates direction). Every cell belongs to exactly one block, so
  nothing is skipped and nothing is fired twice; a 50-cell field is **8
  teleports** of nine calls each. The band it relies on was measured live: a
  take from **20 studs to the side** at +8 (30 refused) and from **+80 straight
  up**. The stage re-read after the **first** stop decides — if the
  server takes nothing from a parked blade the grid fires **that same stop
  once more**; between stops it **waits for the blade**, not a fixed beat — a
  hitched tool trails the tractor for a moment after a jump, so the call only
  fires once the blade is actually on the block (re-parking once if it is
  still swinging) — the first call after a long ride is routinely refused while the
  server still holds the old pose — and only then ends
  (`remote seed: fired 46 of 46 cell(s) from 8 stop(s) across the field
  (reach 20) — 46 took, 0 left`). Whatever it misses is then **hopped**: one
  teleport per remaining cell with the blade on it. Anything still standing
  after the hop is **retried**: grid → hop again, round after round, until the
  field reports none of that stage left (Stop ends it). Two rounds that take
  nothing end the pass with an honest line —
  `<verb>: N cell(s) never took a call even with the blade on them — leaving
  them for the next pass`. There is **no tween sweep**: the smooth serpentine
  that slid the ride across the field is gone, so a field pass is teleports
  only. The machine's own budget is still the cap and counts **cells, not
  calls** — a cell a stop fires once is one seed whatever else reaches it.
- **Tests tab** — experiments, none of them a dependency of a
  normal pass. **Batch field remote** tries the abuse the captured shape allows:
  that call already carries a *list* of ids (`{cellId}`), so with the toggle on
  a field job fires **one call with every remaining id** — the live answer is
  that the server takes only the ids under the blade (`batch test: N of M
  cell(s) took the id list`), so the normal one-call-per-cell pass finishes it.
  **On by default** (since v1.88): it costs one ignored call and its 1.2 s
  stage read per field, and it can never switch a job off.
  **Remote list** prints every `RemoteEvent`/`RemoteFunction` the client can
  see — a bulk field door we never fired would only show up there.
  **Field remotes** fires
  `FNCSprayFieldCell(field, {id}, {att})` and reports `IsWatered` /
  `PlantGrowth` / `Stage`, then invokes `FNCEditField()` and
  `FNCConvertRundownField()` with **no arguments** just to read the shape they
  demand (an error names it; nothing that could rebuild the field is handed to
  them).
  **Shop counter** repeats the seed-buy trip: it prints FarmCo's own parts and
  every `CounterAttachments` spot with its world position, carries the crate
  onto that attachment, drops it, and reads the game's context actions and
  prompt billboards at each step, then presses F and reports which layer it
  raised, the toast text and the visible buttons. It exists because the till
  answers *"You must place items on the counter to buy them"* and the buy has
  never landed.
  Every line is logged as `test:` and **Copy report** puts place id, build, player,
  the whole test run **and the last 60 farm-log lines** on the clipboard — so one
  press answers a farm question too. **Copy console** is the same clipboard
  without the test run: the last 150 farm-log lines, for a run that is stalling
  and needs no experiment. Nothing touches animals or another
  player's plot, and the tests refuse to run while a farm pass is going.
  (The settled experiments — seat/stage/attachment checks, the burst, sell,
  carry, spawn, fill, the FieldHelper dump, force-a-tile, the field-packet
  watch/forge, the wrong-tool probe, the lift test and **tool apart** — were
  removed once they had their answer; their results are in the console history. The lift band is
  the one that matters to play: a field call was taken with the blade **20
  studs to the side at +8** (30 refused) and from **+80 straight up** on three
  separate runs, and that is what the stop-and-burst grid's 20-stud reach is
  built on. The packet is
  server→client only: patching a real packet's stage byte sent nothing back and
  moved no cell. The wrong tool was answered live: cultivate fired from a
  plow's own attachment at a Plowed cell the blade was sitting over stayed
  Plowed, so the server checks *which implement* the attachment belongs to —
  one sweep cannot run every stage. Tool apart closed the last one: a plow
  taken **off** the tractor, its blade placed **0.0 studs** from an Empty cell,
  was still `IGNORED`, so the implement has to be on a ride with the driver
  seated — the tractor must be there, it just never has to *drive*.)
- **Equipment on the game's own remotes** — the same capture pass recorded the
  equipment calls, so the script fires them instead of pressing keys or driving
  the Equipment Manager UI: `FNCEnterEquipment(vehicle, seat)` to mount,
  `FNCAttemptHitch(hitchable, socket)` / `FNCUnhitch(hitchable)` for tools,
  `FNCSpawnEquipment(model)` / `FNCStoreEquipment(model)` for storage,
  `EVTRequestToCarry(draggable)` / `EVTRequestToDrop()` for carried items,
  `EVTSellAtStore(harvester, pad)` to unload the tank (fired in place, both
  Drop-off picks) and
  `FNCRequestStorePurchase({crate})` for buying a seed crate. Each is used only
  where the game offers the action, and the effect has to prove it: the seat
  actually holding the character, the existing hitch/unhitch tug, the
  `InStorage` flag (or a >100-stud move for a rebuilt spawn), hands filling or
  emptying, the tank dropping (sell) and the balance or crate count moving
  (buy). A call that does not land falls back to the old F/X/E/Q/UI path in the
  same step, and three misses switch that one call off for the session. **A seed
  you already have is never bought again**: a crate an interrupted trip left
  carried is read from its own `Configurations.CurrentHolder`, and a crate you
  own (its `Configurations.Owner` is you) is read anywhere on the plot, nearest
  first — either one skips the shop entirely and is poured into the seeder. What
  decides "have it" is **how many seeds the crate holds**, read from its own
  `Configurations.Capacity` (the same field the seeder uses): a half crate fills
  the seeder half-way and the pass comes back for more, and a crate that reads
  empty is skipped as the empty box it is — a crate that cannot be read at all is
  still used. A run is allowed **four** shop trips rather than one, so the seed
  pass's own `refill 1/3` promise is reachable when the field is bigger than the
  seeder. After a
  seed is bought the **shop menu is closed** on the way out: the open menu is
  read from `GuiViews.Menus`, its own close control is clicked inside it, the
  result is re-read, and F is only the fallback — so the UI does not stay up
  over the field. The
  **Fulfillment** pad needs no key: parked on it, the pad unloads the harvester
  by itself, so that trip only waits for the tank (its own order call was never
  captured, and it is not needed).
- **Drop-off pick** — Farm tab → **Drop-off**: **Fulfillment** (default) or
  **Sell**. When the harvester's tank fills it first fires the captured
  `EVTSellAtStore` **from wherever it stands**, at any distance, and watches
  the tank for 1.5 s: a tank that drops logs
  `✅ sold in place at N studs … (no pad trip)` and the harvester never moves;
  a call that moves nothing logs the distance and takes one arc hop, where the
  call is fired again at the pad (or Fulfillment parks and lets the pad drain
  it):
  Fulfillment is the warehouse pad
  (`Stores.DropOffs.Deposit_Warehouse`, parked, pressing nothing while the pad
  drains it) and Sell is the old crop sell board (call, then Q/E). The
  tank dropping is the only proof a pad took the load — the console prints
  `fulfillment pad: Deposit_Warehouse at (…)`, `drop-off 1/1: …`, then
  `✅ sold at …` or an honest `still full — none of the pads took the load`,
  after which the trip backs off 60 s and the harvest carries on. Every hop
  lands at the **higher** of the two heights and arcs above it, so the trip
  back from a lower pad drops down onto the field instead of flying under it.
  The store area only streams when you are near it, so a full tank out at the
  farm that finds **no pad at all** first hops the harvester to the store's own
  waypoint, waits for the pads to stream, and looks again (`no Sell pad is
  streamed from here — arc hop to the store, then looking again`); the trip
  back still returns to the field.
  A tank with **less free space than there are cells still standing** counts
  as full (`spudHarvestFull`): 49/50 against 46 standing crops used to fire the
  one slot's call — refused, because the field corner is out of reach — and
  sell anyway, round after round. The pass now fires **no** call in that case
  and unloads first, so the harvester comes back with a whole tank
  (`remote harvest: 1 free slot(s) cannot cover 46 standing cell(s) — selling
  first, then coming back`).
- **Trees are left alone** — the harvester never drives a field whose type or
  model name says wood / tree / log / forest / timber / lumber / sawmill / stump,
  so standing trees are not cut. A field whose cell read succeeds but returns
  **0 cells** is also skipped (empty is not the same as unreadable). Every pass
  prints the real field type, so a differently named soil shows up in the log.
- **No pathfinding** — the A* engine (`SpudPath`: heap Lazy Theta*, clearance
  field, line-of-sight, Bézier smoothing, obstacle caches) was **removed**: the
  only thing left that needed a route was the fallback for a field with no
  readable frame, and that field cannot be swept by the remotes either. Trips
  between fields are **arc hops**, and a field is finished by **teleports** —
  the call pass, the stop-and-burst grid, a teleport onto each remaining cell,
  then **grid → hop again, round after round**, until the field reports none of
  that stage left (Stop ends it). **No row is ever driven and nothing is
  tweened**: a cell the grid and the hop both fail is left for the next round
  or pass, named in the log. A pass whose every
  call was refused says
  `<verb>: every call on <field> was refused — N cell(s) left, no rows driven`.
  Harvesting outranks the other stages: one standing crop sends the harvester
  first, and the harvest loop retries until nothing is standing.
- **Working width** — the sweep measures the tool's ground width across the
  row axis (every BasePart's oriented box, unioned) and plans rows at
  `width / 10` **tiles** instead of the old fixed one tile, so a **3-wide**
  plow/cultivator/seeder/combine covers three rows per pass. The headland band
  and the missed-cell touch-up adapt too (missed cubes are grouped by row, not
  visited one by one). A width declared in an attribute/Configurations is
  logged next to the measurement but only used when no part is readable.
  Console: `plow: tool KQF3000 — 3-wide (model, 42 part(s), declared 3);
  rows every 30, headland band 30`.
- **Someone else's farm** — Farm tab → **Farm owner** (mine + every owner seen
  in streamed fields; **Refresh farm list** rescans after you walk over). That
  owner's fields are worked **alone** — your own fields are left out while a
  pick is active, so the machinery and the soil always belong together. The
  tractor/tool follows the same picker: **that farm's machines first, then
  yours, then one with no readable owner** — another player's is never taken,
  and **nothing is ever spawned or respawned on that plot**: a stored or
  far-away machine is named in the console (and the pass skips) instead of
  driving the Equipment Manager for someone else's equipment.
  The tour log names each field's owner, so a wrong pick is visible. If the
  game refuses an action, the sweep says so
  (`field belongs to <name> — check worker permissions`).
- **Go to the farm** — with a Farm owner picked, the run **teleports to that
  owner's plot first** (only when it is more than 60 studs away; the character
  is stood up first, because a teleport while seated does not travel). It then
  waits half a second for the fields and machines to stream in, finds **that
  farm's** tractor/tool, and logs
  `farm: using <tool> (<owner>) N studs away` before driving. If the plot is
  not streamed the run says so and works from where it stands instead of
  guessing a position.
- **Presets tab** — **Barn Care** (walks every stall near your plot and cleans it —
  uses the game's own CleanAnimalContainer = V context), Chocolate Milk
  (clean stalls → milk cows → deposit → cocoa → levers → collect → sell),
  Cake & Eggs (**7 steps**: eggs → milk → wheat/milk/egg deposits → 4 levers →
  **batter → oven bake** → collect + sell), Wool Run (shear → spindel bundles,
  5 wool each → sell); LOOP toggle, STOP button
- **Milk tab** — **three Farm pickers worked in a rotation** (farm 1 → 2 → 3;
  a slot left on "(none)" is skipped, farm 3 wraps back to farm 1, and a farm
  takes over as soon as the current one has nothing left to milk). A farm that
  is **under the typed herd amount** hands the next pass to the **fullest other
  farm** — a comparison, not a demand for a whole batch. Demanding a full batch
  was the bug behind "it does not switch the plot/players field when it get
  under the heard amount": a real pair of alts almost never has twelve cows at
  300% at the same moment, so the hand-over never fired and a six-cow farm kept
  the pass while a nine-cow farm waited. Cleaning still happens first — a dirty
  stall is never skipped — and a farm with cows **already parked in its
  stalls** is never skipped either, because there is milk to take. What is
  compared is every cow **waiting** on that farm: ready in the field **plus**
  the ones already standing in its barn — a farm whose cows are all in its
  stalls reads as zero *ready*, and leaving it out was the second miss ("it's
  missing sometimes bro"), so its milk sat there while the shorter farm got the
  pass. When **no** other farm has more, the current one is worked exactly as
  before, so a small farm cannot stall the loop, and an equal count never swaps
  (that would ping-pong two equal alts on every pass). The check reads the
  other farms without moving the character (see `milkFarmReadyCount`) and never
  treats a farm it cannot read — streamed out, not built yet — as empty; the
  stay line names the fullest other farm (or the one that could not be read),
  and the status line says `working farm 2/3: <account>` so the active farm is
  visible without opening the dropdowns. The whole rule lives in one function
  ([tools/farm_switch_test.py](tools/farm_switch_test.py)
  exercises the real one: 18 checks, plus 30 more in
  [tools/farm_batch_test.py](tools/farm_batch_test.py)). The **herd
  batch size typed in a box
  (1–12)**, **Store milk in** (live list of the picked account's trailers/silos;
  only free-range jugs are loaded there), **Deliver all milk** switch, **Refill
  feed dispenser** switch (tops the plot's FeedDispenser up from the
  AnimalFoodBoxes), live status paragraph, **milk loop** toggle. The loop cleans
  dirty stalls first, then **milks any cow already waiting in a stall**, herds
  the batch in picking the **cows nearest the barn first** (a far cow can't hold
  the round up), **milks each cow the moment it lands in its stall** and waits
  for the next one — it does not sit until the whole herd is parked — and a
  finished round goes **straight into the next one** (no idle gap); only a pass
  with nothing to do rests for a minute. If a plot has **more than one barn
  building**, the first cycle locks to one of them (the one nearest the plot
  centre)  for the rest of the session, so stalls, the parked count, the batch
  and the lasso press are never split across two barns. That lock is held as
  **name + where the building stands**, not as the model itself: a barn that
  streams out and comes back is a *new* instance, and matching it by identity
  used to leave the herd step with no barn at all — it then fell back to the
  first building named `AutoWoodenBarn` in the map, which is another player's,
  so the cows were herded and sent to the wrong barn (or nowhere). The bug, its
  reproduction and the fix are in
  [tools/herd_send_test.py](tools/herd_send_test.py)
- **Run controls (Settings tab)** — **▶ Start everything** / **■ Stop everything** flip the three
  loops in a safe order (farm → milk → delivery; delivery turns itself back off
  when no trailer/silo is picked), and **verbose logs** puts the per-cow
  prompt/button dump back on for every cow (off, it runs once per session — the
  walk covers the whole PlayerGui and was a measurable FPS cost). Every
  **Reload** keeps the three farm picks, the typed batch size, the seed choice
  and the movement mode, and — more importantly — **stops every loop the old
  build started**. Before that, Unload
  only hid the window: the milk loop, delivery loop, webhook pump, 15-min field
  scan and FPS meter kept running, and each reload added another copy of each.
  The guard is a generation counter each build captures
  ([tools/lifecycle_test.py](tools/lifecycle_test.py) runs the real one and
  proves an old loop stops, including after Unload-then-Reload).
- **Per-pass timing** — the status paragraph ends with
  `pass: scan 0 ms · clean 1.9s · herd 3.1s · milk 4.0s · store 0.2s · 7 tp`, and
  the Doctor shows the same line plus the live dirt line, batch, delivery state,
  session and teleport count. "Slow or stuck?" is a number now.
- **A stall that will not clean is backed off** — six seconds, doubling to a
  minute, cleared by any success. It used to be re-teleported to every 6 s
  forever ([tools/clean_visit_test.py](tools/clean_visit_test.py), "backed off
  on the next pass").
- **Reload is validated** — the fetched text must carry the build marker before
  `loadstring`, so a GitHub error page can never be executed. The Fluent library
  URL is built from `FLUENT_TAG` (top of the file) so it can be pinned to a
  release tag instead of following `latest`.
- **Player tab** — walkspeed, jump power, infinite jump, noclip, anti-AFK, FPS boost
- **Teleport tab** — Ctrl+Click teleport + FarmCo / AnimalCo / TractorCo / LumberCo /
  Bulk Store / Warehouse / **My Farm** (resolves your plot by its "Your Farm"
  billboard) / Spawn buttons (2026 central-town map, part names from in-game dump)
- **Stealth tab** — detection-risk reduction (see below)
- **Settings tab** — Movement mode (**VFly** = fast BodyVelocity fly + snap teleport,
  **Tween** = slow safe glide) + vfly speed slider; fix in-game names (cow, milker, shop,
  factory, field tile, sell key, tractor, **planter, harvester, batter drop, oven**)
  without touching code; unload button
- **Webhook window** (📡 button in the title bar) — its own UI with URL box, enable
  toggle, test button, **live feed** (every farm round, preset cycle and stealth
  break appears instantly, even with logging off) and a queue status line.
  Sends to your own Discord webhook, rate-limited (≈1 msg / 6.5s) with coin-gain notes.
  The URL must be a real `discord.com` / `discordapp.com` `/api/webhooks/` URL —
  "contains the word discord" is rejected, because this box mirrors the whole
  console (account and plot names included) into whatever it is given
- **🥔 potato button** (left edge of the screen, its own overlay) — press it to hide
  **every** window at once (main + webhook), press again to bring them all back. It
  stays visible while everything else is hidden, and you can drag it anywhere
- Menu keybind: **RIGHT SHIFT** (same as the potato: toggles all windows)

Wiki-accurate details baked in (researched 2026): FarmCo selling = drive onto the
elevated platform → **Q** (opens sell menu) → **E** (confirms); **prices rotate every
~5 min** — red/green/rainbow boards, rainbow = peak (wait for it on big potato/tomato
hauls); real equipment names (ZM80 tractor, SRC6 combine, KGF 3000 planter, AED300
lvl-2 seeder, Oxbo3220 cocoa harvester, TK500/chainsaw forestry); factory levers pulled
one-by-one in the exact wiki sequences.

Recipes: **Chocolate Milk** = 25 cocoa + 10 regular milk (or 5 free-range, 2:1;
spoiled milk rejected) per jug, ~20–23k coins, max 60/run; **Cake** = 100 wheat + 1 egg
box (12 eggs) + 1 milk → batter → oven; **Wool** = 5 raw wool per spindel bundle.
Cow happiness decides milk quality (<60% spoiled, 60–89% regular, 90%+ free-range).
The milk store step only loads **free-range** jugs — regular and spoiled are left
on the ground for selling (`store: leaving N non-free-range jug(s)`).

### Speed — what was actually slow
Measured, not guessed. The deposit pass now prints its own time:
`store: 20 jug(s) into LH150 in 5.8s (100/180)`.

- **`task.wait(t)` is frame-quantised.** It sleeps *at least* `t` and then
  resumes on the next Heartbeat, so at 60 FPS `task.wait(0.2)` costs 200–216 ms
  and a loop of them is pure stand-still. The store step now polls **every
  frame** (same deadline in seconds, so a high-FPS client does not give up
  early) against a read the game already answers: the jug leaving the world,
  the hand filling, the tank label changing.
- **`FireServer` does not wait for a reply.** Only the *result* has to come back,
  so the fast path is one network round trip per action, not a fixed sleep.
- **A CFrame teleport needs ~50 ms to reach the server** (physics replication is
  ~20 Hz), so the step waits three frames after a teleport instead of 150–250 ms.
- **GUI-shaped reads stay at 50 ms**, not per frame: `milkMenuFor`, `milkStallGui`
  and `milkDrops` walk the GUI/world, so polling them per frame would cost more
  CPU than it saves.

Measured with [tools/store_timing.py](tools/store_timing.py) (virtual clock, real
extracted functions, `task.wait` modelled as frame-quantised): a 10-jug pass at
120 ms latency went **5.42 s → 2.75 s** (0.54 → 0.27 s per jug), at 40 ms it went
**4.08 s → 1.50 s**. Arm-the-herd (`milkHerdArm`) went **1.6 s → ~0.05 s** per cow
when the menu is up, and the old 3.6 s "no menu" timeout is 3.0 s
([tools/herd_arm_test.py](tools/herd_arm_test.py)). The rest of the time is the
cows walking in and the server's own answer — no script can remove those.

**The cow checks, cached.** A scan (`milkCows`) reads three things off every
animal in the world, and the Owner read walks up to eight parents per animal
looking for a `Configurations.Owner` when the animal has none - which is most of
them. The **instances** are now remembered per model in a weak-keyed table, so a
repeat read is one property access. Measured on a fake 120-animal world (40 tagged,
80 strays) with the real functions ([tools/cow_scan_bench.py](tools/cow_scan_bench.py)):
**1400 → 560 instance calls per scan** (11.7 → 4.7 per cow) once warm; the cold
pass is unchanged, and an animal is never cached as untagged, so a cow that gets
its owner a moment later is still picked up. The **arrival wait** no longer scans
at all while nothing is happening: it watches the plot's own stall `Occupant`
values (12 parts, ~30 reads) and only scans when a cow that was not milked yet
turns up parked. [tools/milk_arrivals_test.py](tools/milk_arrivals_test.py) counts
the scans: 6 scans over the 12.6 s a five-cow batch took, where the old code
scanned on every 200 ms poll (~60).

**The stall scan, narrowed.** Finding one barn's stalls was
`workspace:GetDescendants()` plus a name compare per instance — and this game has
~112,531 instances (run-3 dump), so every pass built that table to find a dozen
parts. The stalls are `<barn>.Spots.<n>.Adornee_BarnStallMenu` and barns are the
models in `Objects.Buildings`, so the scan now starts at those few buildings (and
at the barn the farm is already locked to, which is one building). Measured on a
95k-instance fake map with 8 barns and the real functions
([tools/stall_scan_bench.py](tools/stall_scan_bench.py)): **95,517 calls + 95,410
name reads per pass → 73 calls + 0 name reads** once the barn is locked, 101 on
the first pass, 380 if the distance prune takes nothing out. Same 12 stalls kept,
and the whole-map walk still runs as a fallback if a layout matches none of this.
The stall's `Occupant` value is cached per stall too (the arrival wait reads it
five times a second, and the milk step reads it per cow), so a repeat read is one
property access instead of two instance calls. The pass now prints the scan time:
`milk: 12 stall(s) found by the narrow scan in 0 ms - ...`.

**The clean pass, without the teleport tour.** Asking "is this stall dirty?"
used to mean **teleporting into all twelve stalls every pass** — 0.2 s for the
teleport to settle plus a 0.3 s floor before the first read, so a barn with
nothing to clean still cost twelve teleports and 6.00 s of standing still, every
single pass. The answer is read without moving, and the pass only visits a stall
that **reports** dirt. What the live build actually uses was named by
`SpudStallProbe.lua`: the stall folder (`<barn>.AnimalContainer.Spots.<n>`) carries
**`FilthLevel`** (0–4, how many of its four stain levels are showing) and
`FilthPercentage`. **`FilthLevel > 0` is the trigger** — it is the game saying
dirt is drawn there, readable from the plot centre. `FilthPercentage` is the
meter behind it, and it is a trigger **only above the 24 % baseline** the probe
found on a stall whose every stain was invisible (the user's "over 20/24
dirtyness"): the clean reading itself can never bring the twelve-stall tour
back, but a stall that climbs past it is cleaned before its levels are drawn.
The line only ever moves **up**, and only when the game itself says a stall it
pointed at is clean (`... reads 60% but the game offers no Clean there - the
dirty line moves to 60%`), so a build with a different baseline costs one look
and then settles instead of hopping into the same stalls every pass. If a build
loses the attribute, the **same answer is read
from the drawing**: `Filth/Level1..Level4` are the four level meshes and every
one of them is `Transparency = 1` while its level is clean, so the count of
visible ones is `FilthLevel` by another route and needs no teleport either. The
folder is only trusted when it actually holds `Level` parts — any other `Filth`
shape falls through instead of answering "0". For builds without any of that, a
direct `Filth` child (the old dump's shape), a nested value, an attribute (`Filth`
/ `Dirt` / `Grime`) or a dirty-named child are all still read.

A clean is **not instant** — it takes about **2 s** in this game (the user's own
number) — so both clean paths wait on the game's own signal instead of a flat
sleep: the Clean offer switching off is the proof, read every **50 ms** so the
pass leaves the moment it flips, and the log says how long it took
(`OK milk: stall 3 cleaned in 1.94s (2 stain(s) -> 0)`). The per-cow clean used
to give up after **0.96 s** and press for milk while the stall was still being
cleaned — a press the game ignores, which is one way a cow came back unmilked —
so it now holds until the offer clears (2.25 s ceiling).

**No cow goes into a dirty stall** (user: "before it brings the cows inside make
it check for over 20/24 dirtyness"). The clean pass already runs before the
herd, but if it could not clear a stall, the herd step now **skips that stall**
instead of shoving a cow into it: `herd: 2 free stall(s) still over the dirt line
(2 stain(s)) - no cow sent into them`, and the status line repeats it. The same
three readings decide it (`FilthLevel`, a visible `Stain`, the meter over the
line), so the gate and the cleaner can never disagree about what dirty means. A
barn where **every** free stall is dirty herds nobody that pass and retries in
the usual short interval rather than standing in muck.

A build that exposes **none** of those used to fall back to visiting all twelve
(every stall "unreadable" = a visit), which is exactly the tour this was meant
to remove — the console said `12 of 12 stall(s) need a visit (no readable dirt)`.
That fallback is **gone**: an unreadable stall is **never** a reason to move, it
is cleaned at the stall itself while a cow there is milked (the game only offers
Clean while you stand in that stall anyway), and the console names the stall and
lists what it actually holds **once per session**, so a build whose dirt lives
somewhere unexpected can be pointed at exactly instead of guessed at. A clean
barn is **0 teleports and 0.00 s** (`milk: 12 stall(s) read from here - none
reports dirt, so no teleports`). Measured with
[tools/clean_visit_test.py](tools/clean_visit_test.py) (virtual clock, real
extracted functions, a fake 12-stall barn): **12 teleports / 6.00 s → 0 / 0.00 s**
on a clean barn, **12 → 1** when one stall is dirty, **12 → 0** when the dirt is
unreadable, **12 → 1** for dirt given as an attribute or as a nested value (both
of which the old read missed entirely), **12 → 1** for dirt that is only drawn as
visible `Level` meshes, **12 → 0** when those meshes are all hidden, **12 → 1**
for one stall whose meter reads 60 % over the 24 % line, **12 → 1 → 0** for a
meter the game disagrees with (the first look teaches the line, the next pass
hops nowhere), and a stall that keeps refusing Clean still gets the same three
attempts. [tools/herd_order_test.py](tools/herd_order_test.py) covers the gate
itself: a dirty free stall is skipped and the clean one used, and a barn with
every free stall dirty arms nobody.

**Letting a cow out, from where we stand.** Opening the stall gate used to
**always** hop to `Gate.ProximityPart` and sleep a flat 0.9 s first — even though
the game's `BarnDoorInteract` billboard names *that* gate (its `Adornee` is the
gate's own part) wherever the press comes from, and after milking a cow the
character is already standing in its stall. So the hop now happens only when the
action is **not** already offered *and* the character is not already within 8
studs of the gate, and a retry polls from where it stands instead of jumping to
the same stud again (two inline poll loops collapsed into one helper, so the file
has two fewer `task.wait` sites than before). Measured with
[tools/gate_visit_test.py](tools/gate_visit_test.py): **1 teleport / 1.60 s → 0 /
0.00 s** when the door is already offered, **4 → 1** hop in the path where the
game never offers the action at all, and a gate that is *already open* is still
never pressed again (that press would shut it on the cow).

**Farms are teleported to, not walked to.** A distant plot is streamed *out* of
workspace, so the pass saw "no plot" and moved on - a farm that was never really
looked at. Each farm's plot centre is remembered on first sight; when the plot is
missing the character teleports to the remembered centre and waits up to 4 s for
the plot to stream back in, and when the plot is visible but we are more than 200
studs away the pass jumps to it before reading anything (every other step already
teleports to its own target, so the walk was the only slow part of a farm change).

Economy (per seed box = 50 crops, average prices): Wheat ≈3,000/hr … **Tomatoes
≈7,686/hr** (best field crop), Potatoes ≈7,500/hr, Cabbage ≈6,500/hr; Cocoa raw ≈5,625/hr
but is meant for chocolate milk (S-tier); Pine logs ≈19,500/hr; Cypress logs ≈63,000/hr.
Animal prices: chicken 1,500 · sheep 3,000 (Sheep License ~7,200 XP) · cow 4,500;
cows/barns are free of license, eggs feed the Cake + Scrambled Egg factories.
Joining the Dunn Games Roblox group (Farmer's Club) adds **+5% sell value**.
Licenses gate shops (Goals system) — the script can't buy locked stock for you.

### Stealth / "undetected" — what it can and cannot do
Roblox detection has three layers. **No Luau script can affect layer 1:**
1. **Hyperion/Byfron (client integrity)** — detects the *executor* (injection, hooks,
   unsigned modules). Depends entirely on your executor being currently patched.
2. **Server movement validation** — flags instant teleports / huge speeds.
   Mitigations built in: **two movement modes** — VFly (BodyVelocity fly +
   snap teleport, fast; the default) or Tween (slow stepped glide, safer) —
   Walkspeed/Jump clamps, NoClip force-blocked in stealth, all actions via
   real context-key binds (F/X/E/V) via virtual input (no RemoteEvent guessing =
   no honeypot risk). **Three exceptions:** the milk store step fires two
   remotes *recorded from the game itself* (`EVTRequestToCarry`,
   `EVTFillLiquidCarrier`); the field passes replay the game's own cell calls
   (`EVTCultivateFieldCell` was recorded verbatim; the plow/seed/harvest
   siblings share that shape on the same captured path); and the equipment
   steps fire the captured mount, hitch/unhitch, spawn/store, carry/drop, sell
   and purchase calls. Nothing is trusted: a jug only counts once it is in
   `CarryLinks`, a fill only once the tank rises, three ignored calls put the
   key path back for the session, every field batch is re-read after firing,
   and every equipment call has to show its effect (seat, tug, `InStorage`,
   hands, tank, balance) — a job the server ignores goes back to keys/UI for
   the rest of the session.
3. **Behavioral/ML scoring** — flags robotic timing, 24/7 sessions, crowded-server
   play. Mitigations built in: ±40% timing jitter, random micro-pauses, session
   limiter (auto-break, default 45 min on / 4 min off).

**Honest limits:** these reduce risk, they do not make you invisible. Use a **free VIP
server** (this game has them), keep sessions short, and consider an alt account.
Running 24/7 in public servers is the fastest way to get reported regardless.

**"Modified client" is layer 1, not layer 2 or 3.** That exact wording is
Hyperion/Byfron reporting the **injector** (or a patched Roblox build — FPS
unlockers that patch the client, modded mobile APKs), not your movement or timing.
No edit to this script can change it: every line here runs *after* the executor has
already injected, and the check fires on the injection itself. Tween mode, quieter
timings and shorter sessions do **nothing** for that notice. The only lever is not
injecting on that account.

**If you get a warning, stop on that account.** Roblox enforcement escalates —
notice, then short bans (1/3/7 days), then permanent — and a warned account's next
catch comes faster than the first. Read the exact wording under Account → Settings
→ Violations & Appeals. If it names exploiting / a modified client, standing down
means standing down: don't relaunch the executor "just to test" a build. If you
ever resume in a stock client, the loudest *script* signal is the **snap teleport**
(`root.CFrame = ...`, one jump per jug, many per minute): Tween movement plus the
key-only milk path (no fast remote) is the quietest this gets.

**The probes are louder than the farm loop.** `SpudRemoteProbe.lua`, `SpudDump.lua`
and the other scrapers hook `game`'s `__namecall` with `getrawmetatable` /
`hookmetamethod`. The farm script itself never touches the metatable — it only
presses keys and writes CFrames. If the warning came right after running a probe,
that is the more likely trigger; don't run them on an account you care about.

### `FarmingAndFriends_Main.lua` — earlier generic version
Generic crop-plot script (attribute/remote auto-detection). Kept as a fallback;
`SpudFarm_Full.lua` supersedes it for Farming and Friends.

### `spud-gui-preview.html` — GUI preview
Interactive browser preview of the GUI look/feel — open it in any browser.

### `SpudDump.lua` — in-game structure scraper (read-only)
Run it **in game** (MuMu + Delta supported) to build a text report of the live game
structure: proximity prompts, tools, your plot's tiles, equipment names, NPCs,
vehicles, remotes, signs and the **live sell-price boards**. It sends nothing
anywhere by itself — it uploads the report to a random unlisted paste link,
prints the link and copies it to your clipboard. Roblox streams objects in
near you, so run it twice: once **in town** (zoomed out) and once **at your
farm standing among your fields/animals/barn**, then send both links back so
guessed names in `CONFIG` can be replaced with real ones.

### `SpudStallProbe.lua` — one stall folder, dumped (read-only)
The clean pass decides "dirty?" from where the character stands, so it needs the
stall's own dirt field. The dump's shape (`Spots.<n>.Filth`) is not what every
build exposes — one live build answered nothing at all — so this probe dumps
**one whole stall folder**: every descendant with its class, value and
attributes, every part with its transparency/position, which stain parts are
actually **visible**, every dirt-sounding instance in the stall / barn / plot
with its full path, and the game's own `CleanAnimalContainer` billboard (what it
is adorned to, whether it is enabled, and the key it prints). It presses nothing,
teleports nothing and writes nothing, and the whole report is also shown in a
small on-screen panel with **COPY REPORT** / **CLOSE** (the report is put on the
clipboard as soon as it finishes). Stand on the farm and run:

```lua
loadstring(game:HttpGet("https://raw.githubusercontent.com/simba13231/spud-farm/main/SpudStallProbe.lua?t=" .. os.time()))()
```

Paste everything it prints (one block, prefixed `[STALL]`); the path list at the
end is what names the field exactly.

### `SpudRemoteProbe.lua` — what the game SENDS (read-only)
Run it in game, then do one milk deposit **by hand** (pick up a jug, press Fill at
the truck, milk one cow) and run `spudRemoteStop()`. It records every
`FireServer` / `InvokeServer` the game itself makes, with the exact remote name
and arguments, lists every remote in `ReplicatedStorage`, uploads the report and
copies the link to the clipboard. It fires nothing. A small on-screen panel has
**Copy report**, **Upload & stop** and **Stop (no upload)** so neither step needs
the executor console. The report it produced is what the milk store step now
uses: `EVTFillLiquidCarrier(<carrier>)` and `EVTRequestToCarry(<jug>)` are fired
as a fast path, with the key presses kept as the fallback whenever the world does
not confirm the result.

The same run also captures **field** calls, which is what the remote-driven
field pass uses: drive over **one** cell with any of the plow, cultivator,
planter or harvester, and/or press V at the seeder holding a seed crate. The
report gains a **FIELD CALLS** section with the exact arguments for
`EVTPlowFieldCell`, `EVTCultivateFieldCell`, `FNCSeedFieldCell`,
`FNCHarvestFieldCell` and `FNCFillSeeder` (plus the remote's full path). The
captured cultivate call and `FNCFillSeeder(seeder)` are what the field pass now
fires; the plow/seed/harvest siblings share that shape and switch themselves
back to driving if the server ignores them. The report also lists
**EQUIPMENT CALLS** (the mount / hitch / spawn / store / carry calls the script
now fires) and an **ACTION CALLS** section for the rest of the job — clean a
stall, milk a cow, send one, sell a load, fulfill an order, buy a crate, fill a
feeder, open a gate — or just let one normal milk/barn cycle run while it is
recording, because the script's own key presses produce the same calls.

### `SpudBoot.lua` — loader that shows its own errors
A tiny (~8 KB) launcher for when the executor console is not visible: it
downloads `SpudFarm_Full.lua`, compiles it and runs it, and puts every step in a
small on-screen panel — downloaded byte count, the build string, and the exact
compile or runtime error if one happens (also copied to the clipboard so it can
be pasted into chat). Paste this one line:

```lua
loadstring(game:HttpGet("https://raw.githubusercontent.com/simba13231/spud-farm/main/SpudBoot.lua?t=" .. os.time()))()
```

## Contributing / fixing names
Found a wrong in-game name after a game update? Open an issue (or PR) with the
correct name and which feature it affects — Settings-box defaults live in the
`CONFIG` block at the top of `SpudFarm_Full.lua`.

## Codes (status: disabled)
As of mid-2026 Dunn Games has **temporarily removed code redemption** (confirmed by the
community manager; the medal-icon Social menu accepts nothing). Sites listing "working"
codes (HARVESTDAY, COINBLAST, …) are fake lists. Expired real codes: NOSPAM, DunnGames,
Seniac, BunnyFilms. Watch the official Discord for when redemption returns.

## Name fixing
The game updates its internals often. If a feature can't find its target
(e.g. milking does nothing), open **Settings**, use a workspace explorer /
remote spy to find the real in-game name, and type it into the matching box.
You can list **several guesses separated by commas** (e.g. `Milker, Udder Tool`) —
any candidate matching an in-game name will be used.
The wiki-sourced defaults (Cow, Milker, FarmCo, KGF, SRC6, …) are best guesses.

## Executor compatibility
Synapse X, Xeno, Delta, Wave, Solara, Fluxus, etc. (uses getgenv/gethui/cloneref
with fallbacks where available).
