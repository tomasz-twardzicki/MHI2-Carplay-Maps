#!/usr/bin/env python3
"""Extend real-controller regression coverage with clean and upstream restores."""
from pathlib import Path

HERE = Path(__file__).resolve().parent
source = HERE.parent / 'stable/test-host.py'
code = source.read_text().replace('carplay-mu1367-wireless-native-v161t2', 'carplay-mu1367-wireless-native-v163t2').replace('release-v161', 'release-v163e').replace('1_6_1', '1_6_3_E')
code = code.replace("version='1.6.1'", "version='1.6.3-e'")
code = code.replace("controller_sha256=sha((a.build/'sd-card/Custom/carplay_mu1367_release/control.sh').read_bytes())", "controller_sha256=sha((a.build/'sd-card/Custom/carplay_mu1367_release/control.sh').read_bytes()),oem_controller_sha256=sha((a.build/'sd-card/Custom/carplay_mu1367_oem_reset/control.sh').read_bytes())")
# Complete the original firmware fixture (previous tests preinstalled the base).
code = code.replace('  self.stock={}', '''  self.stock={}
  for dest,name in [('proc/boot/libz.so.2','libz.so.2'),('mnt/app/eso/bin/apps/gal','gal')]:
   target=self.root/dest;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes((a.inputs/name).read_bytes());target.chmod(0o755)
  target=self.root/'mnt/app/armle/usr/sbin/mm-ipod';target.parent.mkdir(parents=True);target.write_bytes((self.sd/'Custom/carplay_mu1367_oem_reset/payload/mmipod').read_bytes());target.chmod(0o755)
''')
extra = r'''
class ExtendedSuite(Suite):
 def test_oem_refuses_active_upstream_session(self):
  flag=self.root/'dev/shmem/wcp_cp_session';flag.parent.mkdir(parents=True,exist_ok=True);flag.write_bytes(b'active session')
  before=self.runtime(self.root)
  self.assertIn('DISCONNECT_PHONE_AND_ADAPTER_FULL_REBOOT_FIRST',self.stable('restore-oem',False))
  self.assertEqual(before,self.runtime(self.root))
  self.assertFalse((self.app/'carplay-mu1367-oem-reset').exists())
 def test_fresh_install_without_prior_release(self):
  self.assertFalse((self.app/'carplaymaps').exists())
  self.assertIn('RELEASE_BASE_STAGE_COMPLETE',self.stable('install'))
  self.assertIn('FULL_REBOOT_REQUIRED',self.stable('install',False))
  self.reboot()
  self.assertIn('RELEASE_1_6_3_E_INSTALLED',self.stable('install'))
  self.native_expected()
  self.reboot()
  before=self.runtime(self.root)
  self.assertIn('ALREADY_INSTALLED',self.stable('install'))
  self.assertEqual(before,self.runtime(self.root))
 def test_upstream_forward_reset_without_saved_controllers(self):
  oem=self.sd/'Custom/carplay_mu1367_oem_reset'
  om=json.loads((oem/'manifest.json').read_text())
  # Use all paths in the downloaded v3.2 manifests, including earlier wired
  # mm-ipod/navigation/menu overrides. No upstream executable is run.
  for path in om['additional_removed_files']:
   f=self.root/path.lstrip('/');f.parent.mkdir(parents=True,exist_ok=True);f.write_bytes(b'upstream addon\n')
  for row in om['additional_factory_files'].values():
   (self.root/row['target'].lstrip('/')).write_bytes(b'upstream override\n')
  for name in ('wireless-carplay-maps','cpmapvc-local','.wireless-carplay-maps-manager'):
   d=self.app/('eso/hmi/engdefs/scripts/'+name);d.mkdir(parents=True,exist_ok=True);(d/'journal').write_bytes(b'retain first snapshot')
  d=self.app/'carplaymaps';d.mkdir();(d/'core.so').write_bytes(b'upstream runtime')
  paired=self.root/'mnt/persist/wcp/pairing.key';paired.parent.mkdir();paired.write_bytes(b'per-unit pairing')
  self.assertIn('RELEASE_COMPLETE_OEM_RESTORE',self.stable('restore-oem'))
  for path in om['additional_removed_files']:self.assertFalse((self.root/path.lstrip('/')).exists(),path)
  for k,row in om['additional_factory_files'].items():
   self.assertEqual(sha((self.root/row['target'].lstrip('/')).read_bytes()),row['sha256'])
  for name in ('wireless','wired','manager-recovery'):
   name={'wireless':'upstream-wireless-manager','wired':'upstream-wired-manager','manager-recovery':'upstream-manager-recovery'}[name]
   self.assertEqual((self.app/('carplay-mu1367-oem-reset/archive/'+name+'/journal')).read_bytes(),b'retain first snapshot')
  self.assertEqual(paired.read_bytes(),b'per-unit pairing')
  self.reboot();self.assertIn('ALREADY_COMPLETE',self.stable('restore-oem'))
  # A fresh installation after reset must retain the completed reset record.
  self.assertIn('RELEASE_BASE_STAGE_COMPLETE',self.stable('install'))
  self.reboot();self.assertIn('RELEASE_1_6_3_E_INSTALLED',self.stable('install'))
  self.native_expected()
 def test_oem_refuses_symlink_before_writes(self):
  outside=self.root/'protected';outside.write_bytes(b'do not touch')
  target=self.root/'mnt/ota/wcp_receiver';target.symlink_to(outside)
  before=self.runtime(self.root)
  self.assertIn('UNSAFE_TARGET',self.stable('restore-oem',False))
  self.assertEqual(before,self.runtime(self.root));self.assertEqual(outside.read_bytes(),b'do not touch')
  self.assertFalse((self.app/'carplay-mu1367-oem-reset').exists())
 def test_oem_interrupted_commit_resumes_preserving_first_snapshot(self):
  oem=self.sd/'Custom/carplay_mu1367_oem_reset'
  tools=Path(self.tmp.name)/'fault';tools.mkdir();once=tools/'once'
  (tools/'mv').write_text('#!/bin/ksh\ncase "$1" in *.oem-reset-new) if [ ! -f "'+str(once)+'" ];then : > "'+str(once)+'";exit 1;fi;;esac\nexec '+shutil.which('mv')+' "$@"\n');(tools/'mv').chmod(0o755)
  self.run_script(self.rel/'control.sh',['restore-oem',self.rel],False,env=dict(self.env,PATH=str(tools)+':'+self.env['PATH']))
  r=self.app/'carplay-mu1367-oem-reset'
  snapshots={f.name:f.read_bytes() for f in (r/'pre-reset').iterdir()}
  self.reboot();self.assertIn('RELEASE_COMPLETE_OEM_RESTORE',self.stable('restore-oem'))
  self.assertEqual(snapshots,{f.name:f.read_bytes() for f in (r/'pre-reset').iterdir()})
Suite=ExtendedSuite
'''
code = code.replace("names=[n for n in Suite.__dict__ if n.startswith('test_')]", extra + "\nnames=sorted(n for n in dir(Suite) if n.startswith('test_') and (n in ExtendedSuite.__dict__ or n in ExtendedSuite.__mro__[1].__dict__))", 1)
exec(compile(code, str(source), 'exec'), dict(__file__=str(source), __name__='v163e_tests'))
