"""Stands in for altscreen-most-bridge: creates/initialises the ring like the real one (A64) and
logs what it reads to $FAKE_BRIDGE_OUT (one JSON line per slot). With FAKE_BRIDGE_KF_AT="s1,s2,..." it creates the IDR
request file $PMCP_AA_KF_REQ (as request_fresh_idr: open O_WRONLY|O_CREAT|O_TRUNC) when it has read slot s."""
import json, mmap, os, signal, struct, sys, time
RING = os.environ['PMCP_AA_RING']; OUT = os.environ['FAKE_BRIDGE_OUT']
SIZE, HDR, SLOT, SLOTS, MAGIC = 0x1000710, 0x10, 0x4001c, 64, 0x43505247
stop = []
signal.signal(signal.SIGTERM, lambda *a: stop.append(1))
fd = os.open(RING, os.O_RDWR | os.O_CREAT, 0o666); os.ftruncate(fd, SIZE)
m = mmap.mmap(fd, SIZE)
if struct.unpack_from('<I', m, 0)[0] != MAGIC:
    m[0:HDR] = b'\0' * HDR; struct.pack_into('<III', m, 4, 1, 1, 0); struct.pack_into('<I', m, 0, MAGIC)
want, out = 1, open(OUT, 'a')
KF_AT = {int(x) for x in os.environ.get('FAKE_BRIDGE_KF_AT', '').split(',') if x}
KF_REQ = os.environ.get('PMCP_AA_KF_REQ', '')
PRINT = os.environ.get('FAKE_BRIDGE_PRINT') == '1'   # print bridge-like lines on stdout
if PRINT: print('bridge: start status=0 packets=64', flush=True)
while not stop:
    if struct.unpack_from('<I', m, 0xc)[0] >= want:
        off = HDR + ((want - 1) & 63) * SLOT
        seq, typ, ln, z, fno, ts = struct.unpack_from('<IIIIIQ', m, off)
        if seq == want:
            data = bytes(m[off + 0x1c: off + 0x1c + ln])
            if struct.unpack_from('<I', m, off)[0] == want:
                out.write(json.dumps(dict(seq=seq, type=typ, len=ln, zero=z, frame=fno, ts=ts, data=data.hex())) + '\n'); out.flush()
                if PRINT and seq == 10:
                    print('bridge: latency-reset sequence=10 queued=9 discarded=9 limit=8 idr_request_deferred=1 resets=1', flush=True)
                    print('bridge: metrics input_bps=123 ts_bps=456 fps_milli=30000 frame_max=1 idr_max=1 queue=0 queue_hi=1 queue_hi_total=1 pts_step_max=3000', flush=True)
                if seq in KF_AT and KF_REQ:
                    os.close(os.open(KF_REQ, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o666))
                    out.write(json.dumps(dict(kf_request=seq)) + '\n'); out.flush()
                want += 1; continue
        elif seq > want:
            out.write(json.dumps(dict(overrun=[want, seq])) + '\n'); want = seq; continue
    time.sleep(0.001)
out.write(json.dumps(dict(sigterm=1)) + '\n')
