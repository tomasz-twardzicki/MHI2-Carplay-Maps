#!/usr/bin/env python3
"""B3 installation/rollback suite, including direct upgrade from actual B2.

Usage: python test-install-b3.py STOCK_DRIVER STOCK_CONFIG BUILT_B3_SD_PAYLOAD
"""
import importlib.util
import os
from pathlib import Path
import shlex
import shutil
import sys
import unittest

HERE = Path(__file__).resolve().parent
payload = Path(sys.argv[3]).resolve()
os.environ['CPMAP_INSTALL_TEST_SCRIPT'] = str(payload.parents[1] / 'Toolbox/scripts/cpmap_rgi_b1.sh')


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    obj = importlib.util.module_from_spec(spec); spec.loader.exec_module(obj)
    return obj


base = module('install_tests', HERE / 'test-install.py')
patch = module('b2_patch', HERE / 'patch-driver.py')
B2_DATA = patch.build(base.STOCK_DRIVER.read_bytes())[0]


class InstallB3Tests(base.InstallTests):
    def b2_active(self):
        self.install(); self.restore()
        self.driver.write_bytes(B2_DATA)
        shutil.copyfile(base.PAYLOAD / 'iap2.cfg', self.config)
        (self.backup / 'VERSION').write_text('MU1427-iAP2-RGI-B2-0763b7aa\n')
        self.assertEqual(len(B2_DATA), 741944)

    def test_direct_b2_upgrade_preserves_originals_and_local_rollback(self):
        self.b2_active()
        originals = [(self.backup / n).read_bytes() for n in ('stock-driver.so', 'stock-iap2.cfg')]
        self.install()
        self.assertEqual([(self.backup / n).read_bytes() for n in ('stock-driver.so', 'stock-iap2.cfg')], originals)
        self.restore(script=self.backup / 'rg-b1.sh')

    def test_wrong_b2_marker_refused_without_modification(self):
        self.b2_active()
        (self.backup / 'VERSION').write_text('unknown-build\n')
        result = self.invoke('install')
        self.assertIn('DIFFERENT_BUILD_RESTORE_FIRST', result.stdout)
        self.assertEqual(self.driver.read_bytes(), B2_DATA)
        self.restore()

    def test_b2_upgrade_second_rename_failure_restores_oem_pair(self):
        self.b2_active()
        once = shlex.quote(str(self.root / 'failed-once'))
        stubs = self.fault('mv', f'if [ "$2" = {shlex.quote(str(self.config))} ] && [ ! -f {once} ]; then echo failed > {once}; exit 1; fi')
        result = self.invoke('install', stubs=stubs)
        self.assertIn('CONFIG_REPLACE_FAILED_STOCK_RESTORED', result.stdout)
        self.stock()
        self.restore(script=self.backup / 'rg-b1.sh')


if __name__ == '__main__': unittest.main(verbosity=2)
