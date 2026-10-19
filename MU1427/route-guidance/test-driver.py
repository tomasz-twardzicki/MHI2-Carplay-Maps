#!/usr/bin/env python3
"""ARM emulation against the real MU1427 driver; no phone/unit required.

Usage: python test-driver.py FACTORY_DRIVER
Dependencies: pyelftools, unicorn. Executes the actual injected instructions,
stock packet_addparam_blob, link_send_raw_message and checksum implementation.
OS logging, memcpy, queue/transport primitives are intercepted.
Receive regressions execute the real transport return/recycle branch, reply
table gate and semantic dispatcher. ACK/sequence processing is bypassed in the
test harness; it is unchanged by the patch.
"""
import importlib.util
import io
from pathlib import Path
import struct
import sys
import unittest

from elftools.elf.elffile import ELFFile
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM, UC_HOOK_CODE
from unicorn.arm_const import *

spec = importlib.util.spec_from_file_location("patch", Path(__file__).with_name("patch-driver.py"))
patch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(patch)
STOCK = Path(sys.argv.pop(1)).read_bytes()
DATA, MANIFEST = patch.build(STOCK)
SYMBOLS = {k: int(v, 16) for k, v in MANIFEST["symbols"].items()}


def tlvs(data):
    result = []
    while data:
        if len(data) < 4:
            raise ValueError("truncated TLV header")
        length, ident = struct.unpack_from(">HH", data)
        if not 4 <= length <= len(data):
            raise ValueError("bad TLV length")
        result.append((ident, data[4:length]))
        data = data[length:]
    return result


class Machine:
    def __init__(self, bias=0):
        self.bias = bias
        self.u = u = Uc(UC_ARCH_ARM, UC_MODE_ARM)
        u.mem_map(bias, 0xC0000)
        for p in ELFFile(io.BytesIO(DATA)).iter_segments():
            if p["p_type"] == "PT_LOAD":
                u.mem_write(bias + p["p_vaddr"], p.data())
        elf = ELFFile(io.BytesIO(DATA))
        dynsym = elf.get_section_by_name(".dynsym")
        for reloc in elf.get_section_by_name(".rel.dyn").iter_relocations():
            at = bias + reloc["r_offset"]
            if reloc["r_info_type"] == 23:  # R_ARM_RELATIVE
                value = struct.unpack("<I", u.mem_read(at, 4))[0] + bias
            elif reloc["r_info_type"] == 21:  # R_ARM_GLOB_DAT
                sym = dynsym.get_symbol(reloc["r_info_sym"])
                value = bias + sym["st_value"] if sym["st_shndx"] != "SHN_UNDEF" else 0
            else:
                raise AssertionError("unexpected dynamic relocation")
            u.mem_write(at, struct.pack("<I", value))
        u.mem_map(0x200000, 0x20000)
        self.driver, self.packet, self.buffer = 0x200000, 0x201000, 0x202000
        self.sp, self.end = 0x21F000, 0x21FF00
        self.logs, self.dumps, self.sent, self.queued = [], [], [], []
        self.no_packet = False
        self.send_rc = 0
        self.mock_reply_rc = None
        self.reply_calls = []
        self.put(self.driver + 0x14, 0x204000)
        self.put(self.driver + 0x7C, 0x205000)
        self.put(self.packet + 0x18, self.buffer)
        self.put(self.packet + 0x20, 4096)
        for i, reg in enumerate(range(UC_ARM_REG_R0, UC_ARM_REG_R12 + 1)):
            u.reg_write(reg, 0x900000 + i)
        u.reg_write(UC_ARM_REG_SP, self.sp)
        u.reg_write(UC_ARM_REG_LR, self.end)
        u.hook_add(UC_HOOK_CODE, self.intercept)

    def put(self, at, value):
        self.u.mem_write(at, struct.pack("<I", value))

    def word(self, at):
        return struct.unpack("<I", self.u.mem_read(at, 4))[0]

    def cstr(self, at):
        out = bytearray()
        while self.u.mem_read(at, 1) != b"\0":
            out.extend(self.u.mem_read(at, 1)); at += 1
        return out.decode()

    def intercept(self, u, address, size, _):
        at = address - self.bias
        r = lambda n: u.reg_read(UC_ARM_REG_R0 + n)
        result = 0
        if at == 0x4934:  # Not expected: no config lookup in injected path.
            raise AssertionError("unexpected config call")
        if at == 0x4988:  # memcpy
            u.mem_write(r(0), bytes(u.mem_read(r(1), r(2)))); result = r(0)
        elif at == 0x4C4C:
            self.logs.append((self.cstr(r(2)), r(3), self.word(u.reg_read(UC_ARM_REG_SP))))
        elif at == 0x4D30:
            self.dumps.append(bytes(u.mem_read(r(1), r(2))))
        elif at == 0x1F198:
            result = 0 if self.no_packet else self.packet
        elif at == 0x1EE00:
            self.queued.append(r(1))
        elif at == 0x1DEBC:
            result = 0x0A
        elif at == 0x1105C:
            assert r(0) == self.driver and r(1) == self.packet
            assert r(2) == 0x40 and r(3) == 0x0A
            self.sent.append(bytes(u.mem_read(self.word(self.packet + 0x24), self.word(self.packet + 0x1C))))
            result = self.send_rc
        elif at == 0x11A2C:
            self.reply_calls.append((r(0), r(1)))
            if self.mock_reply_rc is None:
                return  # Execute the real stock table lookup.
            result = self.mock_reply_rc
        elif at in (0xE13C, 0xE11C):
            self.exit = at
            u.emu_stop(); return
        else:
            return
        # Exercise caller-saved clobbering; native ABI preserves r4-r11.
        for reg in (UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3, UC_ARM_REG_R12):
            u.reg_write(reg, 0xDEADBEEF)
        u.reg_write(UC_ARM_REG_R0, result)
        u.reg_write(UC_ARM_REG_PC, u.reg_read(UC_ARM_REG_LR))

    def run(self, name):
        self.u.emu_start(self.bias + SYMBOLS[name], self.end, count=10000)
        assert self.u.reg_read(UC_ARM_REG_SP) == self.sp
        assert self.u.reg_read(UC_ARM_REG_PC) in (self.end, self.bias + 0xE13C, self.bias + 0xE11C)


