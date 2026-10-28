#!/usr/bin/env python3
"""Execute N2 and stock transfer routines, plus B4 guidance regressions.
SPDX-License-Identifier: GPL-3.0-or-later
"""
import importlib.util
import json
from pathlib import Path
import struct
import sys
import unittest
from unicorn.arm_const import *

HERE = Path(__file__).resolve().parent
RG = HERE.parents[1] / 'route-guidance'
STOCK_PATH = Path(sys.argv[1])
OUTPUT = Path(sys.argv[2]) if len(sys.argv)>2 else None
del sys.argv[2:]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


pub = load('n2_publication_tests', RG / 'test-publication.py')
patch = load('n2_driver_builder', HERE / 'build-driver.py')
DATA, MANIFEST = patch.build(STOCK_PATH.read_bytes())
pub.DATA = pub.base.DATA = DATA
pub.base.SYMBOLS = {k: int(v, 16) for k, v in MANIFEST['symbols'].items()}


class Machine(pub.Machine):
    def intercept(self, u, address, size, user):
        at = address - self.bias
        if at in (0x1faec, 0x1faac, 0x4c40, 0x4bd4):
            # PPS and stock mutexes are OS seams. Transfer allocation/copy,
            # complete-state transition and the shared cursor are real ARM.
            u.reg_write(UC_ARM_REG_R0, 0)
            u.reg_write(UC_ARM_REG_PC, u.reg_read(UC_ARM_REG_LR)); return
        if at == 0x49b8:
            result = 0 if self.fail_alloc == 'native_malloc' else self.allocate(u.reg_read(UC_ARM_REG_R0))
            u.reg_write(UC_ARM_REG_R0, result)
            u.reg_write(UC_ARM_REG_PC, u.reg_read(UC_ARM_REG_LR)); return
        if at == 0x4a90:
            u.reg_write(UC_ARM_REG_R0, 0x30d000)
            u.reg_write(UC_ARM_REG_PC, u.reg_read(UC_ARM_REG_LR)); return
        return super().intercept(u, address, size, user)

    def slot(self, ident=7): return self.driver + 48 * ident
    def counter(self, offset): return self.word(self.pool + 33088 + offset)
    def begin(self, size=600, kind=1):
        self.call('artwork_init_hook', self.driver, 7, kind, 0)
        self.call('artwork_setup_hook', self.driver, 7, size, 0)
    def data(self, value):
        self.u.mem_write(0x30c000, value)
        return self.call('artwork_data_hook', self.driver, 7, 0x30c000, len(value))


