#!/usr/bin/env python3
"""Exercise the removable settings layer on a real base-install fixture.
SPDX-License-Identifier: GPL-3.0-or-later
"""
import argparse
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'port'))
from firmware import sha


class Controls(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.seed_tmp=tempfile.TemporaryDirectory(prefix='settings-golden-');cls.seed=Path(cls.seed_tmp.name)/'mmx';app=cls.seed/'mnt/app'
  for dest,source in [('ifs/lsd.jxe','lsd.jxe'),('mnt/app/armle/lib/dll/ipod-drvr-iap2.so','driver'),('mnt/system/etc/mm/iap2.cfg','iap2.cfg'),('mnt/app/eso/hmi/lsd/lsd.sh','boot'),('mnt/app/eso/bin/apps/dio_manager','dio')]:
   file=cls.seed/dest;file.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ARGS.inputs/source,file)
  (cls.seed/'ramdisk').mkdir();(app/'eso/hmi/lsd/jars').mkdir()
  env=dict(os.environ,CPMAP_TEST_ROOT=str(cls.seed));maps=ARGS.base/'sd-card/Custom/carplay_maps_vc/payload'
  subprocess.run(['/bin/ksh',str(maps/'common/install-carplay-maps.sh'),str(maps),'MU1367','791'],env=env,check=True,capture_output=True)
  payload=Path(cls.seed_tmp.name)/'parent';shutil.copytree(ARGS.base/'sd-card/Custom/carplay_mu1367',payload,ignore=shutil.ignore_patterns('source'));shutil.copy2(ARGS.verifier,payload/'verify')
  subprocess.run(['/bin/ksh',str(payload/'control.sh'),'install',str(payload)],env=env,check=True,capture_output=True)
 @classmethod
 def tearDownClass(cls):cls.seed_tmp.cleanup()
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(prefix='settings-control-');self.addCleanup(self.tmp.cleanup);self.work=Path(self.tmp.name);self.root=self.work/'mmx'
  shutil.copytree(self.seed,self.root);self.app=self.root/'mnt/app';self.saved=self.app/'carplay-mu1367-settings'
  self.payload=self.work/'payload';shutil.copytree(ARGS.payload,self.payload,ignore=shutil.ignore_patterns('source'));shutil.copy2(ARGS.verifier,self.payload/'verify')
  self.tools=self.work/'bin';self.tools.mkdir()
  for n in ('ls','cat','awk','cp','mv','rm','mkdir','chmod','sync'):(self.tools/n).symlink_to(shutil.which(n))
  self.env=dict(os.environ,CPMAP_TEST_ROOT=str(self.root),PATH=str(self.tools))
  self.lsd=self.app/'eso/hmi/lsd/lsd.sh';self.parent=self.app/'carplay-mu1367/control.sh'
  self.original=self.snapshot()
 def snapshot(self):
  return {str(f.relative_to(self.root)):(sha(f.read_bytes()),f.stat().st_mode&0o777) for f in self.root.rglob('*') if f.is_file() and '/carplay-mu1367-settings/' not in str(f) and '/ramdisk/' not in str(f)}
 def run_control(self,action,success=True,saved=False):
  file=self.saved/'control.sh' if saved else self.payload/'control.sh'
  result=subprocess.run(['/bin/ksh',str(file),action,str(self.payload)],env=self.env,capture_output=True,text=True,timeout=30)
  self.assertEqual(result.returncode==0,success,result.stdout+result.stderr);return result.stdout
 def test_install_idempotence_no_sd_uninstall(self):
  self.run_control('install');self.assertIn('ALREADY_INSTALLED',self.run_control('install'));self.assertEqual(self.lsd.read_text().count('VCMenu.jar'),1)
  shutil.rmtree(self.payload);self.run_control('uninstall',saved=True);self.assertEqual(self.snapshot(),self.original)
 def test_parent_remove_guard_and_reverse_order(self):
  self.run_control('install')
  r=subprocess.run(['/bin/ksh',str(self.parent),'uninstall'],env=self.env,capture_output=True,text=True);self.assertNotEqual(r.returncode,0);self.assertIn('SETTINGS_LAYER_FIRST',r.stdout)
  self.run_control('uninstall',saved=True)
  subprocess.run(['/bin/ksh',str(self.parent),'uninstall'],env=self.env,check=True,capture_output=True)
  self.assertEqual((self.app/'armle/lib/dll/ipod-drvr-iap2.so').read_bytes(),(ARGS.inputs/'driver').read_bytes())
 def test_unknown_payload_refused(self):
  file=self.payload/'core.so';data=bytearray(file.read_bytes());data[-1]^=1;file.write_bytes(data)
  self.run_control('install',False);self.assertEqual(self.snapshot(),self.original)
 def test_unknown_guard_refused(self):
  (self.payload/'guard').write_text('exit 0\n');self.run_control('install',False);self.assertEqual(self.snapshot(),self.original)
 def test_damaged_installed_boot_not_reported_as_idempotent(self):
  self.run_control('install');self.lsd.write_text(self.lsd.read_text().replace('$BASE_DIR/lsd/jars/VCMenu.jar:',''))
  self.run_control('install',False)
 def test_wrong_cluster_refused(self):
  (self.app/'carplaymaps/PROFILE').write_text('MU1367/790\n');original=self.snapshot();self.run_control('install',False);self.assertEqual(self.snapshot(),original)
 def test_active_phone_refused(self):
  (self.root/'ramdisk/carplay-altstream.ready').write_text('ready');self.run_control('install',False);self.assertEqual(self.snapshot(),self.original)
 def test_rename_failure_restores_every_target(self):
  file=self.tools/'mv';file.unlink();real=shutil.which('mv');target=self.lsd
  once=self.work/'once';file.write_text('#!/bin/ksh\nif [ "$2" = '+shlex.quote(str(target))+' ] && [ ! -f '+shlex.quote(str(once))+' ]; then : > '+shlex.quote(str(once))+'; exit 1; fi\nexec '+shlex.quote(real)+' "$@"\n');file.chmod(0o755)
  self.run_control('install',False);self.assertEqual(self.snapshot(),self.original)
 def test_crash_snapshot_recovery_without_sd(self):
  self.run_control('install');(self.saved/'STATE').write_text('prepared\n');(self.app/'carplaymaps/core.so.settings-new').write_bytes(b'partial');shutil.rmtree(self.payload)
  self.run_control('recover',saved=True);self.assertEqual(self.snapshot(),self.original)
 def test_corrupt_backup_refuses_before_any_restore(self):
  self.run_control('install');(self.saved/'backup/core').write_bytes(b'bad');current=self.snapshot();self.run_control('recover',False,saved=True);self.assertEqual(self.snapshot(),current)
 def test_later_boot_entries_preserved(self):
  self.run_control('install');self.lsd.write_text(self.lsd.read_text()+'# Later unrelated setting\n');self.run_control('uninstall',saved=True)
  self.assertIn('# Later unrelated setting',self.lsd.read_text());self.assertNotIn('VCMenu.jar',self.lsd.read_text())
 def test_symlink_parent_refused(self):
  target=self.app/'carplaymaps/libcpvc-mirror-tap.so';sentinel=self.work/'sentinel';sentinel.write_text('safe');target.symlink_to(sentinel)
  self.run_control('install',False);self.assertEqual(sentinel.read_text(),'safe')
 def test_unknown_existing_core_refused(self):
  file=self.app/'carplaymaps/core.so';file.write_bytes(b'other');current=self.snapshot();self.run_control('install',False);self.assertEqual(self.snapshot(),current)
 def test_existing_settings_recovery_never_overwritten(self):
  self.run_control('install');self.run_control('uninstall',saved=True);digest=sha((self.saved/'backup/core').read_bytes());self.run_control('install',False);self.assertEqual(digest,sha((self.saved/'backup/core').read_bytes()))


if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__)
 for n in ('base','payload','inputs','verifier','output'):p.add_argument('--'+n,type=Path,required=True)
 ARGS=p.parse_args();r=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Controls))
 result={'passed':r.wasSuccessful(),'tests':r.testsRun,'controller_sha256':sha((ARGS.payload/'control.sh').read_bytes()),'test_sha256':sha(Path(__file__).read_bytes())};ARGS.output.write_text(json.dumps(result,indent=2)+'\n');raise SystemExit(not r.wasSuccessful())
