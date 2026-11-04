#!/usr/bin/env python3
"""Real v3 controllers/actions in isolated host filesystems."""
import argparse,hashlib,importlib.util,json,re,shlex,shutil,unittest,zipfile
from pathlib import Path
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('v3_parent_tests',HERE/'baseline.py');parent=importlib.util.module_from_spec(spec);spec.loader.exec_module(parent)
sha=parent.sha
class Suite(parent.Suite):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.revisions=cls.work/'revisions'
        shutil.copytree(HERE/'revisions',cls.revisions,ignore=shutil.ignore_patterns('verify'))
        for f in cls.revisions.rglob('control.sh'):shutil.copy2(ARGS.verifier,f.parent/'verify')
    # Exercise current controllers using isolated actual-baseline fixtures.
    def setUp(self):
        super().setUp();self.parentp=self.p;self.p=self.sd/'Custom/carplay_mu1367_guidance_v3'
    @staticmethod
    def runtime(root):
        values=parent.Suite.runtime(root);p=root/'mnt/app/carplay-mu1367-guidance-v3/control.sh'
        values['carplay-mu1367-guidance-v3/control.sh']=(sha(p.read_bytes()),p.stat().st_mode&0o777) if p.is_file() else None
        p=root/'mnt/app/carplay-mu1367/rgi-observer'
        values['carplay-mu1367/rgi-observer']=(sha(p.read_bytes()),p.stat().st_mode&0o777) if p.is_file() else None
        return values
    def expected(self,variant='6'):
        super().expected(variant)
        m=json.loads((self.p/variant/'manifest.json').read_text())
        self.assertEqual(sha((self.app/'carplay-mu1367/rgi-observer').read_bytes()),m['files']['reader'])
    def saved(self,action,success=True,name='guidance-v3'):
        return self.run_script(self.app/('carplay-mu1367-'+name)/'control.sh',[action],success)
    def v2(self,v='6'):
        self.prepare(v);self.old_install()
        self.run_script(self.parentp/'actions.sh',['install',self.parentp])
    def compare_without_v3(self,before):
        after=self.runtime(self.root);after.pop('carplay-mu1367-guidance-v3/control.sh');before=dict(before);before.pop('carplay-mu1367-guidance-v3/control.sh');self.assertEqual(after,before)
    def test_v3_fresh_repeat_optional_and_oem(self):
        self.action('install');self.expected();after=self.runtime(self.root)
        self.action('install');self.assertEqual(self.runtime(self.root),after)
        self.action('enable-cards');self.assertIn('REMOVE_CHILD_FIRST',self.saved('uninstall',False))
        self.action('disable-cards');self.assertEqual(self.runtime(self.root),after)
        self.action('enable-cards');self.action('disable-cards')
        self.assertEqual(len(list(self.app.glob('carplay-mu1367-turn-cards.removed-*'))),1)
        self.action('enable-cards');self.action('restore-oem');self.assertEqual(self.runtime(self.root),self.original)
        archive=self.app/'carplay-mu1367-oem-reset/archive'
        for n in ('guidance-v3','map-only','turn-cards','refinements'):self.assertTrue((archive/('carplay-mu1367-'+n)).is_dir())
    def test_v3_all_four_existing_v2_upgrade_restore(self):
        for v in ('6','7','6-road','7-road'):
            with self.subTest(variant=v):
                if v!='6':shutil.rmtree(self.root);shutil.copytree(self.seed,self.root)
                self.v2(v);before=self.runtime(self.root);self.action('install');self.expected(v)
                self.assertIn('REMOVE_CHILD_FIRST',self.saved('uninstall',False,'map-only'))
                new=self.runtime(self.root);self.action('enable-cards');self.action('disable-cards');self.assertEqual(self.runtime(self.root),new)
                self.saved('uninstall');self.compare_without_v3(before)
    def test_v3_commit_faults_restore_parent_and_runtime(self):
        self.v2();before=self.runtime(self.root)
        for dest in ('carplaymaps/core.so','eso/hmi/lsd/jars/CarPlayMU1367Guidance.jar','eso/hmi/lsd/jars/VCMenu.jar','carplay-mu1367/rgi-observer','carplay-mu1367-map-only/control.sh'):
            with self.subTest(target=dest):
                tools=Path(self.tmp.name)/('fault-'+str(abs(hash(dest))));tools.mkdir();once=tools/'once';target=self.app/dest
                (tools/'mv').write_text('#!/bin/ksh\nif [ "$2" = '+shlex.quote(str(target))+' ] && [ ! -f '+shlex.quote(str(once))+' ];then : > '+shlex.quote(str(once))+';exit 1;fi\nexec '+shlex.quote(shutil.which('mv'))+' "$@"\n');(tools/'mv').chmod(0o755)
                self.assertIn('SNAPSHOT_RESTORED',self.run_script(self.p/'actions.sh',['install',self.p],False,dict(self.env,PATH=str(tools)+':'+self.env['PATH'])))
                self.compare_without_v3(before)
    def test_v3_removed_snapshot_and_corruption_protection(self):
        self.v2();before=self.runtime(self.root);self.action('install');self.action('uninstall');self.compare_without_v3(before)
        self.action('install');self.expected();self.assertEqual(len(list(self.app.glob('carplay-mu1367-guidance-v3.removed-*'))),1)
        r=self.app/'carplay-mu1367-guidance-v3';(r/'backup/menu').write_bytes(b'corrupt');before=self.runtime(self.root)
        self.saved('recover',False);self.assertEqual(self.runtime(self.root),before)
        (r/'STATE').write_text('removed\n');self.assertIn('REMOVED_SNAPSHOT_DAMAGED',self.action('install',False));self.assertEqual(len(list(self.app.glob('carplay-mu1367-guidance-v3.removed-*'))),1)
    def test_v3_checks_before_writes_and_reset_settings(self):
        # Optional Toolbox examples/customizations are unrelated to this suite.
        for path in list(self.sd.joinpath('Custom').iterdir()):
            if not (path.name == 'carplay_maps_vc' or path.name == 'carplay_mu1367' or path.name.startswith('carplay_mu1367_')):
                if path.is_dir():shutil.rmtree(path)
                else:path.unlink()
        before=self.runtime(self.root);ready=self.root/'ramdisk/carplay-altstream.ready';ready.touch();self.action('install',False);ready.unlink();self.assertEqual(self.runtime(self.root),before)
        f=self.p/'6/core.so';content=f.read_bytes();f.write_bytes(b'corrupt');self.assertIn('SD_PAYLOAD_HASH',self.action('install',False));self.assertEqual(self.runtime(self.root),before);f.write_bytes(content)
        prefs=self.root/'mnt/icab/persistent/cpmap-ui';(prefs/'display.state').write_text('saved');(prefs/'navigation-card.state').write_text('on')
        self.action('reset-settings');self.assertFalse(prefs.exists());saved=list(prefs.parent.glob('cpmap-ui.saved-*'));self.assertEqual(len(saved),1);self.assertEqual((saved[0]/'display.state').read_text(),'saved');self.assertEqual(self.runtime(self.root),before)
    def test_v3_lane_status_and_legacy_restore_wrappers(self):
        before=self.runtime(self.root);self.assertIn('NO_LANE_EVIDENCE_YET',self.action('lane-status'))
        f=self.root/'ramdisk/carplay-route-guidance/lane-evidence.txt';f.parent.mkdir();f.write_text('selected_lane=0 description=0 recommendation=0\n')
        self.assertIn(f.read_text(),self.action('lane-status'));self.assertEqual(self.runtime(self.root),before)
        scripts=ARGS.package/'sd-card/Toolbox/scripts'
        for name in ('cpmap_suite_install.sh','cpmap_suite_enable-cards.sh','cpmap_restore.sh','cpmap_restore_core.sh'):
            self.assertIn('carplay_mu1367_guidance_v3',(scripts/name).read_text())
    def test_v3_old_optional_tuning_refuses_update(self):
        self.v2();self.run_script(self.parentp/'actions.sh',['enable-cards',self.parentp]);before=self.runtime(self.root)
        self.assertIn('REMOVE_OR_RECOVER_TURN_CARD_TUNING_FIRST',self.action('install',False));self.assertEqual(before,self.runtime(self.root))


    def test_release_published_prefixes_and_integrated_arrows(self):
        for count in (2,3,5,6):
            with self.subTest(baseline=count):
                shutil.rmtree(self.root);shutil.copytree(self.seed,self.root)
                custom=self.sd/'Custom';maps=custom/'carplay_maps_vc/payload'
                self.run_script(maps/'common/install-carplay-maps.sh',[maps,'MU1367','791'])
                for name in ('carplay_mu1367','carplay_mu1367_settings','carplay_mu1367_lanes','carplay_mu1367_wireless','carplay_mu1367_artwork')[:min(count,5)]:
                    layer=custom/name;self.run_script(layer/'control.sh',['install',layer])
                if count==6:self.old_install()
                self.assertIn('RELEASE_1_4_4_E_EXPERIMENTAL_INSTALLED',self.action('install'));self.expected()

    def revision(self, revision, variant='6', tuning=False):
        old=self.revisions/revision
        # Actual archived controllers and payloads; only the verifier is host-native.
        main=old/'carplay_mu1367_guidance_v3'/variant
        self.run_script(main/'control.sh',['install',main])
        if tuning:
            t=old/'carplay_mu1367_v3_turn_cards'/variant
            self.run_script(t/'control.sh',['install',t])
    def reboot(self):
        f=self.root/'ramdisk/.cpmap-release-migration-reboot'
        if f.exists():f.unlink()
    def test_release_supported_revision_migrations(self):
        cases=[(release,v,t) for release in ('release-v1.4.1','release-v1.4.2','release-v1.4.3','release-v1.4.3-e') for v in ('6','7','6-road','7-road') for t in (False,True)]+[('guidance-v3','6',False),('lane-window','6',False),('lane-type','6',False),
               ('safe-area','6',False),('safe-area','7',False),('safe-area','6-road',False),
               ('safe-area','7-road',False),('safe-area','6',True)]
        for revision,variant,tuning in cases:
            with self.subTest(revision=revision,variant=variant,tuning=tuning):
                shutil.rmtree(self.root);shutil.copytree(self.seed,self.root)
                self.v2(variant);self.revision(revision,variant,tuning)
                r=self.app/'carplay-mu1367-guidance-v3'
                version=(r/'VERSION').read_text()
                backups={f.name:sha(f.read_bytes()) for f in (r/'backup').iterdir()}
                self.assertIn('MIGRATION_BASE_RESTORED',self.action('install'))
                before=self.runtime(self.root)
                self.assertIn('FULL_REBOOT_REQUIRED',self.action('install',False))
                self.assertEqual(before,self.runtime(self.root))
                self.reboot();self.assertIn('RELEASE_1_4_4_E_EXPERIMENTAL_INSTALLED',self.action('install'));self.expected(variant)
                archives=list(self.app.glob('carplay-mu1367-guidance-v3.removed-*'))
                self.assertEqual(len(archives),1);self.assertEqual((archives[0]/'VERSION').read_text(),version)
                self.assertEqual({f.name:sha(f.read_bytes()) for f in (archives[0]/'backup').iterdir()},backups)
                after=self.runtime(self.root);self.action('install');self.assertEqual(after,self.runtime(self.root))
    def test_release_unknown_or_corrupt_legacy_refused_before_writes(self):
        self.v2();self.revision('release-v1.4.1');r=self.app/'carplay-mu1367-guidance-v3'
        control=(r/'control.sh').read_bytes();(r/'control.sh').write_bytes(control+b'\n# changed\n')
        before=self.runtime(self.root);self.assertIn('UNKNOWN_OR_DAMAGED_LEGACY_REVISION',self.action('install',False));self.assertEqual(before,self.runtime(self.root))
        (r/'control.sh').write_bytes(control);backup=r/'backup/menu';backup.write_bytes(b'corrupt')
        before=self.runtime(self.root);self.assertIn('UNKNOWN_OR_DAMAGED_LEGACY_REVISION',self.action('install',False));self.assertEqual(before,self.runtime(self.root))
    def test_release_legacy_tuning_and_corrupt_parent_refused(self):
        self.v2();self.revision('release-v1.4.1',tuning=True)
        r=self.app/'carplay-mu1367-guidance-v3';(self.app/'eso/hmi/lsd/jars/CarPlayMU1367Guidance.jar').write_bytes(b'corrupt')
        before=self.runtime(self.root);self.action('install',False)
        self.assertEqual((self.app/'carplay-mu1367-turn-cards/STATE').read_text().strip(),'installed')
        self.assertEqual(before,self.runtime(self.root))

