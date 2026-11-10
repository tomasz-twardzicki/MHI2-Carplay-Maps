"""v1.5.1-e: the MU1367 bridge after a gap in the frame sequence (disposable Debian container, no network).
The CarPlay build waits for a keyframe (and asks for one); the Android Auto build (ALTSCREEN_AA_SINGLE_IDR) keeps
delivering frames, because an Android phone sends one IDR per connection. Car test 2026-11-10: the AA cluster map froze.
Usage: python3 -I bridge_recovery.py CARPLAY_BRIDGE AA_BRIDGE H264SYNTH_DIR RESULT_JSON
SPDX-License-Identifier: GPL-3.0-or-later
"""
import json, mmap, os, random, struct, subprocess, sys, time
CP, AA, SYN, RESULT = sys.argv[1:5]
sys.path.insert(0, SYN)
import h264synth as hs
RING = '/ramdisk/carplay-alt-ring.bin'; SIZE, HDR, SLOT, MAGIC = 0x1000710, 0x10, 0x4001c, 0x43505247
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

def nal_types(ts):
    pes = bytearray(); out = []
    for i in range(0, len(ts) - 187, 188):
        p = ts[i:i + 188]; afc = (p[3] >> 4) & 3; off = 4 + (1 + p[4] if afc & 2 else 0)
        if afc & 1 and off < 188:
            d = p[off:]
            if p[1] & 0x40 and d[:3] == b'\0\0\1': d = d[9 + d[8]:]
            pes += d
    j = 0
    while True:
        k = pes.find(b'\0\0\1', j)
        if k < 0 or k + 3 >= len(pes): break
        out.append(pes[k + 3] & 0x1f); j = k + 3
    return out

def run(binary, name):
    for f in (RING, '/ramdisk/carplay-alt-force-idr.request'):
        if os.path.exists(f): os.unlink(f)
    out = '/tmp/%s.ts' % name
    log = open('/tmp/%s.log' % name, 'w')
    b = subprocess.Popen([binary, out], stdout=log, stderr=subprocess.STDOUT)
    t = time.time()
    while time.time() - t < 5:
        if os.path.exists(RING) and os.path.getsize(RING) == SIZE:
            with open(RING, 'r+b') as f:
                m = mmap.mmap(f.fileno(), SIZE)
            if struct.unpack_from('<I', m, 0)[0] == MAGIC: break
        time.sleep(0.02)
    time.sleep(0.3)
    if os.path.exists('/ramdisk/carplay-alt-force-idr.request'): os.unlink('/ramdisk/carplay-alt-force-idr.request')   # start-up request
    seq = [0]
    def put(typ, data, frame_no):
        seq[0] += 1; off = HDR + ((seq[0] - 1) & 63) * SLOT
        struct.pack_into('<I', m, off, 0)
        ns = time.monotonic_ns(); ntp = ((ns // 10**9) << 32) | (((ns % 10**9) << 32) // 10**9)
        struct.pack_into('<IIIIII', m, off + 4, typ, len(data), 0, frame_no, ntp & 0xffffffff, ntp >> 32)
        m[off + 0x1c:off + 0x1c + len(data)] = data
        struct.pack_into('<I', m, off, seq[0]); struct.pack_into('<I', m, 0x0c, seq[0])
    rng = random.Random(3)
    put(1, avcc_config(), 0)
    sent_p = 0
    frames = [(1, True)] + [(n, False) for n in range(2, 31)] + [(n, False) for n in range(41, 101)]   # gap 31..40
    for n, idr in frames:
        _, vcl = hs.access_unit(idr, 3000 if idr else 900, rng, with_ps=False)
        put(2, avcc_frame([hs.AUD] + vcl), n); sent_p += not idr
        time.sleep(1 / 30)
    time.sleep(1.5); b.terminate(); b.wait(timeout=10); log.close()
    types = nal_types(open(out, 'rb').read())
    return types, sent_p, open('/tmp/%s.log' % name).read(), os.path.exists('/ramdisk/carplay-alt-force-idr.request')

cp_types, sent_p, cp_log, cp_req = run(CP, 'carplay')
aa_types, _, aa_log, aa_req = run(AA, 'aa')
for f in (RING, '/ramdisk/carplay-alt-force-idr.request'):
    if os.path.exists(f): os.unlink(f)
cp_p, aa_p = cp_types.count(1), aa_types.count(1)
print('carplay: P slices %d/%d, IDR request %s' % (cp_p, sent_p, cp_req)); print('aa: P slices %d/%d, IDR request %s' % (aa_p, sent_p, aa_req))
check('predictive-chain-gap' in cp_log and cp_p <= 29 + 2, 'CarPlay build: after the gap it waits for a keyframe (%d P slices)' % cp_p)
check('aa-chain-gap-kept' in aa_log and 'latency-reset' not in aa_log, 'AA build: gap logged and kept, no latency reset')
check(aa_p >= sent_p - 2, 'AA build: frames after the gap delivered (%d/%d P slices)' % (aa_p, sent_p))
check(not aa_req, 'AA build: no IDR request (the phone sends none)')
json.dump({'passed': not fails, 'checks': len(checks), 'failed': fails, 'p_slices_sent': sent_p, 'carplay_p_slices': cp_p,
           'aa_p_slices': aa_p, 'carplay_idr_request': cp_req, 'aa_idr_request': aa_req}, open(RESULT, 'w'), indent=2)
print('FAILED CHECKS: %d' % len(fails)); sys.exit(1 if fails else 0)
