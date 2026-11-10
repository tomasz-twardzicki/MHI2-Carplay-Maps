"""MU1367 v1.5.0-e end-to-end host test (disposable Debian container, no network):
fake gal hook -> patched aa-most-feeder (shipped feeder.conf) -> /ramdisk ring -> the real MU1367 altscreen-most-bridge
(ALTSCREEN_BRIDGE_FILE_OUTPUT: MPEG-TS to a file instead of /dev/mlb/isoTX2), while the real MU1367
carplay-cluster-supervisor runs idle with its video-cache cleanup active (no CarPlay phone).
Usage: python3 -I run_e2e.py BIN_DIR FEEDER_CONF H264SYNTH_DIR RESULT_JSON
SPDX-License-Identifier: GPL-3.0-or-later
"""
import json, os, random, socket, struct, subprocess, sys, threading, time
BIN, CONF, SYN, RESULT = sys.argv[1:5]
sys.path.insert(0, SYN)
import h264synth as hs

RING = '/ramdisk/carplay-alt-ring.bin'; LOCK = '/ramdisk/cpmap-video-cache.lock'
W = '/w'; os.makedirs(W); os.makedirs('/ramdisk', exist_ok=True); os.makedirs(W + '/prefs')
open(W + '/auto', 'w').close()
fails = []; checks = []
def check(c, m):
    print(('ok    ' if c else 'FAILED ') + m, flush=True); checks.append(m)
    if not c: fails.append(m)
def wait_for(fn, t=5.0):
    e = time.time() + t
    while time.time() < e:
        if fn(): return True
        time.sleep(0.02)
    return False
def sup_log():
    try: return open('/ramdisk/carplay-cluster-supervisor.log').read()
    except FileNotFoundError: return ''

with open(W + '/dmdt.sh', 'w') as f: f.write('#!/bin/sh\necho "$*" >> /w/dmdt.log\n')
with open(W + '/bridge.sh', 'w') as f: f.write('#!/bin/sh\nexec %s/altscreen-most-bridge /w/most.ts\n' % BIN)
os.chmod(W + '/dmdt.sh', 0o755); os.chmod(W + '/bridge.sh', 0o755)

