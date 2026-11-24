#!/usr/bin/env python3
"""P4521 recognition, full features and separate experimental-to-integrated update."""
import argparse,importlib.util,json,shutil,unittest,zipfile
from pathlib import Path
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('release_tests',HERE/'test-package.py');release=importlib.util.module_from_spec(spec);spec.loader.exec_module(release)
sha=release.sha
class Suite(release.Suite):
    def train(self,value):
        p=self.root/'net/rcc/dev/shmem/version.txt';p.parent.mkdir(parents=True,exist_ok=True)
        p.write_bytes(('Current train = "'+value+'"\r\n').encode())
    def test_train_and_exact_identity_gates(self):
        before=self.runtime(self.root)
        for train,kind in [('MHI2_ER_VWG13_P4521','P4521_EXPERIMENTAL'),('MHI2_ER_VWG13_P4521_MU1367','P4521_EXPERIMENTAL'),('MHI2_ER_VWG13_K4525_1_AIO_MU1367','K4525')]:
            self.train(train);self.assertIn('MU1367_FIRMWARE_TYPE='+kind,self.action('lane-status'));self.assertEqual(before,self.runtime(self.root))
        for train in ('MHI2_ER_VWG13_P45210','MHI2_ER_VWG13_P9999','MHI2_ER_AUG11_P4521'):
            self.train(train);self.assertIn('UNSUPPORTED_FIRMWARE_TRAIN',self.action('install',False));self.assertEqual(before,self.runtime(self.root))
        (self.root/'net/rcc/dev/shmem/version.txt').unlink()
        self.assertIn('K4525_OR_P4521_HASH_MATCH',self.action('lane-status'))
        self.train('MHI2_ER_VWG13_P4521');(self.root/'ifs/lsd.jxe').write_bytes(b'wrong firmware')
        self.assertIn('EXACT_K4525_OR_P4521_MU1367_REQUIRED',self.action('install',False));self.assertEqual(before,self.runtime(self.root))
    def test_p4521_fresh_all_features_tuning_and_reset(self):
        self.train('MHI2_ER_VWG13_P4521')
        self.assertIn('P4521_EXPERIMENTAL',self.action('install'));self.expected()
        after=self.runtime(self.root);self.action('install');self.assertEqual(after,self.runtime(self.root))
        self.action('enable-cards');self.action('disable-cards');self.assertEqual(after,self.runtime(self.root))
        self.action('restore-oem');self.assertEqual(self.runtime(self.root),self.original)
    def test_separate_experimental_reset_reboot_install(self):
        self.train('MHI2_ER_VWG13_P4521')
        old=Path(self.tmp.name)/'old';old.mkdir()
        archive=ARGS.p4521_package
        self.assertEqual(sha(archive.read_bytes()),'6995e85764345f6d8dabe1f4c9af71f3b7d427a96d881eca9c0f10bf15267c79')
        with zipfile.ZipFile(archive) as z:
            for n in z.namelist():
                if n.startswith('Custom/') and not '/source/' in n:
                    path=old/n;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(z.read(n))
        for f in old.rglob('verify'):shutil.copy2(ARGS.verifier,f)
        custom=old/'Custom';maps=custom/'carplay_maps_vc/payload'
        self.run_script(maps/'common/install-carplay-maps.sh',[maps,'MU1367','791'])
        for layer in ('carplay_mu1367','carplay_mu1367_settings','carplay_mu1367_lanes'):
            p=custom/layer;self.run_script(p/'control.sh',['install',p])
        self.assertEqual((self.app/'carplay-mu1367-settings/VERSION').read_text().strip(),'MU1367-P4521-settings-e59e7a883ca0')
        before=self.runtime(self.root)
        self.assertIn('P4521_EXPERIMENTAL_BASE_USE_RECOVERY_RESTORE_OEM_REBOOT_THEN_INSTALL',self.action('install',False));self.assertEqual(before,self.runtime(self.root))
        prefs=self.root/'mnt/icab/persistent/cpmap-ui';(prefs/'display.state').write_text('retained')
        self.action('restore-oem');self.assertEqual(self.runtime(self.root),self.original)
        archive_root=self.app/'carplay-mu1367-oem-reset/archive'
        for layer in ('carplaymaps','carplay-mu1367','carplay-mu1367-settings','carplay-mu1367-lanes'):
            self.assertTrue((archive_root/layer).is_dir())
        self.reboot();self.action('install');self.expected();self.action('enable-cards');self.action('disable-cards');self.expected()
        self.assertEqual((prefs/'display.state').read_text(),'retained')

def main():
    global ARGS
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('package','inputs','verifier','p4521-package','output'):p.add_argument('--'+name,type=Path,required=True)
    ARGS=p.parse_args();release.ARGS=ARGS;release.parent.ARGS=ARGS;release.parent.base.ARGS=ARGS
    inventory=json.loads((ARGS.package/'sd-card/FILES_SHA256.json').read_text())
    for name,h in inventory.items():assert sha((ARGS.package/'sd-card'/name).read_bytes())==h,name
    tests=[name for name in Suite.__dict__ if name.startswith('test_')]
    r=unittest.TextTestRunner(verbosity=2).run(unittest.TestSuite(Suite(name) for name in tests))
    m=json.loads((ARGS.package/'manifest.json').read_text())
    result={'passed':r.wasSuccessful(),'tests':r.testsRun,'archive_sha256':m['archive_sha256'],'p4521_hardware_variants':['50','70'],'prior_experimental_archive_sha256':sha(ARGS.p4521_package.read_bytes()),'mounts_and_sync_mocked_on_host':True,'final_package_vehicle_tested':False}
    ARGS.output.write_text(json.dumps(result,indent=2)+'\n');raise SystemExit(not r.wasSuccessful())
if __name__=='__main__':main()
