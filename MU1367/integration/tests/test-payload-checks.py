#!/usr/bin/env python3
"""Check optional Toolbox customization and required CarPlay payload integrity."""
import argparse
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('payload_checks', HERE.parent / 'tools/payload_checks.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class Suite(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix='carplay-payload-checks-')
        self.addCleanup(temp.cleanup)
        self.custom = Path(temp.name) / 'Custom'
        self.required = (
            'carplay_maps_vc/payload/common/install-carplay-maps.sh',
            'carplay_mu1367/control.sh',
            'carplay_mu1367_settings/VCMenu.jar',
            'carplay_mu1367_guidance_v3/6/core.so',
            'carplay_mu1367_map_only/actions.sh',
            'carplay_mu1367_refinements/actions.sh',
            'carplay_mu1367_oem_reset/payload/boot',
            'carplay_mu1367_v3_turn_cards/6/core.so',
            'carplay_mu1367_audio_progress/CarPlayMU1367Audio.jar',
        )
        for name in (*self.required, 'GreenMenu/Demo.esd', 'GreenMenu/Demo_sub.esd',
                     'GreenMenu/example.esd', 'GreenMenu/mqbcoding_tests.esd',
                     'GEM/GEM.jar', 'FEC/place FECContainer.fec here', 'passwords.csv'):
            path = self.custom / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(name + '\n')
        for name in module.CHECKER_ROOTS:
            shutil.copy2(ARGS.verifier, self.custom / name / 'verify')
        module.write_payload_checks(self.custom)

    def check(self, name, success):
        result = subprocess.run(
            ['/bin/ksh', '-c', 'P=$1; . "$P/payload-check.sh"', 'preflight',
             str(self.custom / name)], capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode == 0, success, result.stdout + result.stderr)

    def test_optional_toolbox_files_can_be_removed_or_changed(self):
        for name in ('GreenMenu', 'GEM', 'FEC'):
            shutil.rmtree(self.custom / name)
        (self.custom / 'passwords.csv').write_text('customized\n')
        for name in module.CHECKER_ROOTS:
            self.check(name, True)

    def test_missing_or_modified_carplay_files_are_rejected(self):
        for name in self.required:
            with self.subTest(file=name):
                file = self.custom / name
                original = file.read_bytes()
                file.write_bytes(b'modified')
                self.check(module.CHECKER_ROOTS[0], False)
                file.unlink()
                self.check(module.CHECKER_ROOTS[0], False)
                file.write_bytes(original)

    def test_all_three_stages_keep_the_same_protection(self):
        scripts = [(self.custom / name / 'payload-check.sh').read_bytes()
                   for name in module.CHECKER_ROOTS]
        self.assertEqual(len(set(scripts)), 1)
        (self.custom / 'carplay_mu1367_oem_reset/payload/boot').unlink()
        for name in module.CHECKER_ROOTS:
            self.check(name, False)


def main():
    global ARGS
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verifier', required=True, type=Path)
    parser.add_argument('--output', type=Path)
    ARGS = parser.parse_args()
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Suite))
    if ARGS.output:
        ARGS.output.write_text(json.dumps({'passed': result.wasSuccessful(), 'tests': result.testsRun}, indent=2) + '\n')
    raise SystemExit(not result.wasSuccessful())


if __name__ == '__main__':
    main()
