#!/usr/bin/env python3
"""Execute N3 copy/lifetime seams and inherited N2/B4 ARM regressions.
SPDX-License-Identifier: GPL-3.0-or-later
"""
import importlib.util
import io
import json
from pathlib import Path
import struct
import sys
import unittest
from elftools.elf.elffile import ELFFile

HERE=Path(__file__).resolve().parent
STOCK=Path(sys.argv[1]); OUTPUT=Path(sys.argv[2]); del sys.argv[2:]
def load(name,path):
    s=importlib.util.spec_from_file_location(name,path)
    m=importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
n2=load('n3_n2_tests',HERE.parent/'n2/test-driver.py')
patch=load('n3_build',HERE/'build-driver.py')
DATA,MANIFEST=patch.build(STOCK.read_bytes())
n2.DATA=n2.pub.DATA=n2.pub.base.DATA=DATA
n2.pub.base.SYMBOLS={k:int(v,16) for k,v in MANIFEST['symbols'].items()}
n2.pub.base.SYMBOLS.update(n3_setup_entry=0x89ac,n3_destroy_entry=0x85ac)


class Machine(n2.Machine):
    def data(self,value):
        # Large synthetic transport packets must not overlap the emulated
        # driver/pool heap at 0x310000 (N2 used only tiny fixture packets).
        self.u.mem_write(0x900000,value)
        return self.call('artwork_data_hook',self.driver,7,0x900000,len(value))
    def begin(self,size=600,kind=1):
        self.put(self.driver+0xbc,7)
        self.call('artwork_init_hook',self.driver,7,kind,0)
        self.call('n3_setup_entry',self.driver,7,size,0)
    def meta(self,offset): return self.word(self.pool+33216+offset)
    def image(self):
        self.put(self.ocb+0x80,0); self.put(self.msg+4,800128)
        result=self.call('artwork_read_hook_n3',self.driver,self.ctp,self.msg,self.ocb)
        return result,self.replies[-1][1] if result==0x80000000 else None
    def intercept(self,u,address,size,user):
        if address-self.bias==0x4988 and getattr(self,'inject_read_fault',False):
            from unicorn.arm_const import UC_ARM_REG_R1
            if u.reg_read(UC_ARM_REG_R1)==self.pool+33216:
                # Model RX losing its nonblocking lock attempt during the
                # resource-manager copy. The copied frame must be rejected.
                self.put(self.pool+33216+16,1)
        if address-self.bias==0x1faec and hasattr(self,'pool'):
            if not hasattr(self,'pps_lengths'):self.pps_lengths=[]
            self.pps_lengths.append(self.meta(20))
        return super().intercept(u,address,size,user)


