-- SPUD FULFILLMENT PROBE — read-only. It presses nothing, teleports nothing,
-- and dumps the Fulfillment / Shipment area so the harvester's drop-off and the
-- Company's orders are named exactly instead of guessed.
--
-- WHY IT EXISTS
--   The unload leg is wired (park on the pad; the pad drains the tank), so the
--   open question is now the other half: WHAT the Company is asking for and HOW
--   LONG each crop takes to grow. Both live in structures nobody has ever read
--   from the inside — `Stores.DropOffs` turned out to be empty in the live
--   world, and no dump has named an order instance. Guessing either shape is
--   what put a 50/50 tank on a navigation marker for 60 s at a time. This dump
--   answers it from the game.
--
-- HOW TO RUN
--   1. stand at the Company / Fulfillment board itself (the orders are the
--      point now), with the vehicle you unload with spawned nearby — the farm
--      loop can be off.
--   2. run this loader:
--        loadstring(game:HttpGet("https://raw.githubusercontent.com/adwadwadadadawdwqeqweq/spud-farm/main/1000054.lua?t=" .. os.time()))()
--   3. a panel shows the report: COPY REPORT puts it on the clipboard, CLOSE
--      hides it. The same lines go to the console, prefixed [FULFILL]. The
--      report is also copied the moment it finishes building.
--
-- WHAT IT ANSWERS
--   * every building/model near the area whose name looks like
--     Fulfillment / Shipment / Warehouse / Drop-off / Sell / Pad / Load-in:
--     position, size, attributes, Configurations, children
--   * parts that could be the unload pad (name, position, size, transparency)
--   * text on signs/billboards (the "Fulfillment" sign included) and where it
--     is adorned
--   * ProximityPrompts in the area (action text, object text, key code)
--   * the game's own context actions RIGHT NOW (stand near the building) —
--     the key it wants for unloading will be in that list
--   * the old sell-pad targets the script scans today (Stores.DropOffs,
--     GameplayVisuals.SellArea) so a wrong pad is visible
--   * COMPANY ORDERS (v2, the reason this run exists): every instance whose
--     name says order/contract/request/company/cargo/shipment, with its whole
--     value tree, so the board's real shape is named instead of guessed
--   * the board's VISIBLE TEXT, from workspace AND from PlayerGui — the first
--     version only walked workspace, so a ScreenGui board would have read as
--     "no orders anywhere"
--   * what we actually hold that could fill an order (Stores / inventory values)
--   * whether a crop's GROW TIME is readable anywhere: every seed crate's
--     Configurations, and one field cell's full key list plus FieldHelper's own
--     exports. If no duration is in either, the answer is "not readable" and
--     the order pick ranks on cost alone.
--
-- Nothing here writes to the game. It only reads. It fires no remote, presses
-- no key and moves nobody — the ORDER CALL SHAPE comes from 1000055.lua
-- (its ACTION CALLS list already watches FulfillOrder) while you fulfil one by
-- hand.

local Players = game:GetService("Players")
local LP = Players.LocalPlayer

