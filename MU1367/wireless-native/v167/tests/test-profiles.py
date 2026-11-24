#!/usr/bin/env python3
"""Exercise real child transactions over the actual installed unchanged v1.6.5-e-test2 parent."""
from pathlib import Path
HERE=Path(__file__).resolve().parent
source=HERE.parents[1]/'stable/test-host.py'
code=source.read_text().replace('carplay-mu1367-wireless-native-v161t2','carplay-mu1367-wireless-native-v165t2').replace('release-v161','release-v165t2').replace('1_6_1','1_6_5_E_TEST2')
code=code.replace('  self.stock={}', "  self.stock={}\n  for dest,name in [('proc/boot/libz.so.2','libz.so.2'),('mnt/app/eso/bin/apps/gal','gal')]:\n   target=self.root/dest;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes((a.inputs/name).read_bytes());target.chmod(0o755)\n")
code=code.replace("version='1.6.1'","version='1.6.7-e'")
extra=r'''
class Profiles(Suite):
 def setUp(self):
  super().setUp()
  self.mod=self.sd/'Custom/carplay_mu1367_input_profile'
  self.profile_root=json.loads((self.mod/'manifest.json').read_text())['790']['recovery_root']
  native=sha((a.build/'sd-card/Custom/carplay_mu1367_wireless_native/verify').read_bytes())
  for f in self.mod.rglob('payload-check.sh'):f.write_text(f.read_text().replace(native,sha(a.verifier.read_bytes())))
  self.parent_root=self.app/'carplay-mu1367-wireless-native-v165t2'
 def boot(self):
  self.reboot();(self.root/'ramdisk/.cpmap-profile-v167-reboot').unlink(missing_ok=True)
 def profile(self,action,success=True):return self.run_script(self.mod/'actions.sh',[action,self.mod],success)
 def setup_parent(self):
  self.current_base();self.stable('install');self.boot()
  self.parent_receipt=(self.parent_root/'backup.index').read_bytes()
  self.rows=json.loads((self.mod/'manifest.json').read_text())['790']['rows']
  self.originals={r['target']:(self.root/r['target'].lstrip('/')).read_bytes() if (self.root/r['target'].lstrip('/')).exists() else None for r in self.rows}
 def originals_ok(self):
  for path,data in self.originals.items():
   f=self.root/path.lstrip('/')
   if data is None:self.assertFalse(f.exists(),path)
   else:self.assertEqual(f.read_bytes(),data,path)
  self.assertEqual((self.parent_root/'backup.index').read_bytes(),self.parent_receipt)
 def test_install_switch_tune_and_restore_parent(self):
  self.setup_parent();self.profile('select-790')
  self.assertEqual((self.app/'carplaymaps/PROFILE').read_text(),'MU1367/790\n')
  self.assertIn('FULL_REBOOT_REQUIRED',self.profile('select-791',False));self.boot()
  # A previous SD cannot silently uninstall the modified parent.
  self.run_script(self.wcp/'control.sh',['uninstall',self.wcp],False)
  conf=self.root/'mnt/persist/altscreen.conf';before=conf.read_bytes()
  self.run_script(self.mod/'tune.sh',['set',self.mod/'790','220','20','600','330'])
  self.assertIn(b'safex=220\n',conf.read_bytes());self.assertIn(b'nsafex=220\n',conf.read_bytes())
  changed=conf.read_bytes()
  self.run_script(self.mod/'tune.sh',['set',self.mod/'790','900','20','600','330'],False)
  self.assertEqual(conf.read_bytes(),changed)
  self.run_script(self.mod/'tune.sh',['reset',self.mod/'790']);self.assertEqual(conf.read_bytes(),before)
  self.profile('select-791');self.originals_ok();self.boot();self.profile('select-791');self.boot()
  self.assertEqual((self.app/'carplaymaps/PROFILE').read_text(),'MU1367/791\n')
  self.profile('remove');self.originals_ok()
 def test_all_commit_failures_and_interruptions(self):
  self.setup_parent();p=self.mod/'790';r=self.app/self.profile_root
  for row in self.rows:
   key=row['key']
   with self.subTest(kind='rollback',key=key):
    self.run_script(p/'control.sh',['install',p],False,dict(self.env,CPMAP_TEST_FAIL_AFTER_KEY=key));self.originals_ok()
   with self.subTest(kind='interrupt',key=key):
    self.run_script(p/'control.sh',['install',p],False,dict(self.env,CPMAP_TEST_INTERRUPT_AFTER_KEY=key))
    self.run_script(r/'control.sh',['recover',r]);self.originals_ok()
 def test_oem_restore_archives_profile_snapshots(self):
  self.setup_parent();self.profile('select-790');self.boot()
  self.assertIn('V167_RESTORED=',self.profile('base-restore-oem'));self.originals_ok();self.boot()
  self.assertIn('WIRELESS_PREVIOUS_LAYER_RESTORED',self.profile('base-restore-oem'));self.boot()
  self.assertIn('RELEASE_COMPLETE_OEM_RESTORE',self.profile('base-restore-oem'))
  self.assertTrue((self.app/'carplay-mu1367-oem-reset/archive'/self.profile_root/'backup.index').is_file())
 def test_base_only_and_damaged_targets_refused(self):
  self.current_base()
  self.assertIn('FINISH_TEST2_BASELINE',self.profile('select-790',False))
  self.assertFalse((self.app/self.profile_root).exists())
  self.stable('install');self.boot();self.profile('select-790');self.boot()
  f=self.root/'mnt/ota/wcp_receiver';f.write_bytes(f.read_bytes()+b'unknown drift')
  before=f.read_bytes();self.profile('remove',False);self.assertEqual(f.read_bytes(),before)
 def test_precommit_preparations_are_retained_and_resumable(self):
  self.setup_parent();self.profile('select-790');self.boot();self.profile('remove');self.boot()
  r=self.app/self.profile_root
  (r/'STATE').write_text('prepared\n')
  for n in ('installed.index','installed.index.sha256'):(r/n).unlink()
  self.profile('remove');self.originals_ok();self.boot()
  (r/'STATE').write_text('collecting\n');(r/'BACKUPS_READY').unlink()
  self.profile('remove');self.originals_ok();self.assertFalse(r.exists());self.boot()
  saved=list(self.app.glob(self.profile_root+'.incomplete-*'));self.assertEqual(len(saved),1)
  self.profile('select-790');self.boot();self.profile('remove');self.boot()
  (r/'STATE').write_text('collecting\n');(r/'BACKUPS_READY').unlink()
  self.profile('select-790');self.boot();self.profile('remove');self.originals_ok()
  self.assertEqual(len(list(self.app.glob(self.profile_root+'.incomplete-*'))),2)

 def _from_v166(self,variant):
  self.current_base()
  archive=a.build.parent/'dist/v1.6.6-e/CarPlay_Maps_VC_MU1367_790_791_v1.6.6-e.zip'
  self.assertEqual(sha(archive.read_bytes()),'1c16da70848c6b81ae7020e514c209e3ce25228f965dbccb3c15e14ea77d8343')
  old=self.root/'withdrawn-v166'
  with zipfile.ZipFile(archive) as z:
   for name in z.namelist():
    if name.startswith('Custom/') and '/source/' not in name and not name.endswith('/'):
     f=old/name;f.parent.mkdir(parents=True,exist_ok=True);f.write_bytes(z.read(name))
  parent=old/'Custom/carplay_mu1367_wireless_native';child=old/'Custom/carplay_mu1367_input_profile'/variant
  native=sha((parent/'verify').read_bytes());config=sha((parent/'config-patch').read_bytes())
  shutil.copy2(self.config_helper,parent/'config-patch')
  for f in old.rglob('verify'):shutil.copy2(a.verifier,f)
  for f in old.rglob('payload-check.sh'):f.write_text(f.read_text().replace(native,sha(a.verifier.read_bytes())).replace(config,sha(self.config_helper.read_bytes())))
  self.run_script(parent/'control.sh',['install',parent]);self.boot()
  self.run_script(child/'control.sh',['install',child]);self.boot()
  roots=json.loads((child.parent/'manifest.json').read_text());saved_child=self.app/roots[variant]['recovery_root'];saved_parent=self.app/'carplay-mu1367-wireless-native-v166'
  indexes={r:(r/'backup.index').read_bytes() for r in (saved_child,saved_parent)}
  c=(saved_child/'control.sh').read_bytes();(saved_child/'control.sh').write_bytes(c+b'\n# unknown edit\n')
  before=self.runtime(self.root)
  self.assertIn('CHANGED_SAVED_CONTROLLER',self.profile('base-install',False));self.assertEqual(before,self.runtime(self.root))
  (saved_child/'control.sh').write_bytes(c)
  self.assertIn('V167_RESTORED=',self.profile('base-install'))
  self.assertEqual((saved_child/'STATE').read_text(),'removed\n');self.assertEqual((saved_child/'backup.index').read_bytes(),indexes[saved_child])
  self.assertIn('FULL_REBOOT_REQUIRED',self.profile('base-install',False));self.boot()
  self.assertIn('V167_RESTORED=',self.profile('base-install'))
  self.assertEqual((saved_parent/'STATE').read_text(),'removed\n');self.assertEqual((saved_parent/'backup.index').read_bytes(),indexes[saved_parent]);self.boot()
  for attempt in range(4):
   output=self.profile('base-install')
   if 'MU1367_RELEASE_1_6_5_E_TEST2_INSTALLED' in output or 'MU1367_RELEASE_1_6_5_E_TEST2_ALREADY_INSTALLED' in output:break
   self.boot()
  else:self.fail('v166 to exact test2 migration did not finish')
  self.native_expected();self.boot()
  jars=self.app/'eso/hmi/lsd/jars'
  expected={name:(jars/name).read_bytes() for name in ('CarPlayWireless-CP-55915411.jar','CarPlayWireless-Touch-55915411.jar')}
  self.profile('select-790');self.boot()
  for name,data in expected.items():self.assertEqual((jars/name).read_bytes(),data,name)
  self.assertEqual(sha(expected['CarPlayWireless-CP-55915411.jar']),'2d9af8e957107b6a82e79e43d22710439061371a3d6766173518d21fc81fdff6')
  for r,index in indexes.items():self.assertEqual((r/'backup.index').read_bytes(),index)
 def test_withdrawn_v166_790_restores_then_installs_test2(self):self._from_v166('790')
 def test_withdrawn_v166_791_restores_then_installs_test2(self):self._from_v166('791')
 def test_profile_has_no_input_or_bluetooth_preference_writes(self):
  self.setup_parent();rows=self.rows
  self.assertEqual(len(rows),14)
  self.assertFalse(any(r['target'].endswith('.jar') or 'btaudio' in r['target'] for r in rows))
  jars=self.app/'eso/hmi/lsd/jars';before={p.name:p.read_bytes() for p in jars.glob('*.jar')}
  self.profile('select-790');self.boot()
  self.assertEqual({p.name:p.read_bytes() for p in jars.glob('*.jar')},before)
  self.assertFalse((self.root/'mnt/persist/wcp_btaudio_release').exists())
  self.profile('remove');self.originals_ok();self.assertEqual({p.name:p.read_bytes() for p in jars.glob('*.jar')},before)
Suite=Profiles
'''
start=code.index("names=[n for n in Suite.__dict__")
code=code[:start]+extra+code[start:]
exec(compile(code,str(source),'exec'),dict(__file__=str(source),__name__='v167_profile_tests'))
