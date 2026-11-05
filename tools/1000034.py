"""The seed shop must never click a control that deletes something.

Reported by reading the live console (2026-11-03, nobody pasted it):

  seed shop: clicking Players.ok_simba3.PlayerGui.GuiViews.HUD.Notifications
      .ConfirmAction.Content.ConfirmButton ('Delete Farm') - the Purchase button
  seed shop: the menu is still showing after 267 visible control(s) - nothing bought.

The script pressed a **destructive** control three times and called it a buy.
Root cause, read from the source: `harvestMenu` built ONE string out of
`guiTextOf(g) .. " " .. g.Name`, and the buy test looked for "purchase"/"buy"/
"confirm" in that joined string. `guiTextOf` only falls back to `btn.Name` when
the control has **no readable text** - so here the player-visible label was
`Delete Farm` while the *instance name* was `ConfirmButton`, and the name's
"confirm" outranked the label. The refuse list had no destructive word at all,
and a **third tier** then clicked "the first usable control" out of 267 buttons.

Three rules, all pinned here:

  * a danger word in **either** half refuses the click - refusing is the safe
    direction, and a control named `DeleteFarmButton` with no text is exactly as
    dangerous as one that says it out loud;
  * a buy word counts in the **label**, and the Name may speak only when the
    label cannot (an image-only Purchase control reads as its own Name) - which
    is what `spudShopBuyChoice` encodes;
  * there is **no arbitrary click tier**. A buy the game has not NAMED is not a
    buy: say what is on screen and click nothing.

THE SECOND INCIDENT (2026-11-03, same session, a fourth reload): the three rules
above stopped the destructive press and then bought nothing anyway, because the
loop took the **first** buy-shaped control and broke:

  seed shop: clicking Players.ok_simba3.PlayerGui.GuiViews.Stores.PalletStoreMenu
      .Main.Border.Content.InfoPanel.PurchaseButton ('Buy') - the Purchase button
  seed shop: balance 1519251 -> 1519251
  ⚠ the Rice purchase could NOT be confirmed   (toast: "You need to own the
      Forklift License!")

`PalletStoreMenu` is the **pallet** till - §5 v1.107 measured it, and its
Purchase answers the licence toast, never a seed. It is buy-shaped, it is not
dangerous, and it sorted ahead of the dialog. So a fourth rule, and it is a
**path** rule because that is the only thing that names which till it is:

  * a buy-shaped control whose path says `pallet` or `forklift` is passed over
    for any other buy-shaped control, and if it is the ONLY one the run clicks
    nothing and prints which till it refused.

Both words are measured, from that console line and that toast; nothing else is
refused by path (rule 4 - an invented word would refuse the real buy).

The pure predicates and the picker are run for real, and so is the **actual**
tier block sliced out of `buySeedAndFill` - the fixtures are the live shapes.

    python tools/1000034.py [path-to-luau.exe]
"""

import os
import pathlib
import re
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "1000051.lua"

PURE = ["spudShopDanger", "spudShopBuyChoice", "spudShopBuyPick"]


def extract(text: str, name: str) -> str:
    m = re.search(r"^    (?:local )?function " + name + r"\(", text, re.M)
    if not m:
        return ""
    tail = text[m.start():]
    end = re.search(r"\n    (?:local function |function |-- )", tail[10:])
    block = tail[: end.start() + 10] if end else tail
    return "\n".join(l[4:] if l.startswith("    ") else l for l in block.splitlines())


def words_table(text: str) -> str:
    m = re.search(r"^    spudShopDangerWords = \{[\s\S]*?\}\n", text, re.M)
    if not m:
        return ""
    return "\n".join(l[4:] if l.startswith("    ") else l
                     for l in m.group(0).splitlines())


def region(text: str, start: str, end: str) -> str:
    """From one marker to the next — the tier block nested in buySeedAndFill."""
    a = text.find(start)
    if a < 0:
        return ""
    b = text.find(end, a + len(start))
    return text[a:b] if b > a else text[a:]