local REPL = {}
local function say(s)
    local line = tostring(s)
    REPL[#REPL + 1] = line
    print("[FULFILL] " .. line)
end

local function safe(fn, fallback)
    local ok, v = pcall(fn)
    if ok then return v end
    return fallback
end

local function posText(p)
    if not p then return "?" end
    return string.format("%d,%d,%d", math.floor(p.X), math.floor(p.Y), math.floor(p.Z))
end

local function attrsOf(inst)
    local out = {}
    local list = safe(function() return inst:GetAttributes() end, nil)
    if type(list) == "table" then
        for k, v in pairs(list) do out[#out + 1] = tostring(k) .. "=" .. tostring(v) end
    end
    table.sort(out)
    return out
end

local function valueOf(inst)
    local cls = safe(function() return inst.ClassName end, "?")
    if cls:find("Value", 1, true) then
        local v = safe(function() return inst.Value end, nil)
        if typeof and typeof(v) == "Instance" then
            return cls .. "=" .. tostring(v:GetFullName())
        end
        return cls .. "=" .. tostring(v)
    end
    return cls
end

local function boxOf(inst)
    local ok, cf, sz = pcall(function() return inst:GetBoundingBox() end)
    if ok and cf and sz then return cf.Position, sz end
    return safe(function() return inst:GetPivot().Position end, nil), nil
end

local WORDS = {
    "fulfill", "fulfil", "shipment", "shipping", "warehouse", "dropoff",
    "drop-off", "drop off", "sell", "pad", "loadin", "load-in", "load in",
    "unload", "delivery", "trailer",
}
local function interesting(name)
    local n = tostring(name):lower()
    if n == "" then return nil end
    for _, w in ipairs(WORDS) do
        if n:find(w, 1, true) then return w end
    end
    return nil
end

local function cfgLines(model)
    local out = {}
    local cfg = model:FindFirstChild("Configurations")
        or model:FindFirstChild("Configuration")
    if not cfg then return out end
    for _, d in ipairs(cfg:GetDescendants()) do
        local bits = { d.Name .. " [" .. valueOf(d) .. "]" }
        local attrs = attrsOf(d)
        if #attrs > 0 then bits[#bits + 1] = "attrs{" .. table.concat(attrs, ",") .. "}" end
        out[#out + 1] = table.concat(bits, " ")
    end
    return out
end

local function dumpModel(m, label)
    local p, sz = boxOf(m)
    say(string.format("== %s  %s  at %s%s", label, m:GetFullName(), posText(p),
        sz and string.format("  size %.0fx%.0fx%.0f", sz.X, sz.Y, sz.Z) or ""))
    local attrs = attrsOf(m)
    if #attrs > 0 then say("   attrs: " .. table.concat(attrs, " ")) end
    for _, line in ipairs(cfgLines(m)) do say("   cfg." .. line) end
    local kids, seen = {}, {}
    for _, c in ipairs(m:GetChildren()) do
        seen[c.Name] = (seen[c.Name] or 0) + 1
    end
    for n, c in pairs(seen) do kids[#kids + 1] = n .. (c > 1 and ("x" .. c) or "") end
    table.sort(kids)
    if #kids > 0 then say("   children: " .. table.concat(kids, ", ")) end
    -- the useful descendants: pads/parts, prompts, signs
    local shown = 0
    for _, d in ipairs(m:GetDescendants()) do
        if shown >= 70 then say("   … (descendants capped)"); break end
        local cls = safe(function() return d.ClassName end, "")
        if cls == "ProximityPrompt" then
            shown += 1
            say(string.format("   prompt %s  key=%s  action='%s'  object='%s'  enabled=%s  dist=%.0f",
                d.Name, tostring(safe(function() return d.KeyCode end, "?")),
                tostring(safe(function() return d.ActionText end, "")),
                tostring(safe(function() return d.ObjectText end, "")),
                tostring(safe(function() return d.Enabled end, "?")),
                tonumber(safe(function() return d.MaxActivationDistance end, 0)) or 0))
        elseif cls:find("TextLabel") or cls == "TextButton" then
            local txt = safe(function() return d.Text end, nil)
            if txt and tostring(txt) ~= "" then
                shown += 1
                say(string.format("   text %s = '%s'", d:GetFullName(), tostring(txt)))
            end
        elseif cls == "BillboardGui" or cls == "SurfaceGui" then
            local ad = safe(function() return d.Adornee end, nil)
            say("   gui " .. d:GetFullName() .. " adornee="
                .. (ad and ad:GetFullName() or "none"))
            shown += 1
        elseif cls:find("Part") or cls == "MeshPart" or cls == "UnionOperation" then
            local n = tostring(d.Name):lower()
            local tr = tonumber(safe(function() return d.Transparency end, 1)) or 1
            if interesting(d.Name) or n:find("trigger", 1, true)
                or n:find("pad", 1, true) or tr < 0.9 then
                shown += 1
                local dp, ds = boxOf(d)
                say(string.format("   part %s  at %s%s  transp=%.2f",
                    d:GetFullName(), posText(dp),
                    ds and string.format("  size %.0fx%.0fx%.0f", ds.X, ds.Y, ds.Z) or "",
                    tr))
            end
        end
    end
end

local function contextActions()
    say("")
    say("== actions the game offers RIGHT NOW ==")
    -- ▸ USE THE BILLBOARDS, NOT THE BUTTON LIST (dump §24 pattern): every
    --   action in the game is in Buttons — that is why the first runs listed
    --   all 70 of them with no key. Billboards holds ONLY the actions the game
    --   is offering at this spot, each with its own one-letter key label and
    --   the part it is adorned to.
    local cpa = safe(function()
        local pg = LP and LP:FindFirstChildOfClass("PlayerGui")
        local gv = pg and pg:FindFirstChild("GuiViews")
        local hud = gv and gv:FindFirstChild("HUD")
        local gw = hud and hud:FindFirstChild("MainHUD")
        return (gw and gw:FindFirstChild("PCGP_ContextActions"))
            or (hud and hud:FindFirstChild("PCGP_ContextActions"))
    end, nil)
    if not cpa then
        say("   PCGP_ContextActions NOT FOUND")
        return
    end
    local function keyOf(b)
        local texts, key = {}, nil
        for _, d in ipairs(safe(function() return b:GetDescendants() end, {})) do
            if d:IsA("TextLabel") and d.Text ~= "" then
                texts[#texts + 1] = d.Text
                if not key and d.Text:match("^%u$") then key = d.Text end
            end
        end
        return key, table.concat(texts, " | ")
    end
    local bills = safe(function() return cpa:FindFirstChild("Billboards") end, nil)
    local shown = 0
    if bills then
        for _, b in ipairs(bills:GetChildren()) do
            local on
            if b:IsA("LayerCollector") then
                on = b.Enabled == true
            elseif b:IsA("GuiObject") then
                on = b.Visible == true
            else
                on = false
            end
            if on then
                shown += 1
                local key, text = keyOf(b)
                local ad = safe(function() return b.Adornee end, nil)
                local p = ad and select(1, boxOf(ad)) or nil
                say(string.format("   ON  %s  key=%s  text='%s'  adornee=%s at %s",
                    b.Name, tostring(key or "?"), text,
                    ad and ad:GetFullName() or "none", posText(p)))
            end
        end
    else
        say("   Billboards NOT FOUND")
    end
    if shown == 0 then
        say("   (no billboard is on — the character is not on the pad, or nothing is offered here)")
    end
    local btns = safe(function() return cpa:FindFirstChild("Buttons") end, nil)
    if btns then
        local on, off = {}, 0
        for _, b in ipairs(btns:GetChildren()) do
            if b:IsA("GuiObject") and b.Visible then
                local key, text = keyOf(b)
                on[#on + 1] = string.format("%s(key=%s '%s')", b.Name, tostring(key or "?"), text)
            elseif b:IsA("GuiObject") then
                off += 1
            end
        end
        say(string.format("   visible buttons (%d, %d hidden): %s", #on, off,
            #on > 0 and table.concat(on, "  ·  ") or "none"))
    end
end

-- what the character is standing on (a pad is usually a transparent part)
local function standingOn()
    say("")
    say("== what you are standing on ==")
    local char = LP and LP.Character
    local root = char and char:FindFirstChild("HumanoidRootPart")
    if not root then say("   no character"); return end
    local params = safe(function()
        local p = RaycastParams.new()
        p.FilterType = Enum.RaycastFilterType.Exclude
        p.FilterDescendantsInstances = { char }
        return p
    end, nil)
    local hit = params and safe(function()
        return workspace:Raycast(root.Position, Vector3.new(0, -20, 0), params)
    end, nil)
    if not (hit and hit.Instance) then
        say("   raycast hit nothing within 20 studs")
        return
    end
    local inst = hit.Instance
    say(string.format("   %s  [%s]  at %s  (you are %.1f above it)",
        inst:GetFullName(), tostring(safe(function() return inst.ClassName end, "?")),
        posText(hit.Position), hit.Distance))
    local sz = safe(function() return inst.Size end, nil)
    if sz then
        say(string.format("   size %.1fx%.1fx%.1f  transp=%.2f  collide=%s  touch=%s",
            sz.X, sz.Y, sz.Z,
            tonumber(safe(function() return inst.Transparency end, 0)) or 0,
            tostring(safe(function() return inst.CanCollide end, "?")),
            tostring(safe(function() return inst.CanTouch end, "?"))))
    end
    local attrs = attrsOf(inst)
    if #attrs > 0 then say("   attrs: " .. table.concat(attrs, " ")) end
    local chain, p = {}, inst
    for _ = 1, 6 do
        p = p and p.Parent
        if not p or p == workspace then break end
        table.insert(chain, 1, p.Name)
    end
    if #chain > 0 then say("   under: " .. table.concat(chain, " / ") .. " / " .. inst.Name) end
end

-- everything close enough to be the thing you are supposed to use
local function nearby(radius)
    radius = radius or 30
    say("")
    say("== within " .. radius .. " studs (prompts, pad parts, labels) ==")
    local char = LP and LP.Character
    local root = char and char:FindFirstChild("HumanoidRootPart")
    if not root then say("   no character"); return end
    local here = root.Position
    local function guiSpot(d)
        local p = d
        for _ = 1, 5 do
            if not p then return nil end
            local ad = safe(function() return p.Adornee end, nil)
            if ad then return safe(function() return ad.Position end, nil), ad end
            if p:IsA("BasePart") then return safe(function() return p.Position end, nil), p end
            p = p.Parent
        end
        return nil
    end
    local prompts, pads, labels = {}, {}, {}
    for _, d in ipairs(safe(function() return workspace:GetDescendants() end, {})) do
        local cls = safe(function() return d.ClassName end, "")
        if cls == "ProximityPrompt" then
            local par = safe(function() return d.Parent end, nil)
            local pos = par and safe(function() return par.Position end, nil)
            if pos and (pos - here).Magnitude <= radius then
                prompts[#prompts + 1] = string.format(
                    "   prompt %s  key=%s  action='%s'  object='%s'  enabled=%s  dist=%.0f",
                    d:GetFullName(),
                    tostring(safe(function() return d.KeyCode end, "?")),
                    tostring(safe(function() return d.ActionText end, "")),
                    tostring(safe(function() return d.ObjectText end, "")),
                    tostring(safe(function() return d.Enabled end, "?")),
                    tonumber(safe(function() return d.MaxActivationDistance end, 0)) or 0)
            end
        elseif cls:find("Part") or cls == "UnionOperation" then
            local pos = safe(function() return d.Position end, nil)
            if pos and (pos - here).Magnitude <= radius then
                local tr = tonumber(safe(function() return d.Transparency end, 1)) or 1
                if interesting(d.Name) or tr < 0.6 then
                    local sz = safe(function() return d.Size end, nil)
                    pads[#pads + 1] = string.format(
                        "   part %s  at %s  dist=%.0f%s  transp=%.2f  collide=%s",
                        d:GetFullName(), posText(pos), (pos - here).Magnitude,
                        sz and string.format("  size %.1fx%.1fx%.1f", sz.X, sz.Y, sz.Z) or "",
                        tr, tostring(safe(function() return d.CanCollide end, "?")))
                end
            end
        elseif cls == "TextLabel" or cls == "TextButton" then
            local pos, ad = guiSpot(d)
            local txt = tostring(safe(function() return d.Text end, "") or "")
            if pos and txt ~= "" and (pos - here).Magnitude <= radius then
                labels[#labels + 1] = string.format("   text '%s'  at %s  dist=%.0f  %s%s",
                    txt, posText(pos), (pos - here).Magnitude, d:GetFullName(),
                    ad and ad ~= d and ("  -> " .. ad:GetFullName()) or "")
            end
        end
    end
    local function dump(list, cap, empty)
        for i = 1, math.min(#list, cap or 40) do say(list[i]) end
        if #list == 0 then say("   " .. empty) end
        if #list > (cap or 40) then say("   … (" .. (#list - (cap or 40)) .. " more)") end
    end
    say("   -- prompts")
    dump(prompts, 20, "(none)")
    say("   -- pad-like / see-through parts")
    dump(pads, 30, "(none)")
    say("   -- labels (a pad's key is usually one of these)")
    dump(labels, 40, "(none)")
end

-- the drop-off parts the script scans, with distance from here, and the
-- nearest one's insides (a prompt/trigger would live there)
local function dropTargets()
    say("")
    say("== Stores.DropOffs from here ==")
    local char = LP and LP.Character
    local root = char and char:FindFirstChild("HumanoidRootPart")
    local here = root and root.Position
    local stores = safe(function() return workspace:FindFirstChild("Stores") end, nil)
    local drops = stores and safe(function() return stores:FindFirstChild("DropOffs") end, nil)
    if not drops then
        say("   Stores.DropOffs NOT FOUND")
        return
    end
    local best, bestD
    for _, d in ipairs(drops:GetChildren()) do
        local p, sz = boxOf(d)
        local dist = (p and here) and (p - here).Magnitude or nil
        if dist and (not bestD or dist < bestD) then best, bestD = d, dist end
        say(string.format("   %s  at %s%s%s", d:GetFullName(), posText(p),
            sz and string.format("  size %.0fx%.0fx%.0f", sz.X, sz.Y, sz.Z) or "",
            dist and string.format("  %.0f studs from you", dist) or ""))
    end
    if best then
        say("   -- nearest: " .. best:GetFullName())
        local attrs = attrsOf(best)
        if #attrs > 0 then say("      attrs: " .. table.concat(attrs, " ")) end
        for _, d in ipairs(safe(function() return best:GetDescendants() end, {})) do
            local cls = safe(function() return d.ClassName end, "?")
            if cls == "ProximityPrompt" then
                say(string.format("      prompt %s key=%s action='%s' enabled=%s",
                    d:GetFullName(), tostring(safe(function() return d.KeyCode end, "?")),
                    tostring(safe(function() return d.ActionText end, "")),
                    tostring(safe(function() return d.Enabled end, "?"))))
            elseif cls == "TextLabel" or cls == "TextButton" then
                say(string.format("      text %s = '%s'", d:GetFullName(),
                    tostring(safe(function() return d.Text end, ""))))
            else
                say("      " .. cls .. " " .. d.Name)
            end
        end
        if #safe(function() return best:GetDescendants() end, {}) == 0 then
            say("      (no children — the part itself is the whole pad)")
        end
    end
end

-- the machines near you: is a harvester spawned, and is its tank readable?
local function equipmentNear()
    say("")
    say("== equipment within 120 studs ==")
    local char = LP and LP.Character
    local root = char and char:FindFirstChild("HumanoidRootPart")
    local here = root and root.Position
    local equip = safe(function()
        return workspace:FindFirstChild("Objects")
            and workspace.Objects:FindFirstChild("Equipment")
    end, nil)
    if not equip or not here then say("   Objects.Equipment NOT FOUND"); return end
    local any = 0
    for _, m in ipairs(equip:GetChildren()) do
        local p = safe(function() return m:GetPivot().Position end, nil)
        local dist = p and (p - here).Magnitude or nil
        if dist and dist <= 120 then
            any += 1
            say(string.format("   %s  at %s  %.0f studs", m:GetFullName(), posText(p), dist))
            local attrs = attrsOf(m)
            if #attrs > 0 then say("      attrs: " .. table.concat(attrs, " ")) end
            for _, line in ipairs(cfgLines(m)) do say("      cfg." .. line) end
        end
    end
    if any == 0 then say("   (none — spawn the harvester/trailer here first)") end
end

local function signsAnywhere()
    say("")
    say("== signs / texts that mention fulfill / ship / drop / sell ==")
    local char = LP and LP.Character
    local root = char and char:FindFirstChild("HumanoidRootPart")
    local here = root and root.Position
    local localHits, farHits = {}, {}
    for _, d in ipairs(safe(function() return workspace:GetDescendants() end, {})) do
        local cls = safe(function() return d.ClassName end, "")
        if cls:find("TextLabel") or cls == "TextButton" then
            local txt = tostring(safe(function() return d.Text end, "") or "")
            local low = txt:lower()
            if low:find("fulfill", 1, true) or low:find("fulfil", 1, true)
                or low:find("ship", 1, true) or low:find("drop", 1, true)
                or low:find("sell", 1, true) then
                -- a label's spot is its gui's adornment, or the part holding it
                local p, probe = nil, d
                for _ = 1, 5 do
                    if not probe then break end
                    local ad = safe(function() return probe.Adornee end, nil)
                    if ad then p = select(1, boxOf(ad)); break end
                    if probe:IsA("BasePart") then p = safe(function() return probe.Position end, nil); break end
                    probe = probe.Parent
                end
                local dist = (p and here) and (p - here).Magnitude or nil
                local line = string.format("   '%s'  at %s%s  %s", txt, posText(p),
                    dist and string.format("  %.0f studs", dist) or "", d:GetFullName())
                if dist and dist <= 60 then
                    localHits[#localHits + 1] = line
                elseif #farHits < 12 then
                    farHits[#farHits + 1] = line
                end
            end
        end
    end
    say("   -- near you (<=60 studs)")
    if #localHits == 0 then say("      (none)") end
    for _, line in ipairs(localHits) do say(line) end
    say("   -- elsewhere (first 12)")
    if #farHits == 0 then say("      (none)") end
    for _, line in ipairs(farHits) do say(line) end
end

local function oldTargets()
    say("")
    say("== the other old sell targets (SellArea / Buildings) ==")
    local objects = safe(function() return workspace:FindFirstChild("Objects") end, nil)
    local gv = safe(function() return workspace:FindFirstChild("GameplayVisuals") end, nil)
    local sell = gv and safe(function() return gv:FindFirstChild("SellArea") end, nil)
    if sell then
        for _, d in ipairs(sell:GetChildren()) do
            local p, sz = boxOf(d)
            say(string.format("   SellArea.%s [%s]  at %s%s", d.Name,
                safe(function() return d.ClassName end, "?"), posText(p),
                sz and string.format("  size %.0fx%.0fx%.0f", sz.X, sz.Y, sz.Z) or ""))
        end
    else
        say("   GameplayVisuals.SellArea NOT FOUND")
    end
    local buildings = objects and safe(function() return objects:FindFirstChild("Buildings") end, nil)
    if buildings then
        say("   Objects.Buildings:")
        for _, d in ipairs(buildings:GetChildren()) do
            local p = safe(function() return d:GetPivot().Position end, nil)
            say("     " .. d.Name .. " at " .. posText(p))
        end
    end
end

-- ── COMPANY ORDERS ─────────────────────────────────────────────────────────
-- ▸ WHY THIS IS A SEPARATE WALK. The order feature has to answer three things
--   no run has ever printed: where the game keeps the orders, what one order
--   holds (item / wanted count / how much is in / reward), and whether a crop's
--   GROW TIME is readable so the pick can rank "easiest first". Guessing any of
--   them is how the Fulfillment pad ended up being a navigation marker, so this
--   prints the tree the game actually has and lets the report name the fields.
local ORDER_WORDS = {
    "order", "contract", "request", "demand", "company", "cargo", "freight",
    "shipment", "fulfill", "deliver", "pallet", "goal", "want", "need",
    "inbound", "outbound",
}
local function orderish(name)
    local n = tostring(name):lower()
    if n == "" then return nil end
    for _, w in ipairs(ORDER_WORDS) do
        if n:find(w, 1, true) then return w end
    end
    return nil
end

-- one instance, one line: path, class, its value if it has one, its attrs
local function lineFor(d)
    local cls = safe(function() return d.ClassName end, "?")
    local bits = { tostring(d:GetFullName()), "[" .. cls .. "]" }
    if cls:find("Value", 1, true) then
        local v = safe(function() return d.Value end, nil)
        if typeof and typeof(v) == "Instance" then
            bits[#bits + 1] = "=" .. tostring(v:GetFullName())
        else
            bits[#bits + 1] = "=" .. tostring(v)
        end
    end
    if cls == "TextLabel" or cls == "TextButton" then
        local t = safe(function() return d.Text end, "")
        if t and tostring(t) ~= "" then bits[#bits + 1] = "text='" .. tostring(t) .. "'" end
    end
    local sz = safe(function() return d.Size end, nil)
    if sz and typeof and typeof(sz) == "Vector3" then
        bits[#bits + 1] = string.format("size %.0fx%.0fx%.0f at %s",
            sz.X, sz.Y, sz.Z, posText(safe(function() return d.Position end, nil)))
    end
    local attrs = attrsOf(d)
    if #attrs > 0 then bits[#bits + 1] = "attrs{" .. table.concat(attrs, ",") .. "}" end
    return table.concat(bits, "  ")
end

-- the whole tree under a folder/model, capped so a building cannot eat the report
local function treeUnder(root, cap)
    local kids, shown = {}, 0
    for _, d in ipairs(safe(function() return root:GetDescendants() end, {})) do
        if shown >= cap then
            kids[#kids + 1] = "      … (capped at " .. cap .. ")"
            break
        end
        shown += 1
        kids[#kids + 1] = "      " .. lineFor(d)
    end
    if #kids == 0 then kids[1] = "      (no descendants)" end
    return kids
end

local function orderTrees()
    say("")
    say("== COMPANY ORDERS: instances whose name says order/company/cargo/… ==")
    local found, shown = {}, 0
    for _, d in ipairs(safe(function() return workspace:GetDescendants() end, {})) do
        local why = orderish(d.Name)
        if why then
            found[#found + 1] = { d = d, why = why }
            if #found >= 40 then break end
        end
    end
    if #found == 0 then
        say("   (NOTHING in the streamed world is named like an order)")
        say("   workspace children: " .. table.concat((function()
            local n = {}
            for _, c in ipairs(safe(function() return workspace:GetChildren() end, {})) do
                n[#n + 1] = c.Name
            end
            table.sort(n)
            return n
        end)(), ", "))
        return
    end
    -- the small ones are the interesting ones: a data folder is dumped whole,
    -- a building is only named (its tree is dumpModel's job)
    for _, hit in ipairs(found) do
        if shown >= 25 then say("   … (25 order-named instances shown)"); break end
        shown += 1
        local d = hit.d
        local cls = safe(function() return d.ClassName end, "?")
        local nkids = #safe(function() return d:GetChildren() end, {})
        say(string.format("   %s  [%s]  matched '%s'  %d child(ren)",
            lineFor(d), cls, hit.why, nkids))
        if cls == "Folder" or cls == "Model" or cls:find("Value", 1, true) then
            if nkids > 0 and nkids <= 60 then
                for _, line in ipairs(treeUnder(d, 60)) do say(line) end
            elseif nkids > 60 then
                say("      (too many children to dump — names only)")
                local names = {}
                for _, c in ipairs(d:GetChildren()) do names[#names + 1] = c.Name end
                say("      " .. table.concat(names, ", "))
            end
        end
    end
end

-- ▸ THE BOARD IS PROBABLY TEXT, NOT DATA. A board the player reads is drawn
--   from somewhere, and the words on it are the one source that cannot lie
--   about what the Company wants. The first version of this probe only walked
--   workspace, so a ScreenGui board would have read as "no orders anywhere" —
--   PlayerGui is walked here too, and a label under an order-named parent
--   counts even when its own text does not.
local function boardTexts()
    say("")
    say("== COMPANY ORDERS: the words on the board (workspace + PlayerGui) ==")
    local roots = { workspace }
    local pg = LP and LP:FindFirstChildOfClass("PlayerGui")
    if pg then roots[#roots + 1] = pg end
    local hits, shown = 0, 0
    for _, root in ipairs(roots) do
        for _, d in ipairs(safe(function() return root:GetDescendants() end, {})) do
            local cls = safe(function() return d.ClassName end, "")
            if (cls == "TextLabel" or cls == "TextButton" or cls == "TextBox") then
                local txt = tostring(safe(function() return d.Text end, "") or "")
                local low = txt:lower()
                local underOrder = false
                local p = d
                for _ = 1, 8 do
                    p = p and p.Parent
                    if not p then break end
                    if orderish(p.Name) then underOrder = true; break end
                end
                local saysOrder = orderish(txt) ~= nil
                    or low:find("coins", 1, true) ~= nil
                    or low:find("reward", 1, true) ~= nil
                    or low:find("deliver", 1, true) ~= nil
                if txt ~= "" and (saysOrder or underOrder) then
                    hits += 1
                    if shown < 70 then
                        shown += 1
                        say(string.format("   '%s'%s  %s", txt,
                            underOrder and "  (under an order-named parent)" or "",
                            d:GetFullName()))
                    end
                end
            end
        end
    end
    if hits == 0 then
        say("   (no label anywhere says order/company/reward/coins — the board")
        say("    may be a 3D sign streamed only when you stand at it: run this")
        say("    again standing right in front of it)")
    elseif hits > shown then
        say("   … (" .. (hits - shown) .. " more label(s) not shown)")
    else
        say("   " .. hits .. " order-sounding label(s) read")
    end
end

-- what we could hand over: the store/warehouse inventory numbers
local function heldGoods()
    say("")
    say("== what we hold that could fill an order ==")
    local roots = {}
    local stores = safe(function() return workspace:FindFirstChild("Stores") end, nil)
    if stores then roots[#roots + 1] = stores end
    local objects = safe(function() return workspace:FindFirstChild("Objects") end, nil)
    if objects then
        for _, c in ipairs(objects:GetChildren()) do
            local n = c.Name:lower()
            if n:find("inventor", 1, true) or n:find("warehous", 1, true)
                or n:find("storage", 1, true) or n:find("stock", 1, true) then
                roots[#roots + 1] = c
            end
        end
    end
    if #roots == 0 then
        say("   (no Stores folder and no inventory/warehouse/storage child in Objects)")
        return
    end
    for _, r in ipairs(roots) do
        say("   " .. r:GetFullName() .. " [" .. tostring(safe(function() return r.ClassName end, "?")) .. "]")
        local nums, shown = {}, 0
        for _, d in ipairs(safe(function() return r:GetDescendants() end, {})) do
            local cls = safe(function() return d.ClassName end, "")
            if cls == "IntValue" or cls == "NumberValue" or cls == "BoolValue"
                or cls == "StringValue" then
                shown += 1
                if shown <= 60 then nums[#nums + 1] = "      " .. lineFor(d) end
            end
        end
        for _, line in ipairs(nums) do say(line) end
        if shown > 60 then say("      … (" .. (shown - 60) .. " more value(s))") end
        if shown == 0 then say("      (no plain values here — its contents are models/parts)") end
    end
end

-- ▸ THE GROW-TIME QUESTION. "easiest by seeding time and cost" needs a time per
--   crop. Two honest places it could live: the seed crate's own Configurations
--   (next to the Capacity and CostBillboard we already read) or the field cell
--   (PlantGrowth / GrowthMultiplier are known to be there). Both are printed in
--   full, plus FieldHelper's own exports — if no duration is in any of them the
--   report says so and the pick ranks on cost alone instead of a made-up table.
local function seedData()
    say("")
    say("== seed crates: every Configuration, looking for a grow time ==")
    local objects = safe(function() return workspace:FindFirstChild("Objects") end, nil)
    local gv = safe(function() return workspace:FindFirstChild("GameplayVisuals") end, nil)
    local folders = {
        objects and objects:FindFirstChild("DraggableObjects"),
        gv and gv:FindFirstChild("LockedDraggables"),
    }
    local names, shown = {}, 0
    for _, f in ipairs(folders) do
        if f then
            for _, c in ipairs(f:GetChildren()) do
                local cfg = c:FindFirstChild("Configurations") or c:FindFirstChild("Configuration")
                local seedName = nil
                if cfg then
                    for _, v in ipairs(cfg:GetDescendants()) do
                        local n = v.Name:lower()
                        if n:find("seed", 1, true) or n:find("type", 1, true) then
                            seedName = tostring(safe(function() return v.Value end, v.Name))
                        end
                    end
                end
                names[tostring(seedName or c.Name)] = (names[tostring(seedName or c.Name)] or 0) + 1
                if shown < 14 then
                    shown += 1
                    say("   " .. lineFor(c))
                    if cfg then
                        for _, line in ipairs(cfgLines(c)) do say("      cfg." .. line) end
                    else
                        say("      (no Configurations folder)")
                    end
                end
            end
        end
    end
    local kinds = {}
    for k in pairs(names) do kinds[#kinds + 1] = k end
    table.sort(kinds)
    say("   seed kinds seen: " .. (#kinds > 0 and table.concat(kinds, ", ") or "(none)"))
    if shown == 0 then say("   (no crates streamed — stand near the shop and run again)") end

    say("")
    say("== one field cell, every key: is a growth DURATION readable? ==")
    local ok, err = pcall(function()
        local mods = game:GetService("ReplicatedStorage"):FindFirstChild("Modules")
        local F = mods and mods:FindFirstChild("FieldHelper")
        if not F then say("   Modules.FieldHelper NOT FOUND"); return end
        F = require(F)
        local exports = {}
        for k, v in pairs(F) do exports[#exports + 1] = tostring(k) .. "(" .. type(v) .. ")" end
        table.sort(exports)
        say("   FieldHelper exports: " .. table.concat(exports, " "))
        local fields = objects and objects:FindFirstChild("Fields")
        local field = fields and fields:GetChildren()[1]
        if not field then say("   no Objects.Fields child streamed — nothing to read a cell from"); return end
        say("   field: " .. field:GetFullName())
        if type(F.GetCells) ~= "function" then say("   GetCells is not a function"); return end
        local cells = F.GetCells(field)
        if type(cells) ~= "table" then say("   GetCells returned " .. type(cells)); return end
        local firstKey, first
        local n = 0
        for k, v in pairs(cells) do
            n += 1
            if not firstKey then firstKey, first = k, v end
        end
        say("   " .. n .. " cell(s); one cell's keys:")
        if type(first) ~= "table" then
            say("      the cell is a " .. type(first) .. " — " .. tostring(first))
            return
        end
        local keys = {}
        for k in pairs(first) do keys[#keys + 1] = tostring(k) end
        table.sort(keys)
        for _, k in ipairs(keys) do
            local v = first[k]
            local vs
            if typeof and typeof(v) == "Vector3" then
                vs = string.format("(%.0f, %.0f, %.0f)", v.X, v.Y, v.Z)
            else
                vs = tostring(v)
            end
            say(string.format("      %-18s = %s  [%s]", k, vs, type(v)))
        end
        -- ▸ GROW TIME, NAME BY NAME. A whole-cell substring search is a lie
        --   here: PlantGrowth and GrowthMultiplier both contain "grow" and
        --   neither is a duration. A time key has to say time / duration / a
        --   unit / ripe / ready on its own.
        local TIME_WORDS = { "time", "duration", "sec", "minute", "hour",
            "day", "ripe", "ready", "harvestat", "growsec", "growtime" }
        local hits = {}
        for _, k in ipairs(keys) do
            local n = k:lower()
            for _, w in ipairs(TIME_WORDS) do
                if n:find(w, 1, true) then
                    hits[#hits + 1] = k .. "(" .. w .. ")"
                    break
                end
            end
        end
        table.sort(hits)
        if #hits > 0 then
            say("   → a time-shaped key IS on the cell: " .. table.concat(hits, ", "))
        else
            say("   → NO time-shaped key on a cell: grow time is not readable here")
        end
    end)
    if not ok then say("   cell read failed: " .. tostring(err)) end
end

-- one failing section must not eat the whole report
local function section(label, fn)
    local ok, err = pcall(fn)
    if not ok then
        say("   !! " .. label .. " FAILED: " .. tostring(err))
    end
end

local function run()
    say("== SPUD FULFILLMENT PROBE (read-only) · company orders ==")
    say("place " .. tostring(game.PlaceId) .. "  job " .. tostring(game.JobId))
    local char = LP and LP.Character
    local root = char and char:FindFirstChild("HumanoidRootPart")
    say("you: " .. tostring(LP and LP.Name or "?") .. " at " .. posText(root and root.Position))

    -- 0. the orders, first: this is the part the Company-order feature is
    --    waiting on, and it is the part that can be read from anywhere in the
    --    streamed area. Each runs behind a guard so one failure still leaves
    --    the rest of the report.
    section("order instances", orderTrees)
    section("board text", boardTexts)

    -- 1. the local answer first: what is offered here, what is underfoot, and
    --    what is close enough to be the pad. This is the part that names the
    --    unload action and its key.
    contextActions()
    standingOn()
    nearby(30)
    dropTargets()
    equipmentNear()
    section("goods we hold", heldGoods)
    section("seed crates + cell keys", seedData)

    -- 2. candidate buildings / models anywhere whose name says what this is
    say("")
    say("== candidate buildings/models ==")
    local seen = {}
    local shown = 0
    local function consider(m, why)
        if not (m and m:IsA("Model")) or seen[m] then return end
        seen[m] = true
        shown += 1
        dumpModel(m, why)
    end
    local objects = safe(function() return workspace:FindFirstChild("Objects") end, nil)
    local stores = safe(function() return workspace:FindFirstChild("Stores") end, nil)
    local function scanFolder(folder)
        for _, m in ipairs(folder and folder:GetChildren() or {}) do
            if interesting(m.Name) then
                consider(m, "folder " .. tostring(folder.Name))
            end
        end
    end
    scanFolder(objects and objects:FindFirstChild("Buildings"))
    scanFolder(stores and stores:FindFirstChild("Buildings"))
    scanFolder(stores)
    scanFolder(safe(function() return workspace:FindFirstChild("GameplayVisuals") end, nil))
    -- names deeper in the map (the building model may sit under a plot)
    for _, m in ipairs(safe(function() return workspace:GetDescendants() end, {})) do
        if shown >= 30 then break end
        if m:IsA("Model") and interesting(m.Name) and not seen[m] then
            consider(m, "workspace")
        end
    end
    if shown == 0 then
        say("   (no model name matched — stand closer so the area is streamed in)")
    end

    signsAnywhere()
    oldTargets()
end

-- ── the panel: the same lines, with COPY ───────────────────────────────────
local function finish()
    local text = table.concat(REPL, "\n")
    local copied = safe(function() setclipboard(text) return true end, false)
    local ok = pcall(function()
        local pg = LP and LP:FindFirstChildOfClass("PlayerGui")
        if not (pg and Instance and UDim2 and Color3) then return end
        local gui = Instance.new("ScreenGui")
        gui.Name = "SpudFulfillProbe"
        gui.ResetOnSpawn = false
        gui.DisplayOrder = 200
        gui.IgnoreGuiInset = true
        gui.Parent = pg

        local frame = Instance.new("Frame")
        frame.Name = "Panel"
        frame.Size = UDim2.new(0, 640, 0, 420)
        frame.Position = UDim2.new(0, 12, 0, 12)
        frame.BackgroundColor3 = Color3.fromRGB(18, 20, 24)
        frame.BorderSizePixel = 0
        frame.Parent = gui

        local title = Instance.new("TextLabel")
        title.Name = "Title"
        title.Size = UDim2.new(1, 0, 0, 26)
        title.BackgroundColor3 = Color3.fromRGB(32, 36, 42)
        title.BorderSizePixel = 0
        title.Text = "SPUD FULFILLMENT PROBE - read-only, company orders"
        title.TextColor3 = Color3.fromRGB(210, 230, 210)
        title.TextSize = 14
        title.Font = Enum.Font.Code
        title.Parent = frame

        local box = Instance.new("TextBox")
        box.Name = "Report"
        box.Size = UDim2.new(1, -16, 1, -76)
        box.Position = UDim2.new(0, 8, 0, 30)
        box.BackgroundColor3 = Color3.fromRGB(12, 14, 17)
        box.BorderSizePixel = 0
        box.TextColor3 = Color3.fromRGB(200, 210, 205)
        box.TextXAlignment = Enum.TextXAlignment.Left
        box.TextYAlignment = Enum.TextYAlignment.Top
        box.ClearTextOnFocus = false
        box.TextWrapped = false
        -- ▸ MULTI-LINE, because the report is now long. Without it a TextBox
        --   shows ONE line, so the whole order dump was invisible on screen and
        --   only the clipboard carried it.
        safe(function() box.MultiLine = true end)
        box.TextSize = 12
        box.Text = text
        safe(function() box.TextEditable = false end)
        box.Parent = frame

        local function button(label, x, width, colour)
            local b = Instance.new("TextButton")
            b.Name = label
            b.Size = UDim2.new(0, width, 0, 30)
            b.Position = UDim2.new(0, x, 1, -38)
            b.BackgroundColor3 = colour
            b.BorderSizePixel = 0
            b.Text = label
            b.TextColor3 = Color3.fromRGB(235, 240, 235)
            b.TextSize = 14
            b.Font = Enum.Font.Code
            b.Parent = frame
            return b
        end

        local copy = button("COPY REPORT", 8, 170, Color3.fromRGB(40, 96, 58))
        local close = button("CLOSE", 186, 100, Color3.fromRGB(70, 40, 40))

        safe(function()
            copy.MouseButton1Click:Connect(function()
                local put = pcall(function() setclipboard(text) end)
                copy.Text = put and "COPIED" or "NO CLIPBOARD"
                task.delay(1.5, function()
                    pcall(function() copy.Text = "COPY REPORT" end)
                end)
            end)
        end)
        safe(function()
            close.MouseButton1Click:Connect(function() gui:Destroy() end)
        end)
    end)
    if not ok then
        say("(the on-screen panel could not be built - the report above is the console)")
    elseif copied then
        say("(report copied to the clipboard; the panel has COPY REPORT / CLOSE)")
    else
        say("(panel on screen - press COPY REPORT to copy it)")
    end
end

local okRun, errRun = pcall(run)
if not okRun then
    say("PROBE ERROR: " .. tostring(errRun))
end
finish()
