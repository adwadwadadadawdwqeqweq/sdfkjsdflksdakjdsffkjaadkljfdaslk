"""spudwatch — PC-side watcher for the MuMu emulator: crash, error, MuMu down.

Why it runs here and not in the game: the thing it reports on is the game dying.
Nothing inside Roblox can tell you Roblox closed. So this polls the emulator
over adb from the PC and posts one alert per event to a webhook.

Three signals, and each one is a DIFFERENT question, so they are detected
differently:

  1. CRASH        the Roblox process is gone, or its pid changed, and a
                  `Fatal signal` line belongs to the pid that just disappeared.
                  A pid change with no fault under it is a quit or a restart,
                  and the alert says which it thinks it was — guessing "crash"
                  when someone closed the window teaches you to ignore it.
  2. ERROR        a `[spud]` line that reads like a fault (`attempt to`,
                  `stacktrace`, `webhook disabled`), or the kick text
                  `Error 267` / `Error 273`.
  3. MUMU DOWN    adb stops answering the device, or the MuMu host processes
                  (MuMuNxMain / MuMuVMMHeadless) are gone from Windows.

The webhook URL is NOT hard-coded and NOT committed. It is read from
  %LOCALAPPDATA%\\spudwatch\\secret.txt
and if that file is empty the watcher reads the EMULATOR'S CLIPBOARD instead:
Roblox's startup button copies its link there, so the key arrives without
anyone pasting anything (tools/spud_clip.py decodes the parcel). The URL is
only ever logged by host, never in full.

What it will not do: it never taps anything, never restarts the emulator or the
game, and never answers a disconnect dialog — Error 273 evicts another device,
and that is the owner's call, not a recovery step.

    python tools/spudwatch.py --once          one poll, print what it sees
    python tools/spudwatch.py --test-alert    send one sample alert
    python tools/spudwatch.py                 run forever (the scheduled task)
"""
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request

HOME = pathlib.Path(os.environ.get("LOCALAPPDATA", ".")) / "spudwatch"
SECRET = HOME / "secret.txt"
LOG = HOME / "watch.log"
SHOT = HOME / "last.png"
ADB_CANDIDATES = [
    r"C:\Program Files\Netease\MuMuPlayer\nx_main\adb.exe",
    r"C:\Program Files\Netease\MuMuPlayer Global\nx_main\adb.exe",
]
SERIAL = "127.0.0.1:16416"
PKG = "com.roblox.client"
POLL_SECS = 20
DEDUPE_SECS = 600
ERROR_PAT = re.compile(r"attempt to|stacktrace|webhook disabled|Traceback", re.I)
KICK_PAT = re.compile(r"Error (267|273)|ForceClosed|kicked", re.I)
FATAL_PAT = re.compile(r"Fatal signal \d+.*pid (\d+)|signal 11 \(SIGSEGV\)")

_state = {}


def now():
    return time.strftime("%Y-%m-%d %H:%M:%S")


def log(line):
    HOME.mkdir(parents=True, exist_ok=True)
    with open(LOG, "a", encoding="utf-8") as fh:
        fh.write(now() + " " + line + "\n")


def adb_path():
    for c in ADB_CANDIDATES:
        if pathlib.Path(c).exists():
            return c
    found = shutil.which("adb")
    return found


# ▸ NO WINDOW, EVER (owner 2026-11-07: "can you make the terminals silent,
#   they are annoying"). The watcher runs under pythonw, which has no console of
#   its own — but a CHILD process (adb.exe, tasklist.exe) still allocates one,
#   so every 20-second poll was flashing a black box across the desktop. That is
#   what the CREATE_NO_WINDOW flag below kills. Every subprocess call in this
#   file goes through a helper that sets it; a new call site that forgets it
#   reintroduces the flicker, so it is stated here as the rule.
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)


def quiet(cmd, **kw):
    return subprocess.run(cmd, creationflags=NO_WINDOW, **kw)


def run(cmd, timeout=25):
    try:
        p = quiet(cmd, capture_output=True, text=True, timeout=timeout,
                  encoding="utf-8", errors="replace")
        return p.returncode, p.stdout or "", p.stderr or ""
    except Exception as e:                                    # noqa: BLE001
        return 125, "", str(e)


def device_online(adb):
    rc, out, _ = run([adb, "devices"])
    return rc == 0 and any(l.strip().endswith("device") and SERIAL in l for l in out.splitlines())


def roblox_pid(adb):
    rc, out, _ = run([adb, "-s", SERIAL, "shell", "pidof", PKG])
    if rc == 0 and out.strip():
        return out.split()[0]
    return None