class CaptureTests(unittest.TestCase):
    def test_owned_fragmented_image_before_pps_and_preserved_stock(self):
        for bias in (0,0x14000000):
            m=Machine(bias);m.init(); before=m.snapshot()
            self.assertEqual(m.allocations[m.pool],833344)
            m.begin(); value=b'\xff\xd8\xff'+bytes(range(199))*3
            m.data(value[:200]);self.assertEqual(m.meta(20),0)
            m.data(value[200:]);self.assertEqual(m.meta(20),600)
            self.assertEqual(m.meta(24),2);self.assertEqual(m.meta(28),1)
            self.assertEqual(m.pps_lengths[-1],600)
            self.assertEqual(m.counter(32),1);self.assertEqual(m.word(m.slot()+0x138),0)
            m.u.mem_write(m.word(m.slot()+0x130),b'x'*600)
            result,image=m.image();self.assertEqual(result,0x80000000)
            self.assertEqual(image[:4],b'N3AR');self.assertEqual(image[128:],value)
            self.assertEqual(struct.unpack_from('<I',image,36)[0],1)
            self.assertEqual(m.snapshot(),before)
            m.data(b'x');self.assertEqual(m.meta(28),1)

    def test_exact_maximum_and_no_producer_allocation_or_io(self):
        m=Machine();m.init();m.begin(800000);m.calls.clear()
        value=b'\x89PNG\r\n\x1a\n'+bytes(800000-8)
        m.data(value)
        self.assertEqual(m.meta(20),800000);self.assertEqual(m.meta(24),1)
        self.assertEqual(set(m.calls),{'native_memcpy','native_free'}) # stock frees PPS scratch
        self.assertEqual(m.image()[1][128:],value)

    def test_destroy_setup_cancel_and_id_reuse_clear_owned_image(self):
        for action in ('destroy','setup','init'):
            m=Machine();m.init();m.begin();m.data(b'\xff\xd8\xff'+bytes(597))
            generation=m.meta(12)
            if action=='destroy':m.call('n3_destroy_entry',m.driver,7)
            elif action=='setup':m.call('n3_setup_entry',m.driver,7,600,0)
            else:m.call('artwork_init_hook',m.driver,7,1,0)
            self.assertGreater(m.meta(12),generation)
            self.assertEqual(len(m.image()[1]),128)
            self.assertEqual(m.word(m.slot()+0x138),0)

    def test_session_change_and_disable_hide_previous_payload(self):
        for action in ('session','disable'):
            m=Machine();m.init();m.begin();m.data(b'\xff\xd8\xff'+bytes(597))
            if action=='session':m.call('publication_control',m.driver,1)
            else:m.call('publication_control',m.driver,0)
            result,image=m.image();self.assertEqual(result,0x80000000)
            self.assertEqual(len(image),128);self.assertEqual(struct.unpack_from('<I',image,20)[0],0)

    def test_current_slot_filter_and_bounds(self):
        for reason in ('wrong_id','short','oversize','bad_signature','bad_received','high_size'):
            m=Machine();m.init();m.begin(2 if reason=='short' else 800001 if reason=='oversize' else 600)
            if reason=='wrong_id':m.put(m.driver+0xbc,9)
            value=(b'noimage!' if reason=='bad_signature' else b'\xff\xd8\xff')
            value=(value+bytes(800001))[:2 if reason=='short' else 800001 if reason=='oversize' else 600]
            m.data(value)
            if reason in ('bad_received','high_size'):
                m.put(m.pool+33216+20,0)
                m.put(m.slot()+(0x140 if reason=='bad_received' else 0x12c),1)
                m.call('artwork_capture',m.driver,7)
            self.assertEqual(m.meta(20),0,reason)

    def test_trylock_and_wrap_fail_closed_keep_guidance(self):
        for action in ('busy','wrap'):
            m=Machine();m.init();m.begin();before=m.snapshot()
            m.put(m.pool+33216+(80 if action=='busy' else 12),1 if action=='busy' else 0xffffffff)
            m.data(b'\xff\xd8\xff'+bytes(597))
            self.assertEqual(m.meta(16),1)
            self.assertEqual(m.image()[0],11)
            self.assertEqual(m.snapshot(),before)
            self.assertEqual(m.counter(32),1)

    def test_read_permissions_eof_malloc_and_normal_fallback(self):
        m=Machine();m.init();m.begin();m.data(b'\xff\xd8\xff'+bytes(597))
        m.verify_rc=13;self.assertEqual(m.image()[0],13)
        m.verify_rc=0;m.fail_alloc='native_malloc';self.assertEqual(m.image()[0],12)
        m.fail_alloc=None;self.assertEqual(m.image()[0],0x80000000)
        m.call('artwork_read_hook_n3',m.driver,m.ctp,m.msg,m.ocb)
        self.assertEqual(m.replies[-1],(0,b''))
        for count,expected in ((128,128),(65536,33088)):
            m.put(m.ocb+0x80,0);m.put(m.msg+4,count)
            m.call('artwork_read_hook_n3',m.driver,m.ctp,m.msg,m.ocb)
            self.assertEqual(len(m.replies[-1][1]),expected)

    def test_rx_contention_during_reader_copy_rejects_frame(self):
        m=Machine();m.init();m.begin();m.data(b'\xff\xd8\xff'+bytes(597))
        before=m.snapshot();m.inject_read_fault=True
        self.assertEqual(m.image()[0],11)
        self.assertEqual(m.meta(16),1);self.assertEqual(m.meta(80),0)
        self.assertEqual(m.snapshot(),before)

    def test_patch_scope_and_no_new_imports(self):
        baseline,_=patch.n2.build(STOCK.read_bytes());allowed=set()
        for at in MANIFEST['hooks']:allowed.update(range(int(at,16),int(at,16)+4))
        elf=ELFFile(io.BytesIO(baseline));ph=elf['e_phoff']+3*elf['e_phentsize']
        allowed.update(range(ph+16,ph+24))
        self.assertTrue(all(i in allowed for i,(a,b) in enumerate(zip(baseline,DATA)) if a!=b))
        patched=ELFFile(io.BytesIO(DATA))
        self.assertEqual(elf.get_section_by_name('.dynamic').data(),patched.get_section_by_name('.dynamic').data())
        self.assertEqual(DATA,patch.build(STOCK.read_bytes())[0])


if __name__=='__main__':
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(CaptureTests)
    for case in (n2.ArtworkTests,n2.pub.PublicationTests,n2.pub.base.DriverTests):
        for test in unittest.defaultTestLoader.loadTestsFromTestCase(case):
            if not any(x in test.id() for x in ('test_patch_scope','real_fragmented_jpeg',
                'deterministic_fingerprint','test_elf_and_only_expected_changes','test_fingerprints_and_determinism')):
                suite.addTest(test)
    result=unittest.TextTestRunner(verbosity=1).run(suite)
    record={'passed':result.wasSuccessful(),'tests':result.testsRun,
        'skipped':[t.id() for t,why in result.skipped],
        'driver_sha256':MANIFEST['driver_sha256'],
        'sources':{p.name:patch.sha(p.read_bytes()) for p in (HERE/'artwork-hooks.S',HERE/'build-driver.py',Path(__file__))}}
    OUTPUT.write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record));sys.exit(not result.wasSuccessful())
