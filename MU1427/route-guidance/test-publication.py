#!/usr/bin/env python3
"""Execute B3 ARM producer/read hooks with real B2 receive/recycle paths.

OS allocation, iofunc verification, memcpy and MsgReply are mocked. The
publication instructions, exclusive-access instructions and barriers execute.
"""
import importlib.util
import io
import os
from pathlib import Path
import struct
import sys
import unittest

from elftools.elf.elffile import ELFFile
from unicorn.arm_const import *

HERE = Path(__file__).resolve().parent
STOCK_PATH = Path(sys.argv[1])


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    obj = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj


# test-driver.py consumes argv[1]. Its stock helpers and receive harness are
# reused against B3 without changing the B2 source, patcher or generated ZIP.
base = module("driver_tests", HERE / "test-driver.py")
patch = module("publication_patch", HERE / "patch-publication.py")
DATA, MANIFEST = patch.build(STOCK_PATH.read_bytes())
base.DATA = DATA
base.SYMBOLS = {k: int(v, 16) for k, v in MANIFEST["symbols"].items()}


class Machine(base.Machine):
    def __init__(self, bias=0, **kwargs):
        super().__init__(bias, **kwargs)
        self.u.mem_map(0x300000, 0x1000000)
        self.heap = 0x310000
        self.allocations = {}
        self.replies = []
        self.calls = []
        self.fail_alloc = None
        self.verify_rc = 0
        self.clock_rc = 0
        self.unstable = False
        self.original_entries = bytes([0x41]) * 0x110
        self.u.mem_write(0x300000, self.original_entries)
        for n, name in enumerate((b'eap\0', b'media\0')):
            self.u.mem_write(0x30a000 + n * 16, name)
            self.put(0x300000 + n * 0x88 + 0x78, 0x30a000 + n * 16)
            self.put(0x300000 + n * 0x88 + 0x70, 0)
        self.original_entries = bytes(self.u.mem_read(0x300000, 0x110))
        self.put(self.driver + 0x114, 0x300000)
        self.put(self.driver + 0x118, 2)
        self.ctp, self.msg, self.ocb = 0x304000, 0x305000, 0x306000
        self.put(self.ctp, 123)
        self.put(self.msg + 4, 65536)

    def allocate(self, size):
        at = self.heap
        self.heap = (self.heap + size + 15) & ~15
        self.allocations[at] = size
        self.u.mem_write(at, bytes(size))
        return at

    def intercept(self, u, address, size, user):
        at = address - self.bias
        r = lambda n: u.reg_read(UC_ARM_REG_R0 + n)
        name = {**{v: k for k, v in patch.NATIVE.items()},
                0x4cac: 'native_strlen', 0x4bbc: 'native_strcmp', 0x4ce8: 'native_strchr',
                0x49f4: 'native_stackavail', 0x4904: 'native_strcpy'}.get(at)
        if name not in ("native_calloc", "native_realloc", "native_malloc", "native_free",
                        "native_memcpy", "native_memset", "native_attr_init",
                        "native_read_verify", "native_reply", "native_clock_gettime",
                        "native_strlen", "native_strcmp", "native_strchr", "native_stackavail", "native_strcpy"):
            return super().intercept(u, address, size, user)
        self.calls.append(name)
        result = 0
        if name in ("native_calloc", "native_malloc", "native_realloc"):
            if self.fail_alloc != name:
                count = r(0) * r(1) if name == "native_calloc" else r(1) if name == "native_realloc" else r(0)
                result = self.allocate(count)
                if name == "native_realloc":
                    u.mem_write(result, bytes(u.mem_read(r(0), 0x110)))
        elif name == "native_clock_gettime":
            assert r(0) == 2
            u.mem_write(r(1), struct.pack("<II", 123, 456789))
            result = self.clock_rc
        elif name == "native_memset":
            u.mem_write(r(0), bytes([r(1) & 255]) * r(2))
            result = r(0)
        elif name == "native_memcpy":
            u.mem_write(r(0), bytes(u.mem_read(r(1), r(2))))
            if self.unstable and r(2) == patch.POOL_SIZE:
                self.put(r(1) + 12, self.word(r(1) + 12) + 2)
            result = r(0)
        elif name == "native_attr_init":
            assert r(1) == 0x8124 and r(2) == 0 and r(3) == 0
            self.put(r(0) + 0x4c, r(1))
        elif name == "native_read_verify":
            assert r(0) == self.ctp and r(1) == self.msg and r(2) == self.ocb and r(3) == 0
            result = self.verify_rc
        elif name == "native_reply":
            assert r(0) == 123
            self.replies.append((r(1), bytes(u.mem_read(r(2), r(3))) if r(3) else b""))
        elif name == "native_free":
            self.allocations.pop(r(0), None)
        elif name == 'native_strlen': result = len(self.cstr(r(0)).encode())
        elif name == 'native_strcmp':
            a, b = self.cstr(r(0)), self.cstr(r(1))
            result = 0 if a == b else 1 if a > b else 0xffffffff
        elif name == 'native_strchr':
            value = self.cstr(r(0)); pos = value.find(chr(r(1)))
            result = r(0) + pos if pos >= 0 else 0
        elif name == 'native_stackavail': result = 0x100000
        elif name == 'native_strcpy':
            u.mem_write(r(0), self.cstr(r(1)).encode() + b'\0'); result = r(0)
        for reg in (UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3, UC_ARM_REG_R12):
            u.reg_write(reg, 0xDEADBEEF)
        u.reg_write(UC_ARM_REG_R0, result)
        u.reg_write(UC_ARM_REG_PC, u.reg_read(UC_ARM_REG_LR))

    def call(self, name, *args):
        self.u.reg_write(UC_ARM_REG_SP, self.sp)
        self.u.reg_write(UC_ARM_REG_LR, self.end)
        for n, arg in enumerate(args): self.u.reg_write(UC_ARM_REG_R0 + n, arg)
        saved = {reg: self.u.reg_read(reg) for reg in range(UC_ARM_REG_R4, UC_ARM_REG_R11 + 1)}
        self.run(name)
        assert saved == {reg: self.u.reg_read(reg) for reg in saved}
        return self.u.reg_read(UC_ARM_REG_R0)

    def init(self):
        self.call("publication_init", self.driver)
        self.entries = self.word(self.driver + 0x114)
        self.entry = self.entries + 2 * 0x88
        self.pool = self.word(self.entry + 0x7c)
        self.put(self.ocb, self.entry)
        self.call("publication_control", self.driver, 1)

    def enqueue(self, mid=0x5201, data=b"synthetic"):
        self.u.mem_write(0x307000, data)
        self.call("publication_enqueue", self.driver, 0x307000, len(data), mid)

    def read(self):
        return self.call("publication_read_hook", self.driver, self.ctp, self.msg, self.ocb)

    def snapshot(self):
        return bytes(self.u.mem_read(self.pool, patch.POOL_SIZE))