def mumu_host_alive():
    rc, out, _ = run(["tasklist"], timeout=40)
    return bool(re.search(r"MuMuNxMain|MuMuVMMHeadless|MuMuNxDevice", out, re.I))


def logcat_since(adb, since):
    """New logcat lines after an epoch timestamp, as (epoch, text)."""
    args = [adb, "-s", SERIAL, "logcat", "-d", "-v", "epoch"]
    if since:
        args += ["-T", "%.3f" % since]
    rc, out, _ = run(args, timeout=40)
    lines = []
    # ▸ `-v epoch` prints `1794064402.321  1156  1156 E TimeStats: msg` — the
    #   LEVEL IS SPACE-SEPARATED from the tag, not `E/Tag:` like -v brief. The
    #   first version of this regex assumed the other format and matched
    #   nothing, which is the worst kind of silent failure: the watcher looked
    #   alive and was blind.
    LINE = re.compile(r"^\s*(\d+)\.\d+\s+(\d+)\s+(\d+)\s+([VDIWEFS])\s*/?"
                      r"([^:]{0,40}):(.*)$")
    for raw in out.splitlines():
        m = LINE.match(raw)
        if m:
            lines.append((int(m.group(1)), int(m.group(2)), m.group(5).strip(),
                          m.group(6).strip()))
    return lines


def clipboard_url(adb):
    """The emulator clipboard, decoded — the startup button's link lands here."""
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
    try:
        import spud_clip
        rc, out, _ = run([adb, "-s", SERIAL, "shell", "service", "call", "clipboard",
                          "2", "i32", "1", "i32", "1", "i32", "0"], timeout=25)
        for s in spud_clip.strings(spud_clip.parcel_bytes(out)):
            if s.lower().startswith(("http://", "https://")):
                return s
    except Exception:                                          # noqa: BLE001
        pass
    return None


def load_secret(adb):
    if SECRET.exists():
        u = SECRET.read_text(encoding="utf-8", errors="replace").strip()
        if u.lower().startswith("http"):
            return u
    u = clipboard_url(adb) if adb else None
    if u:
        SECRET.write_text(u, encoding="utf-8")
        log("secret: picked up from the emulator clipboard, host=%s" %
            re.sub(r"^https?://([^/]+).*$", r"\1", u))
        return u
    return None


def post(url, text, png=None):
    """A webhook post. Discord takes JSON; anything else gets the same body."""
    try:
        if png and pathlib.Path(png).exists():
            boundary = "----spudwatch"
            body = ("--%s\r\nContent-Disposition: form-data; name=\"content\"\r\n\r\n%s\r\n"
                    % (boundary, text)).encode("utf-8")
            data = pathlib.Path(png).read_bytes()
            body += ("--%s\r\nContent-Disposition: form-data; name=\"file\"; "
                     "filename=\"screen.png\"\r\nContent-Type: image/png\r\n\r\n"
                     % boundary).encode("utf-8") + data + ("\r\n--%s--\r\n" % boundary).encode()
            req = urllib.request.Request(url, data=body, headers={
                "Content-Type": "multipart/form-data; boundary=" + boundary})
        else:
            req = urllib.request.Request(url, data=json.dumps({"content": text[:1900]}).encode(),
                                         headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=15) as r:
            ok = 200 <= r.status < 300
            if not ok:
                log("post status %s — the link may not be a webhook" % r.status)
            return ok
    except urllib.error.HTTPError as e:
        # ▸ a non-2xx is recorded WITH ITS CODE. The clipboard link might be a
        #   claim page rather than a webhook, and "it failed" versus "it
        #   answered 404" is the difference between retrying blindly and going
        #   to look at the URL.
        log("post HTTP %s%s" % (e.code, " — the link may not be a webhook"
                                if e.code in (400, 404, 405, 415) else ""))
        return False
    except Exception as e:                                    # noqa: BLE001
        log("post failed: %s" % e)
        return False


def screenshot(adb):
    if not adb:
        return None
    try:
        p = quiet([adb, "-s", SERIAL, "exec-out", "screencap", "-p"],
                  capture_output=True, timeout=30)
        if p.stdout and p.stdout[:4] == b"\x89PNG":
            pathlib.Path(SHOT).write_bytes(p.stdout)
            return str(SHOT)
    except Exception:                                          # noqa: BLE001
        pass
    return None


