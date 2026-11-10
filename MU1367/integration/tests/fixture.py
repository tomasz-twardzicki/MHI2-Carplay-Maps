#!/usr/bin/env python3
"""Exercise real install/update/rollback/reset actions with isolated filesystems."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest
import zipfile

HERE = Path(__file__).resolve().parent


def sha(data):
    return hashlib.sha256(data).hexdigest()


class Suite(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='mu1367-suite-seed-')
        cls.work = Path(cls.temp.name).resolve()
        cls.sd = cls.work / 'sd'
        shutil.copytree(ARGS.package / 'sd-card/Custom', cls.sd / 'Custom', ignore=shutil.ignore_patterns('source'))
        native_sha = sha((cls.sd / 'Custom/carplay_mu1367_refinements/verify').read_bytes())
        host_sha = sha(ARGS.verifier.read_bytes())
        for f in (cls.sd / 'Custom').rglob('verify'):
            shutil.copy2(ARGS.verifier, f)
        f = cls.sd / 'Custom/carplay_mu1367_refinements/payload-check.sh'
        f.write_text(f.read_text().replace(native_sha, host_sha))
        cls.seed = cls.work / 'seed'
        for dest, name in [('ifs/lsd.jxe', 'lsd.jxe'), ('mnt/app/armle/lib/dll/ipod-drvr-iap2.so', 'driver'),
                           ('mnt/system/etc/mm/iap2.cfg', 'iap2.cfg'), ('mnt/app/eso/hmi/lsd/lsd.sh', 'boot'),
                           ('mnt/app/eso/bin/apps/dio_manager', 'dio'),
                           # v1.4.6: compressed artwork (default) checks the factory zlib
                           ('proc/boot/libz.so.2', 'libz.so.2')]:
            p = cls.seed / dest
            p.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ARGS.inputs / name, p)
            if name in ('boot', 'dio', 'driver'):
                p.chmod(0o755)
        (cls.seed / 'mnt/app/eso/hmi/lsd/jars').mkdir()
        (cls.seed / 'ramdisk').mkdir()
        (cls.seed / 'mnt/icab/persistent/cpmap-ui').mkdir(parents=True)
        cls.tools = cls.work / 'tools'
        cls.tools.mkdir()
        (cls.tools / 'mount').write_text('#!/bin/ksh\nexit 0\n')
        (cls.tools / 'mount').chmod(0o755)
        cls.base_env = dict(os.environ, PATH=str(cls.tools) + ':' + os.environ['PATH'])
        cls.original = cls.runtime(cls.seed)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    @staticmethod
    def runtime(root):
        app = root / 'mnt/app'
        paths = ['eso/hmi/lsd/jars/CarPlayMU1367Guidance.jar', 'carplaymaps/core.so', 'eso/hmi/lsd/lsd.sh',
                 'armle/lib/dll/ipod-drvr-iap2.so', 'eso/bin/apps/dio_manager',
                 'eso/hmi/lsd/jars/CarPlayMU1367Audio.jar', 'eso/hmi/lsd/jars/VCMenu.jar',
                 'eso/hmi/lsd/jars/CarPlayClusterControls.jar']
        paths += [n + '/control.sh' for n in ('carplay-mu1367', 'carplay-mu1367-settings', 'carplay-mu1367-lanes',
                                              'carplay-mu1367-wireless', 'carplay-mu1367-artwork',
                                              'carplay-mu1367-card-scene', 'carplay-mu1367-road-name')]
        return {p: (sha((app / p).read_bytes()), (app / p).stat().st_mode & 0o777) if (app / p).is_file() else None for p in paths}

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='mu1367-suite-case-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve() / 'mmx'
        shutil.copytree(self.seed, self.root)
        self.app = self.root / 'mnt/app'
        self.env = dict(self.base_env, CPMAP_TEST_ROOT=str(self.root))
        self.p = self.sd / 'Custom/carplay_mu1367_refinements'

    def run_script(self, p, args, success=True, env=None):
        r = subprocess.run(['/bin/ksh', str(p), *map(str, args)], env=env or self.env, capture_output=True, text=True, timeout=300)
        self.assertEqual(r.returncode == 0, success, r.stdout + r.stderr)
        return r.stdout + r.stderr

    def action(self, action, success=True):
        return self.run_script(self.p / 'actions.sh', [action, self.p], success)

    def saved(self, action, success=True):
        return self.run_script(self.app / 'carplay-mu1367-refinements/control.sh', [action], success)

    def base6(self):
        custom = self.sd / 'Custom'
        maps = custom / 'carplay_maps_vc/payload'
        self.run_script(maps / 'common/install-carplay-maps.sh', [maps, 'MU1367', '791'])
        for name in ('carplay_mu1367', 'carplay_mu1367_settings', 'carplay_mu1367_lanes', 'carplay_mu1367_wireless', 'carplay_mu1367_artwork'):
            p = custom / name
            self.run_script(p / 'control.sh', ['install', p])

    def prepare(self, variant):
        self.base6()
        if variant.startswith('7'):
            p = self.sd / 'Custom/carplay_mu1367_card_scene'
            self.run_script(p / 'control.sh', ['install', p])
        if variant.endswith('-road'):
            n = 'carplay_mu1367_road_name' if variant.startswith('7') else 'carplay_mu1367_road_name_without_card_scene'
            p = self.sd / 'Custom' / n
            self.run_script(p / 'control.sh', ['install', p])
