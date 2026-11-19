"""v1.5.1-e: boot-time MOST reclaim in the MU1367 bridge (disposable Debian container, no network).
On every boot in the 2026-11-10 exports, the factory video encoder opened isoTX2 about 15 s after the bridge, flushed
the driver queue, and the bridge's next write failed with ENOMEM; the bridge exited into the supervisor's full restart.
The bridge now re-asserts the cluster-map release (dmdt dc 72 + sc 4 72), reopens isoTX2 and resyncs the picture,
within the boot window and at most three times. Builds come from test-aa-host.py with a simulated ENOMEM:
  CP / AA   ENOMEM once at block 150 (CarPlay build / Android Auto build)
  EXHAUST   ENOMEM at block 100 and every 30 blocks after it
  WINDOW    ENOMEM once, outside the boot window
Usage: python3 -I most_reclaim.py CP AA EXHAUST WINDOW H264SYNTH_DIR FAKE_DMDT_LOG RESULT_JSON
SPDX-License-Identifier: GPL-3.0-or-later
"""
import json, mmap, os, random, struct, subprocess, sys, time
CP, AA, EXHAUST, WINDOW, SYN, DMDT_LOG, RESULT = sys.argv[1:8]
sys.path.insert(0, SYN)
import h264synth as hs
RING = '/ramdisk/carplay-alt-ring.bin'; IDR_REQ = '/ramdisk/carplay-alt-force-idr.request'
SIZE, HDR, SLOT, MAGIC = 0x1000710, 0x10, 0x4001c, 0x43505247
os.makedirs('/ramdisk', exist_ok=True)
OUT = os.path.dirname(os.path.abspath(RESULT))
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
        if afc & 1 and off < 188 and ((p[1] & 0x1f) << 8 | p[2]) == 0x11:
            d = p[off:]
            if p[1] & 0x40 and d[:3] == b'\0\0\1': d = d[9 + d[8]:]
            pes += d
    j = 0
    while True:
        k = pes.find(b'\0\0\1', j)
        if k < 0 or k + 3 >= len(pes): break
        out.append(pes[k + 3] & 0x1f); j = k + 3
    return out

def dmdt_calls():
    return open(DMDT_LOG).read().split('\n')[:-1] if os.path.exists(DMDT_LOG) else []

