#!/usr/bin/env python3
"""Reproduce the reported step-3 failure and test exact dormant-menu migration.
SPDX-License-Identifier: GPL-3.0-or-later
"""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import unittest
import zipfile
import migration

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('p4521_settings_fixture', HERE.parent / 'MU1367/settings-v2/test-controls.py')
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)


class Migration(fixture.Controls):
    def setUp(self):
        super().setUp()
        self.menu = self.app / 'eso/hmi/lsd/jars/VCMenu.jar'
        shutil.copy2(ARGS.legacy_v201, self.menu)
        self.original = self.snapshot()

    def test_original_release_reproduces_reported_failure_without_writes(self):
        controller = (self.payload / 'control.sh').read_bytes()
        version = (self.payload / 'VERSION').read_bytes()
        with zipfile.ZipFile(HERE.parent / 'releases/MU1367/v1.4.0/CarPlay_Maps_VC_MU1367_791_Native_Lanes_Test.zip') as archive:
            for name in ('control.sh', 'VERSION'):
                (self.payload / name).write_bytes(archive.read('Custom/carplay_mu1367_settings/' + name))
        self.assertIn('UNEXPECTED_BASE_menu', self.run_control('install', False))
        self.assertEqual(self.snapshot(), self.original)
        self.assertFalse(self.saved.exists())
        (self.payload / 'control.sh').write_bytes(controller)
        (self.payload / 'VERSION').write_bytes(version)
        self.run_control('install')
        self.assertEqual((self.saved / 'backup/menu').read_bytes(), ARGS.legacy_v201.read_bytes())

    def test_both_known_upstream_versions_restored_exactly(self):
        # Default v2.0.1 also runs through every inherited fault/recovery test.
        shutil.copy2(ARGS.legacy_v200, self.menu)
        original = self.snapshot()
        self.run_control('install')
        self.assertEqual((self.saved / 'backup/menu').read_bytes(), ARGS.legacy_v200.read_bytes())
        self.assertFalse((self.saved / 'backup/menu.absent').exists())
        self.run_control('uninstall', saved=True)
        self.assertEqual(self.snapshot(), original)

    def test_modified_menu_refused_with_actual_hash_before_backup(self):
        data = bytearray(self.menu.read_bytes())
        data[-1] ^= 1
        self.menu.write_bytes(data)
        before = self.snapshot()
        output = self.run_control('install', False)
        self.assertIn('UNEXPECTED_BASE_menu', output)
        self.assertIn('ACTUAL_SHA256=' + migration.sha(data), output)
        self.assertEqual(self.snapshot(), before)
        self.assertFalse(self.saved.exists())

    def test_active_known_upstream_boot_entry_refused(self):
        self.lsd.write_text(self.lsd.read_text().replace('-Xbootclasspath/p:', '-Xbootclasspath/p:$BASE_DIR/lsd/jars/VCMenu.jar:'))
        before = self.snapshot()
        self.assertIn('REMOVE_OTHER_V2_HMI_FIRST', self.run_control('install', False))
        self.assertEqual(self.snapshot(), before)
        self.assertFalse(self.saved.exists())

    def test_menu_symlink_refused(self):
        self.menu.unlink()
        sentinel = self.work / 'legacy-menu'
        shutil.copy2(ARGS.legacy_v201, sentinel)
        self.menu.symlink_to(sentinel)
        before = sentinel.read_bytes()
        self.run_control('install', False)
        self.assertEqual(sentinel.read_bytes(), before)
        self.assertFalse(self.saved.exists())

    def test_corrupt_menu_backup_refused_before_any_restore(self):
        self.run_control('install')
        (self.saved / 'backup/menu').write_bytes(b'corrupt')
        before = self.snapshot()
        self.run_control('recover', False, saved=True)
        self.assertEqual(self.snapshot(), before)

    def test_step4_and_no_sd_full_restore_preserve_dormant_menu(self):
        self.run_control('install')
        lanes = self.work / 'lanes'
        shutil.copytree(ARGS.base / 'sd-card/Custom/carplay_mu1367_lanes', lanes,
                        ignore=shutil.ignore_patterns('source'))
        shutil.copy2(ARGS.verifier, lanes / 'verify')
        env = dict(os.environ, CPMAP_TEST_ROOT=str(self.root))
        subprocess.run(['/bin/ksh', str(lanes / 'control.sh'), 'install', str(lanes)], env=env, check=True, capture_output=True)
        self.assertEqual((self.app / 'carplay-mu1367-lanes/STATE').read_text().strip(), 'installed')
        scripts = self.app / 'eso/hmi/engdefs/scripts/mqb'
        shutil.copytree(ARGS.base / 'sd-card/Toolbox/scripts', scripts)
        shutil.rmtree(lanes)
        shutil.rmtree(self.payload)
        subprocess.run(['/bin/ksh', str(scripts / 'cpmap_restore.sh')], env=env, check=True, capture_output=True)
        self.assertEqual(self.menu.read_bytes(), ARGS.legacy_v201.read_bytes())
        for name, target in [('boot', self.lsd), ('dio', self.app / 'eso/bin/apps/dio_manager'),
                             ('driver', self.app / 'armle/lib/dll/ipod-drvr-iap2.so'),
                             ('iap2.cfg', self.root / 'mnt/system/etc/mm/iap2.cfg')]:
            self.assertEqual(target.read_bytes(), (ARGS.inputs / name).read_bytes())
        self.assertNotIn('VCMenu.jar', self.lsd.read_text())
        self.assertFalse((self.app / 'carplaymaps').exists())


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('base', 'payload', 'inputs', 'verifier', 'legacy-v200', 'legacy-v201', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    ARGS = parser.parse_args()
    for tag, path in [('toolbox-plaintext-v2.0.0', ARGS.legacy_v200), ('toolbox-plaintext-v2.0.1', ARGS.legacy_v201)]:
        if migration.sha(path.read_bytes()) != migration.LEGACY_MENUS[tag]:
            parser.error('Exact official upstream menu required: ' + tag)
    fixture.ARGS = ARGS
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Migration))
    evidence = {'passed': result.wasSuccessful(), 'tests': result.testsRun,
                'legacy_menu_sha256': migration.LEGACY_MENUS, 'test_sha256': migration.sha(Path(__file__).read_bytes()),
                'controller_sha256': migration.sha((ARGS.payload / 'control.sh').read_bytes()), 'on_unit_validated': False}
    ARGS.output.write_text(json.dumps(evidence, indent=2) + '\n')
    raise SystemExit(not result.wasSuccessful())
