"""v1.5.3-e: the startup animation in the real MU1367 bridge (disposable Debian container, no network).
The CarPlay build plays its built-in clip, then skips the frames that arrived meanwhile and waits for the IDR it
requested; without the clip it starts exactly as v1.5.2 (first ring entry, no IDR request). The Android Auto build has
no clip. The preference is the MU UI's animation.state (Java wire format, CRC32), the once-per-boot marker is
/ramdisk/carplay-v725-intro-played. A fake hook answers each IDR request with config + IDR.
  A  default (no saved preference), first connection: the 126 clip access units reach the TS byte for byte, then the
     requested IDR with SPS/PPS, then live frames; the marker is created.
  B  default, marker present (second connection in the boot): no clip, starts at the session's first IDR, no request.
  C  saved "off", no marker: no clip, no marker.
  D  saved "every connection", marker present: the clip plays, and again after a reconnect (ring generation change).
  E  Android Auto build, no marker: no clip, no IDR request, starts at the session's IDR.
Usage: python3 -I intro_clip.py CARPLAY_BRIDGE AA_BRIDGE CLIP_H264 H264SYNTH_DIR RESULT_JSON
SPDX-License-Identifier: GPL-3.0-or-later
"""
import json, mmap, os, random, shutil, struct, subprocess, sys, time, zlib
CP, AA, CLIP, SYN, RESULT = sys.argv[1:6]
sys.path.insert(0, SYN)
import h264synth as hs
RING = '/ramdisk/carplay-alt-ring.bin'; IDR_REQ = '/ramdisk/carplay-alt-force-idr.request'
MARKER = '/ramdisk/carplay-v725-intro-played'; PREFS = '/mnt/icab/persistent/cpmap-ui'
SIZE, HDR, SLOT, MAGIC = 0x1000710, 0x10, 0x4001c, 0x43505247
OUT = os.path.dirname(os.path.abspath(RESULT))
os.makedirs('/ramdisk', exist_ok=True)
fails = []; checks = []
def check(c, m):
    checks.append(m); print(('ok     ' if c else 'FAILED ') + m, flush=True)
    if not c: fails.append(m)

clip = open(CLIP, 'rb').read()
def split_aud(data):
    s = [i for i in range(len(data) - 4) if data[i:i + 5] == b'\0\0\0\1\x09']
    return [data[a:b] for a, b in zip(s, s[1:] + [len(data)])]
CLIP_AUS = split_aud(clip)

def avcc_frame(nals):
    return b''.join(struct.pack('>I', len(n)) + n for n in nals)
def avcc_config():
    s, p = hs.sps(), hs.pps()
    return bytes([1, s[1], s[2], s[3], 0xff, 0xe1]) + struct.pack('>H', len(s)) + s + bytes([1]) + struct.pack('>H', len(p)) + p

def preference(mode):
    shutil.rmtree(PREFS, ignore_errors=True)
    if mode is None: return
    os.makedirs(PREFS)
    body = 'format=1\nmode=%d\ngeneration=1\n' % mode
    open(PREFS + '/animation.state', 'w').write(body + 'crc32=%x\n' % zlib.crc32(body.encode()))

def access_units(ts):
    """Video PES payloads (PID 0x11) in order: one access unit each."""
    aus = []; cur = None
    for i in range(0, len(ts) - 187, 188):
        p = ts[i:i + 188]; pid = ((p[1] & 0x1f) << 8) | p[2]
        if pid != 0x11: continue
        afc = (p[3] >> 4) & 3; off = 4 + (1 + p[4] if afc & 2 else 0)
        if not afc & 1 or off >= 188: continue
        d = p[off:]
        if p[1] & 0x40 and d[:3] == b'\0\0\1':
            if cur is not None: aus.append(bytes(cur))
            cur = bytearray(d[9 + d[8]:])
        elif cur is not None: cur += d
    if cur is not None: aus.append(bytes(cur))
    return aus

def starts_idr(au):
    """The bridge writes AUD, SPS, PPS in front of a key frame (the synthetic frame carries its own AUD too)."""
    t = nal_types(au); return t[:3] == [9, 7, 8] and 5 in t

def nal_types(au):
    out = []; j = 0
    while True:
        k = au.find(b'\0\0\1', j)
        if k < 0 or k + 3 >= len(au): return out
        out.append(au[k + 3] & 0x1f); j = k + 3

