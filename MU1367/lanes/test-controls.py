#!/usr/bin/env python3
"""Lane transaction fault injection over an actually installed v1.3.0 fixture.
SPDX-License-Identifier: GPL-3.0-or-later
"""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import unittest
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'port'))
from firmware import sha
spec=importlib.util.spec_from_file_location('settings_fixture',HERE.parent/'settings-v2/test-controls.py')
fixture=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixture)

class Controls(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  fixture.ARGS=ARGS;fixture.Controls.setUpClass();cls.seed=fixture.Controls.seed
  source=ARGS.package/'sd-card/Custom/carplay_mu1367_settings'
  payload=Path(fixture.Controls.seed_tmp.name)/'settings';shutil.copytree(source,payload,ignore=shutil.ignore_patterns('source'));shutil.copy2(ARGS.verifier,payload/'verify')
  subprocess.run(['/bin/ksh',str(payload/'control.sh'),'install',str(payload)],env=dict(os.environ,CPMAP_TEST_ROOT=str(cls.seed)),check=True,capture_output=True)
 @classmethod
 def tearDownClass(cls):fixture.Controls.tearDownClass()
 def setUp(self):
  fixture.Controls.setUp(self);self.saved=self.app/'carplay-mu1367-lanes'
  self.settings=self.app/'carplay-mu1367-settings/control.sh'
  self.original=self.snapshot()
 def snapshot(self):
  return {str(f.relative_to(self.root)):(sha(f.read_bytes()),f.stat().st_mode&0o777) for f in self.root.rglob('*') if f.is_file() and '/carplay-mu1367-lanes/' not in str(f) and '/ramdisk/' not in str(f)}
 run_control=fixture.Controls.run_control
 test_unknown_payload_refused=fixture.Controls.test_unknown_payload_refused
 test_unknown_guard_refused=fixture.Controls.test_unknown_guard_refused
 test_wrong_cluster_refused=fixture.Controls.test_wrong_cluster_refused
 test_active_phone_refused=fixture.Controls.test_active_phone_refused
 test_unknown_existing_core_refused=fixture.Controls.test_unknown_existing_core_refused
 test_corrupt_backup_refuses_before_any_restore=fixture.Controls.test_corrupt_backup_refuses_before_any_restore
 test_existing_settings_recovery_never_overwritten=fixture.Controls.test_existing_settings_recovery_never_overwritten
 def test_install_idempotence_no_sd_uninstall(self):
  self.run_control('install');self.assertIn('ALREADY_INSTALLED',self.run_control('install'))
  self.assertEqual(self.lsd.read_text().count('VCMenu.jar'),1)
  for key,path in [('guidance','eso/hmi/lsd/jars/CarPlayMU1367Guidance.jar'),('menu','eso/hmi/lsd/jars/VCMenu.jar'),('core','carplaymaps/core.so')]:
   self.assertNotEqual(sha((self.app/path).read_bytes()),sha((self.saved/'backup'/key).read_bytes()))
  shutil.rmtree(self.payload);self.run_control('uninstall',saved=True);self.assertEqual(self.snapshot(),self.original)
 def test_both_parent_guards_and_reverse_order(self):
  self.run_control('install')
  for parent in (self.parent,self.settings):
   for action in ('uninstall','recover'):
    r=subprocess.run(['/bin/ksh',str(parent),action],env=self.env,capture_output=True,text=True)
    self.assertNotEqual(r.returncode,0);self.assertIn('LANES_LAYER_FIRST',r.stdout)
  self.run_control('uninstall',saved=True);self.assertEqual(self.snapshot(),self.original)
 def test_final_guard_rename_failure_restores_all_five(self):
  file=self.tools/'mv';file.unlink();real=shutil.which('mv');once=self.work/'once'
  file.write_text('#!/bin/ksh\nif [ "$2" = '+shlex.quote(str(self.settings))+' ] && [ ! -f '+shlex.quote(str(once))+' ];then : > '+shlex.quote(str(once))+';exit 1;fi\nexec '+shlex.quote(real)+' "$@"\n');file.chmod(0o755)
  self.assertIn('SNAPSHOT_RESTORED',self.run_control('install',False));self.assertEqual(self.snapshot(),self.original)
 def test_crash_recovery_without_sd_and_stale_stages(self):
  self.run_control('install');(self.saved/'STATE').write_text('prepared\n');(self.app/'carplaymaps/core.so.lanes-new').write_bytes(b'partial')
  shutil.rmtree(self.payload);self.run_control('recover',saved=True);self.assertEqual(self.snapshot(),self.original)
  self.assertFalse((self.app/'carplaymaps/core.so.lanes-new').exists())
 def test_changed_installed_file_refuses_idempotence_and_removal(self):
  self.run_control('install');(self.app/'carplaymaps/core.so').write_bytes(b'changed');current=self.snapshot()
  self.run_control('install',False);self.run_control('uninstall',False,saved=True);self.assertEqual(self.snapshot(),current)
  self.run_control('recover',saved=True);self.assertEqual(self.snapshot(),self.original)
 def test_preferences_survive_install_and_restore(self):
  prefs=self.root/'mnt/icab/persistent/cpmap-ui';prefs.mkdir(parents=True)
  # Opaque explicit user preference bytes must never be changed by installation.
  (prefs/'navigation-card.state').write_bytes(b'explicit-on-fixture\n');(prefs/'display.state').write_bytes(b'explicit-30-5-fixture\n')
  original=self.snapshot();self.run_control('install');self.run_control('uninstall',saved=True);self.assertEqual(self.snapshot(),original)
 def test_target_symlink_refused(self):
  file=self.app/'carplaymaps/core.so';file.unlink();sentinel=self.work/'sentinel';sentinel.write_text('safe');file.symlink_to(sentinel)
  self.run_control('install',False);self.assertEqual(sentinel.read_text(),'safe')
 def test_recovery_symlink_refused(self):
  sentinel=self.work/'sentinel';sentinel.mkdir();self.saved.symlink_to(sentinel);self.run_control('install',False);self.assertEqual(list(sentinel.iterdir()),[])
 def test_wrong_parent_or_firmware_refused(self):
  for file in (self.app/'carplay-mu1367/VERSION',self.app/'carplay-mu1367-settings/VERSION',self.root/'ifs/lsd.jxe'):
   data=file.read_bytes();file.write_bytes(b'wrong');current=self.snapshot();self.run_control('install',False);self.assertEqual(self.snapshot(),current);file.write_bytes(data)
 def test_stale_stage_refused_until_recovery(self):
  self.run_control('install');(self.app/'carplaymaps/core.so.lanes-new').write_bytes(b'partial');self.run_control('uninstall',False,saved=True)
  self.run_control('recover',saved=True);self.assertEqual(self.snapshot(),self.original)
 def test_shared_lock_respected(self):
  lock=self.root/'ramdisk/.carplay-guidance-install-lock';lock.mkdir();self.run_control('install',False);self.assertTrue(lock.is_dir());self.assertEqual(self.snapshot(),self.original)
 def test_status_reads_actual_adapter_path(self):
  status=self.root/'ramdisk/carplay-route-guidance/adapter-status.txt';status.parent.mkdir();status.write_text('lane_count=3 lane_at=1000\n')
  self.assertIn('lane_count=3',self.run_control('status'));self.assertEqual(self.snapshot(),self.original)

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__)
 for name in ('base','package','payload','inputs','verifier','output'):p.add_argument('--'+name,type=Path,required=True)
 ARGS=p.parse_args();r=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Controls))
 result={'passed':r.wasSuccessful(),'tests':r.testsRun,'controller_sha256':sha((ARGS.payload/'control.sh').read_bytes()),'test_sha256':sha(Path(__file__).read_bytes()),'on_unit_validated':False}
 ARGS.output.write_text(json.dumps(result,indent=2)+'\n');raise SystemExit(not r.wasSuccessful())