def run(binary, name, seconds=6.0, answer_idr=True):
    for f in (RING, IDR_REQ, DMDT_LOG):
        if os.path.exists(f): os.unlink(f)
    out = '/tmp/%s.ts' % name
    log = open(os.path.join(OUT, 'reclaim-%s.log' % name), 'w')
    b = subprocess.Popen([binary, out], stdout=log, stderr=subprocess.STDOUT)
    t = time.time()
    while time.time() - t < 5:
        if os.path.exists(RING) and os.path.getsize(RING) == SIZE:
            with open(RING, 'r+b') as f:
                m = mmap.mmap(f.fileno(), SIZE)
            if struct.unpack_from('<I', m, 0)[0] == MAGIC: break
        time.sleep(0.02)
    time.sleep(0.3)
    if os.path.exists(IDR_REQ): os.unlink(IDR_REQ)   # start-up request
    seq = [0]
    def put(typ, data, frame_no):
        seq[0] += 1; off = HDR + ((seq[0] - 1) & 63) * SLOT
        struct.pack_into('<I', m, off, 0)
        ns = time.monotonic_ns(); ntp = ((ns // 10**9) << 32) | (((ns % 10**9) << 32) // 10**9)
        struct.pack_into('<IIIIII', m, off + 4, typ, len(data), 0, frame_no, ntp & 0xffffffff, ntp >> 32)
        m[off + 0x1c:off + 0x1c + len(data)] = data
        struct.pack_into('<I', m, off, seq[0]); struct.pack_into('<I', m, 0x0c, seq[0])
    rng = random.Random(5)
    put(1, avcc_config(), 0)
    sent_p = 0; idr_sent_on_request = 0; exited_at = None
    n = 0; start = time.time()
    while time.time() - start < seconds:
        n += 1
        idr = n == 1
        if answer_idr and os.path.exists(IDR_REQ):
            os.unlink(IDR_REQ); idr = True; idr_sent_on_request += 1
        _, vcl = hs.access_unit(idr, 3000 if idr else 900, rng, with_ps=False)
        put(2, avcc_frame([hs.AUD] + vcl), n); sent_p += not idr
        if exited_at is None and b.poll() is not None: exited_at = time.time() - start
        time.sleep(1 / 30)
    if b.poll() is None:
        b.terminate(); b.wait(timeout=10)
    elif exited_at is None: exited_at = time.time() - start
    log.close()
    text = open(os.path.join(OUT, 'reclaim-%s.log' % name)).read()
    types = nal_types(open(out, 'rb').read()) if os.path.exists(out) else []
    return {'log': text, 'types': types, 'sent_p': sent_p, 'idr_on_request': idr_sent_on_request,
            'exited_by_itself': exited_at is not None, 'dmdt': dmdt_calls(), 'idr_request_left': os.path.exists(IDR_REQ)}

def after(log, marker):
    k = log.find(marker)
    return log[k:] if k >= 0 else ''

res = {}
# 1. CarPlay: reclaim, then the usual latency recovery asks for an IDR and resumes on it.
r = run(CP, 'cp'); res['carplay'] = {k: v for k, v in r.items() if k not in ('log', 'types')}
log = r['log']; tail = after(log, 'most-reclaim attempt=1')
check('MOST write failed: Cannot allocate memory' in log or 'MOST write failed: Out of memory' in log, 'CarPlay: ENOMEM write failure logged')
check('most-reclaim attempt=1 uptime_ms=' in log and 'dmdt=0/0' in log, 'CarPlay: reclaim re-asserted the cluster-map release (dmdt 0/0)')
check(r['dmdt'] == ['dc 72', 'sc 4 72'], 'CarPlay: dmdt called exactly as the supervisor release: %s' % r['dmdt'])
check('most-reclaim attempt=1 reopen=ok' in log, 'CarPlay: isoTX2 reopened')
check('most-reclaim-resync' in tail and 'latency-reset' in tail, 'CarPlay: picture resync through latency recovery')
check('latency-request-idr' in tail and r['idr_on_request'] >= 1 and 'latency-resume-idr' in tail, 'CarPlay: IDR requested and resumed on it')
check(not r['exited_by_itself'], 'CarPlay: bridge kept running (no supervisor restart)')
check(r['types'].count(5) >= 2 and r['types'].count(1) > 60, 'CarPlay: output continues after the reclaim (IDR %d, P %d)' % (r['types'].count(5), r['types'].count(1)))
check('reclaims=1' in log, 'CarPlay: one reclaim counted at stop')

# 2. Android Auto build: reclaim, no keyframe wait, no IDR request.
r = run(AA, 'aa', answer_idr=False); res['android_auto'] = {k: v for k, v in r.items() if k not in ('log', 'types')}
log = r['log']; tail = after(log, 'most-reclaim attempt=1')
check('most-reclaim attempt=1 reopen=ok' in log and r['dmdt'] == ['dc 72', 'sc 4 72'], 'AA: reclaimed with the same dmdt release')
check('most-reclaim-resync' in tail and 'latency-reset' not in log, 'AA: resync marked, no latency reset')
check(not r['idr_request_left'] and r['idr_on_request'] == 0, 'AA: no IDR request (the phone sends none)')
check(r['types'].count(1) >= r['sent_p'] - 25 and not r['exited_by_itself'], 'AA: frames keep flowing (P %d of %d sent)' % (r['types'].count(1), r['sent_p']))

# 3. Repeated ENOMEM: three reclaims, then the previous exit path.
r = run(EXHAUST, 'exhaust', seconds=7.0); res['exhaust'] = {k: v for k, v in r.items() if k not in ('log', 'types')}
log = r['log']
check(all('most-reclaim attempt=%d reopen=ok' % i in log for i in (1, 2, 3)) and 'attempt=4' not in log, 'exhaust: three reclaims, no fourth')
check('most-reclaim not-attempted reclaims=3 max=3' in log and r['exited_by_itself'], 'exhaust: fourth ENOMEM exits (supervisor restart path)')
check(r['dmdt'] == ['dc 72', 'sc 4 72'] * 3, 'exhaust: three dmdt releases')

# 4. Outside the boot window: no reclaim, exit as before.
r = run(WINDOW, 'window', seconds=4.0); res['window'] = {k: v for k, v in r.items() if k not in ('log', 'types')}
log = r['log']
check('most-reclaim not-attempted reclaims=0' in log and 'most-reclaim attempt' not in log and r['exited_by_itself'], 'window: no reclaim outside the boot window, exit as before')
check(r['dmdt'] == [], 'window: dmdt not called')

for f in (RING, IDR_REQ, DMDT_LOG):
    if os.path.exists(f): os.unlink(f)
json.dump({'passed': not fails, 'checks': len(checks), 'failed': fails, 'runs': res}, open(RESULT, 'w'), indent=2)
print('FAILED CHECKS: %d' % len(fails)); sys.exit(1 if fails else 0)