def make_frame(msg, payload=bytes.fromhex("0006000000100005000100"), sequence=1):
    semantic = struct.pack(">HHH", 0x4040, 6 + len(payload), msg) + payload
    header = bytearray(b"\xff\x5a" + struct.pack(">H", len(semantic) + 10) + bytes((0x40, sequence & 255, 0, 1)))
    header.append((-sum(header)) & 255)
    return bytes(header) + semantic + bytes(((-sum(semantic)) & 255,))


class ReceiveMachine(Machine):
    """Six-buffer transport harness; native lookup/dispatch/recycle branching."""
    def __init__(self, bias=0, b1_gate=False):
        super().__init__(bias)
        self.available = [self.packet + n * 0x100 for n in range(6)]
        for n, packet in enumerate(self.available):
            self.put(packet + 0x18, 0x208000 + n * 0x1000)
            self.put(packet + 0x20, 4096)
        self.current_frame = b""
        self.starved = False
        self.recycled = 0
        self.nowplay_received = 0
        if b1_gate:
            # B1's later hook at 0x13470 is unreachable for an unregistered ID.
            # Reproduce its stock pre-hook gate using the original instruction.
            self.u.mem_write(bias + 0x133A0, struct.pack("<I", 0xEBFFF9A1))

    def return_primitive(self, value):
        self.u.reg_write(UC_ARM_REG_R0, value)
        self.u.reg_write(UC_ARM_REG_PC, self.u.reg_read(UC_ARM_REG_LR))

    def intercept(self, u, address, size, user):
        at = address - self.bias
        r = lambda n: u.reg_read(UC_ARM_REG_R0 + n)
        if at == 0x1F050:
            if not self.available:
                self.starved = True
                u.emu_stop()
            else:
                self.return_primitive(self.available.pop())
            return
        if at == 0x12208:  # Physical USB read; real parse_hdr runs afterwards.
            packet = r(1)
            u.mem_write(self.word(packet + 0x18), self.current_frame)
            self.put(packet + 0x1C, len(self.current_frame))
            self.return_primitive(0)
            return
        if at == 0x12E08:
            # Real handler prologue has run. Bypass its unchanged ACK/sequence
            # path and start at the real reply gate used by B1 and B2.
            u.reg_write(UC_ARM_REG_R5, r(0))
            u.reg_write(UC_ARM_REG_R8, r(1))
            u.reg_write(UC_ARM_REG_R9, self.bias + 0xA98C0)
            u.reg_write(UC_ARM_REG_PC, self.bias + 0x13398)
            return
        if at == 0x1ED78:
            packet = r(1)
            assert packet not in self.available, "double recycle"
            self.available.append(packet)
            self.recycled += 1
            self.return_primitive(0)
            return
        if at == 0x1BB18:  # Existing now-playing handler; PPS is outside this test.
            self.nowplay_received += 1
            self.return_primitive(0)
            return
        super().intercept(u, address, size, user)

    def receive(self, frame):
        self.current_frame = frame
        self.u.reg_write(UC_ARM_REG_R0, self.driver)
        self.u.reg_write(UC_ARM_REG_SP, self.sp)
        self.u.reg_write(UC_ARM_REG_LR, self.end)
        self.u.emu_start(self.bias + 0x2121C, self.end, count=10000)
        if not self.starved:
            assert self.u.reg_read(UC_ARM_REG_SP) == self.sp
            assert self.u.reg_read(UC_ARM_REG_PC) == self.end


