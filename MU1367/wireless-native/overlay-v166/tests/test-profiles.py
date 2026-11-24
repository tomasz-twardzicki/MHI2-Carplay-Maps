#!/usr/bin/env python3
"""Exercise real child transactions over the actual installed v1.6.3-e parent."""
from pathlib import Path
HERE=Path(__file__).resolve().parent
source=HERE.parents[1]/'stable/test-host.py'
code=source.read_text().replace('carplay-mu1367-wireless-native-v161t2','carplay-mu1367-wireless-native-v166').replace('release-v161','release-v166').replace('1_6_1','1_6_6_E')
code=code.replace('  self.stock={}', "  self.stock={}\n  for dest,name in [('proc/boot/libz.so.2','libz.so.2'),('mnt/app/eso/bin/apps/gal','gal')]:\n   target=self.root/dest;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes((a.inputs/name).read_bytes());target.chmod(0o755)\n")
extra=r'''
class Profiles(Suite):
 def setUp(self):
  super().setUp()
  self.mod=self.sd/'Custom/carplay_mu1367_input_profile'
  self.profile_root=json.loads((self.mod/'manifest.json').read_text())['790']['recovery_root']
  native=sha((a.build/'sd-card/Custom/carplay_mu1367_wireless_native/verify').read_bytes())
  for f in self.mod.rglob('payload-check.sh'):f.write_text(f.read_text().replace(native,sha(a.verifier.read_bytes())))
  # Native factory Android Auto/zlib fixtures come from the current integration.
  f=self.app/'armle/usr/sbin/mm-ipod';f.parent.mkdir(parents=True,exist_ok=True);f.write_bytes((self.sd/'Custom/carplay_mu1367_oem_reset/payload/mmipod').read_bytes())
  self.parent_root=self.app/'carplay-mu1367-wireless-native-v166'
 def boot(self):
  self.reboot();(self.root/'ramdisk/.cpmap-profile-test-reboot').unlink(missing_ok=True)
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
  self.profile('tune-card-on');self.assertIn(b'alturl=maps:/car/instrumentcluster\n',conf.read_bytes())
  self.profile('tune-card-off');self.assertIn(b'alturl=maps:/car/instrumentcluster/map\n',conf.read_bytes())
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
  self.assertIn('PROFILE_REMOVED',self.profile('base-restore-oem'));self.originals_ok();self.boot()
  self.assertIn('WIRELESS_PREVIOUS_LAYER_RESTORED',self.profile('base-restore-oem'));self.boot()
  self.assertIn('RELEASE_COMPLETE_OEM_RESTORE',self.profile('base-restore-oem'))
  self.assertTrue((self.app/'carplay-mu1367-oem-reset/archive'/self.profile_root/'backup.index').is_file())
 def test_base_only_and_damaged_targets_refused(self):
  self.current_base()
  self.assertIn('FINISH_NATIVE_V163',self.profile('select-790',False))
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
 def test_upgrade_preserves_test1_snapshots_and_parent_identity(self):
  self.current_base()
  archive=a.build.parent/'dist/overlay790-test3-final/CarPlay_MU1367_Overlay_790_Experimental_Test3.zip'
  self.assertEqual(sha(archive.read_bytes()),'202ab34e7339324ca204e6ea64ef754d94a1174f76e9d139c41d59bfc28d3359')
  legacy=self.root/'legacy-test3'
  with zipfile.ZipFile(archive) as z:
   for name in z.namelist():
    if name.startswith('Custom/') and '/source/' not in name and not name.endswith('/'):
     f=legacy/name;f.parent.mkdir(parents=True,exist_ok=True);f.write_bytes(z.read(name))
  parent=legacy/'Custom/carplay_mu1367_wireless_native';child=legacy/'Custom/carplay_mu1367_input_profile/790'
  native=sha((parent/'verify').read_bytes());config=sha((parent/'config-patch').read_bytes())
  shutil.copy2(self.config_helper,parent/'config-patch')
  for f in legacy.rglob('verify'):shutil.copy2(a.verifier,f)
  for f in legacy.rglob('payload-check.sh'):f.write_text(f.read_text().replace(native,sha(a.verifier.read_bytes())).replace(config,sha(self.config_helper.read_bytes())))
  self.run_script(parent/'control.sh',['install',parent]);self.boot()
  self.run_script(child/'control.sh',['install',child]);self.boot()
  old=self.app/'carplay-mu1367-profile-790-test3';index=(old/'backup.index').read_bytes();control=(old/'control.sh').read_bytes()
  (old/'control.sh').write_bytes(control+b'\n# unknown edit\n');before=self.runtime(self.root)
  self.assertIn('CHANGED_SAVED_CONTROLLER',self.profile('base-install',False));self.assertEqual(before,self.runtime(self.root))
  (old/'control.sh').write_bytes(control)
  self.assertIn('PROFILE_REMOVED',self.profile('base-install'));self.assertEqual((old/'backup.index').read_bytes(),index);self.boot()
  self.assertIn('WIRELESS_PREVIOUS_LAYER_RESTORED',self.profile('base-install'));self.boot()
  for attempt in range(4):
   output=self.profile('base-install')
   if 'RELEASE_1_6_6_E_INSTALLED' in output:break
   self.boot()
  else:self.fail('test3 to v166 migration did not finish')
  self.native_expected();self.boot();self.profile('select-790');self.boot()
  self.assertEqual((self.app/'carplaymaps/PROFILE').read_text(),'MU1367/790\n')
  self.assertEqual((old/'STATE').read_text(),'removed\n');self.assertEqual((old/'backup.index').read_bytes(),index)
 def test_call_preference_defaults_and_snapshot_restoration(self):
  self.setup_parent();flag=self.root/'mnt/persist/wcp_btaudio_release'
  self.profile('select-790');self.boot();self.assertFalse(flag.exists())
  choice=self.parent_root/'bt-release.mode';choice.write_bytes(b'profiles\n')
  self.assertIn('ALREADY_INSTALLED',self.run_script(self.mod/'790/control.sh',['install',self.mod/'790']))
  self.assertFalse(flag.exists());self.assertEqual(choice.read_bytes(),b'profiles\n')
  self.profile('remove');self.originals_ok();self.assertEqual(choice.read_bytes(),b'profiles\n')
  self.assertIn('gps-preference.sh" bt-release', (self.mod/'actions.sh').read_text())
if json.loads((a.build/'sd-card/Custom/carplay_mu1367_input_profile/manifest.json').read_text())['790']['recovery_root'].endswith('-test'):
 del Profiles.test_upgrade_preserves_test1_snapshots_and_parent_identity
if not json.loads((a.build/'sd-card/Custom/carplay_mu1367_input_profile/manifest.json').read_text())['790']['recovery_root'].endswith(('test3','v166')):
 del Profiles.test_call_preference_defaults_and_snapshot_restoration
Suite=Profiles
'''
start=code.index("names=[n for n in Suite.__dict__")
code=code[:start]+extra+code[start:]
exec(compile(code,str(source),'exec'),dict(__file__=str(source),__name__='profile_transaction_tests'))
