"""Host test for aa-most-feeder with a fake hook, fake bridge and fake dmdt.
Usage: python3 -I run_host_test.py FEEDER_BINARY"""
import fcntl, json, os, random, signal, socket, struct, subprocess, sys, tempfile, time, zlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import h264synth as hs

FEEDER = os.path.abspath(sys.argv[1]); HERE = os.path.dirname(os.path.abspath(__file__))
fails = []
def check(cond, msg):
    print(('ok    ' if cond else 'FAILED ') + msg)
    if not cond: fails.append(msg)

def wait_for(fn, timeout=5.0):
    t = time.time()
    while time.time() - t < timeout:
        if fn(): return True
        time.sleep(0.02)
    return False

CS = {}   # case -> number of 'C' (v5 config-method request) bytes
KS = {}   # case -> number of 'K' (fresh IDR request) bytes on the ACK pipe; acks count only the other bytes
AT_CONNECT = {}   # case -> dmdt lines already written when the feeder connected to the stream (v3: takeover first)
FIRST_ACK_S = {}  # case -> seconds from the first frame sent to the first ACK byte
def run(case, mode, n_frames=60, kill_after=None, rate=None, idr_every=30, conf=None, kf_at=None, kf_file=False, pre=None, env_add=None, ack_idle=0.3, during=None):
    d = tempfile.mkdtemp(prefix='pmcp-aa-' + case + '-')
    P = lambda n: os.path.join(d, n)
    ack_path = P('ack.sock')
    ack_srv = socket.socket(socket.AF_UNIX); ack_srv.bind(ack_path); ack_srv.listen(1)
    srv = socket.socket(); srv.bind(('127.0.0.1', 0)); srv.listen(1)
    with open(P('feeder.conf'), 'w') as f: f.write(conf or '')
    env = dict(os.environ, PMCP_AA_CONF=P('feeder.conf'), PMCP_AA_STATUS=P('status.txt'), PMCP_AA_RING=P('ring.bin'),
               PMCP_AA_BRIDGE=os.path.join(HERE, 'fake_bridge.sh'), PMCP_AA_DMDT=os.path.join(HERE, 'fake_dmdt.sh'),
               PMCP_AA_ACK=ack_path, PMCP_AA_FLUSH_DEV=P('flush.dev'), FAKE_DMDT_LOG=P('dmdt.log'),
               FAKE_BRIDGE_OUT=P('bridge.jsonl'), PMCP_AA_KF_REQ=P('kf.request'), PMCP_AA_RUNDIR=d)
    # MU1367 v1.5.0-e: video cache lease and the MU menu map policy (empty preference directory = map on)
    os.mkdir(P('prefs')); open(P('auto.enable'), 'w').close()
    env.update(PMCP_AA_CACHE_LOCK=P('cache.lock'), PMCP_AA_PREF_DIR=P('prefs'), PMCP_AA_AUTO_ENABLE=P('auto.enable'))
    if env_add: env.update({k: v.replace('@DIR@', d) for k, v in env_add.items()})
    if pre: pre(P)
    if kf_at: env['FAKE_BRIDGE_KF_AT'] = ','.join(map(str, kf_at))
    if kf_file: open(P('kf.request'), 'w').close()        # left over: must not reach the hook in analyze mode
    if mode is not None: env['PMCP_AA_MODE'] = mode
    if rate is not None: env['PMCP_AA_RATE_KBPS'] = str(rate)
    feeder = subprocess.Popen([FEEDER, 'tcp://127.0.0.1:%d' % srv.getsockname()[1]], env=env)
    conn, _ = srv.accept(); AT_CONNECT[case] = list(dmdt_lines(P))
    ack_srv.settimeout(5); ack, _ = ack_srv.accept(); ack.setblocking(False)
    t_first = None
    rng = random.Random(7); expected = []; acks = 0; ks = 0; cs = 0
    def take(b):
        nonlocal acks, ks, cs
        if b and case not in FIRST_ACK_S: FIRST_ACK_S[case] = time.time() - t_first
        k = b.count(b'K'); c = b.count(b'C'); ks += k; cs += c; acks += len(b) - k - c
    conn.sendall(b''.join(hs.SC + n for n in (hs.sps(), hs.pps())))      # codec config replay, as the hook does
    time.sleep(0.02)
    for i in range(n_frames):
        idr = i % idr_every == 0
        au, vcl = hs.access_unit(idr, 60000 if idr else 1500, rng, slices=2 if i == idr_every else 1)
        expected.append(vcl)
        if t_first is None: t_first = time.time()
        if i % 7 == 3:                         # split inside a frame, shorter than the idle flush
            conn.sendall(au[:len(au) // 2]); time.sleep(0.002); conn.sendall(au[len(au) // 2:])
        else:
            conn.sendall(au)
        time.sleep(0.033)
        try: take(ack.recv(4096))
        except BlockingIOError: pass
        if during is not None and i == 10: during(P)
        if kill_after is not None and i == kill_after:
            time.sleep(0.1); feeder.send_signal(signal.SIGKILL); break
    if kill_after is None:
        time.sleep(0.3)
        last = time.time()
        while True:                            # read ACKs until none came for ack_idle seconds
            try:
                b = ack.recv(4096)
                if not b: break
                take(b); last = time.time()
            except BlockingIOError:
                if time.time() - last >= ack_idle: break
                time.sleep(0.02)
        conn.close()
    feeder.wait(timeout=5)
    KS[case] = ks; CS[case] = cs
    return d, P, expected, acks, feeder.returncode

def bridge_log(P):
    try: return [json.loads(l) for l in open(P('bridge.jsonl'))]
    except FileNotFoundError: return []

def frames_ok(entries, expected):
    frames = [e for e in entries if e.get('type') == 2]
    good = True
    for e, vcl in zip(frames, expected):
        data = bytes.fromhex(e['data']); i = 0; nals = []
        while i < len(data):
            n = struct.unpack('>I', data[i:i + 4])[0]; nals.append(data[i + 4:i + 4 + n]); i += 4 + n
        if i != len(data) or nals != vcl: good = False
    return good, len(frames)

def dmdt_lines(P):
    try: return open(P('dmdt.log')).read().split('\n')[:-1]
    except FileNotFoundError: return []

# A: full session in "most" mode, the hook closes the stream at the end
d, P, exp, acks, rc = run('A', 'most')
P_A = P
check(wait_for(lambda: len(dmdt_lines(P)) >= 4), 'A: dmdt release + restore %r' % dmdt_lines(P))
check(dmdt_lines(P) == ['dc 72', 'sc 4 72', 'dc 70 33', 'sc 4 70'], 'A: dmdt order')
e = bridge_log(P)
check(len(e) > 0 and e[0].get('type') == 1, 'A: avcC first')
if e and e[0].get('type') == 1:
    a = bytes.fromhex(e[0]['data']); sl = struct.unpack('>H', a[6:8])[0]
    check(a[0] == 1 and a[4] == 0xff and a[8:8 + sl] == hs.sps() and a[8 + sl + 3:] == hs.pps(), 'A: avcC = SPS/PPS, 4-byte lengths')
ok, nf = frames_ok(e, exp)
check(nf == len(exp) and ok, 'A: %d/%d frames AVCC, no AUD/SPS/PPS, NALs intact (2-slice IDR too)' % (nf, len(exp)))
check([x['seq'] for x in e if 'seq' in x] == list(range(1, len(e) + (0 if 'sigterm' in e[-1] else 1))), 'A: seq 1..N without gaps')
ts = [x['ts'] for x in e if x.get('type') == 2]
check(all(b > a for a, b in zip(ts, ts[1:])), 'A: NTP timestamps increase')
check(acks == len(exp), 'A: one ACK per frame (%d)' % acks)
check(any('sigterm' in x for x in e), 'A: bridge got SIGTERM from the guardian')
check(rc == 0, 'A: feeder exit 0')

# B: the hook SIGKILLs the feeder mid-stream; the guardian must still stop the bridge and give MOST back
d, P, exp, acks, rc = run('B', 'most', kill_after=20)
check(wait_for(lambda: len(dmdt_lines(P)) >= 4), 'B: guardian restored after SIGKILL %r' % dmdt_lines(P))
check(wait_for(lambda: any('sigterm' in x for x in bridge_log(P))), 'B: bridge stopped')
def pgrep_f(text):   # MU1367: the Debian test image has no procps
    found = []
    for e in os.listdir('/proc'):
        if e.isdigit() and int(e) != os.getpid():
            try: cmd = open('/proc/%s/cmdline' % e, 'rb').read().replace(b'\0', b' ')
            except OSError: continue
            if text.encode() in cmd: found.append(e)
    return found
check(pgrep_f(P('bridge.jsonl')) == [], 'B: no bridge left')

# C: analyze mode touches nothing
d, P, exp, acks, rc = run('C', 'analyze')
st = open(P('status.txt')).read(); print(st)
check(dmdt_lines(P) == [] and not os.path.exists(P('ring.bin')), 'C: no dmdt, no ring')
check('profil=66' in st and '800x480' in st and 'CAVLC' in st and 'klatki=60 IDR=2' in st, 'C: summary parsed')
check(acks == 60, 'C: ACK per frame (%d)' % acks)

# D: pacing - 200 KB/s with a 60 KB IDR every 5 frames must delay ACKs
d, P, exp, acks, rc = run('D', 'most', n_frames=40, rate=200, idr_every=5)
st = open(P('status.txt')).read()
dl = [l for l in st.split('\n') if l.startswith('ack=')]
check(dl and 'opoznione=0 ' not in dl[0], 'D: ACKs delayed under load: %s' % dl)
check(dl and int(dl[0].split('max=')[1].rstrip('ms')) < 10000, 'D: max ACK delay is a real time')
check(wait_for(lambda: len(dmdt_lines(P)) >= 4), 'D: restored')

# E: mode from the settings file (as on the unit); path keys in the file are ignored
d, P, exp, acks, rc = run('E', None, n_frames=20, conf='# pmcp\nPMCP_AA_MODE=most\nPMCP_AA_BRIDGE=/nonexistent\nPMCP_AA_DMDT=/nonexistent\n')
check(wait_for(lambda: len(dmdt_lines(P)) >= 4), 'E: most from feeder.conf, fake dmdt/bridge kept %r' % dmdt_lines(P))
check(len([x for x in bridge_log(P) if x.get('type') == 2]) == 20, 'E: 20 frames through the (fake) bridge')

# F: fresh IDR requests (v2). 'K' once 300 ms after the takeover, then for each bridge request, at most one per 1000 ms
d, P, exp, acks, rc = run('F', 'most', n_frames=150, idr_every=50, kf_at=[60, 63, 120],
                          conf='PMCP_AA_MODE=most\nPMCP_AA_KF_TAKE_MS=300\nPMCP_AA_KF_MIN_MS=1000\nPMCP_AA_KF_BRIDGE=1\n')
st = open(P('status.txt')).read(); kl = [l for l in st.split('\n') if l.startswith('IDR prosby')]
print(kl)
check(acks == 150, 'F: K bytes are not counted as ACKs, one ACK per frame (%d)' % acks)
check(KS['F'] == 3, "F: 3 x 'K' on the ACK pipe: takeover + seq 60 + seq 120 (%d)" % KS['F'])
check(kl and kl[0].startswith('IDR prosby (focus):') and 'bridge=3 start=1 wyslane=3 pominiete=1 bledy=0' in kl[0], 'F: status counts %s' % kl)
check(not os.path.exists(P('kf.request')), 'F: request file removed')
check(kl and ' IDR po ' in kl[0] and 'bez IDR=0' in kl[0], 'F: IDR after request measured')
check(KS['A'] == 0, "A: v3 default: no 'K' after the takeover (%d)" % KS['A'])
check(AT_CONNECT['A'] == ['dc 72', 'sc 4 72'], 'A: v3: MOST taken before the stream connected %r' % AT_CONNECT['A'])
check(FIRST_ACK_S.get('A', 9) < 0.3, 'A: first ACK %.3f s after the first frame (no takeover stall)' % FIRST_ACK_S.get('A', 9))
check(AT_CONNECT['C'] == [], 'C: analyze: no dmdt before the stream')

# G: analyze mode never answers a request (the ring is not ours) and leaves the file alone
d, P, exp, acks, rc = run('G', 'analyze', n_frames=30, kf_file=True)
check(KS['G'] == 0 and os.path.exists(P('kf.request')), "G: analyze: no 'K', request file untouched")
check(acks == 30, 'G: ACK per frame (%d)' % acks)

# H: the takeover request switched off (PMCP_AA_KF_TAKE_MS=0), no bridge request: no 'K' at all
d, P, exp, acks, rc = run('H', 'most', n_frames=90, conf='PMCP_AA_MODE=most\nPMCP_AA_KF_TAKE_MS=0\n')
check(KS['H'] == 0, "H: no 'K' without a request (%d)" % KS['H'])

# v4 checks on the default session (A was run with the default settle of 1 s)
check(not os.path.exists(P_A('pmcp-aa-guard.pid')), 'A: v4 guardian marker removed after the restore')
sess = open(P_A('pmcp-aa-sessions.txt')).read() if os.path.exists(P_A('pmcp-aa-sessions.txt')) else ''
check('sesja start=' in sess and 'klatki=60' in sess, 'A: v4 session line %r' % sess.strip())

# I: the previous session's guardian is still alive for ~1.5 s: v4 waits, then takes MOST
holder = []
def guard_alive(sec):
    def pre(P):
        # double fork: the sleep is reparented and reaped when it ends (a zombie child would still pass kill(pid, 0))
        pid = int(subprocess.run(['sh', '-c', 'sleep %s >/dev/null 2>&1 & echo $!' % sec], capture_output=True, text=True).stdout)
        holder.append(pid)
        open(P('pmcp-aa-guard.pid'), 'w').write('%d\n' % pid)
    return pre
d, P, exp, acks, rc = run('I', 'most', n_frames=30, pre=guard_alive(1.5))
st = open(P('status.txt')).read(); wl = [l for l in st.split('\n') if l.startswith('czekanie')]
wms = lambda l: int(l.split(': ')[1].split('ms')[0])
check(AT_CONNECT['I'] == ['dc 72', 'sc 4 72'], 'I: took MOST after the previous guardian left %r' % AT_CONNECT['I'])
check(wl and 1300 <= wms(wl[0]) <= 3000 and '(poprzednia sesja AA)' in wl[0], 'I: waited %s' % wl)

# J: the previous guardian stays longer than PMCP_AA_WAIT_MS: no takeover, analysis only, reason shown
d, P, exp, acks, rc = run('J', 'most', n_frames=20, pre=guard_alive(10),
                          conf='PMCP_AA_MODE=most\nPMCP_AA_WAIT_MS=800\n')
st = open(P('status.txt')).read()
check('MOST zajety (poprzednia sesja AA)' in st and dmdt_lines(P) == [], 'J: busy, reason shown, no dmdt')
check(acks == 20, 'J: still ACKs every frame (%d)' % acks)
for pid in holder:
    try: os.kill(pid, signal.SIGKILL)
    except ProcessLookupError: pass

# K: bridge output counted through the guardian's pipe
d, P, exp, acks, rc = run('K', 'most', n_frames=40, env_add={'FAKE_BRIDGE_PRINT': '1'})
check(wait_for(lambda: os.path.exists(P('pmcp-aa-bridge.txt')) and 'reset_opoznienia=1' in open(P('pmcp-aa-bridge.txt')).read()),
      'K: bridge latency reset counted')
bt = open(P('pmcp-aa-bridge.txt')).read() if os.path.exists(P('pmcp-aa-bridge.txt')) else ''
check('bridge metryki: bridge: metrics input_bps=123' in bt, 'K: last metrics line kept')
st = open(P('status.txt')).read()
check('bridge: reset_opoznienia=1' in st, 'K: bridge summary in the status')

# M: v5 config method (soft mode): 'C' instead of 'K', once after the takeover and on a bridge request
d, P, exp, acks, rc = run('M', 'most', n_frames=150, kf_at=[130],
                          conf='PMCP_AA_MODE=most\nPMCP_AA_KF_METHOD=config\nPMCP_AA_KF_TAKE_MS=300\nPMCP_AA_KF_BRIDGE=1\n')
st = open(P('status.txt')).read(); kl = [l for l in st.split('\n') if l.startswith('IDR prosby')]
check(CS['M'] == 2 and KS['M'] == 0, "M: config method: 2 x 'C', no 'K' (C=%d K=%d)" % (CS['M'], KS['M']))
check(acks == 150, 'M: C bytes are not ACKs (%d)' % acks)
check(kl and kl[0].startswith('IDR prosby (config):'), 'M: status names the method %s' % kl)

# P: v7: CarPlay's bridge still there for ~1.5 s (carplay-bridge.ready; no /proc here, so the marker alone counts):
# wait for it, then take MOST
def cp_alive(sec):
    def pre(P):
        open(P('cp.ready'), 'w').close()
        pid = int(subprocess.run(['sh', '-c', '(sleep %s; rm -f %s) >/dev/null 2>&1 & echo $!' % (sec, P('cp.ready'))],
                                 capture_output=True, text=True).stdout)
        holder.append(pid)
    return pre
CPENV = {'PMCP_AA_CP_READY': '@DIR@/cp.ready'}
d, P, exp, acks, rc = run('P', 'most', n_frames=30, pre=cp_alive(1.5), env_add=CPENV)
st = open(P('status.txt')).read(); wl = [l for l in st.split('\n') if l.startswith('czekanie')]
check(AT_CONNECT['P'] == ['dc 72', 'sc 4 72'], 'P: took MOST after CarPlay left %r' % AT_CONNECT['P'])
check(wl and 1300 <= wms(wl[0]) <= 3000 and '(bridge CarPlay)' in wl[0], 'P: waited for CarPlay %s' % wl)
# Q: CarPlay stays longer than PMCP_AA_CP_WAIT_MS: no takeover, reason shown
d, P, exp, acks, rc = run('Q', 'most', n_frames=20, pre=cp_alive(10), env_add=CPENV, conf='PMCP_AA_MODE=most\nPMCP_AA_CP_WAIT_MS=800\n')
st = open(P('status.txt')).read()
check('MOST zajety (bridge CarPlay)' in st and dmdt_lines(P) == [], 'Q: CarPlay busy after the wait, no dmdt')
check(acks == 20, 'Q: still ACKs every frame (%d)' % acks)
# R: AA 3 settings: 5 s before the stream connects, no 'C' probe any more (A-AA26: the phone dropped the connection)
for cf in ('feeder.conf',):   # MU1367: the shipped settings (upstream feeder-gamma.conf, byte-identical)
    s3 = open(os.path.join(HERE, '..', '..', '..', 'src', 'android-auto', 'unit', cf)).read()
    check('PMCP_AA_PACE_KBPS=6000' in s3 and 'PMCP_AA_PACE_BURST_KB=64' in s3 and 'PMCP_AA_SETTLE_MS=5000' in s3 and 'PMCP_AA_SYNC_HOLD_MS=3000' in s3 and 'PMCP_AA_SYNC_REPEAT_MS=500' in s3 and 'KF_METHOD' not in s3.replace("('C')", '') .split('PMCP_AA_MODE')[1] and 'KF_TAKE_MS' not in s3 and 'PMCP_AA_PACE_GAP_MS=20' in s3 and 'PMCP_AA_KF_BRIDGE=0' in s3, 'R: AA 3 settings ' + cf)
s3 = open(os.path.join(HERE, '..', '..', '..', 'src', 'android-auto', 'unit', 'feeder.conf')).read()
d, P, exp, acks, rc = run('R', 'most', n_frames=60, conf=s3.replace('=5000', '=2500'))
check(CS['R'] == 0 and KS['R'] == 0, "R: no probe after the takeover (C=%d K=%d)" % (CS['R'], KS['R']))
check(acks == 60, 'R: ACK per frame (%d)' % acks)
for pid in holder:
    try: os.kill(pid, signal.SIGKILL)
    except ProcessLookupError: pass

# N: v6 start sync (AA 3 settings, shorter): the first IDR repeated while its ACK is held, the frames sent meanwhile kept
# in order, then every ACK; one ACK per frame
sync_conf = 'PMCP_AA_MODE=most\nPMCP_AA_SYNC_HOLD_MS=2500\nPMCP_AA_SYNC_REPEAT_MS=500\n'   # v6 mechanism, off in the AA 3 settings since v7
d, P, exp, acks, rc = run('N', 'most', n_frames=60, idr_every=100,
                          conf=sync_conf.replace('=2500', '=600').replace('=500', '=200'))
st = open(P('status.txt')).read(); sl = [l for l in st.split('\n') if l.startswith('sync startu')]
print(sl, [l for l in st.split('\n') if l.startswith('pierwsze IDR')])
rep = int(sl[0].split('powtorki IDR=')[1].split()[0]) if sl else -1
check(sl and 'zrobiony' in sl[0] and rep in (2, 3) and 'przepelnienie=0' in sl[0], 'N: sync done, %d repeats %s' % (rep, sl))
ok, nf = frames_ok(bridge_log(P), [exp[0]] * (1 + rep) + exp[1:])
check(ok and nf == 60 + rep, 'N: ring = IDR x %d, then every frame in order (%d)' % (1 + rep, nf))
check(acks == 60, 'N: one ACK per frame (%d)' % acks)
check(0.55 <= FIRST_ACK_S.get('N', 0) < 1.5, 'N: first ACK after the hold (%.3f s)' % FIRST_ACK_S.get('N', 0))
check(any(l.startswith('pierwsze IDR (ms po przejeciu/KB): ') for l in st.split('\n')), 'N: first IDRs listed')
check(wait_for(lambda: len(dmdt_lines(P)) >= 4), 'N: restored')

# O: more frames during the hold than the pool keeps (32): the hold ends early, nothing lost or reordered
d, P, exp, acks, rc = run('O', 'most', n_frames=80, idr_every=100,
                          conf='PMCP_AA_MODE=most\nPMCP_AA_SYNC_HOLD_MS=3000\nPMCP_AA_SYNC_REPEAT_MS=500\n')
st = open(P('status.txt')).read(); sl = [l for l in st.split('\n') if l.startswith('sync startu')]
rep = int(sl[0].split('powtorki IDR=')[1].split()[0]) if sl else -1
check(sl and 'przepelnienie=1' in sl[0] and 'wstrzymane klatki=32' in sl[0], 'O: pool full ends the hold %s' % sl)
ok, nf = frames_ok(bridge_log(P), [exp[0]] * (1 + rep) + exp[1:])
check(ok and nf == 80 + rep, 'O: every frame in order (%d)' % nf)
check(acks == 80, 'O: one ACK per frame (%d)' % acks)

# S (v8): a ring left by CarPlay (right size, magic, sequence 500, stale slots) is reused in place, never unlinked
INO = {}
def cp_ring(P):
    import mmap as _m, struct as _s
    fd = os.open(P('ring.bin'), os.O_RDWR | os.O_CREAT, 0o666); os.ftruncate(fd, 0x1000710)
    m = _m.mmap(fd, 0x1000710)
    _s.pack_into('<IIII', m, 0, 0x43505247, 1, 7, 500)
    for i in range(64): _s.pack_into('<II', m, 0x10 + i * 0x4001c, 437 + i, 2)
    m.flush(); m.close(); os.close(fd); INO['S'] = os.stat(P('ring.bin')).st_ino
d, P, exp, acks, rc = run('S', 'most', n_frames=40, pre=cp_ring)
st = open(P('status.txt')).read()
check('plik ringu: uzyty ponownie' in st, 'S: status says the ring was reused')
check(os.stat(P('ring.bin')).st_ino == INO['S'], 'S: same file (not unlinked)')
log = bridge_log(P)
check(not any('overrun' in e for e in log), 'S: no overrun / replay of the stale slots')
ok, nf = frames_ok(log, exp)
check(ok and nf == 40, 'S: every frame in order from sequence 1 (%d)' % nf)
# T: a ring file of another size is unlinked as before
def odd_ring(P):
    with open(P('ring.bin'), 'wb') as f: f.write(b'x' * 4096)
d, P, exp, acks, rc = run('T', 'most', n_frames=20, pre=odd_ring)
st = open(P('status.txt')).read()
check('plik ringu: inny rozmiar/magic: usuniety' in st and os.path.getsize(P('ring.bin')) == 0x1000710, 'T: odd ring unlinked, new one made')
ok, nf = frames_ok(bridge_log(P), exp)
check(ok and nf == 20, 'T: every frame (%d)' % nf)

# U (v9): pacing 400 kbit/s (50 KB/s), 16 KB burst: a 60 KB IDR every 10 frames holds back the frames after it, in order;
# their ACKs wait too; the ring timestamps show the gap after each IDR
d, P, exp, acks, rc = run('U', 'most', n_frames=40, idr_every=10,
                          conf='PMCP_AA_MODE=most\nPMCP_AA_PACE_KBPS=400\nPMCP_AA_PACE_BURST_KB=16\n', ack_idle=2.5)
st = open(P('status.txt')).read(); pl = [l for l in st.split('\n') if l.startswith('dawkowanie:')]
print(pl)
e = bridge_log(P); ok, nf = frames_ok(e, exp)
check(ok and nf == 40, 'U: every frame in order with pacing (%d)' % nf)
check(acks == 40, 'U: one ACK per frame (%d)' % acks)
dl = int(pl[0].split('opoznione=')[1].split()[0]) if pl else 0
check(pl and pl[0].startswith('dawkowanie: 400 kbit/s zapas 16 KB') and dl > 0 and 'przepelnienie=0' in pl[0], 'U: status %s' % pl)
fr = [x for x in e if x.get('type') == 2]
gap = (fr[1]['ts'] - fr[0]['ts']) / 2.0 ** 32 if len(fr) > 1 else 0
check(0.6 <= gap < 2.0, 'U: the frame after a 60 KB IDR waits for the budget (%.2f s)' % gap)
check(wait_for(lambda: len(dmdt_lines(P)) >= 4), 'U: restored')

# V (v10): pacing queue 3/4 full (192 of 256) -> drained over the byte budget, never all at once; nothing lost
d, P, exp, acks, rc = run('V', 'most', n_frames=260, idr_every=1000,
                          conf='PMCP_AA_MODE=most\nPMCP_AA_PACE_KBPS=100\nPMCP_AA_PACE_BURST_KB=8\n', ack_idle=3.5)
st = open(P('status.txt')).read(); pl = [l for l in st.split('\n') if l.startswith('dawkowanie:')]
ok, nf = frames_ok(bridge_log(P), exp)
check(ok and nf == 260, 'V: every frame in order (%d)' % nf)
check(acks == 260, 'V: one ACK per frame (%d)' % acks)
qm = int(pl[0].split('kolejka max=')[1].split('/')[0]) if pl else 0
check(pl and 'przepelnienie=0' in pl[0] and 'oproznianie=0 ' not in pl[0] and 190 <= qm <= 194, 'V: drained at 3/4, no overflow %s' % pl)

# V2 (v10): a 100 ms gap cannot keep up with 30 fps: the queue fills (256), only the oldest frames go for room
d, P, exp, acks, rc = run('V2', 'most', n_frames=520, idr_every=1000,
                          conf='PMCP_AA_MODE=most\nPMCP_AA_PACE_GAP_MS=100\n', ack_idle=3.5)
st = open(P('status.txt')).read(); pl = [l for l in st.split('\n') if l.startswith('dawkowanie:')]
ok, nf = frames_ok(bridge_log(P), exp)
check(ok and nf == 520, 'V2: every frame in order (%d)' % nf)
check(acks == 520, 'V2: one ACK per frame (%d)' % acks)
check(pl and 'przepelnienie=0' not in pl[0] and 'kolejka max=256/256' in pl[0] and 'odstep 100ms' in pl[0], 'V2: full queue, room made %s' % pl)

# T (v10): start hold + 25 ms gap: the frames held during the hold go into the ring spaced, not as one burst
d, P, exp, acks, rc = run('T', 'most', n_frames=60, idr_every=100,
                          conf='PMCP_AA_MODE=most\nPMCP_AA_SYNC_HOLD_MS=600\nPMCP_AA_SYNC_REPEAT_MS=200\nPMCP_AA_PACE_GAP_MS=25\n')
st = open(P('status.txt')).read(); sl = [l for l in st.split('\n') if l.startswith('sync startu')]
rep = int(sl[0].split('powtorki IDR=')[1].split()[0]) if sl else -1
held = int(sl[0].split('wstrzymane klatki=')[1].split()[0]) if sl else 0
e = bridge_log(P); ok, nf = frames_ok(e, [exp[0]] * (1 + rep) + exp[1:])
check(sl and 'zrobiony' in sl[0] and held >= 10 and ok and nf == 60 + rep, 'T: sync, %d held, every frame in order (%d)' % (held, nf))
fr = [x for x in e if x.get('type') == 2][1 + rep:]
gaps = [(b['ts'] - a['ts']) / 2.0 ** 32 for a, b in zip(fr, fr[1:])]
check(gaps and min(gaps) >= 0.022, 'T: frames after the hold at least ~25 ms apart (min %.3f s)' % (min(gaps) if gaps else 0))
check(acks == 60, 'T: one ACK per frame (%d)' % acks)

# X (v10): default: the bridge's IDR request file is removed and counted, nothing goes to the hook
d, P, exp, acks, rc = run('X', 'most', n_frames=90, kf_at=[30, 60], conf='PMCP_AA_MODE=most\nPMCP_AA_KF_MIN_MS=1000\n')
st = open(P('status.txt')).read(); kl = [l for l in st.split('\n') if l.startswith('IDR prosby')]
check(KS['X'] == 0 and CS['X'] == 0, "X: no 'K'/'C' for bridge requests (K=%d C=%d)" % (KS['X'], CS['X']))
check(kl and 'bridge=2 ' in kl[0] and 'wyslane=0 ' in kl[0] and 'zignorowane=2 (prosby bridge nie ida do telefonu)' in kl[0], 'X: counted only %s' % kl)
check(not os.path.exists(P('kf.request')), 'X: request file removed')
check(acks == 90, 'X: one ACK per frame (%d)' % acks)

# W (v9): the shipped AA 3 / gamma settings (start sync + pacing), shorter: sync then paced frames, nothing lost
s3 = open(os.path.join(HERE, '..', '..', '..', 'src', 'android-auto', 'unit', 'feeder.conf')).read()
d, P, exp, acks, rc = run('W', 'most', n_frames=60, idr_every=100,
                          conf=s3.replace('SETTLE_MS=5000', 'SETTLE_MS=200').replace('HOLD_MS=3000', 'HOLD_MS=600').replace('REPEAT_MS=500', 'REPEAT_MS=200'))
st = open(P('status.txt')).read(); sl = [l for l in st.split('\n') if l.startswith('sync startu')]
rep = int(sl[0].split('powtorki IDR=')[1].split()[0]) if sl else -1
ok, nf = frames_ok(bridge_log(P), [exp[0]] * (1 + rep) + exp[1:])
check(sl and 'zrobiony' in sl[0] and ok and nf == 60 + rep, 'W: sync + pacing, every frame in order (%d, %s)' % (nf, sl))
check(acks == 60, 'W: one ACK per frame (%d)' % acks)
check(any(l.startswith('dawkowanie: 6000 kbit/s zapas 64 KB odstep 20ms') for l in st.split('\n')), 'W: pacing + gap on in the gamma settings')

# ---- MU1367 v1.5.0-e cases ----
def prefs(text):
    def pre(P):
        with open(P('prefs/settings.state'), 'w') as f: f.write(text)
    return pre
def state3(mask):
    body = 'format=3\nvc_map_mask=%d\nvc_mirror_mask=0\ncarplay_information=0\ngeneration=7\n' % mask
    return body + 'crc32=%x\n' % zlib.crc32(body.encode())
def exclusive_free(P):
    fd = os.open(P('cache.lock'), os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.lockf(fd, fcntl.LOCK_EX | fcntl.LOCK_NB); fcntl.lockf(fd, fcntl.LOCK_UN); return True
    except OSError: return False
    finally: os.close(fd)
LEASE = {}
def probe(case):
    def f(P): LEASE[case] = exclusive_free(P)
    return f
def vw_only(case, P, acks, n):
    st = open(P('status.txt')).read()
    check(dmdt_lines(P) == [] and not os.path.exists(P('ring.bin')), case + ': no dmdt, no ring %r' % dmdt_lines(P))
    check('mode=analyze' in st and '-> vw' in st, case + ': analyze, policy vw: ' + [l for l in st.split('\n') if l.startswith('mu1367')][0])
    check(acks == n, case + ': ACK per frame (%d)' % acks)
# MU1: the MU menu turned the cluster map off: AID keeps VW, no MOST, no ring, no lease
d, P, exp, acks, rc = run('MU1', 'most', n_frames=30, pre=prefs(state3(0)), during=probe('MU1'))
vw_only('MU1', P, acks, 30); check(LEASE.get('MU1') is True, 'MU1: no lease without MOST')
# MU2: unreadable preferences follow the supervisor: no cluster map
d, P, exp, acks, rc = run('MU2', 'most', n_frames=20, pre=prefs('format=3\nvc_map_mask=1\n'))
vw_only('MU2', P, acks, 20)
# MU3: without CLUSTER_AUTO_ENABLE (CarPlay Maps cluster video not enabled) AA does not take MOST either
d, P, exp, acks, rc = run('MU3', 'most', n_frames=20, pre=lambda P: os.unlink(P('auto.enable')))
vw_only('MU3', P, acks, 20)
# MU4: map requested explicitly: MOST taken, shared lease held for the session and released afterwards
d, P, exp, acks, rc = run('MU4', 'most', n_frames=40, pre=prefs(state3(1)), during=probe('MU4'))
check(wait_for(lambda: len(dmdt_lines(P)) >= 4), 'MU4: dmdt release + restore %r' % dmdt_lines(P))
st = open(P('status.txt')).read()
check('-> map' in st and 'mode=most' in st, 'MU4: policy map')
check(LEASE.get('MU4') is False, 'MU4: supervisor cleanup blocked while the feeder owns the ring')
check(wait_for(lambda: exclusive_free(P)), 'MU4: lease released after the session')
ok, nf = frames_ok(bridge_log(P), exp)
check(ok and nf == len(exp), 'MU4: %d/%d frames' % (nf, len(exp)))
# MU5: default (no preference files) is map on, lease held as well
d, P, exp, acks, rc = run('MU5', 'most', n_frames=20, during=probe('MU5'))
check(LEASE.get('MU5') is False and 'prefs=0 map_mask=1' in open(P('status.txt')).read(), 'MU5: default map on, lease held')
# MU6: the cleanup holds the exclusive lock: the takeover waits for it, then proceeds (cleanup is momentary)
def hold_briefly(P):
    fd = os.open(P('cache.lock'), os.O_RDWR | os.O_CREAT, 0o600); fcntl.lockf(fd, fcntl.LOCK_EX)
    import threading; threading.Timer(0.6, lambda: os.close(fd)).start()
d, P, exp, acks, rc = run('MU6', 'most', n_frames=20, pre=hold_briefly)
check('mode=most' in open(P('status.txt')).read() and wait_for(lambda: len(dmdt_lines(P)) >= 4), 'MU6: takeover after a momentary cleanup lock')

# diagnostics (v9) in A: windows, gaps, large frames (two 60 KB IDRs), pacing off
st = open(P_A('status.txt')).read().split('\n')
check(any(l.startswith('klatki co 10s (od 0s, najstarsze->teraz): ') for l in st), 'A: frames per 10 s')
check(any(l.startswith('przerwy: ostatnia klatka ') for l in st), 'A: gaps line')
check(any(l.startswith('duze klatki >=32KB: 2 ostatnie') for l in st), 'A: large frames %s' % [l for l in st if l.startswith('duze')])
check('dawkowanie: wylaczone' in st, 'A: pacing off by default')

# A without sync settings: no hold (v5 behaviour), no sync line
check('sync startu' not in open(P_A('status.txt')).read(), 'A: no start sync by default')

print('FAILED CHECKS: %d' % len(fails))
sys.exit(1 if fails else 0)