def session(binary, name, mode, marker, reconnect=False, seconds=7.0):
    """Start the bridge, stream config + IDR + P frames at 30 fps, answer IDR requests. Returns (log, aus, info)."""
    for f in (RING, IDR_REQ):
        if os.path.exists(f): os.unlink(f)
    if marker: open(MARKER, 'w').close()
    elif os.path.exists(MARKER): os.unlink(MARKER)
    preference(mode)
    out = '/tmp/intro-%s.ts' % name
    log = open(os.path.join(OUT, 'intro-%s.log' % name), 'w')
    b = subprocess.Popen([binary, out], stdout=log, stderr=subprocess.STDOUT)
    t = time.time(); m = None
    while time.time() - t < 5:
        if os.path.exists(RING) and os.path.getsize(RING) == SIZE:
            with open(RING, 'r+b') as f: m = mmap.mmap(f.fileno(), SIZE)
            if struct.unpack_from('<I', m, 0)[0] == MAGIC: break
        time.sleep(0.02)
    rng = random.Random(5); st = {'seq': 0, 'frame': 0, 'requests': 0, 'requests_at_start': os.path.exists(IDR_REQ)}
    def put(typ, data):
        st['seq'] += 1; off = HDR + ((st['seq'] - 1) & 63) * SLOT
        struct.pack_into('<I', m, off, 0)
        ns = time.monotonic_ns(); ntp = ((ns // 10**9) << 32) | (((ns % 10**9) << 32) // 10**9)
        struct.pack_into('<IIIIII', m, off + 4, typ, len(data), 0, st['frame'], ntp & 0xffffffff, ntp >> 32)
        m[off + 0x1c:off + 0x1c + len(data)] = data
        struct.pack_into('<I', m, off, st['seq']); struct.pack_into('<I', m, 0x0c, st['seq'])
    def frame(idr):
        st['frame'] += 1
        _, vcl = hs.access_unit(idr, 3000 if idr else 700, rng, with_ps=False)
        put(2, avcc_frame([hs.AUD] + vcl))
    def stream(duration):
        put(1, avcc_config()); frame(True)
        end = time.time() + duration
        while time.time() < end:
            if os.path.exists(IDR_REQ):
                os.unlink(IDR_REQ); st['requests'] += 1; put(1, avcc_config()); frame(True)
            else: frame(False)
            time.sleep(1 / 30)
    stream(seconds)
    if reconnect:
        # A new phone video connection in the same bridge: the producer bumps the generation and restarts at 1.
        gen = struct.unpack_from('<I', m, 8)[0]
        struct.pack_into('<I', m, 0x0c, 0); st['seq'] = 0
        for i in range(64): struct.pack_into('<I', m, HDR + i * SLOT, 0)
        struct.pack_into('<I', m, 8, gen + 1)
        stream(seconds)
    time.sleep(0.5); b.terminate(); b.wait(timeout=10); log.close()
    text = open(os.path.join(OUT, 'intro-%s.log' % name)).read()
    return text, access_units(open(out, 'rb').read()), st

res = {}
# A: default policy, first connection of the boot.
log, aus, st = session(CP, 'a-default', None, False)
res['a'] = {'aus': len(aus), 'requests': st['requests']}
check('intro-policy=once-per-boot' in log and 'intro-start bytes=%d frames=126 fps=30' % len(clip) in log, 'A: default policy is once per boot; the built-in clip starts')
check(aus[:len(CLIP_AUS)] == CLIP_AUS, 'A: the %d clip access units reach the TS byte for byte' % len(CLIP_AUS))
check('intro-complete frames=126' in log and os.path.exists(MARKER), 'A: clip complete, once-per-boot marker created')
nxt = aus[len(CLIP_AUS)] if len(aus) > len(CLIP_AUS) else b''
check(starts_idr(nxt) and 'intro-live-resume-idr' in log and st['requests'] == 1, 'A: then the requested IDR with SPS/PPS (one request, answered)')
live = aus[len(CLIP_AUS) + 1:]
check(len(live) >= 50 and all(5 not in nal_types(x) for x in live), 'A: live P frames follow (%d), no stale frames from before the request' % len(live))
check('priority thread=input' in log and 'priority thread=writer' in log and 'target=14' in log, 'A: both bridge threads report the priority step (host build: unchanged, target 14)')
# B: second connection in the same boot.
log, aus, st = session(CP, 'b-played', None, True)
res['b'] = {'aus': len(aus), 'requests': st['requests']}
check('intro not played (already played in this boot)' in log and 'intro-start' not in log, 'B: marker present: no clip')
check(aus and starts_idr(aus[0]) and st['requests'] == 0 and not st['requests_at_start'], 'B: starts at the session\'s first IDR without an IDR request (as v1.5.2)')
check(len(aus) >= 150, 'B: every frame delivered (%d)' % len(aus))
# C: saved off.
log, aus, st = session(CP, 'c-off', 2, False)
res['c'] = {'aus': len(aus), 'requests': st['requests']}
check('intro-policy=off' in log and 'intro not played (off)' in log and not os.path.exists(MARKER), 'C: saved off: no clip, no marker')
check(aus and starts_idr(aus[0]) and st['requests'] == 0, 'C: starts at the session\'s first IDR without an IDR request')
# D: saved every connection, marker present, then a reconnect.
log, aus, st = session(CP, 'd-every', 0, True, reconnect=True)
res['d'] = {'aus': len(aus), 'requests': st['requests'], 'intro_starts': log.count('intro-start')}
check('intro-policy=every-connect' in log and log.count('intro-start') == 2 and log.count('intro-complete frames=126') == 2, 'D: every connection: clip at start and again after the reconnect')
check(aus[:len(CLIP_AUS)] == CLIP_AUS and st['requests'] >= 2 and 'reconnect intro skipped stale ring' in log, 'D: both clips end on an answered IDR request (%d)' % st['requests'])
# E: Android Auto build.
log, aus, st = session(AA, 'e-aa', None, False)
res['e'] = {'aus': len(aus), 'requests': st['requests']}
check(not any(k in log for k in ('intro-policy', 'intro-start', 'intro not played', 'intro-live')) and 'intro_frames=0' in log and not os.path.exists(MARKER), 'E: Android Auto build: no clip, no intro policy, no marker')
check(aus and starts_idr(aus[0]) and st['requests'] == 0 and len(aus) >= 150, 'E: Android Auto starts at the session IDR without a request (%d frames)' % len(aus))
for f in (RING, IDR_REQ, MARKER):
    if os.path.exists(f): os.unlink(f)
shutil.rmtree(PREFS, ignore_errors=True)
json.dump({'passed': not fails, 'checks': len(checks), 'failed': fails, 'clip_access_units': len(CLIP_AUS), 'clip_bytes': len(clip), **res},
          open(RESULT, 'w'), indent=2)
print('FAILED CHECKS: %d' % len(fails)); sys.exit(1 if fails else 0)
