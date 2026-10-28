#!/usr/bin/env python3
"""N3 driver-only install/recovery and snapshot-helper regressions.
SPDX-License-Identifier: GPL-3.0-or-later
"""
import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import struct
import subprocess
import sys
import tempfile
import time
import unittest

HERE=Path(__file__).resolve().parent
DRIVER=Path(sys.argv[1]); HELPER=Path(sys.argv[2]); OUTPUT=Path(sys.argv[3])
HOST_HELPER=Path(sys.argv[4]) if len(sys.argv)>4 else HELPER
BUILD='MU1427-AUDIO-N3-'+hashlib.sha256(DRIVER.read_bytes()+HELPER.read_bytes()).hexdigest()[:12]


def controller():
    text=(HERE/'control.sh').read_text()
    for key,value in {'BUILD':BUILD,'DRIVER_SIZE':str(DRIVER.stat().st_size),'READER_SIZE':str(HELPER.stat().st_size)}.items():
        text=text.replace('@'+key+'@',value)
    return text


class Controls(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory(prefix='n3-controls-');self.addCleanup(temp.cleanup)
        self.work=Path(temp.name);self.root=self.work/'mmx';self.payload=self.work/'payload';self.payload.mkdir()
        self.saved=self.root/'mnt/app/carplay-artwork-n3'
        self.driver=self.root/'mnt/app/armle/lib/dll/ipod-drvr-iap2.so'
        def write(name,data):
            f=self.root/name;f.parent.mkdir(parents=True,exist_ok=True);f.write_bytes(data);return f
        self.driver=write('mnt/app/armle/lib/dll/ipod-drvr-iap2.so',bytes(743196));self.driver.chmod(0o755)
        write('ifs/lsd.jxe',b'').touch()
        with (self.root/'ifs/lsd.jxe').open('wb') as f:f.truncate(52751492)
        write('mnt/app/carplaymaps/PROFILE',b'MU1427/791\n')
        write('mnt/app/carplay-now-playing-n1/VERSION',b'MU1427-AUDIO-N1-8bbacafe81af\n')
        self.preserved={}
        for name,data in (('mnt/app/eso/hmi/lsd/jars/CarPlayNowPlayingTextN1.jar',bytes(21300)),
                          ('mnt/app/eso/hmi/lsd/lsd.sh',b'preserve boot'),('mnt/system/etc/mm/iap2.cfg',bytes(6006)),
                          ('mnt/app/route-guidance-b1/VERSION',b'MU1427-iAP2-RGI-B4-3760797a\n')):
            self.preserved[write(name,data)]=data
        (self.root/'ramdisk').mkdir()
        (self.payload/'VERSION').write_text(BUILD+'\n');shutil.copy2(DRIVER,self.payload/'ipod-drvr-iap2.so');shutil.copy2(HELPER,self.payload/'snapshot')
        self.script=self.work/'control.sh';self.script.write_text(controller())
        self.bin=self.work/'bin';self.bin.mkdir()
        for n in ('ls','cat','rm','mkdir','awk','cp','mv','chmod','sync'):(self.bin/n).symlink_to(shutil.which(n))
        self.env=dict(os.environ,PATH=str(self.bin),CPMAP_TEST_ROOT=str(self.root))

    def tearDown(self):
        for f,data in self.preserved.items():self.assertEqual(f.read_bytes(),data)

    def call(self,action,ok=True,saved=False,arg=None):
        script=self.saved/'control.sh' if saved else self.script
        r=subprocess.run(['/bin/ksh',str(script),action,str(arg or self.payload)],env=self.env,capture_output=True,text=True,timeout=10)
        self.assertEqual(r.returncode==0,ok,r.stdout+r.stderr);return r.stdout

    def fail_mv(self,target):
        f=self.bin/'mv';f.unlink();f.write_text('#!/bin/sh\nif [ "$2" = '+shlex.quote(str(target))+' ]; then exit 1; fi\nexec '+shlex.quote(shutil.which('mv'))+' "$@"\n');f.chmod(0o755)

    def test_install_idempotent_remove_no_sd_and_reinstall(self):
        self.call('install');self.assertEqual(self.driver.read_bytes(),DRIVER.read_bytes())
        self.assertIn('ALREADY_INSTALLED',self.call('install'))
        shutil.rmtree(self.payload);self.call('uninstall',saved=True)
        self.assertEqual(self.driver.read_bytes(),bytes(743196));self.assertEqual(self.driver.stat().st_mode&0o777,0o755)
        self.payload.mkdir();(self.payload/'VERSION').write_text(BUILD+'\n');shutil.copy2(DRIVER,self.payload/'ipod-drvr-iap2.so');shutil.copy2(HELPER,self.payload/'snapshot')
        self.call('install')

    def test_unknown_driver_and_missing_n1_refused(self):
        self.driver.write_bytes(b'unknown');self.call('install',False)
        self.driver.write_bytes(bytes(743196));(self.root/'mnt/app/carplay-now-playing-n1/VERSION').unlink();self.call('install',False)

    def test_failed_install_commit_recoverable(self):
        self.fail_mv(self.driver);self.call('install',False)
        self.assertEqual(self.driver.read_bytes(),bytes(743196));self.call('uninstall',saved=True)

    def test_failed_remove_commit_preserves_recovery(self):
        self.call('install');self.fail_mv(self.driver);self.call('uninstall',False,saved=True)
        self.assertEqual(self.driver.read_bytes(),DRIVER.read_bytes());self.assertTrue((self.saved/'b4-driver.so').exists())
        (self.bin/'mv').unlink();(self.bin/'mv').symlink_to(shutil.which('mv'));self.call('uninstall',saved=True)

    def test_marker_failure_after_commit_recoverable(self):
        # A directory at the marker path is rejected before any write.
        self.saved.mkdir(parents=True);(self.saved/'VERSION').mkdir();self.call('install',False)
        self.assertEqual(self.driver.read_bytes(),bytes(743196))

    def test_stale_lock_and_stage_and_symlink_refused(self):
        lock=self.root/'ramdisk/.carplay-guidance-install-lock';lock.mkdir();self.call('install',False);lock.rmdir()
        stage=Path(str(self.driver)+'.n3-new');stage.write_bytes(b'preserve stage');self.call('install',False);self.assertEqual(stage.read_bytes(),b'preserve stage');stage.unlink()
        self.saved.mkdir(parents=True);(self.saved/'b4-driver.so').symlink_to(self.driver);self.call('install',False)

    def test_unrecognized_later_driver_not_overwritten(self):
        self.call('install');self.driver.write_bytes(b'later unrelated driver');self.call('uninstall',False,saved=True)
        self.assertEqual(self.driver.read_bytes(),b'later unrelated driver')


    def test_export_image_and_empty_and_error_preserved(self):
        self.call('install')
        shutil.copy2(HOST_HELPER,self.saved/'snapshot')
        # The installed size gate is intentional; use the same-sized executable
        # as the controller fixture for this host-only export scenario.
        installed=(self.saved/'control.sh').read_text()
        installed=installed.replace('READER_SIZE='+str(HELPER.stat().st_size),'READER_SIZE='+str(HOST_HELPER.stat().st_size))
        (self.saved/'control.sh').write_text(installed)
        device=self.root/'dev/ipod0/rgi-events';device.parent.mkdir(parents=True)
        import importlib.util
        spec=importlib.util.spec_from_file_location('n3_worker_fixture',HERE/'test-worker.py')
        fixtures=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixtures)
        image=fixtures.png(3,2)
        device.write_bytes(fixtures.frame(image))
        out=self.work/'export1';self.call('export',saved=True,arg=out)
        self.assertEqual((out/'original.bin').read_bytes(),image)
        self.assertTrue((out/'cover.png').is_file())
        self.assertIn('snapshot_result=0',(out/'install.txt').read_text())
        self.call('export',False,saved=True,arg=out)
        device.write_bytes(fixtures.frame())
        out=self.work/'export2';self.call('export',saved=True,arg=out)
        self.assertFalse((out/'original.bin').exists())
        device.unlink()
        out=self.work/'export3';self.call('export',saved=True,arg=out)
        self.assertIn('N3_ERROR=CAPTURE_2',(out/'native.txt').read_text())
        self.assertIn('snapshot_result=1',(out/'install.txt').read_text())

    def test_n2_installed_marker_refused(self):
        old=self.root/'mnt/app/carplay-artwork-n2/VERSION';old.parent.mkdir();old.write_text('N2 installed')
        self.call('install',False)
        self.assertEqual(self.driver.read_bytes(),bytes(743196))


if __name__=='__main__':
    suite=unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromTestCase(c) for c in (Controls,))
    result=unittest.TextTestRunner(verbosity=1).run(suite)
    record={'passed':result.wasSuccessful(),'tests':result.testsRun,'build':BUILD,
            'driver_sha256':hashlib.sha256(DRIVER.read_bytes()).hexdigest(),
            'helper_sha256':hashlib.sha256(HELPER.read_bytes()).hexdigest(),
            'sources':{n:hashlib.sha256((HERE/n).read_bytes()).hexdigest() for n in ('control.sh','capture.c','test-controls.py')}}
    OUTPUT.write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record));raise SystemExit(not result.wasSuccessful())