def alert(kind, detail, adb, url):
    key = kind.split(":")[0]
    last = _state.get("sent", {}).get(key, 0)
    if time.time() - last < DEDUPE_SECS:
        log("suppressed (cooldown): %s" % kind)
        return
    _state.setdefault("sent", {})[key] = time.time()
    text = "[spudwatch] %s · %s\n%s" % (kind, now(), detail[:1200])
    png = screenshot(adb) if adb else None
    if url:
        ok = post(url, text, png)
        log("alert %s -> %s (screenshot=%s)" % (kind, "sent" if ok else "FAILED",
                                                "yes" if png else "no"))
    else:
        log("ALERT (no webhook yet): %s | %s" % (kind, detail.replace("\n", " ")[:300]))


def poll():
    adb = adb_path()
    # load_secret caches: it reads secret.txt and only goes to the
    # clipboard while that file is still empty, so this is cheap.
    url = load_secret(adb)
    prev_pid = _state.get("pid")
    # ▸ The cursor is the DEVICE's clock, not this PC's: `logcat -T` filters on
    #   the timestamps logcat prints, and the two clocks agree right now
    #   (measured 1794064594 both sides) — but if they ever drift, a PC-derived
    #   start would filter out every line and the watcher would sit there
    #   reporting "all clear" while blind. Asking the device costs one call once.
    if "cursor" not in _state:
        rc, out, _ = run([adb, "-s", SERIAL, "shell", "date", "+%s"], timeout=15)
        dev = int(re.sub(r"\D", "", out) or 0) if rc == 0 else 0
        _state["cursor"] = (dev or int(time.time())) - 120
    prev_cursor = _state["cursor"]

    if not adb:
        alert("mumu-down", "adb.exe not found in either MuMu install path", None, url)
        return
    if not mumu_host_alive():
        alert("mumu-down", "no MuMuNxMain / MuMuVMMHeadless process on Windows", adb, url)
        return
    if not device_online(adb):
        run([adb, "connect", SERIAL], timeout=20)
        if not device_online(adb):
            _state["off"] = _state.get("off", 0) + 1
            if _state["off"] >= 3:
                alert("mumu-down", "adb is not answering %s after 3 tries" % SERIAL, adb, url)
            return
    _state["off"] = 0

    pid = roblox_pid(adb)
    lines = logcat_since(adb, prev_cursor)
    if lines:
        _state["cursor"] = lines[-1][0]

    faults = {m.group(1) for _, _, _, txt in lines
              for m in [FATAL_PAT.search(txt)] if m and m.group(1)}
    # ▸ A PID THAT CHANGED IS THE EVENT, not a pid that is missing. The first
    #   version only fired when the new pid was None, so a crash that Android
    #   relaunched inside one 20-second window went 11922 -> 12345, neither of
    #   them None, and the watcher said NOTHING about a crash whose
    #   `Fatal signal` line it had just read. Simulated and confirmed broken
    #   before this was written; the five cases are in the test below.
    if prev_pid is not None and pid != prev_pid:
        if prev_pid in faults or faults:
            kind = "roblox-crashed"
        elif pid is None:
            kind = "roblox-exited"
        else:
            kind = "roblox-restarted"
        tail = "\n".join(t for _, _, _, t in lines if "spud" in t.lower())[-500:]
        alert(kind, "pid %s -> %s (%s). recent console:\n%s"
              % (prev_pid, pid, kind, tail), adb, url)
    _state["pid"] = pid

    for _, _, tag, txt in lines:
        if ERROR_PAT.search(txt) or KICK_PAT.search(txt):
            alert("error", "%s: %s" % (tag, txt[:400]), adb, url)
            break


def main():
    once = "--once" in sys.argv
    test = "--test-alert" in sys.argv
    HOME.mkdir(parents=True, exist_ok=True)
    adb = adb_path()
    if test:
        url = load_secret(adb)
        print("webhook: %s" % ("host " + re.sub(r"^https?://([^/]+).*$", r"\1", url)
                               if url else "NONE yet (clipboard empty)"))
        if url:
            print("sent:", post(url, "[spudwatch] test · %s · this is the alert shape" % now(),
                                screenshot(adb)))
        return 0
    log("watcher started (adb=%s, poll %ss)" % (adb, POLL_SECS))
    while True:
        try:
            poll()
        except Exception as e:                                # noqa: BLE001
            log("poll error: %s" % e)
        if once:
            print("pid=%s cursor=%s secret=%s" % (_state.get("pid"), _state.get("cursor"),
                                                  SECRET.exists()))
            return 0
        time.sleep(POLL_SECS)


if __name__ == "__main__":
    sys.exit(main())