# 1. The idle supervisor releases a ring left by an earlier CarPlay session (nobody holds a lease).
sup = subprocess.Popen([BIN + '/carplay-cluster-supervisor'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
check(wait_for(lambda: 'supervisor-started' in sup_log()), 'supervisor started')
with open(RING, 'wb') as f: f.write(struct.pack('<IIII', 0x43505247, 1, 3, 0)); f.truncate(0x1000710)
check(wait_for(lambda: not os.path.exists(RING)), 'idle supervisor releases a stale CarPlay ring')

# 2. Android Auto session: the hook's stream socket and ACK socket.
ack_path = W + '/ack.sock'
ack_srv = socket.socket(socket.AF_UNIX); ack_srv.bind(ack_path); ack_srv.listen(1)
srv = socket.socket(); srv.bind(('127.0.0.1', 0)); srv.listen(1)
env = dict(os.environ, PMCP_AA_CONF=CONF, PMCP_AA_STATUS=W + '/status.txt', PMCP_AA_RING=RING,
           PMCP_AA_BRIDGE=W + '/bridge.sh', PMCP_AA_DMDT=W + '/dmdt.sh', PMCP_AA_ACK=ack_path,
           PMCP_AA_FLUSH_DEV=W + '/flush.dev', PMCP_AA_KF_REQ='/ramdisk/carplay-alt-force-idr.request',
           PMCP_AA_RUNDIR=W, PMCP_AA_CP_READY='/ramdisk/carplay-bridge.ready', PMCP_AA_CACHE_LOCK=LOCK,
           PMCP_AA_PREF_DIR=W + '/prefs', PMCP_AA_AUTO_ENABLE=W + '/auto')
feeder = subprocess.Popen([BIN + '/aa-most-feeder', 'tcp://127.0.0.1:%d' % srv.getsockname()[1]], env=env)
t_spawn = time.time()
conn, _ = srv.accept()
check(time.time() - t_spawn >= 4.5, 'shipped settings: stream connects only after the 5 s settle (%.1f s)' % (time.time() - t_spawn))
check(open(W + '/dmdt.log').read().split('\n')[:2] == ['dc 72', 'sc 4 72'], 'MOST released before the stream connects')
ack_srv.settimeout(5); ack, _ = ack_srv.accept(); ack.setblocking(False)

ring_gone = []; stop = []
def watch():
    while not stop:
        if not os.path.exists(RING): ring_gone.append(time.time())
        time.sleep(0.03)
th = threading.Thread(target=watch); th.start()

rng = random.Random(11); N = 240; sent_p = 0; sent_idr = 0; acks = 0
conn.sendall(b''.join(hs.SC + n for n in (hs.sps(), hs.pps())))
for i in range(N):
    idr = i % 120 == 0
    au, _ = hs.access_unit(idr, 30000 if idr else 2500, rng)
    conn.sendall(au); sent_idr += idr; sent_p += not idr
    time.sleep(1 / 30)
    try: acks += len(ack.recv(4096))
    except BlockingIOError: pass
end = time.time() + 3
while time.time() < end:
    try:
        b = ack.recv(4096)
        if not b: break
        acks += len(b)
    except BlockingIOError: time.sleep(0.05)
stop.append(1); th.join()
check(not ring_gone, 'ring never removed while Android Auto streams (supervisor cleanup ran every 100 ms)')
check(sup_log().count('video-cache-released') == 1, 'supervisor released only the stale ring during the session')
check(acks == N, 'one ACK per frame (%d/%d)' % (acks, N))
conn.close()
feeder.wait(timeout=10)
check(feeder.returncode == 0, 'feeder exit 0')
check(wait_for(lambda: open(W + '/dmdt.log').read().split('\n')[:4] == ['dc 72', 'sc 4 72', 'dc 70 33', 'sc 4 70'], 8),
      'VW map restored after the session: %r' % open(W + '/dmdt.log').read().split('\n'))
check(wait_for(lambda: not os.path.exists(RING), 5), 'supervisor frees the 16 MB ring after the session')
sup.terminate(); sup.wait(timeout=5)

# 3. What the AID would receive: MPEG-TS from the real bridge.
ts = open(W + '/most.ts', 'rb').read()
check(len(ts) > 188 * 100 and len(ts) % 188 == 0 and all(ts[i] == 0x47 for i in range(0, len(ts), 188)), 'TS: %d packets, all synced' % (len(ts) // 188))
pes = {}; cur = {}
for i in range(0, len(ts), 188):
    p = ts[i:i + 188]; pid = ((p[1] & 0x1f) << 8) | p[2]; pusi = p[1] & 0x40; afc = (p[3] >> 4) & 3
    off = 4 + (1 + p[4] if afc & 2 else 0)
    if not afc & 1 or off >= 188: continue
    data = p[off:]
    if pusi and data[:3] == b'\0\0\1':
        if pid in cur: pes.setdefault(pid, []).append(cur[pid])
        hl = data[8]; cur[pid] = bytearray(data[9 + hl:])
    elif pid in cur: cur[pid] += data
for pid, b in cur.items(): pes.setdefault(pid, []).append(b)
video = max(pes.values(), key=len) if pes else []
types = []; aud = 0
for b in video:
    j = 0; b = bytes(b)
    while True:
        k = b.find(b'\0\0\1', j)
        if k < 0 or k + 3 >= len(b): break
        types.append(b[k + 3] & 0x1f); j = k + 3
nal = {t: types.count(t) for t in set(types)}
print('TS NAL types:', nal, 'PES:', len(video))
first_vcl = next((t for t in types if t in (1, 5)), None)
check(first_vcl == 5, 'first picture is an IDR')
k = types.index(5) if 5 in types else -1
check(k >= 2 and types[k - 2:k] == [7, 8], 'SPS and PPS in front of the IDR')
check(nal.get(9, 0) >= len(video) - 1, 'one AUD per access unit')
check(nal.get(1, 0) >= sent_p * 0.95, 'P slices delivered %d/%d' % (nal.get(1, 0), sent_p))
st = open(W + '/status.txt').read()
check('mode=most' in st and 'lease=0' in st and '-> map' in st, 'feeder status: most, policy map, lease released')
print(open(W + '/pmcp-aa-bridge.txt').read() if os.path.exists(W + '/pmcp-aa-bridge.txt') else 'no bridge summary')
json.dump({'passed': not fails, 'checks': len(checks), 'failed': fails, 'ts_packets': len(ts) // 188, 'nal_types': nal,
           'frames_sent': N, 'p_slices_sent': sent_p, 'acks': acks}, open(RESULT, 'w'), indent=2)
print('FAILED CHECKS: %d' % len(fails)); sys.exit(1 if fails else 0)