PRE = r"""
local logs = {}
function log(msg) logs[#logs + 1] = tostring(msg) end
"""

POST = r"""
local fails = 0
local function check(name, ok, detail)
    if not ok then fails = fails + 1 end
    print(string.format("%-56s %s%s", name, ok and "PASS" or "FAIL",
        detail and ("  " .. detail) or ""))
end

-- a button shaped exactly like the ones the live shop showed. `label` is what
-- guiTextOf returns (Text, else the first TextLabel, else the NAME), `name` is
-- the instance Name - both already lowercased by harvestMenu. `path` is the
-- control's FULL path as the build reads it (lowercased); with none it is the
-- HUD default, which is what every notification-style fixture gets.
local function mk(label, name, path)
    return {
        label = label,
        name = name,
        text = label .. " " .. name,
        btn = {
            Name = name,
            GetFullName = function(self)
                return path or ("GuiViews.HUD." .. self.Name)
            end,
        },
    }
end

-- the real tier block, run against a fixture list. `want`/`seedName` are the
-- locals the block closes over in the build.
local want = "wheat"
local seedName = "Wheat"
local function decide(btns)
    local got, whyGot
    for _ = 1, 1 do
%%TARGET_BLOCK%%
        got, whyGot = target, why
    end
    return got, whyGot
end

local function pick(label, name)
    local b = decide({ mk(label, name) })
    return b and b.btn.Name
end

-- ── 1. the incident: a 'Delete Farm' label with a ConfirmButton name ───────
check("the buy test reads the LABEL, not the instance name",
    spudShopBuyChoice("Delete Farm", "ConfirmButton") == false,
    "the joined string is what matched 'confirm' before")
check("the danger test sees 'delete' in the label",
    spudShopDanger("Delete Farm", "ConfirmButton") == "delete")
check("so that control is never clicked",
    pick("delete farm", "confirmbutton") == nil)

-- ── 2. a buy-shaped control that is dangerous is REFUSED, and said out loud ─
logs = {}
check("a confirm-labelled delete button is not a buy",
    spudShopBuyChoice("Confirm", "DeleteFarmButton") == true
    and spudShopDanger("Confirm", "DeleteFarmButton") == "delete")
check("clicking it refuses and names the refusal",
    pick("confirm", "deletefarmbutton") == nil
    and table.concat(logs, " "):find("REFUSED", 1, true) ~= nil,
    logs[1])
check("the danger word can come from the NAME alone",
    spudShopDanger("Purchase", "CancelPurchase") == "cancel")

-- ── 3. what a real purchase looks like still gets clicked ─────────────────
local bought = { decide({ mk("purchase", "confirmbutton") }) }
check("a Purchase label with a ConfirmButton name is a buy",
    bought[1] and bought[1].btn.Name == "confirmbutton")
check("and the reason names it as the Purchase button", bought[2] == "the Purchase button",
    tostring(bought[2]))
check("a readable 'buy now' label is a buy", pick("buy now", "Frame1") == "Frame1")
check("a Confirm label is a buy", pick("confirm", "Ok") == "Ok")
check("a Checkout label is a buy", pick("checkout", "Panel") == "Panel")

-- ── 4. the image-only control: guiTextOf fell back to the Name ────────────
-- 2026-11-02's live purchase dialog draws its title and its green button as
-- images, so label == name there. The Name must be allowed to speak THEN.
check("an image-only control speaks through its Name",
    spudShopBuyChoice("purchasebutton", "purchasebutton") == true)
check("and it gets clicked", pick("purchasebutton", "purchasebutton") == "purchasebutton")
check("no readable text at all still reads the Name",
    spudShopBuyChoice("", "buyseeds") == true)
check("but an empty pair is not a buy", spudShopBuyChoice("", "") == false)
check("and nil halves do not crash", spudShopBuyChoice(nil, nil) == false)

-- ── 5. the money words ────────────────────────────────────────────────────
check("'Buy with Robux' is buy-shaped and refused",
    spudShopBuyChoice("buy with robux", "RobuxButton") == true
    and spudShopDanger("buy with robux", "RobuxButton") == "robux")
check("so a robux button is never clicked",
    pick("buy with robux", "robuxbutton") == nil)
check("a 'Sell' label is refused", spudShopDanger("sell cart", "X") == "sell")
check("a 'Close' label is refused", spudShopDanger("close", "X") == "close")
check("a tile with the seed's own word is still the tile",
    (function()
        logs = {}
        local b, why = decide({ mk("wheat seeds 100", "TileButton") })
        return b and b.btn.Name == "TileButton" and why == "the Wheat tile"
    end)())
check("a seed tile named Cancel is refused, not clicked",
    pick("wheat seeds", "cancelbutton") == nil)

-- ── 6. no arbitrary-click tier: name what is on screen and press nothing ──
logs = {}
check("unrelated buttons click nothing",
    decide({ mk("herding mode", "ModeButton"), mk("open shop", "ShopButton") }) == nil)
check("and the line says so, with the count",
    (function()
        local t = table.concat(logs, " ")
        return t:find("clicking nothing", 1, true) ~= nil
            and t:find("2 visible button(s)", 1, true) ~= nil
    end)(), logs[1])

-- ── 7. a refused control does not stop the scan for a real one ────────────
logs = {}
check("the safe Purchase button is found past a dangerous one",
    (function()
        local b = decide({ mk("confirm", "deletefarmbutton"), mk("purchase", "ConfirmButton") })
        return b and b.btn.Name == "ConfirmButton"
    end)())
check("and the refusal is still logged",
    table.concat(logs, " "):find("REFUSED", 1, true) ~= nil)

-- ── 8. the pallet till is not the seed till (v1.143's incident) ───────────
-- The live path, from the console: the trip clicked THIS and called it "the
-- Purchase button", three times, and the balance never moved.
local palletPath = ("Players.ok_simba3.PlayerGui.GuiViews.Stores.PalletStoreMenu"
    .. ".Main.Border.Content.InfoPanel.PurchaseButton"):lower()
local dialogPath = ("Players.ok_simba3.PlayerGui.GuiViews.Stores.SeedShop"
    .. ".Content.Purchase"):lower()

check("the picker passes the till over for the dialog that sorts after it",
    (function()
        local c = spudShopBuyPick({
            { path = palletPath, b = mk("buy", "PurchaseButton", palletPath) },
            { path = dialogPath, b = mk("purchase", "Purchase", dialogPath) },
        })
        return c ~= nil and c.path == dialogPath
    end)(), "the old loop broke on the FIRST buy-shaped control")
check("the FORKLIFT word refuses too (the toast names it)",
    (function()
        local c = spudShopBuyPick({ { path = "gui.co.forkliftshop.buy", btn = mk("buy", "b") } })
        return c == nil
    end)())
check("a till-only screen says so instead of buying a licence",
    (function()
        local c, note = spudShopBuyPick({ { path = palletPath, btn = mk("buy", "b") } })
        return c == nil and note ~= nil and note:find("pallet", 1, true) ~= nil
    end)())
check("and names the path it refused",
    (function()
        local _, note = spudShopBuyPick({ { path = palletPath, btn = mk("buy", "b") } })
        return note ~= nil and note:find(palletPath, 1, true) ~= nil
    end)())
check("no candidates at all is nothing to say",
    (function()
        local c, note = spudShopBuyPick({})
        return c == nil and note == nil
    end)())
check("and a nil list does not crash",
    (function()
        local c = spudShopBuyPick(nil)
        return c == nil
    end)())
check("a plain safe control is still taken (no new tier)",
    (function()
        local c = spudShopBuyPick({ { path = dialogPath, btn = mk("purchase", "Purchase") } })
        return c ~= nil and c.path == dialogPath
    end)())

logs = {}
check("the whole click loop takes the dialog, not the till",
    (function()
        local b = decide({
            mk("buy", "PurchaseButton", palletPath),
            mk("purchase", "Purchase", dialogPath),
        })
        return b ~= nil and b.btn:GetFullName():lower() == dialogPath
    end)(), "the live run clicked the pallet till three times")
logs = {}
check("a till-only screen clicks NOTHING and prints the reason",
    (function()
        local b = decide({ mk("buy", "PurchaseButton", palletPath) })
        local t = table.concat(logs, " ")
        return b == nil and t:find("pallet", 1, true) ~= nil
    end)(), logs[1])

print(fails == 0 and "ALL OK" or (fails .. " FAILED"))
"""


