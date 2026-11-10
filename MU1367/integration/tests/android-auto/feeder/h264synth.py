"""Synthetic H.264 Annex B access units (headers only parse-valid, payload random, no start-code emulation)."""
import random

class Bits:
    def __init__(self): self.v = []
    def u(self, n, x): self.v += [(x >> (n - 1 - i)) & 1 for i in range(n)]
    def ue(self, x):
        x += 1; n = x.bit_length(); self.u(n - 1, 0); self.u(n, x)
    def rbsp(self):
        self.v.append(1)
        while len(self.v) % 8: self.v.append(0)
        return bytes(int(''.join(map(str, self.v[i:i + 8])), 2) for i in range(0, len(self.v), 8))

def sps(w=800, h=480, profile=66, level=31):
    b = Bits(); b.u(8, profile); b.u(8, 0xC0); b.u(8, level); b.ue(0); b.ue(0); b.ue(2); b.ue(1); b.u(1, 0)
    b.ue(w // 16 - 1); b.ue(h // 16 - 1); b.u(1, 1); b.u(1, 1); b.u(1, 0); b.u(1, 0)
    return b'\x67' + b.rbsp()

def pps():
    b = Bits(); b.ue(0); b.ue(0); b.u(1, 0); b.u(1, 0); b.ue(0); b.ue(0); b.ue(0); b.u(1, 0); b.u(2, 0)
    return b'\x68' + b.rbsp()

def slice_nal(idr, first_mb, size, rng):
    b = Bits(); b.ue(first_mb); b.ue(7 if idr else 5)
    head = (b'\x65' if idr else b'\x41') + b.rbsp()
    return head + bytes(rng.randrange(1, 256) for _ in range(max(0, size - len(head))))

AUD = b'\x09\xf0'
SC = b'\x00\x00\x00\x01'

def access_unit(idr, size, rng, slices=1, with_ps=True):
    nals = [AUD]
    if idr and with_ps: nals += [sps(), pps()]
    per = size // slices
    nals += [slice_nal(idr, k * 100, per, rng) for k in range(slices)]
    return b''.join(SC + n for n in nals), [n for n in nals if (n[0] & 0x1f) in (1, 5)]
