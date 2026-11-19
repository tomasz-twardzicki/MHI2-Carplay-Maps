#!/usr/bin/env python3
"""Actual saved-controller migrations, OEM restoration and combined export."""
import argparse,hashlib,importlib.util,json,os,shutil,subprocess,sys,unittest,zipfile
from pathlib import Path
HERE=Path(__file__).resolve().parent
p=argparse.ArgumentParser()
for n in ('build','integration','inputs','verifier','test1-zip','v161-zip','output'):p.add_argument('--'+n,type=Path,required=True)
p.add_argument('--variants',default='6,7,6-road,7-road')
p.add_argument('--tests',default='')
a=p.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
args=argparse.Namespace(package=a.build.resolve(),inputs=a.inputs.resolve(),verifier=a.verifier.resolve(),output=out/'unused.json')
spec=importlib.util.spec_from_file_location('release_tests',a.integration/'tests/test-package.py');old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
old.ARGS=args;old.parent.ARGS=args;old.parent.base.ARGS=args
sha=lambda b:hashlib.sha256(b).hexdigest()
class Suite(old.Suite):
 @classmethod
 def setUpClass(cls):
  super().setUpClass()
  cls.config_helper=out/'config-patch-replay'
  text='#!'+sys.executable+'\nimport sys,hashlib\nfrom pathlib import Path\n'
  text+='root=Path('+repr(str(a.inputs.resolve()))+')\n'
  text+="mode,source,dest=sys.argv[1:]\nname={'connectivity':'connectivity.json','si':'smartphone_integrator.json'}[mode]\n"
  text+="data=(root/(mode+'-native-output')).read_bytes()\noriginal=(root/name).read_bytes()\nassert Path(source).read_bytes() in (original,data)\nPath(dest).write_bytes(data)\n"
  cls.config_helper.write_text(text);cls.config_helper.chmod(0o755)
  native=sha((cls.sd/'Custom/carplay_mu1367_wireless_native/config-patch').read_bytes())
  shutil.copy2(cls.config_helper,cls.sd/'Custom/carplay_mu1367_wireless_native/config-patch')
  for f in cls.sd.glob('Custom/*/payload-check.sh'):f.write_text(f.read_text().replace(native,sha(cls.config_helper.read_bytes())))
 def setUp(self):
  super().setUp();self.rel=self.sd/'Custom/carplay_mu1367_release'
  self.wcp=self.sd/'Custom/carplay_mu1367_wireless_native'
  self.manifest=json.loads((a.build/'manifest.json').read_text())
  for directory in ('mnt/ota','mnt/persist','mnt/system/etc/eso/production','mnt/app/eso/hmi/lsd/config'):
   (self.root/directory).mkdir(parents=True,exist_ok=True)
  self.stock={}
  for dest,name in [('mnt/app/eso/bin/apps/btstack','btstack'),('mnt/app/eso/bin/apps/connectionmanager','connectionmanager'),('mnt/app/eso/hmi/lsd/config/bundles.properties','bundles.properties'),('mnt/system/etc/eso/production/connectivity.json','connectivity.json'),('mnt/system/etc/eso/production/smartphone_integrator.json','smartphone_integrator.json')]:
   target=self.root/dest;target.write_bytes((a.inputs/name).read_bytes());self.stock[dest]=target.read_bytes()
  for path in self.sd.glob('Custom/*/payload-check.sh'):
   # Parent fixture replaces native verifier pins with the host verifier.
   assert '0512b28bd589336fe8a32f8e514f90b2646e2117064454160a660daff48f9a7a' not in path.read_text()
 def stable(self,action,success=True):
  return self.run_script(self.rel/'control.sh',[action,self.rel],success)
 def reboot(self):
  super().reboot()
  marker=self.root/'ramdisk/.cpmap-release-v161-reboot'
  if marker.exists():marker.unlink()
 def native_expected(self):
  m=json.loads((self.wcp/'manifest.json').read_text())
  for row in m['rows']:
   target=self.root/row['target'].lstrip('/')
   if row['kind']=='copy':self.assertEqual(sha(target.read_bytes()),row['sha256'],row['target'])
  self.assertEqual((self.app/'carplay-mu1367-wireless-native-v161t2/STATE').read_text().strip(),'installed')
 def current_base(self,variant='6'):
  if variant!='6':self.prepare(variant)
  self.action('install');self.reboot()
 def test_v154_variants_adopt_and_complete_oem(self):
  for variant in a.variants.split(','):
   with self.subTest(variant=variant):
    if variant!='6':
     self.tearDown();self.setUp()
    self.current_base(variant)
    output=self.stable('install');self.assertIn('RELEASE_1_6_1_INSTALLED_FULL_REBOOT_REQUIRED',output);self.native_expected()
    self.assertIn('FULL_REBOOT_REQUIRED',self.stable('install',False));self.reboot()
    installed=self.runtime(self.root);r=self.app/'carplay-mu1367-wireless-native-v161t2';index=(r/'backup.index').read_bytes()
    self.assertIn('RELEASE_1_6_1_ALREADY_INSTALLED',self.stable('install'));self.assertEqual(installed,self.runtime(self.root));self.assertEqual(index,(r/'backup.index').read_bytes())
    self.assertIn('WIRELESS_PREVIOUS_LAYER_RESTORED',self.stable('restore-oem'))
    self.assertIn('FULL_REBOOT_REQUIRED',self.stable('restore-oem',False));self.reboot()
    self.assertIn('RELEASE_COMPLETE_OEM_RESTORE',self.stable('restore-oem'))
    for dest,data in self.stock.items():self.assertEqual((self.root/dest).read_bytes(),data,dest)
    self.assertEqual(self.runtime(self.root),self.original)
    self.assertFalse((self.app/'carplaymaps').exists())
    archive=self.app/'carplay-mu1367-oem-reset/archive/carplay-mu1367-wireless-native-v161t2'
    self.assertEqual((archive/'backup.index').read_bytes(),index)
    self.reboot();self.assertIn('OEM_RESET_ALREADY_COMPLETE',self.stable('restore-oem'))
 def test_v153_and_android_auto_reboot_resume(self):
  self.v2();self.revision('release-v1.5.3','6')
  oldaa=self.revisions/'release-v1.5.3/carplay_mu1367_android_auto'
  self.run_script(oldaa/'control.sh',['install',oldaa])
  root=self.app/'carplay-mu1367-guidance-v3';saved=(root/'backup/core').read_bytes()
  self.assertIn('MIGRATION_BASE_RESTORED',self.stable('install'))
  self.assertIn('FULL_REBOOT_REQUIRED',self.stable('install',False));self.reboot()
  self.assertIn('RELEASE_BASE_STAGE_COMPLETE',self.stable('install'));self.reboot()
  self.assertIn('RELEASE_1_6_1_INSTALLED',self.stable('install'));self.native_expected()
  archived=list(self.app.glob('carplay-mu1367-guidance-v3.removed-*'))
  self.assertTrue(any((r/'backup/core').read_bytes()==saved for r in archived))
 def test_old_wireless_candidates_retire_without_old_sd(self):
  for label,archive in [('test1',a.test1_zip),('original-v161',a.v161_zip)]:
   with self.subTest(candidate=label):
    if label!='test1':self.tearDown();self.setUp()
    if label=='test1':self.v2();self.revision('release-v1.5.3','6')
    else:self.current_base()
    legacy=self.root/('old-'+label)
    with zipfile.ZipFile(archive) as z:
     prefix='Custom/carplay_mu1367_wireless_native/'
     for n in z.namelist():
      if n.startswith(prefix) and '/source/' not in n and not n.endswith('/'):
       f=legacy/n[len(prefix):];f.parent.mkdir(parents=True,exist_ok=True);f.write_bytes(z.read(n))
    native=sha((legacy/'verify').read_bytes());shutil.copy2(a.verifier,legacy/'verify')
    native_config=sha((legacy/'config-patch').read_bytes());shutil.copy2(self.config_helper,legacy/'config-patch')
    check=legacy/'payload-check.sh';check.write_text(check.read_text().replace(native,sha(a.verifier.read_bytes())).replace(native_config,sha(self.config_helper.read_bytes())))
    self.run_script(legacy/'control.sh',['install',legacy])
    m=json.loads((legacy/'manifest.json').read_text());r=self.app/Path(m.get('recovery_root','carplay-mu1367-wireless-native')).name
    before=(r/'backup.index').read_bytes()
    self.assertIn('WIRELESS_PREVIOUS_LAYER_RESTORED',self.stable('install'));self.assertEqual((r/'STATE').read_text().strip(),'removed')
    self.assertEqual(before,(r/'backup.index').read_bytes());self.reboot()
    for stage in range(4):
     result=self.stable('install')
     if 'RELEASE_1_6_1_INSTALLED' in result:break
     self.reboot()
    else:self.fail('migration did not finish')
    self.native_expected();self.assertEqual(before,(r/'backup.index').read_bytes())
 def test_changed_saved_controller_and_sd_are_preserved(self):
  self.current_base();self.stable('install');self.reboot()
  r=self.app/'carplay-mu1367-wireless-native-v161t2';control=r/'control.sh';control.write_bytes(control.read_bytes()+b'\n# changed\n')
  before=self.runtime(self.root)
  self.assertIn('CHANGED_WIRELESS_CONTROLLER',self.stable('restore-oem',False));self.assertEqual(before,self.runtime(self.root))
  self.assertFalse((self.root/'ramdisk/.cpmap-release-v161-reboot').exists())
 def test_prepared_snapshot_without_installed_receipt_is_retained(self):
  self.current_base();self.stable('install');self.reboot();self.stable('uninstall');self.reboot()
  r=self.app/'carplay-mu1367-wireless-native-v161t2';index=(r/'backup.index').read_bytes()
  (r/'STATE').write_text('prepared\n')
  for name in ('installed.index','installed.index.sha256'):(r/name).unlink()
  before=self.runtime(self.root)
  self.assertIn('PREPARED_SNAPSHOT_RETAINED',self.stable('recover'))
  self.assertEqual(before,self.runtime(self.root));self.assertFalse(r.exists())
  saved=list(self.app.glob('carplay-mu1367-wireless-native-v161t2.prepared-*'))
  self.assertEqual(len(saved),1);self.assertEqual((saved[0]/'backup.index').read_bytes(),index)
  self.reboot();self.assertIn('RELEASE_1_6_1_INSTALLED',self.stable('install'));self.native_expected()
 def test_interrupted_commit_recovers_with_same_sd(self):
  self.current_base();before=self.runtime(self.root)
  result=self.run_script(self.rel/'control.sh',['install',self.rel],False,env=dict(self.env,CPMAP_TEST_INTERRUPT_AFTER_KEY='k23'))
  self.assertIn('SIMULATED_POWER_INTERRUPTION',result)
  r=self.app/'carplay-mu1367-wireless-native-v161t2';self.assertEqual((r/'STATE').read_text().strip(),'installing')
  self.assertIn('WIRELESS_PREVIOUS_LAYER_RESTORED',self.stable('recover'));self.assertEqual(before,self.runtime(self.root))
 def test_standard_diagnostics_contains_wireless_and_excludes_pairing(self):
  vol=self.root/'fs/sda0';vol.mkdir(parents=True);rg=self.root/'ramdisk/wcp-rg';rg.mkdir()
  (rg/'latest.bin').write_bytes(b'bounded-mailbox');(rg/'idr.state').write_bytes(b'WCPIDR1\n23\n1\n1234\n')
  (self.root/'ramdisk/wcp-video-timing.bin').write_bytes(b'timing-only')
  (self.root/'mnt/persist/cpmap-driver-side.state').write_bytes(b'CPDS1\n2\n')
  secret=self.root/'mnt/persist/wcp';secret.mkdir();(secret/'pairing.key').write_bytes(b'SECRET_PAIRING_SENTINEL')
  scripts=a.build/'sd-card/Toolbox/scripts'
  result=subprocess.run(['/bin/ksh',str(scripts/'cpmap_diag.sh')],env=dict(self.env,CPMAP_TEST_MEDIA=str(vol)),capture_output=True,text=True)
  self.assertEqual(result.returncode,0,result.stdout+result.stderr)
  dirs=list((vol/'Log').glob('cpmap-diag-*'));self.assertEqual(len(dirs),1);d=dirs[0]
  self.assertEqual((d/'wireless/state/wcp-rg-latest.bin').read_bytes(),b'bounded-mailbox')
  self.assertEqual((d/'wireless/state/cpmap-driver-side.cached.state').read_bytes(),b'CPDS1\n2\n')
  self.assertEqual((d/'wireless/state/wcp-video-timing.bin').read_bytes(),b'timing-only')
  for f in d.rglob('*'):
   if f.is_file():self.assertNotIn(b'SECRET_PAIRING_SENTINEL',f.read_bytes(),str(f))
names=[n for n in Suite.__dict__ if n.startswith('test_')]
if a.tests:names=[n for n in names if n in a.tests.split(',')]
result=unittest.TextTestRunner(verbosity=2,failfast=True).run(unittest.TestSuite(Suite(n) for n in names))
report=dict(passed=result.wasSuccessful(),tests=result.testsRun,variants=a.variants.split(','),failures=len(result.failures),errors=len(result.errors),scope='Actual release/base/legacy/AA/OEM shell controllers; host SHA verifier; config-patch replays exact outputs captured and hash-verified from the pinned native QNX helper; mounts/sync mocked; reboot RAM markers cleared by fixture.',config_replay=json.loads((a.inputs/'config-replay.json').read_text()),version='1.6.1',controller_sha256=sha((a.build/'sd-card/Custom/carplay_mu1367_release/control.sh').read_bytes()))
(out/'result.json').write_text(json.dumps(report,indent=2)+'\n')
raise SystemExit(not result.wasSuccessful())
