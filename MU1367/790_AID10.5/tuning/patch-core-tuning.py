#!/usr/bin/env python3
"""Stream tuning for the 790 (AID 10.25") core.so (cluster stream and turn card).

Input must be the stock 790 core.so shared by MU1102, MU1367 and MU1440.
It is a separate build from the 791 core.so (different offsets, different display):
the cluster display (type 111) is advertised as 1010x376 px, 202x75 mm.
passive_listener_thread checks the negotiated stream width against 1010, so the
display size is left alone; only the options below change.

Each option rewrites one ARM `mov`/`movw rX, #imm` as `movw rX, #imm16`
(any value 0..65535), or the cluster URL string:

  --max-fps N         AirPlayCopyServerInfo @0x257c: maxFPS advertised for the
                      cluster display. Stock 40.
  --keyframe-interval N
                      passive_listener_thread @0x3b6c: core.so sends forceKeyFrame
                      whenever frame_count % N == 0. Stock 20. @0x3d28 is the same
                      constant passed to the "alt-periodic-force-keyframe" log line;
                      it is kept in sync.
  --cluster-content map|map-card
                      String @0x78c0 (32 bytes), used both as the cluster display's
                      initialURL and in the showUI command
                      (delayed_alt_activation_thread). Stock "map" =
                      maps:/car/instrumentcluster/map; "map-card" =
                      maps:/car/instrumentcluster, the map with Apple's turn card on it.
  --safe-area X,Y,W,H AirPlayCopyServerInfo create_area() for the cluster safeArea:
                      x @0x26b0, y @0x26a0, w @0x26a4, h @0x26a8, inside the
                      1010x376 view area. Stock 202,16,606,344.

Usage: patch-core-tuning.py [options] in.so out.so
"""
import argparse, hashlib, struct, sys

BASE_SHA = "a4bb6ce6e9e63a05cc1b6be20c5257983fb4dcbdf89f55528438acbd8edba8ee"
VIEW_W, VIEW_H = 1010, 376

# file offset (== vaddr) -> stock instruction
MAX_FPS = [(0x257C, 0xE3A02028)]                          # mov r2, #40
KEYFRAME = [(0x3B6C, 0xE3A02014), (0x3D28, 0xE3A02014)]   # mov r2, #20 (check, log)
SAFE_AREA = [(0x26B0, 0xE3A000CA),                        # x: mov r0, #202
             (0x26A0, 0xE3A01010),                        # y: mov r1, #16
             (0x26A4, 0xE300225E),                        # w: movw r2, #606
             (0x26A8, 0xE3A03F56)]                        # h: mov r3, #344

URL_OFF, URL_LEN = 0x78C0, 32
URLS = {"map": b"maps:/car/instrumentcluster/map",
        "map-card": b"maps:/car/instrumentcluster"}


def movw(stock, value):
    """Encode `movw rX, #value` for the destination register of the stock instruction."""
    if not 0 <= value <= 0xFFFF:
        sys.exit("value %d does not fit movw" % value)
    return 0xE3000000 | (value >> 12) << 16 | (stock & 0xF000) | (value & 0xFFF)


def safe_area(s):
    v = [int(x) for x in s.split(",")]
    if len(v) != 4 or min(v) < 0 or v[0] + v[2] > VIEW_W or v[1] + v[3] > VIEW_H or min(v[2:]) < 1:
        raise argparse.ArgumentTypeError("X,Y,W,H must fit inside %dx%d" % (VIEW_W, VIEW_H))
    return v


ap = argparse.ArgumentParser()
ap.add_argument("--max-fps", type=int)
ap.add_argument("--keyframe-interval", type=int)
ap.add_argument("--cluster-content", choices=sorted(URLS))
ap.add_argument("--safe-area", type=safe_area)
ap.add_argument("src")
ap.add_argument("dst")
a = ap.parse_args()

d = bytearray(open(a.src, "rb").read())
h = hashlib.sha256(d).hexdigest()
if h != BASE_SHA:
    sys.exit("unexpected core.so (sha256 %s), expected the stock 790 build" % h)

edits = [(MAX_FPS, [a.max_fps] * len(MAX_FPS)),
         (KEYFRAME, [a.keyframe_interval] * len(KEYFRAME)),
         (SAFE_AREA, a.safe_area or [None] * len(SAFE_AREA))]
for sites, values in edits:
    for (off, stock), value in zip(sites, values):
        assert struct.unpack_from("<I", d, off)[0] == stock, hex(off)
        if value is not None:
            struct.pack_into("<I", d, off, movw(stock, value))

assert d[URL_OFF:URL_OFF + URL_LEN] == URLS["map"] + b"\0"
if a.cluster_content:
    d[URL_OFF:URL_OFF + URL_LEN] = URLS[a.cluster_content].ljust(URL_LEN, b"\0")

open(a.dst, "wb").write(d)
print("%s max_fps=%s keyframe_interval=%s cluster_content=%s safe_area=%s sha256=%s" % (
    a.dst, a.max_fps or 40, a.keyframe_interval or 20, a.cluster_content or "map",
    ",".join(map(str, a.safe_area or [202, 16, 606, 344])), hashlib.sha256(d).hexdigest()))