class ReceiveMachine(Machine, base.ReceiveMachine):
    pass


class PublicationTests(unittest.TestCase):
    def test_deterministic_fingerprint_and_mapping_scope(self):
        self.assertEqual(DATA, patch.build(STOCK_PATH.read_bytes())[0])
        old = patch.b2.build(STOCK_PATH.read_bytes())[0]
        a, b = ELFFile(io.BytesIO(old)), ELFFile(io.BytesIO(DATA))
        for i, (x, y) in enumerate(zip(a.iter_segments(), b.iter_segments())):
            if i != 3: self.assertEqual(x.header, y.header)
        self.assertEqual(list(b.iter_segments())[3]["p_flags"], 5)
        self.assertEqual(a.get_section_by_name('.dynamic').data(), b.get_section_by_name('.dynamic').data())
        allowed = set(range(52 + 3 * 32 + 16, 52 + 3 * 32 + 24))
        for at in MANIFEST['publication_hooks']:
            allowed.update(range(int(at, 16), int(at, 16) + 4))
        for name in ('start_log', 'receive_log'):
            at = base.SYMBOLS[name]
            allowed.update(range(at, at + 20))
        self.assertTrue(all(i in allowed for i, (x, y) in enumerate(zip(old, DATA)) if x != y))
        with self.assertRaises(ValueError): patch.build(DATA)

    def test_initialization_keeps_old_entries_and_adds_readonly_named_file(self):
        for bias in (0, 0x14000000):
            m = Machine(bias); m.init()
            self.assertEqual(bytes(m.u.mem_read(m.entries, 0x110)), m.original_entries)
            self.assertEqual(m.word(m.driver + 0x118), 3)
            self.assertEqual(m.cstr(m.word(m.entry + 0x78)), 'rgi-events')
            self.assertEqual(m.word(m.entry + 0x4c), 0x8124)
            self.assertEqual(m.snapshot()[:12], b'RGI1' + struct.pack('<II', 1, patch.POOL_SIZE))
            self.assertEqual(m.word(m.pool + 16), 1)
            self.assertEqual(m.word(m.pool + 36), 1)
            self.assertEqual(struct.unpack('<II', m.snapshot()[40:48]), (123, 456789))

    def test_init_allocation_and_clock_failures_leave_stock_available(self):
        for fail in ('native_calloc', 'native_realloc', 'clock'):
            m = Machine()
            m.fail_alloc = fail
            m.clock_rc = -1 if fail == 'clock' else 0
            m.call('publication_init', m.driver)
            self.assertEqual(m.word(m.driver + 0x114), 0x300000)
            self.assertEqual(m.word(m.driver + 0x118), 2)
            self.assertFalse(m.allocations)

    def test_producer_performs_only_bounded_memory_copy_and_wraps_history(self):
        for bias in (0, 0x14000000):
            m = Machine(bias); m.init(); m.calls.clear()
            for n in range(1000): m.enqueue(data=bytes([n & 255]) * (n % 2049))
            self.assertEqual(set(m.calls), {'native_memcpy'})
            self.assertEqual(m.word(m.pool + 20), 1000)
            self.assertEqual(m.word(m.pool + 24), 16)
            self.assertEqual(m.word(m.pool + 28), 0)
            for seq in range(985, 1001):
                slot = m.pool + 64 + ((seq - 1) & 15) * 2064
                self.assertEqual(m.word(slot), seq)
                self.assertEqual(m.word(slot + 8), 1)

    def test_contention_oversize_and_wrap_fail_closed_without_waiting(self):
        for reason in ('busy', 'oversize', 'wrap'):
            m = Machine(); m.init(); m.calls.clear()
            if reason == 'busy': m.put(m.pool + 32, 1)
            if reason == 'wrap': m.put(m.pool + 20, 0xffffffff)
            m.enqueue(data=b'x' * (2049 if reason == 'oversize' else 100))
            self.assertEqual(m.word(m.pool + 28), 1)
            self.assertFalse(m.calls)
            if reason == 'busy': m.put(m.pool + 32, 0)
            m.call('publication_control', m.driver, 1)
            self.assertEqual(m.word(m.pool + 28), 1, 'fault must stay sticky')

    def test_read_snapshot_reply_eof_and_no_producer_lock(self):
        for bias in (0, 0x14000000):
            m = Machine(bias); m.init(); m.enqueue(); expected = m.snapshot()
            self.assertEqual(m.read(), 0x80000000)
            self.assertEqual(m.replies[-1], (patch.POOL_SIZE, expected))
            self.assertEqual(m.word(m.pool + 32), 0)
            self.assertEqual(len(m.allocations), 2)  # entry array + pool only
            self.assertEqual(m.read(), 0x80000000)
            self.assertEqual(m.replies[-1], (0, b''))

    def test_busy_or_changing_writer_has_three_attempt_bound_then_eagain(self):
        for odd in (False, True):
            m = Machine(); m.init(); m.calls.clear()
            if odd: m.put(m.pool + 12, 1)
            else: m.unstable = True
            self.assertEqual(m.read(), 11)
            self.assertEqual(m.calls.count('native_memcpy'), 0 if odd else 3)
            self.assertFalse(m.replies)
            self.assertEqual(len(m.allocations), 2)

    def test_read_short_buffer_allocation_verify_and_xtype_errors(self):
        for reason, expected in (('short', 22), ('alloc', 12), ('verify', 13), ('xtype', 89)):
            m = Machine(); m.init()
            if reason == 'short': m.put(m.msg + 4, 4096)
            if reason == 'alloc': m.fail_alloc = 'native_malloc'
            if reason == 'verify': m.verify_rc = 13
            if reason == 'xtype': m.u.mem_write(m.msg + 8, b'\1')
            self.assertEqual(m.read(), expected)
            self.assertFalse(m.replies)
            self.assertEqual(m.word(m.ocb + 0x80), 0)

    def test_other_file_uses_unmodified_stock_read_path(self):
        m = Machine(); m.init()
        m.put(m.ocb, m.entries)
        m.put(m.entries + 0x4c, 0x8124)
        self.assertEqual(m.read(), 0x80000000)
        self.assertEqual(m.replies, [(0, b'')])

    def test_native_path_lookup_finds_new_file_and_rejects_fake_children(self):
        for bias in (0, 0x14000000):
            m = Machine(bias); m.init()
            base.SYMBOLS['stock_lookup'] = 0x90b4
            for name, expected in ((b'rgi-events\0', m.entry), (b'rgi-events/child\0', 0),
                                   (b'missing\0', 0)):
                m.u.mem_write(0x30b000, name)
                self.assertEqual(m.call('stock_lookup', m.driver, 0x30b000), expected)

    def test_stock_root_directory_listing_includes_publication_file(self):
        m = Machine(); m.init()
        m.put(m.ocb, 0x309000)
        m.put(0x309000 + 0x4c, 0x4124)
        for name in (b'eap', b'media', b'rgi-events'):
            self.assertEqual(m.read(), 0x80000000)
            self.assertIn(name + b'\0', m.replies[-1][1])
        self.assertEqual(m.read(), 0x80000000)
        self.assertEqual(m.replies[-1], (0, b''))

    def test_init_epilogue_preserves_stock_return_and_stack(self):
        for result in (0, 0xffffffff):
            m = Machine()
            m.u.reg_write(UC_ARM_REG_R0, result)
            m.u.reg_write(UC_ARM_REG_R5, m.driver)
            saved = [0x500000 + n for n in range(8)] + [m.end]
            m.u.mem_write(m.sp - 36, struct.pack('<9I', *saved))
            m.u.reg_write(UC_ARM_REG_SP, m.sp - 48)
            m.u.reg_write(UC_ARM_REG_LR, m.end)
            m.u.emu_start(base.SYMBOLS['publication_init_hook'], m.end, count=10000)
            self.assertEqual(m.u.reg_read(UC_ARM_REG_R0), result)
            self.assertEqual(m.u.reg_read(UC_ARM_REG_SP), m.sp)
            self.assertEqual(m.word(m.driver + 0x118), 3 if result == 0 else 2)

    def test_identification_wrapper_resets_session_and_keeps_component(self):
        m = Machine(); m.init(); m.enqueue()
        m.put(m.packet + 0x24, m.buffer + 9)
        m.u.mem_write(m.packet + 0x28, struct.pack('<H', 8))
        m.put(m.packet + 0x1c, 8)
        m.u.mem_write(m.buffer + 15, bytes.fromhex('000800004d494232'))
        m.u.reg_write(UC_ARM_REG_R6, m.driver)
        m.u.reg_write(UC_ARM_REG_R7, m.packet)
        m.run('publication_ident_hook')
        self.assertEqual(m.exit, 0xe13c)
        self.assertEqual(m.word(m.pool + 16), 2)
        self.assertEqual(m.word(m.pool + 24), 0)
        self.assertIn(b'RouteGuidanceDisplayComponent', bytes(m.u.mem_read(m.buffer, 256)))

    def test_destroy_disables_and_clears_history_before_native_cleanup(self):
        m = Machine(); m.init(); m.enqueue()
        # Stop at stock resume; prove its original prologue and arguments.
        from unicorn import UC_HOOK_CODE
        hit = []
        def stop(u, address, size, _):
            if address == m.bias + 0x10bac:
                hit.append((u.reg_read(UC_ARM_REG_R0), u.reg_read(UC_ARM_REG_SP)))
                u.emu_stop()
        m.u.hook_add(UC_HOOK_CODE, stop)
        m.u.reg_write(UC_ARM_REG_R0, m.driver)
        m.u.reg_write(UC_ARM_REG_LR, m.end)
        m.u.emu_start(base.SYMBOLS['publication_destroy_hook'], m.end, count=1000)
        self.assertEqual(hit, [(m.driver, m.sp - 8)])
        self.assertEqual(m.word(m.pool + 36), 0)
        self.assertEqual(m.word(m.pool + 24), 0)

    def test_full_transport_keeps_recycling_and_publishes_before_original_logging(self):
        for bias in (0, 0x14000000):
            m = ReceiveMachine(bias); m.init(); m.calls.clear()
            for n in range(1000):
                mid = (0x5201, 0x5202, 0x5204)[n % 3]
                m.receive(base.make_frame(mid, sequence=n))
                self.assertEqual(len(m.available), 6)
            self.assertEqual(m.recycled, 1000)
            self.assertEqual(m.word(m.pool + 20), 1000)
            self.assertEqual(m.word(m.pool + 28), 0)
            self.assertEqual(set(m.calls), {'native_memcpy'})
            m.receive(base.make_frame(0x5001))
            self.assertEqual(m.nowplay_received, 1)
            self.assertEqual(m.word(m.pool + 20), 1000)

    def test_optional_private_b2_capture_matches_direct_state_model(self):
        path = os.environ.get('CPMAP_PRIVATE_B2_LOG')
        if not path: self.skipTest('set CPMAP_PRIVATE_B2_LOG for private integration replay')
        import rgi_decode
        import rgi_publication
        m = ReceiveMachine(); m.init()
        consumer = rgi_publication.Consumer()
        expected = rgi_decode.GuidanceCache()
        pending = None
        count = 0
        with Path(path).open('rb') as f:
            for line in f:
                if pending is not None:
                    mid, length = pending
                    pending = None
                    data = rgi_decode._hook_bytes(line.rstrip(b'\r\n'), length)
                    expected.apply(rgi_decode.decode_payload(mid, data))
                    m.receive(base.make_frame(mid, data, sequence=count))
                    m.put(m.ocb + 0x80, 0)
                    self.assertEqual(m.read(), 0x80000000)
                    result = consumer.consume(m.replies[-1][1])
                    self.assertFalse(result['fault'])
                    self.assertEqual(result['missing_before_window'], 0)
                    self.assertEqual(consumer.cache.route, expected.route)
                    self.assertEqual(consumer.cache.maneuvers, expected.maneuvers)
                    self.assertEqual(len(m.available), 6)
                    count += 1
                marker = rgi_decode.RX.search(line)
                if marker: pending = (int(marker[1], 16), int(marker[2]))
        self.assertIsNone(pending)
        self.assertEqual(count, 167)
        self.assertEqual(consumer.cache.route.get('route_state'), 0)
        self.assertFalse(consumer.cache.maneuvers)


def load_tests(loader, tests, pattern):
    # B2's ABI/protocol/fallback regressions also execute with the B3 mapping.
    for name in ('test_stock_authentication_identification_gates',
                 'test_identification_and_packet_capacity',
                 'test_start_success_failure_and_native_frame',
                 'test_receive_payload_and_callee_register_preservation',
                 'test_other_messages_and_malformed_frames_delegate_to_stock',
                 'test_b1_native_unknown_id_gate_leaks_receive_buffers'):
        tests.addTest(base.DriverTests(name))
    return tests


if __name__ == '__main__':
    unittest.main(verbosity=2)
