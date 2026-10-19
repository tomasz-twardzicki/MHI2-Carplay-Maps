#!/usr/bin/env python3
"""B4 regression: identify precedes filesystem creation on native MU1427.

Usage: python test-activation.py EXACT_FACTORY_DRIVER
Includes B3's publication/receive/reader tests against the B4 image.
"""
import importlib.util
import io
import os
from pathlib import Path
import struct
import unittest

from elftools.elf.elffile import ELFFile
from unicorn.arm_const import *

HERE = Path(__file__).resolve().parent


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec); spec.loader.exec_module(value)
    return value


b3 = module('publication_tests', HERE / 'test-publication.py')
patch = module('activation_patch', HERE / 'patch-activation.py')
DATA, MANIFEST = patch.build(b3.STOCK_PATH.read_bytes())
b3.DATA = DATA
b3.base.DATA = DATA
b3.base.SYMBOLS = {k: int(v, 16) for k, v in MANIFEST['symbols'].items()}


class ActivationTests(b3.PublicationTests):
    def finish_fsys(self, m, hook):
        # Exact stock epilogue stack, without artificially enabling publication.
        m.u.reg_write(UC_ARM_REG_R0, 0)
        m.u.reg_write(UC_ARM_REG_R5, m.driver)
        saved = [0x500000 + n for n in range(8)] + [m.end]
        m.u.mem_write(m.sp - 36, struct.pack('<9I', *saved))
        m.u.reg_write(UC_ARM_REG_SP, m.sp - 48)
        m.u.reg_write(UC_ARM_REG_LR, m.end)
        m.u.emu_start(m.bias + b3.base.SYMBOLS[hook], m.end, count=10000)
        self.assertEqual(m.u.reg_read(UC_ARM_REG_SP), m.sp)
        self.assertEqual(m.u.reg_read(UC_ARM_REG_R0), 0)
        m.entry = m.word(m.driver + 0x114) + 2 * 0x88
        m.pool = m.word(m.entry + 0x7c)
        m.put(m.ocb, m.entry)

    def identify_before_fsys(self, m):
        m.put(m.packet + 0x24, m.buffer + 9)
        m.put(m.packet + 0x1c, 8)
        m.u.mem_write(m.packet + 0x28, struct.pack('<H', 8))
        m.u.mem_write(m.buffer + 15, bytes.fromhex('000800004d494232'))
        m.u.reg_write(UC_ARM_REG_R6, m.driver)
        m.u.reg_write(UC_ARM_REG_R7, m.packet)
        m.u.reg_write(UC_ARM_REG_SP, m.sp)
        m.u.reg_write(UC_ARM_REG_LR, m.end)
        m.run('publication_ident_hook')
        self.assertEqual(m.word(m.driver + 0x118), 2)

    def test_native_order_reproduces_b3_zero_header_and_b4_publishes(self):
        for bias in (0, 0x14000000):
            for hook, enabled in (('publication_init_hook', 0), ('activation_init_hook', 1)):
                m = b3.ReceiveMachine(bias)
                self.identify_before_fsys(m)
                self.finish_fsys(m, hook)
                self.assertEqual(m.word(m.pool + 16), enabled)
                self.assertEqual(m.word(m.pool + 36), enabled)
                # Start stays after filesystem creation, using original B2 send.
                m.u.reg_write(UC_ARM_REG_R4, m.driver)
                m.u.reg_write(UC_ARM_REG_R5, 0)
                m.u.reg_write(UC_ARM_REG_LR, m.end)
                m.run('start_hook')
                self.assertEqual(m.sent[-1][:6], bytes.fromhex('404000185200'))
                m.receive(b3.base.make_frame(0x5201))
                self.assertEqual(m.word(m.pool + 20), enabled)
                self.assertEqual(m.word(m.pool + 28), 0)
                self.assertEqual(len(m.available), 6)
                self.assertEqual(m.read(), 0x80000000)
                import rgi_publication
                snapshot = rgi_publication.decode_snapshot(m.replies[-1][1])
                self.assertEqual(snapshot.enabled, bool(enabled))
                self.assertEqual(len(snapshot.events), enabled)

    def test_native_order_allocation_failure_keeps_stock_epilogue_successful(self):
        m = b3.Machine(); self.identify_before_fsys(m)
        m.fail_alloc = 'native_calloc'
        self.finish_fsys(m, 'activation_init_hook')
        self.assertEqual(m.word(m.driver + 0x118), 2)
        self.assertFalse(m.allocations)

    def test_deterministic_fingerprint_and_mapping_scope(self):
        self.assertEqual(DATA, patch.build(b3.STOCK_PATH.read_bytes())[0])
        baseline, old = patch.b3.build(b3.STOCK_PATH.read_bytes())
        a, b = ELFFile(io.BytesIO(baseline)), ELFFile(io.BytesIO(DATA))
        for n, (x, y) in enumerate(zip(a.iter_segments(), b.iter_segments())):
            if n != 3: self.assertEqual(x.header, y.header)
        allowed = set(range(52 + 3 * 32 + 16, 52 + 3 * 32 + 24)) | set(range(0x909c, 0x90a0))
        for name, prefix in (('start_log', b'CPMAP_RGI_START B'), ('receive_log', b'CPMAP_RGI_RX B')):
            allowed.add(int(old['symbols'][name], 16) + len(prefix))
        self.assertTrue(all(n in allowed for n, (x, y) in enumerate(zip(baseline, DATA)) if x != y))
        self.assertEqual(a.get_section_by_name('.dynamic').data(), b.get_section_by_name('.dynamic').data())

    def test_optional_private_b3_route_lane_and_stop_replay(self):
        path = os.environ.get('CPMAP_PRIVATE_B3_LOG')
        if not path: self.skipTest('set CPMAP_PRIVATE_B3_LOG for B3 lane integration')
        import rgi_decode as rg
        import rgi_publication as pub
        m = b3.ReceiveMachine(); self.identify_before_fsys(m); self.finish_fsys(m, 'activation_init_hook')
        expected = rg.GuidanceCache(); consumer = pub.Consumer()
        pending = None; count = 0; lanes = 0
        with Path(path).open('rb') as f:
            for line in f:
                if pending:
                    mid, size = pending; pending = None
                    data = rg._hook_bytes(line.rstrip(b'\r\n'), size)
                    expected.apply(rg.decode_payload(mid, data))
                    m.receive(b3.base.make_frame(mid, data, sequence=count))
                    m.put(m.ocb + 0x80, 0)
                    self.assertEqual(m.read(), 0x80000000)
                    result = consumer.consume(m.replies[-1][1])
                    self.assertTrue(result['enabled']); self.assertFalse(result['fault'])
                    self.assertEqual(result['missing_before_window'], 0)
                    self.assertEqual(consumer.cache.route, expected.route)
                    self.assertEqual(consumer.cache.maneuvers, expected.maneuvers)
                    self.assertEqual(consumer.cache.lanes, expected.lanes)
                    self.assertEqual(len(m.available), 6)
                    count += 1; lanes += mid == 0x5204
                match = rg.RX.search(line)
                if match: pending = (int(match[1], 16), int(match[2]))
        self.assertIsNone(pending)
        self.assertEqual((count, lanes), (277, 18))
        self.assertEqual(consumer.cache.route.get('route_state'), 0)
        self.assertFalse(consumer.cache.maneuvers); self.assertFalse(consumer.cache.lanes)


def load_tests(loader, tests, pattern):
    # Reuse the six original stock ABI/identification/receive fallback tests.
    return b3.load_tests(loader, tests, pattern)


if __name__ == '__main__': unittest.main(verbosity=2)