class DriverTests(unittest.TestCase):
    def test_fingerprints_and_determinism(self):
        self.assertEqual(DATA, patch.build(STOCK)[0])
        for bad in (STOCK[:-1], bytes(len(STOCK)), DATA):
            with self.assertRaises(ValueError):
                patch.build(bad)

    def test_elf_and_only_expected_changes(self):
        old, new = ELFFile(io.BytesIO(STOCK)), ELFFile(io.BytesIO(DATA))
        self.assertEqual(list(old.iter_segments())[-1].header, list(new.iter_segments())[-1].header)
        loads = [p for p in new.iter_segments() if p["p_type"] == "PT_LOAD"]
        self.assertEqual(len(loads), 3)
        self.assertEqual(loads[-1]["p_flags"], 5)
        self.assertEqual(loads[-1]["p_offset"], patch.INJECT)
        for a, b in zip(old.iter_segments(), new.iter_segments()):
            if a["p_type"] == "PT_LOAD":
                self.assertEqual(a.header, b.header)
        allowed = set(range(52 + 3 * 32, 52 + 4 * 32))
        for at in patch.HOOKS:
            allowed.update(range(at, at + 4))
        self.assertTrue(all(i in allowed for i, (a, b) in enumerate(zip(STOCK, DATA)) if a != b))
        for at, (_, name, link) in patch.HOOKS.items():
            word = struct.unpack_from("<I", DATA, at)[0]
            displacement = word & 0xFFFFFF
            if displacement & 0x800000: displacement -= 0x1000000
            self.assertEqual(at + 8 + displacement * 4, SYMBOLS[name])
            self.assertEqual(bool(word & 0x1000000), link)

    def test_stock_authentication_identification_gates(self):
        for bias in (0, 0x14000000):
            for flags in range(4):
                for at, reg in ((0x13618, UC_ARM_REG_R7), (0x13684, UC_ARM_REG_R4)):
                    m = Machine(bias)
                    m.u.reg_write(reg, flags)
                    reached = []
                    def stop(u, address, size, _):
                        if address in (bias + 0x5FDC, bias + 0x1401C):
                            reached.append(address - bias); u.emu_stop()
                    m.u.hook_add(UC_HOOK_CODE, stop)
                    m.u.emu_start(bias + at, m.end, count=100)
                    self.assertEqual(reached, [0x5FDC if flags == 3 else 0x1401C])

    def test_identification_and_packet_capacity(self):
        for bias in (0, 0x14000000):
            for capacity in (4096, 96):
                with self.subTest(bias=bias, capacity=capacity):
                    m = Machine(bias)
                    m.put(m.packet + 0x20, capacity)
                    # Existing stock parameters remain in the packet.
                    m.put(m.packet + 0x24, m.buffer + 9)
                    m.u.mem_write(m.packet + 0x28, struct.pack("<H", 8))
                    m.put(m.packet + 0x1C, 8)
                    prefix = bytes.fromhex("000800004d494232")
                    m.u.mem_write(m.buffer + 15, prefix)
                    m.u.reg_write(UC_ARM_REG_R6, m.driver)
                    m.u.reg_write(UC_ARM_REG_R7, m.packet)
                    m.run("ident_hook")
                    self.assertEqual(bytes(m.u.mem_read(m.buffer + 15, 8)), prefix)
                    if capacity == 96:
                        self.assertEqual(m.exit, 0xE11C)
                        self.assertEqual(m.u.reg_read(UC_ARM_REG_R5), 0xFFFFFFFF)
                    else:
                        self.assertEqual(m.exit, 0xE13C)
                        self.assertEqual(m.u.reg_read(UC_ARM_REG_R0), m.driver)
                        count = struct.unpack("<H", m.u.mem_read(m.packet + 0x28, 2))[0]
                        outer = tlvs(bytes(m.u.mem_read(m.buffer + 23, count - 8)))
                        self.assertEqual([k for k, _ in outer], [0x1E])
                        inner = tlvs(outer[0][1])
                        self.assertEqual([k for k, _ in inner], list(range(9)))
                        self.assertEqual(inner[0][1], b"\0\x10")
                        self.assertEqual(inner[1][1], b"RouteGuidanceDisplayComponent\0")
                        for k, value in inner[2:]:
                            self.assertEqual(int.from_bytes(value, "big"), 6 if k in (6, 8) else 256)

    def test_start_success_failure_and_native_frame(self):
        for bias in (0, 0x14000000):
            for stock_rc, no_packet, send_rc in ((0, False, 0), (0, True, 0), (0, False, 5), (17, False, 0)):
                with self.subTest(bias=bias, stock_rc=stock_rc, no_packet=no_packet, send_rc=send_rc):
                    m = Machine(bias)
                    m.no_packet, m.send_rc = no_packet, send_rc
                    m.u.reg_write(UC_ARM_REG_R4, m.driver)
                    m.u.reg_write(UC_ARM_REG_R5, stock_rc)
                    m.run("start_hook")
                    self.assertEqual(m.u.reg_read(UC_ARM_REG_R0), stock_rc)
                    self.assertEqual(m.u.reg_read(UC_ARM_REG_R4), m.driver)
                    if stock_rc:
                        self.assertFalse(m.logs)
                        self.assertFalse(m.sent)
                    else:
                        self.assertTrue(any("CPMAP_RGI_START" in x[0] for x in m.logs))
                    if not stock_rc and not no_packet:
                        self.assertEqual(len(m.sent), 1)
                        frame = m.sent[0]
                        self.assertEqual(frame[:6], bytes.fromhex("404000185200"))
                        self.assertEqual(tlvs(frame[6:-1]), [(0, b"\0\x10"), (1, b""), (2, b""), (3, b"")])
                        self.assertEqual(sum(frame) & 255, 0)
                        self.assertEqual(m.queued, [m.packet])
                        self.assertEqual(m.logs[-1][1], send_rc)
                    else:
                        self.assertFalse(m.sent)

    def test_receive_payload_and_callee_register_preservation(self):
        for bias in (0, 0x14000000):
            for msg in (0x5201, 0x5202, 0x5204):
                with self.subTest(bias=bias, msg=msg):
                    m = Machine(bias)
                    payload = bytes.fromhex("0006000000100005000101")
                    frame = make_frame(msg, payload)
                    m.u.mem_write(m.buffer, frame)
                    m.put(m.packet + 0x1C, len(frame))
                    m.put(m.packet + 0x24, m.buffer + 9)
                    m.u.mem_write(m.packet + 0x28, struct.pack("<H", len(frame) - 10))
                    m.u.reg_write(UC_ARM_REG_R0, m.driver)
                    m.u.reg_write(UC_ARM_REG_R1, m.packet)
                    saved = {reg: m.u.reg_read(reg) for reg in range(UC_ARM_REG_R4, UC_ARM_REG_R11 + 1)}
                    m.run("receive_hook")
                    self.assertEqual({reg: m.u.reg_read(reg) for reg in saved}, saved)
                    self.assertEqual(m.u.reg_read(UC_ARM_REG_R0), 0)
                    self.assertEqual(m.reply_calls, [])
                    self.assertEqual(m.dumps, [payload])
                    self.assertEqual(m.logs[0][1:], (msg, len(payload)))

    def test_other_messages_and_malformed_frames_delegate_to_stock(self):
        for bias in (0, 0x14000000):
            cases = [bytearray(make_frame(msg)) for msg in (0x5001, 0x5200, 0x5203, 0x5205, 0x1D02)]
            for field in (9, 10, 11, 12):
                bad = bytearray(make_frame(0x5201)); bad[field] ^= 1; cases.append(bad)
            for frame in cases:
                m = Machine(bias)
                m.mock_reply_rc = 17
                m.u.mem_write(m.buffer, bytes(frame))
                m.put(m.packet + 0x1C, len(frame))
                m.put(m.packet + 0x24, m.buffer + 9)
                m.u.mem_write(m.packet + 0x28, struct.pack("<H", len(frame) - 10))
                m.u.reg_write(UC_ARM_REG_R0, m.driver)
                m.u.reg_write(UC_ARM_REG_R1, m.packet)
                m.run("receive_hook")
                self.assertEqual(m.reply_calls, [(m.driver, m.packet)])
                self.assertEqual(m.u.reg_read(UC_ARM_REG_R0), 17)
                self.assertFalse(m.dumps)

    def test_b1_native_unknown_id_gate_leaks_receive_buffers(self):
        for bias in (0, 0x14000000):
            m = ReceiveMachine(bias, b1_gate=True)
            for n in range(6):
                m.receive(make_frame(0x5201, sequence=n))
                self.assertEqual(len(m.available), 5 - n)
                self.assertFalse(m.starved)
            self.assertEqual(m.recycled, 0)
            self.assertEqual(sum("Invalid packet" in s[0] for s in m.logs), 6)
            m.receive(make_frame(0x5201, sequence=6))
            self.assertTrue(m.starved)

    def test_b2_recycles_thousand_guidance_frames_and_keeps_stock_updates(self):
        for bias in (0, 0x14000000):
            m = ReceiveMachine(bias)
            for n in range(1000):
                m.receive(make_frame((0x5201, 0x5202, 0x5204)[n % 3], sequence=n))
                self.assertFalse(m.starved)
                self.assertEqual(len(m.available), 6)
            self.assertEqual(m.recycled, 1000)
            self.assertEqual(len(m.dumps), 1000)
            self.assertFalse(m.reply_calls)
            self.assertFalse(any("Invalid packet" in s[0] for s in m.logs))
            m.receive(make_frame(0x5001))
            self.assertEqual(m.nowplay_received, 1)
            self.assertEqual(m.recycled, 1001)
            self.assertEqual(len(m.reply_calls), 1)
            self.assertEqual(len(m.available), 6)


if __name__ == "__main__":
    unittest.main(verbosity=2)
