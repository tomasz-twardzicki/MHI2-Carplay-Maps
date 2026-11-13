"""v1.5.2-e: the CarPlay bridge's low-latency backlog limit (disposable Debian container, no network).
A 2026-11 tester drive at 27/5 sent frames up to 145 KB; a key frame landing on the previous one peaked at 1377
queued TS packets, over the old 1024-packet limit, and each such peak became a latency reset (discard, wait, IDR).
The limit is now 2048 packets (about 250 ms at 12.288 Mbit/s). Two host builds (file output, which drains about
6400 packets/s) get the same input:
  burst A  two 145 KB frames back to back, then a small frame: about 1390 packets queued (car: 1377) -> no reset at 2048,
           a reset with the old 1024 limit;
  burst B  four 145 KB frames back to back, then a small frame: about 2650 packets queued -> a reset at 2048 too.
Usage: python3 -I backlog_limit.py BRIDGE_2048 BRIDGE_1024 H264SYNTH_DIR RESULT_JSON
SPDX-License-Identifier: GPL-3.0-or-later
"""
import json, mmap, os, random, struct, subprocess, sys, time
NEW, OLD, SYN, RESULT = sys.argv[1:5]
sys.path.insert(0, SYN)
import h264synth as hs
RING = '/ramdisk/carplay-alt-ring.bin'; IDR_REQ = '/ramdisk/carplay-alt-force-idr.request'
SIZE, HDR, SLOT, MAGIC = 0x1000710, 0x10, 0x4001c, 0x43505247
BIG = 145000
OUT = os.path.dirname(os.path.abspath(RESULT))
os.makedirs('/ramdisk', exist_ok=True)
fails = []; checks = []
def check(c, m):
    checks.append(m); print(('ok     ' if c else 'FAILED ') + m, flush=True)
    if not c: fails.append(m)

def avcc_frame(nals):
    return b''.join(struct.pack('>I', len(n)) + n for n in nals)

def avcc_config():
    s, p = hs.sps(), hs.pps()
    return bytes([1, s[1], s[2], s[3], 0xff, 0xe1]) + struct.pack('>H', len(s)) + s + bytes([1]) + struct.pack('>H', len(p)) + p

def run(binary, name, burst):
    for f in (RING, IDR_REQ):
        if os.path.exists(f): os.unlink(f)
    log = open(os.path.join(OUT, 'backlog-%s.log' % name), 'w')
    b = subprocess.Popen([binary, '/tmp/%s.ts' % name], stdout=log, stderr=subprocess.STDOUT)
    t = time.time()
    while time.time() - t < 5:
        if os.path.exists(RING) and os.path.getsize(RING) == SIZE:
            with open(RING, 'r+b') as f:
                m = mmap.mmap(f.fileno(), SIZE)
            if struct.unpack_from('<I', m, 0)[0] == MAGIC: break
        time.sleep(0.02)
    time.sleep(0.3)
    if os.path.exists(IDR_REQ): os.unlink(IDR_REQ)
    seq = [0]; n = [0]; rng = random.Random(7)
    def put(typ, data, frame_no):
        seq[0] += 1; off = HDR + ((seq[0] - 1) & 63) * SLOT
        struct.pack_into('<I', m, off, 0)
        ns = time.monotonic_ns(); ntp = ((ns // 10**9) << 32) | (((ns % 10**9) << 32) // 10**9)
        struct.pack_into('<IIIIII', m, off + 4, typ, len(data), 0, frame_no, ntp & 0xffffffff, ntp >> 32)
        m[off + 0x1c:off + 0x1c + len(data)] = data
        struct.pack_into('<I', m, off, seq[0]); struct.pack_into('<I', m, 0x0c, seq[0])
    def frame(idr, size):
        n[0] += 1
        _, vcl = hs.access_unit(idr, size, rng, with_ps=False)
        put(2, avcc_frame([hs.AUD] + vcl), n[0])
    put(1, avcc_config(), 0)
    frame(True, 3000)
    for _ in range(20): frame(False, 900); time.sleep(1 / 27)
    time.sleep(0.5)                                     # queue drained
    for _ in range(burst): frame(False, BIG); time.sleep(0.004)
    frame(False, 900)                                   # the limit is checked when this frame arrives
    time.sleep(1.5)                                     # drain
    for _ in range(10): frame(False, 900); time.sleep(1 / 27)
    time.sleep(0.5); b.terminate(); b.wait(timeout=10); log.close()
    return open(os.path.join(OUT, 'backlog-%s.log' % name)).read()

res = {}
log = run(NEW, 'new-a', 2); res['new_a_resets'] = log.count('latency-reset')
check('latency-limit packets=2048' in log, 'v1.5.2-e build logs its 2048-packet limit at start')
check(res['new_a_resets'] == 0, 'burst A (~1390 packets queued): no reset at 2048')
log = run(OLD, 'old-a', 2); res['old_a_resets'] = log.count('latency-reset')
check('latency-limit packets=1024' in log and res['old_a_resets'] >= 1, 'burst A with the old 1024 limit: reset (%d)' % res['old_a_resets'])
log = run(NEW, 'new-b', 4); res['new_b_resets'] = log.count('latency-reset')
check(res['new_b_resets'] >= 1 and 'limit=2048' in log, 'burst B (~2650 packets queued): a reset still happens at 2048 (%d)' % res['new_b_resets'])
for f in (RING, IDR_REQ):
    if os.path.exists(f): os.unlink(f)
json.dump({'passed': not fails, 'checks': len(checks), 'failed': fails, 'limit_packets': 2048, 'big_frame_bytes': BIG, **res},
          open(RESULT, 'w'), indent=2)
print('FAILED CHECKS: %d' % len(fails)); sys.exit(1 if fails else 0)