def main():
    global ARGS
    p=argparse.ArgumentParser()
    for n in ('package','inputs','verifier','output'):p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--tests',nargs='*')
    ARGS=p.parse_args();parent.ARGS=ARGS;parent.base.ARGS=ARGS
    sd=ARGS.package/'sd-card';m=json.loads((ARGS.package/'manifest.json').read_text());inventory=json.loads((sd/'FILES_SHA256.json').read_text())
    with zipfile.ZipFile(ARGS.package/m['archive_name']) as z:
        assert z.testzip() is None and sha((ARGS.package/m['archive_name']).read_bytes())==m['archive_sha256']
        for n,h in inventory.items():assert sha(z.read(n))==h==sha((sd/n).read_bytes()),n
    tests=ARGS.tests or [n for n in Suite.__dict__ if n.startswith('test_')]
    r=unittest.TextTestRunner(verbosity=2).run(unittest.TestSuite(Suite(n) for n in tests))
    result={'passed':r.wasSuccessful(),'tests':r.testsRun,'inventory_checks':len(inventory),'archive_sha256':m['archive_sha256'],'mounts_and_sync_mocked_on_host':True,'on_unit_validated':False}
    ARGS.output.write_text(json.dumps(result,indent=2)+'\n');raise SystemExit(not r.wasSuccessful())
if __name__=='__main__':main()