class ArtworkTests(unittest.TestCase):
    def test_real_fragmented_jpeg_and_no_cursor_change(self):
        for bias in (0, 0x100000):
            m = Machine(bias); m.init(); before = m.snapshot()
            self.assertEqual(m.allocations[m.pool], 33216)
            m.begin(); image = b'\xff\xd8\xff' + bytes(597)
            m.data(image[:200]); self.assertEqual(m.counter(32), 0)
            m.data(image[200:]); self.assertEqual(m.counter(32), 1)
            self.assertEqual(m.counter(36), 1)
            self.assertEqual(m.counter(20), 1); self.assertEqual(m.counter(24), 1)
            self.assertEqual(m.counter(28), 2)
            self.assertEqual(m.word(m.slot() + 0x138), 0)
            self.assertEqual(bytes(m.u.mem_read(m.word(m.slot() + 0x130), 600)), image)
            self.assertEqual(m.snapshot(), before)
            m.data(b'x'); self.assertEqual(m.counter(32), 1)  # no duplicate completion

    def test_png_and_nonimage_and_other_file_kinds(self):
        for signature, counter in ((b'\x89PNG\r\n\x1a\n', 40), (b'notimage', 52)):
            m = Machine(); m.init(); m.begin(); m.data(signature + bytes(592))
            self.assertEqual(m.counter(counter), 1)
        m = Machine(); m.init(); m.begin(kind=0); m.data(bytes(600))
        self.assertEqual(m.counter(20), 0); self.assertEqual(m.counter(32), 0)

    def test_setup_oversize_and_bounded_signature(self):
        m = Machine(); m.init(); m.begin(800001)
        self.assertEqual(m.counter(44), 1)
        # A tiny completed buffer must never cause an eight-byte signature read.
        m = Machine(); m.init(); m.begin(2); m.data(b'ab')
        self.assertEqual(m.counter(32), 1); self.assertEqual(m.counter(52), 0)

    def test_contention_drops_without_touching_guidance(self):
        m = Machine(); m.init(); before = m.snapshot()
        m.put(m.pool + 33088 + 80, 1); m.begin()
        self.assertEqual(m.counter(16), 1); self.assertEqual(m.counter(20), 0)
        self.assertEqual(m.snapshot(), before)

    def test_stock_setup_allocation_failure_preserved(self):
        m=Machine();m.init();m.call('artwork_init_hook',m.driver,7,1,0)
        m.fail_alloc='native_malloc'
        result=m.call('artwork_setup_hook',m.driver,7,600,0)
        self.assertEqual(result,0xffffffff)
        self.assertEqual(m.counter(24),1);self.assertEqual(m.counter(48),1)
        self.assertEqual(m.word(m.slot()+0x130),0)

    def test_missing_diagnostic_pool_keeps_stock_transfer(self):
        m=Machine();m.fail_alloc='native_calloc'
        m.call('publication_init',m.driver)
        m.begin();self.assertEqual(m.data(b'\xff\xd8\xff'+bytes(597)),0)
        self.assertEqual(m.word(m.slot()+0x140),600)

    def test_diagnostic_read_normal_read_eof_and_errors(self):
        m = Machine(); m.init(); m.begin(); m.data(b'\xff\xd8\xff' + bytes(597))
        m.put(m.msg + 4, 128)
        self.assertEqual(m.call('artwork_read_hook', m.driver, m.ctp, m.msg, m.ocb), 0x80000000)
        result = m.replies[-1][1]
        self.assertEqual(len(result), 128); self.assertEqual(result[:4], b'N2AO')
        self.assertEqual(struct.unpack_from('<I', result, 32)[0], 1)
        m.call('artwork_read_hook', m.driver, m.ctp, m.msg, m.ocb)
        self.assertEqual(m.replies[-1], (0, b''))
        m.put(m.ocb + 0x80, 0); m.put(m.msg + 4, 65536)
        m.call('artwork_read_hook', m.driver, m.ctp, m.msg, m.ocb)
        self.assertEqual(len(m.replies[-1][1]), 33088)
        self.assertEqual(m.replies[-1][1][48:64], bytes(16))
        m.put(m.ocb + 0x80, 0); m.put(m.msg + 4, 128); m.verify_rc = 13
        self.assertEqual(m.call('artwork_read_hook', m.driver, m.ctp, m.msg, m.ocb), 13)
        m.verify_rc = 0; m.put(m.pool + 33088 + 12, 1)
        self.assertEqual(m.call('artwork_read_hook', m.driver, m.ctp, m.msg, m.ocb), 11)

    def test_patch_scope(self):
        b4, _ = patch.b4.build(STOCK_PATH.read_bytes())
        allowed = set()
        for word in (0x8658, 0x89ac, 0x86b0, 0x9260, int(MANIFEST['allocation_patch'], 16)):
            allowed.update(range(word, word + 4))
        # Only extension segment file/memory sizes change in the ELF header.
        from elftools.elf.elffile import ELFFile
        import io
        elf = ELFFile(io.BytesIO(b4)); ph = elf['e_phoff'] + 3 * elf['e_phentsize']
        allowed.update(range(ph + 16, ph + 24))
        self.assertTrue(all(i in allowed for i, (a, b) in enumerate(zip(b4, DATA)) if a != b))


if __name__ == '__main__':
    # Reuse inherited B2 receive/recycling and B3 ring tests against N2. The
    # B3 fingerprint/scope assertion is specific to B3, so use N2's above.
    suite = unittest.TestSuite()
    suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(ArtworkTests))
    for case in (pub.PublicationTests, pub.base.DriverTests if hasattr(pub.base, 'DriverTests') else pub.base.PatchTests):
        for test in unittest.defaultTestLoader.loadTestsFromTestCase(case):
            if not any(n in test.id() for n in ('deterministic_fingerprint',
                    'test_elf_and_only_expected_changes', 'test_fingerprints_and_determinism')):
                suite.addTest(test)
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    record = {'passed': result.wasSuccessful(), 'tests': result.testsRun,
              'skipped': [name.id() for name, why in result.skipped],
              'driver_sha256': MANIFEST['driver_sha256'],
              'test_sha256': patch.sha(Path(__file__).read_bytes()),
              'source_sha256': MANIFEST['source_sha256'],
              'builder_sha256': MANIFEST['builder_sha256']}
    if OUTPUT: OUTPUT.write_text(json.dumps(record,indent=2)+'\n')
    print(json.dumps(record))
    raise SystemExit(not result.wasSuccessful())
