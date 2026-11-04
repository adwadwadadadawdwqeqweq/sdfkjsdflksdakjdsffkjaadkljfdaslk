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
  tail gets one retry — **but only of the cells the blade can actually reach**:
  `FNCSeedFieldCell` / `FNCHarvestFieldCell` are `InvokeServer`, so every call
  waits for the server's answer, and from the field corner that is a round trip
  spent on cells that can never take it (live: 11 s for 50 calls, 6 of them in
  reach, then another 9 s retrying the same 44 out-of-band cells from the same
  pose). The corner pass now fires only the ids within `spudFieldReach = 24`
  studs of the tool's own attachment — the measured band is 20 to the side taken,
  30 refused — and hands the rest to the blocks, which park the blade on
  them. **A wider tool gets a wider band** (the band is measured around the
  *blade*, and a 3-wide implement's own ground is inside it): the filter is
  `24 + the tool's tiles past one × 5`, so a 4-wide tool reads cells 39 studs off
  the corner. A field with nothing in reach says
  `remote seed: 50 cell(s) need it but none is within 24 studs of the blade (24
  measured + the KQF3000's own width) — going straight to the blocks` and costs
  **no** call at all. That is what
  removes the ~10 s pause before every tool pass. A field whose frame, cell
  positions or ids cannot be read keeps the unfiltered pass — an unreadable
  reach never skips a call, and a tool whose parts cannot be read adds **no**
  reach. After the call pass there is a
  **block grid**: the remaining cells are grouped into rows, rows that sit within
  one block's own span of each other form a band, and the band is cut into blocks
  by **distance** — never by list position (see below) — so each block is a tight
  `side`×`side` square. Each block gets one stop at its own
  centre — the ride parks with the **blade** on it (the tool trails behind
  the tractor, so the ride goes to `stop − blade offset`), fires that block's
  cells 40 ms apart, then walks **forward** to the next block (each
  band alternates direction). Every cell belongs to exactly one block, so
  nothing is skipped and nothing is fired twice; a 50-cell field is **8
  teleports** of nine calls each. The band it relies on was measured live: a
  take from **20 studs to the side** at +8 (30 refused) and from **+80 straight
  up**. **The cut is measured in the game's own pitch** (`spudFieldPitch = 10`,
  what `cellsAtStage` spaces the cells by), and this is the fix for
  *"why does it onyl do half the field"*: the grid used to take the `side`-th
  **row** and the `side`-th **column of each row's own list**, then park at the
  **mean** of whatever cells landed in the chunk. On a field that is fully
  worked that is a square; on a **part-worked** field every row holds a
  different set of cells, so the "block" comes out an **L**, its mean sits well
  outside the band from its own corners, and every call there is refused — while
  the pass reports no miss at all, because the miss test compares the blade to
  that same mean. Live, on one field:
  `remote plow: fired 361 of 361 cell(s) from 57 stop(s), 3x3 per stop — 180 took, 181 left`
  and `remote cultivate: fired 368 of 368 … — 165 took, 203 left`. 361 cells over
  57 stops is 6.3 a stop where a 3×3 is 9, and the ~50% that were refused is the
  half the owner saw left standing (the per-cell hop then takes them one
  teleport at a time, which is why it finishes — slowly). Now a band ends when
  the next row is more than `(side−1) × 10` studs away (or the band is already
  `side` rows), a block ends at the same span **measured from its first column**
  (a hole in the lattice can't make three counted columns span four pitches), and
  the stop is the block's **bounding-box centre**, not a centroid — so the
  `spudBlockSide` corner rule holds for the cells actually in the block: worst
  cell 14.1 studs out, inside the 20 that was measured to take. An 8-cell ragged
  patch and two 3-cell strips 40 studs apart each get 2 stops and take **all**
  their cells (`tools/field_remote_test.py`), and the full-rectangle fixtures
  keep their exact old counts. **One stop = one equal square** (owner: *"when it plows, now it plows in a
  cross pattern, if it cant do a equal 3x3 or 4x4 or 5x5 or 6x6 or 7x7 it should
  only do one of those, if it make a cross pattern it goes back to a 3x3"*): a
  stop parks on the block's centre, so its corners are the farthest cells, and
  `spudBlockSide` grows `side` only while the **next** square's own corner stays
  inside the reading that actually took (`spudFieldTaken = 20`). On the game's
  10-stud grid a corner sits `√2 × (n−1) × 5` studs out — **14.1** for a 3×3,
  **21.2** for a 4×4 — so this build stops at **3×3**, and the live arithmetic is
  the proof: the 4×4 plow grid logged `fired 2388 … 1793 took, 595 left` (595 of
  2388 is 24.9% refused; the four corners of a 4×4 are 4 of 16 = 25%), while the
  same field's 3×3 cultivate grid took 2374 of 2399. A wide implement grows the
  **corner pass** (its own ground does reach farther) but never the block, because
  the call carries one attachment point and a diagonal earns it nothing. The stage
  re-read after the **first stop that fired** decides — if the
  server takes nothing from a parked blade the grid fires **that same stop
  once more**; between stops it **waits for the blade**, not a fixed beat — a
  hitched tool trails the tractor for a moment after a jump, so the call only
  fires once the blade is actually on the block, **re-aiming from the blade's own
  fresh position** until it lands (the first stop gets three aims: it arrives
  straight out of a long arc, the first call after such a ride is routinely
  refused while the server still holds the old pose, and the hitch settles the
  implement onto its own rest trail after the jump). The live seed failure was
  exactly that: `the blade is 32 studs off stop 1 — firing anyway` then
  `fired 9 of 2362 cell(s) from 276 stop(s), 3x3 per stop — 0 took, 2362 left` —
  nine refused calls were nine seeds spent for nothing. So a block whose blade
  demonstrably is **not** on it now fires **no** calls and its cells stay on the
  field's list for the hop, while an unreadable blade still gets its burst
  (unreadable is not a miss). Three such misses in a row end the grid
  (`the blade has not landed on 3 stop(s) in a row — ending the grid here; the hop
  pass puts it on each cell`). A grid only gives up once a stop that actually
  **fired** takes nothing, so a healthy field still ends like the
  live run that did
  (`remote seed: fired 46 of 46 cell(s) from 8 stop(s), 3x3 per stop — 46 took,
  0 left`). **And it takes a beat between the blocks** (owner 2026-11-04:
  *"when it's doing the 3x3 make it wait 100ms after before going to the next
  3x3"*): after a block's nine calls the grid waits `spudBlockPause` ms — 100 by
  default, in milliseconds so the number is easy to change — before the next
  stop's teleport, and the last stop pays nothing because there is no block
  after it. **And it waits for the tow before it jumps at all** (owner: *"when it
  tp's the tools make the whole thing glitch and it falls out the map, make it
  wait for the tool to be behind the tractor before tping again"*): a second
  teleport while the implement is still swinging adds velocity to it rather than
  turning it, which is what threw tools off the map. `spudWaitTool` samples the
  tool's distance behind the ride twice 50 ms apart — ≤3 studs of movement is
  settled, more than **90** means it is no longer on the hitch, and 30 beats is
  all the wait ever gives — and it runs before **every** jump: each grid stop,
  each per-cell hop, and the field-to-field arc. A tool that reads flung ends the
  pass where it stands (`remote seed: the KADL is 312 studs from the ride — it is
  not on the hitch any more, stopping this hop pass instead of dragging it
  further`) and the arc refuses the field outright rather than towing it 800
  studs off the map; a tool still swinging is named **once** per pass and the
  work continues. **And every jump now takes the tool with it** (owner: *"we need
  to anchor the tractor when it tps because the tool drags it, also the tractor
  tps before the tool can get back in place"*): `Model:PivotTo` moves only the
  model you point it at, so a ride teleport used to leave the hitched implement on
  the old ground with the constraint under the whole length of the trip — one
  286-stud arc hop arrived at **`hitch gap at arrival: 277.7 studs`**, and because
  no 1.5 s wait can close a gap that wide the next pass refused itself again, and
  the field fired **0** calls. `spudPivotRig` now pivots the ride and translates
  the implement by the **same delta**, keeping the tool's own rotation (a turn
  must not spin the plow), at every grid stop, every per-cell hop and every frame
  of the arc; a job whose tool IS the ride (harvest) is moved once, not twice. The
  hitch stays the length of the tow-bar, so the settle wait reads settled instead
  of far, and the whole field gets called at rather than refused. **The carry is
  the anchor; there is no weld** (v1.133 added one, v1.134 removed it — owner:
  *"bro make it anchor te tool permanantly behind the tractor while it's hitched"*,
  then *"it's making the wheels glitch"*). The idea was reasonable: a carried tool
  still hangs on the **game's** constraint, so the pose at arrival is whatever the
  solver managed in the frames available and every grid stop has to re-aim from a
  fresh reading — a client `WeldConstraint` between the ride's hitch part and the
  tool's would make ride + implement **one assembly** and end the swing. The live
  answer came from the emulator console and one screenshot: the server **does**
  accept it (`anchor: JDShank welded to the ChallengerMT9's HitchRoot`, and the gap
  really did drop to `hitch gap at arrival: 1.1 studs`) — and that is the problem.
  The game's own hitch constraint **already** joins those two models into one
  assembly, so the weld is a second joint between the same pair, and a loop is
  over-constrained: the solver threw a **wheel onto the field** next to a tractor
  reading `Speed 0`. The weld also handed the merged assembly's network ownership
  to this client while the server kept simulating the implement, so the two
  stopped agreeing where the blade is — the very next grid logged
  `remote plow: fired 9 of 98 cell(s) from 12 stop(s), 3x3 per stop — 0 took, 98
  left`, against 1793 taken on the same field without the weld. So
  `spudAnchorTool`, `spudUnanchorTool` and the `spudAnchor` state are **deleted**,
  every one of their eight call sites with them, and the only `SetNetworkOwner`
  left is the pre-existing `claimOwnership` on the ride the player is actually
  driving. `tools/tow_anchor_test.py` replaces the weld harness and refuses the
  build if any weld symbol comes back; the source comment says why, so the next
  reader does not re-invent it. The swing the weld was meant to remove is handled
  the way that is known to work: the carry, plus v1.132's re-aim at each stop.
  Whatever it misses is then **hopped**: one
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
  see — a bulk field door we never fired would only show up there. It walks up to
  **3000** nodes and says so if it runs out (v1.124: the old limit was 600, so a
  report of "339 found (601 nodes walked)" was a **cut-off** list presented as a
  complete one).
  **Field remotes** fires
  `FNCSprayFieldCell(field, {id}, {att})` and reports `IsWatered` /
  `PlantGrowth` / `Stage`, naming the attachment that actually went out — or
  saying plainly that **no implement was found**, so the call carried nothing and
  a "no change" is not an answer about water (v1.124: the last live run read
  exactly that way and looked like a verdict). Then it invokes `FNCEditField()` and
  `FNCConvertRundownField()` with **no arguments** just to read the shape they
  demand (an error names it; nothing that could rebuild the field is handed to
  them).
  **Grow now** answers *"can the crops be made to grow instantly"*. The clock
  itself is not reachable — the game's field packets only run server→client, the
  cell table the client can see is not what the server reads, and `FieldHelper`
  has no setter — so this asks the one question that could still skip the wait.
  First it reads the **grow table**: the remote list names
  `EVTUpdateCropGrowthConfig`, which means the server broadcasts a crop-growth
  config, so anything in `Modules` named grow / crop / config is required and
  printed as the game calls it — the per-crop grow time is what both this question
  and the order-ranking want. It prints every stage name on your field with the
  cell's own growth numbers,
  then **gets into the harvester** (bringing it out of storage if it is parked),
  puts the blade on a `Seeded` cell and fires the harvest call at it, reading
  both the cell and the tank: a cell that is cut early **and** puts something in
  the tank is the abuse (plant and harvest on the same pass, no growth wait), one
  that cuts but pays nothing is just a bare cut, and a refusal means the game
  wants a ripe crop. If it refuses, the button then rewrites that cell's growth
  to the ripe number the game itself just printed and re-fires, to say whether
  the server ever consults the number the client can see. Last it tries water on
  a cell that actually holds a crop (the old tests sprayed an empty tile, then a
  planted one with no attachment at all, so this was never really measured) with
  the sprayer's own attachment. It is not part of
  **Run all** — that stays read-only — because this one sits in a machine and
  cuts a cell.
  **It answered: `early cut — Seeded → Empty, tank 0 → 1 — TAKEN AND IT PAID`.**
  The harvest call does not want a ripe crop, so the wait is optional — and the
  farm loop now takes it. See **Early harvest** on the Settings tab.
  **Shop counter** repeats the seed-buy trip: it prints FarmCo's own parts and
  every `CounterAttachments` spot with its world position, carries the crate
  onto that attachment, drops it, and reads the game's context actions and
  prompt billboards at each step, then presses F and reports which layer it
  raised, the toast text and the visible buttons. It exists because the till
  answers *"You must place items on the counter to buy them"* and the buy has
  never landed.
  **Company orders** is the evidence step for the auto-contract feature you asked
  for, and it changes nothing. The design you approved picks the **easiest** order
  by **seeding time and cost**, steers **only the next planting** (never rips out
  what is growing) and unloads before replanting — but no run this script has ever
  made has named a Company order in the world, and no run has ever printed a
  crop's grow time, so writing the reader now would mean inventing both. One press
  answers them instead: it walks the **whole map and your own PlayerGui** for any
  name saying order / contract / request / company / cargo / shipment / goal / task
  / reward, dumps each one it finds with its attributes and every value inside it
  (crop, wanted count, how much is already in, the reward), prints the **words on
  the order board** — which is a screen, so a workspace-only walk would never see
  it — and lists every order-shaped remote in the game's own module with its class,
  so a `RemoteFunction` and a `RemoteEvent` stop being the same question. It then
  asks the game's config module whether a **grow time is readable at all**; if it
  is not, the report says `NO client-side grow time is readable — the ranking would
  have to run on cost alone`, which is a usable answer rather than a guessed
  number. The one thing it does send over the network is a **getter**: only
  `FNCGetOrderProgress` and `FNCGetAvailableBoxes`, only when the game actually has
  them as a `RemoteFunction`, with your coin balance read **before and after** — if
  a getter ever moves the wallet the report says so in the same lines, because then
  no order call is a read. It presses no key, moves nothing and fires no event: no
  `EVT…`, no `FNCAcceptOrder`. Zero results is reported as *"the board is
  elsewhere from here"*, never as *"you have no orders"*.
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
  separate runs, and that is what `spudFieldReach = 24` — the band every field
  call is filtered by — is built on. The packet is
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
  same step, and three misses switch that one call off for the session. **A carry
  is asked for from *beside* the box** (v1.143, live). Every crate trip arrives by
  teleporting the character **onto** the crate, which is what the shop-counter
  probing already found throws you off it — so the offer on screen was the
  machine's `EnterEquipment`, the crate's `Carry` never armed, and E was pressed
  three times at a prompt that was never being shown. `carryCrate` now steps to
  `spudCarryNear = 8` studs off the crate (only if it is standing on it or far
  from it), gives the CFrame the three frames it needs to reach the server, and
  reads what the game renders; `spudOfferSaysCarry` answers **true** for a list
  carrying the word `Carry`, **false** for a list that does not, and **nil** when
  there is no list to read — and it is *fail-open*: the presses run whatever that
  answer says, because an offer list this build does not render is not evidence
  the box is unreachable. A readable "no" is named instead
  (`carry: standing 8 studs off the bought crate offers no Carry — the game
  offers: Open Shop — pressing anyway`). **And a crate that never came to hand is
  a failed trip, not a filled one** (v1.143): the fill helper used to `return true`
  there, so the run reported a purchase that poured nothing and paid for another
  town visit, and another — four shop trips in one buffer, ending
  `the seeder is still empty and this run already made 4 shop trip(s)`. It returns
  false now and says so (`the crate didn't come to hand — nothing was poured`). **The
  default seed is the crop you are planting** (v1.135, owner: *"btw we are
  planting tomatoes so mke it plnt tht"*): a live cell's own `SeedType` reads the
  game's word — the `Grow now` census printed `Seeded ×50 [growth 2012, mult 1,
  watered false, seed Tomato]` — so the Farm tab's default looks for `Tomato` in
  `FieldHelper.SEED_TYPE` through the same folded name key, instead of defaulting
  to a name this build picked. The order is: a pick remembered from the last
  build (while the game still offers it) → **Tomato** → the game's first crop
  (lowest `SEED_TYPE` id) → the first entry of its list, and the
  `seed default: Tomato (the crop you are planting)` line says which one won. A
  hand-picked seed in the dropdown always outranks the default, and a build whose
  list has no Tomato behaves exactly as before. **A seed you already have is
  never bought again**: a crate an interrupted trip left
  carried is read from its own `Configurations.CurrentHolder`, and a crate you
  own (its `Configurations.Owner` is you) is read anywhere on the plot, nearest
  first — either one skips the shop entirely and is poured into the seeder. What
  decides "have it" is **how many seeds the crate holds**, read from its own
  `Configurations.Capacity` (the same field the seeder uses): a half crate fills
  the seeder half-way and the pass comes back for more, and a crate that reads
  empty is skipped as the empty box it is — a crate that cannot be read at all is
  still used. **A seeder is filled to its own capacity, not to 50** (owner: *"if a
  seeder has like 600 capasity, make it fill up the seeder fully"* + *"fill to max,
  trips scales to fix. by the way you can carry to seed crates at once"*, v1.133):
  the pour keeps carrying crates to the till and pouring them until the seeder
  reads `Capacity == MaxCapacity`, so a 600-slot machine gets 600 seeds instead of
  the first box's 50. **Fill the tank before the field, not one crate of it**
  (v1.148, owner: *"it should fill untill max or there is not mroe moeny"*): two
  things used to start planting on a partly-full machine — the check returned
  "ready" on **any** seed in it, so a seeder the last pass left at 48/600 went out
  and planted 48 cells, and an empty one made **one** town trip, took the 50 seeds
  that trip delivered, and went anyway. In the planting stage the run now tops the
  machine up first: it re-reads the tank after each trip and goes back to town
  while it still reads room, and it stops on either half of the owner's rule — the
  till's own price gate (an unaffordable crate is refused without spending, so the
  loop ends on the wallet) or the scaled trip ceiling (`the seeder reads 400/600
  and this run's 11 shop trip(s) are spent — planting with what it holds`). The
  line that used to read `the seeder holds 50 seed(s) now — seeding this run` now
  says which of those it ended on. Related: the purchase line reported the **first**
  balance read after the click, and the HUD's coin counter animates down, so a
  120,000 crate bought from 129,026 printed `→ 87069` while the wallet sat at 9,026
  — the drop is still the proof, but the number printed is now the settled one.
  The shop-trip budget **scales to that arithmetic** instead of  staying the old constant four: `spudSeedTripsNeeded(cap, have, perCrate,
  cratesPerTrip)` works out `ceil(ceil(room / perCrate) / cratesPerTrip)` trips and
  `spudSeedTripCeiling` only ever **raises** the old floor (4 for the entry check, 3
  for a mid-field refill), so a machine whose capacity no crate can cover still
  gets the trips it needs and a 50-slot seeder still gets exactly the four it used
  to. `spudSeedsPerCrate` is **learned**, never guessed — it is the count a real
  pour actually raised — and until a pour has happened it is nil, which means the
  arithmetic answers nil and the old ceiling stands (unreadable is not a number to
  divide by). **The seeder's own capacity is remembered too** (v1.143, owner:
  *"when it puts seeds back in the seeder it isnt filling it up to 600 only about
  100"*): `seederSeedState` writes `spudSeederCap` whenever a `MaxCapacity` ever
  reads, and both trip budgets plan through `spudSeederCapFor(cap, remembered)` —
  the fresh number when this read gave one, otherwise the one this build has
  already seen from the same kind of machine, and the log says
  `planned on a remembered tank of 600` rather than pretending a failed read
  answered it. That is the whole "only about 100": a 600-slot tank that answers
  **nil** while it streams gives `nil` trips, the ceiling answers with its floor,
  and the pass stops after the crate(s) the floor allows — 100-odd seeds into a
  machine with 600 slots, while the same pass's own promise still reads
  `refill 1/6`, because the two gates each asked the machine at a different moment
  and only one of them got an answer. When the
  hands go empty and the tank still reads room, the fill now prints what is left
  (`the hands are empty and the tank still wants 500 seed(s) of 600 — 5 more town
  visit(s) at 2 crate(s) a trip`), so the budget the next round uses is a number
  the console shows instead of one it assumes. **Two crates a trip** (`spudCratesPerTrip = 2`, the game's own carry
  limit): after the first purchase is proven, the run prices and carries a second
  crate in the same town visit, proven by the `CarryLinks` count rather than by
  `carrying()` — which is already true with one box in hand. A second crate dearer
  than the balance is left on the shelf, and anything already bought but not paid
  for is put back down before the fill (`spudDropRemote` until the hands read
  empty), so a shelf box can never reach the seeder. **The visit budget is
  planned on the crates a trip actually came back with** (v1.144, the other
  half of the same "only about 100"): the live console proves the second crate
  usually does **not** land — `the second purchase did not land — putting the
  crates back down and picking up only the one that is paid for` — and a plan
  built on the two-crate **ask** promises 6 visits to a 600-slot tank that can
  only receive 300 seeds in them. Each finished trip records
  `spudCratesTripGot`, every budget divides by `spudCratesTripActual()`, and a
  one-crate till is planned at **12** visits (`the cap is 12, planned on a read
  tank of 600 at 1 crate(s) a trip`), never at six it cannot keep. **And the
  crate size is per crate, not per press** (v1.145, the rest of the same
  report): one `FNCFillSeeder` call drains **every** crate in hand — live the
  seeder read 1 seed, a single fill line ran, no pour round followed, and the
  tank read `101/600`. That rise was being learned as the size of one crate, so
  a 50-seed crate became 100 and every shortfall was planned at half the visits
  (`the tank still wants 499 seed(s) of 600 — 3 more town visit(s)`, which is
  401 seeds at the real size). The rise is now divided by the crates the call
  actually consumed, and the line prints the size it planned on. The
  crate's own price billboard is the only price read, and it is only readable
  standing in town — so the first trip makes that hop, and a seed found dearer
  than the balance is then refused **where the run stands** (`the Cabbage crate
  was 57600 coins at the shelf and the balance is 54159 — not hopping to town for
  a price this run has already read`) instead of paying another 1,000-stud hop to
  rediscover it. The balance is re-read at every check, so the cache remembers
  the price and never the verdict: sell a load and the same seed is buyable
  again. **The trip budget is sized by the field, not by one tank** (v1.150,
  owner: *"STILL not filling the planter all the way nor planting the whole
  field"*). Filling a 600-slot machine at 50 seeds a crate and two crates a
  visit is **six** trips, and that was the whole budget — so on a 2400-cell
  field the run filled the tank once, planted 600 cells, and then refused every
  later refill with its own ceiling (`the cap is 6, planned on a remembered tank
  of 600` → `the refill put no seeds in the seeder — stopping this pass` →
  `1800 cultivated, 600 seeded, 2400 total`). The budget is now the larger of
  filling the machine and covering the cells that still need seed — 2400 cells is
  48 crates, **24** visits — and each refill round re-sizes it from the count it
  just re-read, so the field is what ends the run. An unreadable field is still
  *unknown*, not one visit, and the shelf price is still what stops a run that
  cannot pay. **What the till clicks is decided by its own words** (v1.141, live). A
  purchase dialog is open, and the build used to match a button by joining its
  readable label and its instance **name** into one string — so a control whose
  name is `ConfirmButton` but whose label on screen reads **`Delete Farm`**
  matched "confirm" and was clicked as "the Purchase button":

  ```
  seed shop: clicking …ConfirmAction.Content.ConfirmButton ('Delete Farm') — the Purchase button
  seed shop: the menu is still showing after 267 visible control(s) — nothing bought.
  ```

  An instance name is not a label, and a name that says *Confirm* tells you
  nothing about what the button does. The two are read and judged separately now:
  a **danger** word (`robux`, `premium`, `gems`, `sell`, `cancel`, `close`, `back`,
  `exit`, `delete`, `destroy`, `remove`, `reset`, `unsubscribe`, `leave`) in
  **either** half refuses the click, and a **buy** word (`purchase`, `buy`,
  `confirm`, `checkout`) only counts in the label — the name is consulted when the
  label cannot speak, which is the image-only control this game really draws. A
  buy-shaped control that is also dangerous is not skipped quietly, it is logged
  (`a buy-shaped control was REFUSED, not clicked — …`), because a shop that will
  not take money needs naming. And the last tier is **gone**: the old build, given
  267 visible controls and nothing buy-shaped, clicked the first usable one. Now
  it clicks nothing and prints what is on screen
  (`nothing on screen reads as a buy of Wheat (267 visible button(s): …) —
  clicking nothing`), which is the answer the next run needs rather than a second
  destructive press. The **Shop counter** probe reads a control the same way, so
  the probe can no longer click what the farm refuses to. **And a label is not a
  till** (v1.143, live): stopping at the *first* safe buy-shaped match was the
  other half of the same mistake — the next seed run clicked
  `…GuiViews.Stores.PalletStoreMenu.…InfoPanel.PurchaseButton`, whose label
  genuinely says `Buy`, and the toast answered *"You need to own the Forklift
  License!"* three times while the balance did not move. That is the **pallet**
  till — the same screen the counter probing found answering that licence line —
  it is safe by the word rules, and it sorts
  before the seed dialog. The path tells them apart: the trip now collects every
  safe buy-shaped control with its full path, and `spudShopBuyPick` passes over
  anything under a `pallet` or `forklift` name in favour of a control that is not,
  so the real Purchase still gets clicked from behind the pallet till. A screen
  with **only** that till is a dead end said out loud
  (`every buy-shaped control on screen is the pallet till (…) — it sells pallets,
  not seed — clicking nothing for seed`) rather than a licence the script can
  buy. Only those two words refuse by path, because both came off that live
  path and that toast; an invented third word would refuse the real buy. **The
  close judge reads the same rule** (v1.144, live): the question *"did the buy
  popup shut?"* was answered by the first purchase-shaped control anywhere in
  `GuiViews`, and this town keeps the pallet till's `PurchaseButton` on screen —
  so a dialog that had closed was still reported `Stores is still open after
  handler then again`, the close step chased the till's container, and the
  second crate was bought against a till that was never shut. The judge now
  gathers every purchase-shaped control with its path and hands the list to the
  same picker. After a
  seed is bought the **shop menu is closed** on the way out: the open menu is
  read from `GuiViews.Menus`, its own close control is clicked inside it, the
  result is re-read, and F is only the fallback — so the UI does not stay up
  over the field. The
  **Fulfillment** pad needs no key: parked on it, the pad unloads the harvester
  by itself, so that trip only waits for the tank (its own order call was never
  captured, and it is not needed). A seed **round** that takes nothing is now
  bounded too (v1.135): the field pass repeats grid → hop while it is making
  progress — the owner's "keep retrying until none is left" rule stands — but two
  rounds in a row that leave the same number of cells unseeded end the pass with
  `seeding: N cell(s) still need seed after 2 round(s) that took nothing — leaving
  them for the next pass (the hitch and tool lines above say why)`, because a run
  whose hitch failed keeps re-running that round for ever (live: `round 12` with
  nothing taken, the seeder dry, while `hitch: gave up` sat above it).
- **Drop-off pick** — Farm tab → **Drop-off**: **Fulfillment** (default) or
  **Sell**. When the harvester's tank fills it first fires the captured
  `EVTSellAtStore` **from wherever it stands**, at any distance, and watches
  the tank for 1.5 s: a tank that drops logs
  `✅ sold in place at N studs … (no pad trip)` and the harvester never moves;
  a call that moves nothing logs the distance and takes one arc hop, where the
  call is fired again at the pad (or Fulfillment parks and lets the pad drain
  it):
  Fulfillment is the warehouse pad
  (parked, pressing nothing while the pad drains it) and Sell is the old crop
  sell board (call, then Q/E).
  The pad is **read from the world, never assumed**: `Stores.DropOffs` is
  scanned first, and because the live game now keeps that folder empty (v1.118
  read it twice — at the field and again after a 1,133-stud hop to the store —
  and it held **0 children** both times), a single walk over the world's
  instances looks for the same names wherever the game has put them. A part is
  drive-onto-able *and* fire-able; a model only gives a place to park, which is
  all a Fulfillment pad needs. **A navigation marker is never the pad** (v1.121,
  live): the world-walk scored `Ugc.Markers.GotoLocations.Warehouse` as the pad,
  the run hopped 838 studs onto it and parked there with a full tank forever,
  because a marker is a place to *travel to* — the seed shop already uses
  `Markers.GotoLocations.FarmCo` exactly that way. So a `Markers`/`GotoLocations`
  match comes back as the **waypoint** to hop to, and the pad is re-read once
  that hop has streamed the area around it. **A name match also has to be AT the
  pad, not merely named like it** (v1.128, live): the very next build's walk
  admitted `Ugc.CompanyArea.WarehouseArea` — a whole district whose name says
  *warehouse* — the trip hopped 860 studs onto its centre at `(-278, 138, -212)`
  and parked there **142 studs from the drop deck**, tank unchanged. So a pad the
  walk matched by name is only trusted when it sits within `spudFulfillPadNear`
  (35 studs) of the deck the owner measured; anything further off is a landmark,
  the refusal is logged with its real distance, and the trip answers the way it
  does when the world has no pad at all — hop the marker, look again, then park
  on `-353, 141, -92`. The game's own `Stores.DropOffs` folder is never
  second-guessed: whatever it holds is a drop-off by the game's own grouping.
  The console prints
  `fulfillment pad: Objects.Buildings.CompanyArea.Deposit_Warehouse at (…)`,
  `drop-off 1/1: … at (-353, 140, -90)` (all three numbers — the Y is what this
  whole section is about), then
  `✅ sold at …` or an honest `⚠ no pad took the load — the tank still reads N`,
  after which the trip backs off 60 s and the harvest carries on. **A tank that
  already reads empty is not a failed unload** (v1.139, live): the in-place call
  is only watched for 1.5 s, so a sale that lands a beat later leaves the load
  gone while the park trip is still running — and that trip's proof is *"the
  count dropped below what it read at arrival"*, which can never be true against
  an arrival baseline of 0. The owner's console read
  `no unload at DropOffs.Deposit_Warehouse after 16 s (load 0, coins 644584 →
  923235) — the pad didn't take it while parked` and then `⚠ still full`, about a
  harvester that had been emptied and paid out 278k. So a park that finds the tank
  at 0 says `the tank already reads empty here — the load is gone`, the final
  verdict **re-reads the tank** instead of repeating what the branch assumed, and
  a tank it cannot read is named `UNREADABLE` rather than called full (rule 7).
  Every hop
  lands at the **target's own height** and arcs ~12 studs above it, so it always
  arrives as a descent: up onto the field from a lower pad, and **down onto the
  pad** on the way there (v1.122 — the old "land at the higher of the two" rule
  parked the harvester 28–34 studs above the Fulfillment pad, which sits at Y 138
  (part centre) / 141 (the deck you stand on) under fields at 166–172, and a pad
  that drains by contact cannot drain
  something floating over it).
  The store area only streams when you are near it, so a full tank out at the
  farm that finds **no pad at all** first hops the harvester to the waypoint
  the walk found (the warehouse marker ahead of FarmCo), waits for the pads to
  stream, and looks again (`no Fulfillment pad is streamed from here — arc hop
  to Ugc.Markers.GotoLocations.Warehouse, then looking again`); the trip
  back still returns to the field. If even then no pad instance is readable the
  unload is **not** skipped — the trip parks on the coordinates the owner stood
  on and read with **📍 Get coords** (`-353, 141, -92` for Fulfillment,
  `125, 142, -150` for the crop board — `sell: no pad instance is readable —
  parking on the measured spot (…)`), because Fulfillment needs a *place*, not an
  object: parked, the pad empties the tank by itself, with no call to fire and no
  key to press. A Sell pick behaves the same way about the *place* but not about
  the rest: a crop board is not an auto pad, so once it is parked there the
  script still opens the sell menu (Q) and confirms it (E). A refusal still
  **names what the world does
  hold** that sounds like a pad, with each one's class and path, so the next run
  answers the shape instead of guessing at it.
  A tank with **less free space than there are cells still standing** counts
  as full (`spudHarvestFull`): 49/50 against 46 standing crops used to fire the
  one slot's call — refused, because the field corner is out of reach — and
  sell anyway, round after round. The pass now fires **no** call in that case
  and unloads first, so the harvester comes back with a whole tank
  (`remote harvest: 1 free slot(s) cannot cover 46 standing cell(s) — selling
  first, then coming back`). **That rule needs a load in the tank** (v1.151):
  the same arithmetic on a 600-slot harvester facing a 2400-cell field is always
  true — free space can never cover a field four times its size — so an **empty**
  machine was being called full, sent to sell nothing
  (`harvester is FULL (0/600)` → `the tank already reads empty here — coins
  1664376 → 1664376`), came back, refused to fire a call for the same reason, and
  ended the cycle with `2400 cell(s) never took a harvest call even with the
  blade on them`. A field bigger than one tank is the normal case: the harvest
  fills 600, sells, and comes back for the next 600. The rule now only bites
  when the tank actually holds a load that the remaining space cannot cover.
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
- **What a machine is** — the **game** already says it, and that is what the
  pick reads (owner: *"make it use the games build in scripts to know what is a
  harvester and what is what"*). Every model in `Objects.Equipment` carries an
  `EquipmentType` attribute in the live build (`ZM80=Tractor`, `JDS790=Harvester`,
  `KADL=Planter`, `KQF3000=Cultivator`, `S4204=Plow`, `R150=Truck`,
  `Trailer=Transport`), so the word the game wrote is matched by **stem** —
  `harvest`, `combine`, `forage` all mean the harvester, `cultivat` the
  cultivator, `plant`/`seed`/`drill` the planter — and a machine named anything
  at all is still found. A model name (`SRC6`, `KQF3000`, `ZM80`) is only a
  fallback for a build that ships **no** attribute, and it can never overrule
  what the game says the machine is. If a build ships no word for a ride at all,
  the game's own **structure** answers: a model with a driver **seat** and a
  `Components.Hitchable` pulls implements, and one it calls a Truck / Transport /
  Harvester / tool does not. A machine parked in the garage (`InStorage`) has no
  seat and no position, so it is skipped and counted, never silently treated as
  "no tractor". Every "not found" line ends by naming what the world actually
  holds — `no Harvester for you found — this world holds: JDS790=Harvester
  (stored), KADL=Planter, …`.
- **The game writes a name with spaces the model has none of** (v1.135). One run
  proved it three ways at once: the planter's model is `TempoL16` while its
  Equipment Manager card and its HUD slot both read **`Tempo L16`**. So the
  manager answered `no card for TempoL16 — it is not among the cards listed
  above` next to a list that said `Tempo L16`; the stale-label check looked up a
  model that does not exist and so a stored implement kept reporting itself
  attached; and the wrong-tool guard saw a different machine where the HUD named
  the one it had just hitched, pressed X against its own seeder, and then had to
  re-hitch it — from 1,120 studs, on the respawned instance. Every comparison
  between a model name and something the game wrote now goes through one key:
  `spudNameKey` drops a serial suffix (`#9`), drops everything that is not a
  letter or a digit, and lowercases — `Tempo L16` and `TempoL16` fold together,
  `ZM80` and `ZM80\n#9` fold together, and `TempoL16` and `TempoL20` **do not**
  (the digits are the machine, so the strip is non-alphanumerics, not
  non-letters). A card is still matched by **prefix on that key**, so a card
  whose text merely mentions a name cannot win, and two empty labels never match
  each other.
- **The Equipment Manager shows one tab at a time** (v1.135). A run chasing
  `ChallengerMT9` — a Tractor — read exactly **two** cards, both Planters
  (`KADL · Tempo L16`), because the pass before it had been working on the
  seeder, and the tab the game last showed is the filter on its own card list.
  Five attempts, each ending `no card for ChallengerMT9 — it is not among the
  cards listed above`, then `run ended — the last stage it reached was:
  Equipment Manager: respawning ChallengerMT9`: the run **stores its ride** when
  a pass finishes, so every next pass needed a card it could not reach. The tabs
  are the game's own words (`All · Tractor · Harvester · Plow · Cultivator ·
  Planter · Truck · Transport · Misc`), so a miss now asks the game to show
  everything — it clicks that `All` button **through its own handler** (no
  mouse), re-reads the cards, and only then declares the card absent. A build
  with no `All` tab says so, with the number of tabs it did find, instead of
  failing quietly.
- **A card name is not an identity** (v1.144, live). The same diagnostic printed
  `6 card(s) showing right now: Tempo L16 · JD Shank · Horsch Joker · JD S790 ·
  Tempo L16 · Challenger MT9` — **two** cards named `Tempo L16`, because this
  farm owns two of the planter. The store retry clicked the first match on all
  five attempts, so the machine that was actually out in the field stayed out
  and the console said `couldn't store the TempoL16 after 5 tries` twice in one
  seed pass. Every attempt now asks the **next** card that carries the name
  (wrapping), and the final refusal names what it still holds: whether that
  instance is in the world, its own `InStorage` read, and the game's
  `Name=Type (stored)` list — so the next run says which of the two it clicked.
- **A fall-through names which half broke** (v1.135). `spudEquipRemoteAct`
  returned `false` in five places with no log at all, so a console could not
  tell "this build has no such remote", "the call threw", "switched off for the
  session after 3 ignored calls", "no such model in `Objects.Equipment`" and "it
  already reads the state you asked for" apart — and each of those falls through
  to the slow UI. Each prints its own line now (the missing-model one with the
  child count it did read), and the model lookup folds the name the same way, so
  `Tempo L16` finds the model `TempoL16` instead of reaching the manager for
  nothing.
- **The hitch has two measurements, not one** (v1.135). The line-up aimed at a
  part named `Hitch`/`HitchRoot`/`HitchKnob`/`HitchTip`, and a live run reported
  `hitch parts: tractor=none` on a ride that had answered `HitchRoot` minutes
  earlier — one unreadable measurement and the creep alignment took over for all
  ten attempts. The game's **own** socket pair is now the second source:
  `Components.Hitchable` on the ride and `Chassis.HitchableSocket` on the tool —
  the exact attachments the captured `FNCAttemptHitch` takes — read at their
  `WorldCFrame`. When neither source answers, the refusal names what is missing
  instead of guessing past it: `tractor ChallengerMT2 has no hitch point (1842
  instance(s) read, and it is NOT in the world)`, because a respawned model and a
  machine that names its hitch differently are two different bugs and only one of
  them is fixable here. (`plow=Hitch` — the tool's named part — answered in every
  one of those runs, so the missing half was the ride.)
- **The join is never forced, and a miss now says what it looked at** (v1.146).
  The obvious way to make a tractor and an implement "hitch together" — a
  client-side weld between the two hitch parts — was built (v1.133) and the
  live server **accepted** it: the gap closed to 1.1 studs and the rig threw a
  wheel onto the field, while the next grid took `0 of 98` cells on the same
  field that had taken 1793 of 2388 free. The game's own hitch constraint
  already puts ride and implement in one assembly, so a second joint between
  the same pair is a loop. It is gone and stays gone. What is left is the
  honest half: a tool like the HorschJoker answers `has no hitch point (309
  instance(s) read)` — the client holds the machine but shows no socket to aim
  at, so the precise park is given up and the creep alignment runs instead.
  That refusal now lists up to eight instances on the model whose own name says
  `hitch`, `socket`, `attach` or `connector`, with class and path, so one run
  names the point to aim at rather than this build guessing a fourth name.
- **Go to the farm** — with a Farm owner picked, the run **teleports to that  owner's plot first** (only when it is more than 60 studs away; the character
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
  only free-range jugs are loaded there. That list re-scans every 15 s, and the
  re-scan sets the picker rather than the owner setting it, so a pick that is
  already the pick logs nothing — before v1.139 the console printed
  `milk store: (no trailer or silo found)` twice a minute while milk off),
  **Deliver all milk** switch, **Refill
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
- **A full carrier is now sold, not reported** — the milk loop used to fill the
  trailer or silo picked in **Store milk in**, and when that machine read
  `600/600` the pass simply said `store: <carrier> is FULL (n/m) — empty it or
  pick another carrier` and the milk it had already earned sat there. It now
  drives it to the **sell liquid** deck you measured (`86, 141, -288`): the
  character hops there, the carrier is brought to it with the game's own **Spawn**
  if it is more than 45 studs away, and the load is parked on the deck **pressing
  nothing** first — the same rule the Fulfillment pad follows. Only if the tank
  refuses to move does it read what the spot actually offers and drive one of
  those buttons through the game's own handlers (no mouse, no invented remote).
  **The carrier's own readout dropping is the only proof** a sale happened; the
  line is `✅ liquid sold at the deck — Milk Tanker 600 → 0, coins 14459 → 15231
  (parked, pressing nothing)`, and the pass carries straight on filling against
  the fresh number. A **silo** is left alone (it has no wheels and no Garage card,
  so "drive it to the deck" would mean teleporting a building), every exit —
  sold, refused, or a spawn that never arrived — brings the character **back to
  the plot** so the delivery thread is not standing in town reading "no milk jugs
  waiting here", and three misses in a row switch the trip off for that build. A
  failed trip also prints exactly what the deck offered, so the run that cannot
  sell is the run that names the button. [tools/liquid_deck_test.py](tools/liquid_deck_test.py)
  runs the real trip against a fake world — 35 checks, all green — but
  **whether the live deck drains a parked tanker is only answerable in game.**
- **Run controls (Settings tab)** — **▶ Start everything** / **■ Stop everything** flip the three
  loops in a safe order (farm → milk → delivery; delivery turns itself back off
  when no trailer/silo is picked), and **verbose logs** puts the per-cow
  prompt/button dump back on for every cow (off, it runs once per session — the
  walk covers the whole PlayerGui and was a measurable FPS cost). **Anti-AFK**
  sits beside them and is **on by default**: Roblox marks a client away after
  ~20 minutes of no input and the server drops it, and a Cabbage field grows for
  an hour with nobody pressing anything, so a run left alone overnight died at
  the growth wait. Every ~45 s it sends one press of **ScrollLock** and a
  1-pixel mouse move — neither is bound to anything in this game, so the farm is
  never touched — and the game's own `Idled` signal gets the same nudge if it
  fires first. It logs once at load
  (`anti-afk: on — a press every 45 s keeps this session awake`) and otherwise
  only when the game itself flags the session idle, so an hour-long growth wait
  does not fill the log. Turning it off is remembered across a reload.
  **Early harvest** sits beside it and is **on by default**. The game's own
  harvest call does not want a ripe crop — the **Grow now** test cut a cell
  straight after planting and the tank paid (`Seeded → Empty, tank 0 → 1`) — so
  with this on a run plants a field, comes back minutes later and cuts it,
  unloads and replants, instead of sitting out an hour of
  `🌱 growing: 50/50 cell(s) still Seeded`. The log says which mode produced it:
  `🌱 early cut: 50 cell(s) are cuttable now — restarting the loop instead of
  waiting`. Turn it off and the run waits for the crops to ripen exactly the way
  it always did, and the field census reads `standing` instead of `cuttable`.
  **📍 Get coords** logs where you are standing as `(x, y, z)` and puts the same
  text on the clipboard — stand on a Fulfillment or Sell pad, press it, paste it
  in the chat, and a spot the script cannot stream becomes one it can drive to.
  Every
  **Reload** keeps the three farm picks, the typed batch size, the seed choice,
  the movement mode, the drop-off pick, the anti-AFK choice and the early-harvest
  choice, and — more
  importantly — **stops every loop the old
  build started**. Before that, Unload
  only hid the window: the milk loop, delivery loop, webhook pump, 15-min field
  scan and FPS meter kept running, and each reload added another copy of each.
  The guard is a generation counter each build captures
  **in the table the executor shares across executions** (`getgenv()`), and every
  loop asks it, not just its own thread id. A bare global was not enough: the
  live client ran **two** builds side by side — two `still working` streams and
  two FPS streams, each naming the same frozen stage — because every build
  bumped and passed its own copy. An autostarted build and a hand-run one do not
  necessarily share an environment; they do share `getgenv()`. Unload bumps that
  same counter, a clobbered one stops every loop rather than letting a build that
  cannot prove it owns the session keep driving, and 🩺 DOCTOR prints
  `session 3 — GHOST BUILD (a newer one owns the session)` so the pair of streams
  is visible in one report instead of only in the console timing
  ([tools/lifecycle_test.py](tools/lifecycle_test.py) runs the real block against
  a shared table and proves an old loop stops, including after
  Unload-then-Reload).
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
- **Player tab** — the plot/cow read-out. The keeper that stops the game marking
  this client away is the **Anti-AFK** toggle on the Settings tab (above), on by
  default
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

**A jug that will not come away is named, not retried.** The jugs at a plot all
share one model name (`MilkContainer`), so the old refusal line —
`store: E did not pick up Workspace.Objects.DraggableObjects.MilkContainer — the
game offers: nothing visible` — could not tell one box from another, and the pass
spent every attempt on the **same** one. Now each jug gets one try per pass, and
the first three failures each print a survey of that box instead:

```
store: E did not pick up jug MilkContainer at (-412, 138, 83), I am (-412, 141, 86)
3.2 studs off (2.1 flat) — 7 jug(s) stacked on it, owner Miou2251, on foot, tp ran,
offers: Carry | registry: Carry(hidden) · Open Shop(visible)
```

Where the character actually arrived, how many boxes sit on top of that one, the
jug's **own** owner tag (a parent's tag never counts), whether the teleport moved,
what the game **shows** and what it **holds but hides**. The pass then ends with
`store: the milk jugs could not be reached — N different jug(s) tried this pass`,
because one buried box and a pile that all refuse this client are different
problems, and the number says which one it is.

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

**A plot arriving does not mean the barn arrived.** The plot folder stays in the
world at any distance (which is how a farm 868 studs away is readable at all), but
a barn is a full 3D building and has to stream in around the camera, so the first
stall scan after a hop used to answer `no stall found for <farm> in 17 ms` while
the same pass counted 32 cows - and the loop then rested a minute doing nothing,
because "no stalls" means nowhere to send the herd. After a teleport the scan is
now asked again until the game actually has stalls (a quarter-second a try, up to
3 s), because the scan itself is the signal rather than a guessed sleep. A pass
that did not teleport still reads once and waits zero, exactly as before, and a
barn that never shows is reported as **not streamed** - `this pass reads nothing
here, which is not "no barn"` - instead of an unreadable farm being dressed up as
an empty one. Measured with
[tools/stall_stream_test.py](tools/stall_stream_test.py).

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

### `SpudFulfillProbe.lua` — the Fulfillment area and the Company's orders (read-only)
Two questions live at that building and neither is in any dump yet: **which pad**
drains a parked harvester, and **what the Company is actually asking for** (item,
quantity, how much is already in, reward) and **how long a crop takes to grow** —
the number an "easiest order" choice would rank on. This probe reads the area,
every instance whose name says order / contract / request / company / cargo /
shipment (with its whole value tree), the board's **visible text in `workspace`
and in `PlayerGui`**, what `Stores` holds, every seed crate's `Configurations`,
one field cell's complete key list and `FieldHelper`'s exports, the game's own
**live** offer billboards (each action's key and what it is adorned to), what the
character is standing on, everything within 30 studs and the old sell-pad targets.
It presses nothing, teleports nothing and writes nothing; each section is guarded,
so one shape it did not expect prints a `!! … FAILED` line instead of losing the
report. Stand **at the Company / Fulfillment board** (the area has to be streamed)
and run:

```lua
loadstring(game:HttpGet("https://raw.githubusercontent.com/simba13231/spud-farm/main/SpudFulfillProbe.lua?t=" .. os.time()))()
```

**COPY REPORT** puts the whole thing on the clipboard (it is copied as soon as it
finishes); **CLOSE** hides the panel. Lines also go to the console prefixed
`[FULFILL]`. To learn how the game *fulfils* an order — the call it sends — run
`SpudRemoteProbe.lua` and complete **one order by hand** while it counts.

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