def main() -> int:
    base = pathlib.Path(os.environ.get("LOCALAPPDATA", ".")) / "Temp" / "opencode" / "luau"
    exe = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else base / "luau.exe"
    src = SRC.read_text(encoding="utf-8")

    parts = [PRE, words_table(src)]
    for name in PURE:
        code = extract(src, name)
        if not code:
            print("missing " + name)
            return 2
        parts.append(code)

    tiers = region(src, "            local target, why, refused", "            clickedAny = true")
    if not tiers:
        print("missing the click tier block")
        return 2
    # de-indent 8 -> 0 and drop the trailing break the wrapper's own loop licenses
    tiers = "\n".join(l[12:] if l.startswith(" " * 12) else l
                      for l in tiers.rstrip().splitlines())

    fails = []

    # ── the old defect must not come back, in any of its three parts ──
    for pat, label, why in ((r"\bisPurchase\b", "no joined-text buy test",
                             "isPurchase is back - a joined label+name string is "
                             "what read 'Delete Farm' as the Purchase button"),
                            (r"\bforbidden\(", "no local refuse list",
                             "a local forbidden() list is back - the refuse rule "
                             "has to be a global the harness can run"),
                            (r"first usable control", "no arbitrary-click tier",
                             "the arbitrary click tier is back - 267 visible "
                             "buttons and whatever sorts first must never be a plan")):
        if re.search(pat, src):
            fails.append(why)
        else:
            print(f"{label:<56} PASS")

    # the two rules are globals, in the right order, and read both halves
    if not re.search(r"^    spudShopDangerWords = \{", src, re.M):
        fails.append("spudShopDangerWords is not a global table - the list is hidden")
    else:
        wt = words_table(src)
        missing = [w for w in ("robux", "premium", "gems", "sell", "cancel", "close",
                               "back", "exit", "delete", "destroy", "remove",
                               "reset", "unsubscribe", "leave") if f'"{w}"' not in wt]
        if missing:
            fails.append("the refuse list lost " + ", ".join(missing))
        else:
            print(f"{'the refuse list has every destructive word':<56} PASS")
    for fn in PURE:
        if not re.search(r"^    function " + fn + r"\(", src, re.M):
            fails.append(fn + " is not a global function (local budget / harness)")
    dd = extract(src, "spudShopDanger")
    if dd and ("label or" not in dd or "name or" not in dd):
        fails.append("spudShopDanger no longer reads BOTH the label and the Name - "
                     "a textless destructive button would pass")
    elif dd:
        print(f"{'danger refuses on either half':<56} PASS")
    bc = extract(src, "spudShopBuyChoice")
    if bc and "l ~= \"\" and l ~= n" not in bc.replace(" ", ""):
        pass  # whitespace-insensitive check below
    if bc and 'l ~= ""' not in bc:
        fails.append("spudShopBuyChoice no longer lets the Name speak only when "
                     "the label cannot - the image-only buy button would be missed")
    elif bc:
        print(f"{'the Name speaks only when the label cannot':<56} PASS")

    # the click loop must be the one that consults them, by the halves, not the join
    loop = region(src, "            local target, why, refused",
                  "            clickedAny = true")
    for need, why in (("spudShopBuyChoice(b.label, b.name)",
                       "the buy test does not read b.label/b.name - it is back "
                       "to the joined text"),
                      ("spudShopDanger(b.label, b.name)",
                       "the click loop does not consult spudShopDanger"),
                      ("a buy-shaped control was REFUSED",
                       "a refused buy-shaped control is swallowed silently"),
                      ("clicking nothing",
                       "the no-buy line is gone - a shop it cannot read would "
                       "say nothing")):
        if need not in loop:
            fails.append(why)
    if all(n in loop for n in ("spudShopBuyChoice(b.label, b.name)",
                               "spudShopDanger(b.label, b.name)",
                               "a buy-shaped control was REFUSED", "clicking nothing")):
        print(f"{'the click loop asks both rules by the halves':<56} PASS")
    if re.search(r"spudShopBuyChoice\((b\.text|txt)", loop):
        fails.append("the buy test is being handed the joined text again")

    # THE SECOND INCIDENT: the loop must not stop at the FIRST buy-shaped control.
    # It lives 1,519,251 coins deep in PalletStoreMenu, and it answers "You need
    # to own the Forklift License!" — so the path has to reach the picker and the
    # picker has to be the one that decides.
    for need, why in (("spudShopBuyPick(cands",
                       "the click loop never asks the picker - it is back to "
                       "clicking the first buy-shaped control it meets"),
                      ('path = tostring(b.btn:GetFullName()):lower()',
                       "the click loop does not carry each control's full path "
                       "to the picker - the till is only findable by path")):
        if need not in loop:
            fails.append(why)
    if "spudShopBuyPick(cands" in loop and \
            'path = tostring(b.btn:GetFullName()):lower()' in loop:
        print(f"{'the loop gathers candidates and lets the picker choose':<56} PASS")
    if re.search(r'target, why = b, "the Purchase button"\s*\n\s*break', loop):
        fails.append("the click loop still breaks at the first buy-shaped control - "
                     "that is the pallet till being clicked instead of the seed dialog")

    # harvestMenu has to keep the halves apart, or both rules are blind
    hm = region(src, "local function harvestMenu(top)", "local function crateCount()")
    if "label = lbl" not in hm or "name = tostring(g.Name):lower()" not in hm:
        fails.append("harvestMenu no longer records the label and the Name "
                     "separately - the join is the bug")
    else:
        print(f"{'harvestMenu keeps label and Name apart':<56} PASS")

    # the Shop counter probe asks the same question (it clicks too)
    if "spudShopBuyChoice(lbl, nm) and not spudShopDanger(lbl, nm)" not in src:
        fails.append("the Shop counter probe still picks its own way - it is the "
                     "other place that clicks a purchase control")
    else:
        print(f"{'the shop probe uses the same two rules':<56} PASS")

    # ── v1.144: the CLOSE judge is the third place that reads a Purchase
    # control, and it answers "did the dialog shut?" — live it read the
    # pallet till's PurchaseButton, reported the seed dialog "still open"
    # after it had closed, and the second crate was bought against a till
    # that was never shut. Same picker, same path rule.
    sp = region(src, "local function shownPurchase()",
                "local function closeDialog()")
    if "spudShopBuyPick(cands)" not in sp:
        fails.append("shownPurchase is back to returning the first purchase-shaped "
                     "control in GuiViews - a till on screen makes the dialog read "
                     "as still open")
    elif 'path = tostring(g:GetFullName()):lower()' not in sp:
        fails.append("shownPurchase gives the picker no path to judge - the till "
                     "and the dialog are the same word")
    elif re.search(r'if t:find\("purchase", 1, true\) then return g end', sp):
        fails.append("shownPurchase still short-circuits on the first match")
    else:
        print(f"{'the dialog judge refuses a till-shaped path':<56} PASS")

    body = "\n\n".join(parts) + "\n\n" + POST.replace("%%TARGET_BLOCK%%", tiers)
    with tempfile.NamedTemporaryFile("w", suffix=".lua", delete=False, encoding="utf-8") as fh:
        fh.write(body)
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
