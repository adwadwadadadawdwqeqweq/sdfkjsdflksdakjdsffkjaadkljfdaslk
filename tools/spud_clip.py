"""Decode the Android clipboard parcel that `service call clipboard 2` returns.

The in-game "get your key" button copies a link to the EMULATOR's clipboard, so
this is how the watcher gets it without anyone pasting anything into chat.
Android's parcel dump prints 32-bit words in hex, little-endian, and a string
inside a parcel is UTF-16LE — so: take the hex words (NOT the ASCII column,
which pads with dots), pack them back to bytes, decode UTF-16LE, and pull out
the printable runs. Validated against the live `No items.` reply, which is the
same shape with a URL-sized string in it.

    python tools/spud_clip.py <path-to-adb.exe>
"""
import re
import struct
import subprocess
import sys


def parcel_bytes(text):
    """Every 8-hex-digit word before the ASCII column, packed little-endian."""
    out = bytearray()
    for line in text.splitlines():
        head = line.split("'")[0]
        for w in re.findall(r"\b[0-9a-fA-F]{8}\b", head):
            out += struct.pack("<I", int(w, 16))
    return bytes(out)


def strings(data):
    s = data.decode("utf-16-le", errors="ignore")
    return [r for r in re.findall(r"[\x20-\x7e]{5,}", s) if not set(r) <= set("0123456789.")]


def main():
    if len(sys.argv) > 1:
        raw = subprocess.run([sys.argv[1], "-s", "127.0.0.1:16416", "shell",
                              "service", "call", "clipboard", "2",
                              "i32", "1", "i32", "1", "i32", "0"],
                             capture_output=True, text=True).stdout
    else:
        raw = sys.stdin.read()
    found = strings(parcel_bytes(raw))
    if not found:
        print("NOTHING")
        return 0
    for s in found:
        print(s)
    return 0


if __name__ == "__main__":
    sys.exit(main())
