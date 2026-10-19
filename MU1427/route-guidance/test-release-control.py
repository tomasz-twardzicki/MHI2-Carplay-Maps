#!/usr/bin/env python3
"""Real release JAR/reader/driver and closed-PATH installation/rollback tests."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
PAYLOAD = HERE.parent.parent/'releases/CarPlay_Maps_VC_Full_Toolboxes/VW_SKODA_ALL_CarPlay_Maps_VC_FULL_MQB_Toolbox_V4/Custom/carplay_native_guidance'


class ReleaseControls(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='cpmap-release-control-')
        self.addCleanup(self.temp.cleanup); self.work = Path(self.temp.name)
        self.root = self.work / 'mmx'; self.payload = self.work / 'payload'; self.payload.mkdir()
        self.tools = self.work / 'bin'; self.tools.mkdir()
        for n in ('ls','cat','rm','awk','cp','mv','mkdir','chmod','sync'):
            (self.tools/n).symlink_to(shutil.which(n))
        for n, size in [('ifs/lsd.jxe',52751492), ('mnt/app/armle/lib/dll/ipod-drvr-iap2.so',739925),
                        ('mnt/system/etc/mm/iap2.cfg',5905)]:
            f=self.root/n; f.parent.mkdir(parents=True,exist_ok=True)
            with f.open('wb') as stream: stream.truncate(size)
        (self.root/'ramdisk').mkdir()
        self.driver=self.root/'mnt/app/armle/lib/dll/ipod-drvr-iap2.so'
        self.config=self.root/'mnt/system/etc/mm/iap2.cfg'
        self.lsd=self.root/'mnt/app/eso/hmi/lsd/lsd.sh'; self.lsd.parent.mkdir(parents=True)
        (self.lsd.parent/'jars').mkdir()
        self.original=('#!/bin/ksh\nBASE_DIR=/mnt/app/eso/hmi\nBOOTCLASSPATH="-Xbootclasspath/a:/ifs/lsd.jxe"\n'
          'BOOTCLASSPATH="$BOOTCLASSPATH -Xbootclasspath/p:$BASE_DIR/lsd/jars/NavActiveIgnore.jar:$BASE_DIR/lsd/jars/CarPlayClusterControls.jar"\n'
          '$J9 $VMOPTIONS $BOOTCLASSPATH -jxe $HMI_JXE &\n')
        self.lsd.write_text(self.original); self.lsd.chmod(0o755)
        profile=self.root/'mnt/app/carplaymaps/PROFILE'; profile.parent.mkdir(); profile.write_text('MU1427/791\n')
        self.jar=self.lsd.parent/'jars/CarPlayRouteGuidanceD1.jar'
        self.saved=self.root/'mnt/app/carplay-route-guidance'
        jar=(ARGS.hmi/'CarPlayRouteGuidanceD1.jar').read_bytes()
        reader=(ARGS.native/'rgi-observer').read_bytes()
        (self.payload/'CarPlayRouteGuidanceD1.jar').write_bytes(jar)
        (self.payload/'rgi-observer').write_bytes(reader)
        (self.payload/'VERSION').write_text('release-test\n')
        shutil.copytree(PAYLOAD/'driver',self.payload/'driver')
        shutil.copy2(PAYLOAD/'driver-control.sh',self.payload/'driver-control.sh')
        self.script=self.work/'control.sh'
        self.script.write_text((HERE/'release/control.sh').read_text().replace('@BUILD_ID@','release-test')
                              .replace('@JAR_SIZE@',str(len(jar))).replace('@READER_SIZE@',str(len(reader))))
        self.env=dict(os.environ,PATH=str(self.tools),CPMAP_TEST_ROOT=str(self.root))

    def run_control(self,action,success=True,local=False):
        script=self.saved/'control.sh' if local else self.script
        r=subprocess.run(['/bin/ksh',str(script),action,str(self.payload)],env=self.env,capture_output=True,text=True,timeout=10)
        self.assertEqual(r.returncode==0,success,r.stdout+r.stderr);return r.stdout

    def assert_stock(self):
        self.assertEqual(self.driver.read_bytes(),bytes(739925));self.assertEqual(self.config.read_bytes(),bytes(5905))

    def reject_rename(self,target):
        tool=self.tools/'mv';tool.unlink()
        tool.write_text('#!/bin/sh\nif [ "$2" = '+shlex.quote(str(target))+' ]; then exit 1; fi\nexec '+shlex.quote(shutil.which('mv'))+' "$@"\n')
        tool.chmod(0o755)

    def test_factory_install_reinstall_and_no_sd_complete_removal(self):
        self.run_control('install');self.run_control('install')
        self.assertEqual(self.jar.read_bytes(),(self.payload/'CarPlayRouteGuidanceD1.jar').read_bytes())
        self.assertEqual(self.lsd.stat().st_mode&0o777,0o755)
        self.assertEqual(self.lsd.read_text().count('CPMAP_GUIDANCE_AUTOSTART'),1)
        self.assertEqual(self.driver.stat().st_size,743196)
        shutil.rmtree(self.payload);self.run_control('uninstall',local=True)
        self.assertEqual(self.lsd.read_text(),self.original);self.assertFalse(self.jar.exists());self.assert_stock()

    def test_base_factory_restore_removes_guidance_before_video_restore(self):
        self.run_control('install')
        scripts=self.root/'mnt/app/eso/hmi/engdefs/scripts/mqb';scripts.mkdir(parents=True)
        (scripts/'cpmap_restore_core.sh').write_text('#!/bin/ksh\necho CORE_RESTORE_REACHED\n')
        wrapper=HERE.parent.parent/'releases/CarPlay_Maps_VC_Full_Toolboxes/VW_SKODA_ALL_CarPlay_Maps_VC_FULL_MQB_Toolbox_V4/Toolbox/scripts/cpmap_restore.sh'
        shutil.rmtree(self.payload)
        r=subprocess.run(['/bin/ksh',str(wrapper)],env=self.env,capture_output=True,text=True,timeout=10)
        self.assertEqual(r.returncode,0,r.stdout+r.stderr)
        self.assertIn('CORE_RESTORE_REACHED',r.stdout);self.assertFalse(self.jar.exists());self.assert_stock()

    def test_existing_b4_original_backups_are_preserved(self):
        subprocess.run(['/bin/ksh',str(self.payload/'driver-control.sh'),'install',str(self.payload/'driver')],env=self.env,check=True,capture_output=True)
        b=self.root/'mnt/app/route-guidance-b1/stock-driver.so';original=b.read_bytes()
        self.run_control('install');self.assertEqual(b.read_bytes(),original)
        self.run_control('uninstall');self.assert_stock()

    def test_later_hmi_entries_survive_removal(self):
        self.run_control('install')
        self.lsd.write_text(self.lsd.read_text().replace('-Xbootclasspath/p:','-Xbootclasspath/p:$BASE_DIR/lsd/jars/Later.jar:'))
        self.run_control('uninstall')
        self.assertEqual(self.lsd.read_text(),self.original.replace('-Xbootclasspath/p:','-Xbootclasspath/p:$BASE_DIR/lsd/jars/Later.jar:'))

    def test_wrong_firmware_profile_payload_refused_without_writes(self):
        (self.root/'mnt/app/carplaymaps/PROFILE').write_text('MU1367/791\n')
        self.run_control('install',False);self.assertFalse(self.saved.exists());self.assert_stock()
        (self.root/'mnt/app/carplaymaps/PROFILE').write_text('MU1427/791\n')
        (self.payload/'rgi-observer').write_bytes(b'bad')
        self.run_control('install',False);self.assertFalse(self.saved.exists());self.assertEqual(self.lsd.read_text(),self.original)
        with (self.root/'ifs/lsd.jxe').open('wb') as stream:stream.truncate(55840541)
        self.assertIn('MU1427_ONLY',self.run_control('install',False));self.assert_stock()

    def test_test_adapter_and_unknown_boot_structure_refused(self):
        self.jar.write_bytes(b'old-test-adapter');self.run_control('install',False);self.assert_stock()
        self.jar.unlink();self.lsd.write_text('unknown boot structure\n')
        self.run_control('install',False);self.assertFalse(self.saved.exists());self.assert_stock()

    def test_boot_commit_failure_rolls_back_new_driver_and_jar(self):
        self.reject_rename(self.lsd);self.run_control('install',False)
        self.assertEqual(self.lsd.read_text(),self.original);self.assertFalse(self.jar.exists());self.assert_stock()

    def test_restore_rename_failure_keeps_jar_and_supports_no_sd_retry(self):
        self.run_control('install');modified=self.lsd.read_bytes();self.reject_rename(self.lsd)
        shutil.rmtree(self.payload);self.run_control('uninstall',False,local=True)
        self.assertEqual(self.lsd.read_bytes(),modified);self.assertTrue(self.jar.exists())
        self.assertTrue((self.root/'ramdisk/carplay-route-guidance/disabled').exists())
        (self.tools/'mv').unlink();(self.tools/'mv').symlink_to(shutil.which('mv'))
        self.run_control('uninstall',local=True);self.assert_stock();self.assertEqual(self.lsd.read_text(),self.original)

    def test_driver_restore_failure_retains_local_recovery(self):
        self.run_control('install');self.reject_rename(self.config);self.run_control('uninstall',False)
        self.assertTrue((self.saved/'control.sh').is_file())
        (self.tools/'mv').unlink();(self.tools/'mv').symlink_to(shutil.which('mv'))
        shutil.rmtree(self.payload);self.run_control('uninstall',local=True);self.assert_stock()

    def test_disable_without_sd_driver_jar_or_copy_tools(self):
        self.run_control('install');shutil.rmtree(self.payload);self.jar.unlink();self.driver.unlink()
        (self.tools/'cp').unlink();(self.tools/'mv').unlink()
        self.run_control('disable',local=True)
        self.assertTrue((self.root/'ramdisk/carplay-route-guidance/disabled').is_file())

    def test_reinstall_detects_changed_driver(self):
        self.run_control('install');self.config.write_bytes(b'bad')
        self.assertIn('INSTALLED_DRIVER_CONFIG',self.run_control('install',False))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('hmi',type=Path,nargs='?',default=PAYLOAD);p.add_argument('native',type=Path,nargs='?',default=PAYLOAD)
    p.add_argument('--output',type=Path,required=True);ARGS=p.parse_args()
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(ReleaseControls))
    proof={'passed':result.wasSuccessful(),'tests':result.testsRun,
           'controller_sha256':hashlib.sha256((HERE/'release/control.sh').read_bytes()).hexdigest(),
           'test_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
           'jar_sha256':hashlib.sha256((ARGS.hmi/'CarPlayRouteGuidanceD1.jar').read_bytes()).hexdigest(),
           'reader_sha256':hashlib.sha256((ARGS.native/'rgi-observer').read_bytes()).hexdigest()}
    ARGS.output.write_text(json.dumps(proof,indent=2)+'\n');raise SystemExit(not result.wasSuccessful())
