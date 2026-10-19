#!/usr/bin/env python3
"""Capture C2 tests with only firmware-verified ls/mkdir/dd in PATH."""
from pathlib import Path
import os
import shlex
import shutil
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).with_name("capture-rgi.sh").resolve()
SHELL = shutil.which("ksh")


class CaptureTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="mu1427-capture-")
        self.addCleanup(self.tmp.cleanup)
        self.work = Path(self.tmp.name)
        self.root, self.sd, self.tools = [self.work / x for x in ("mmx", "sd", "bin")]
        for path in (self.root, self.sd, self.tools): path.mkdir()
        for name in ("ls", "mkdir", "dd"):
            (self.tools / name).symlink_to(shutil.which(name))
        self.iap = self.put("dev/shmem/iap2.log", b"CPMAP_RGI_RX synthetic capture fixture\n")
        self.driver = self.put("mnt/app/armle/lib/dll/ipod-drvr-iap2.so", b"synthetic-driver")
        self.config = self.put("mnt/system/etc/mm/iap2.cfg", b"synthetic-config")
        self.oem = self.root / "mnt/ota/system/logs/smartphone_integrator_error_42"
        self.oem.mkdir(parents=True)
        (self.oem / "iap2-tail.txt").write_bytes(b"synthetic original iAP2 tail\n")
        self.put("ramdisk/carplaymaps-video.log", b"synthetic-video\n")
        self.env = dict(os.environ, CPMAP_TEST_ROOT=str(self.root), CPMAP_TEST_VOL=str(self.sd), PATH=str(self.tools))

    def put(self, name, data):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path

    def run_capture(self):
        p = subprocess.run([SHELL, str(SCRIPT)], env=self.env, capture_output=True, text=True, timeout=10)
        outs = list((self.sd / "Log").glob("cpmap-navrecon-C2-*"))
        self.assertEqual(len(outs), 1)
        return p, outs[0]

    def test_copies_files_and_oem_tail_without_modifying_sources(self):
        before = {p: p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        p, out = self.run_capture()
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn("CPMAP_RGI_CAPTURE_OK", p.stdout)
        self.assertEqual((out / "iap2.log").read_bytes(), self.iap.read_bytes())
        self.assertEqual((out / "files/ipod-drvr-iap2.so").read_bytes(), self.driver.read_bytes())
        self.assertEqual((out / "oem-error-42/smartphone_integrator_error_42/iap2-tail.txt").read_bytes(), (self.oem / "iap2-tail.txt").read_bytes())
        self.assertEqual({p: p.read_bytes() for p in before}, before)

    def test_skips_fifo_symlink_directory_and_pps(self):
        os.mkfifo(self.oem / "fifo")
        (self.oem / "symlink").symlink_to(self.iap)
        (self.oem / "nested").mkdir()
        (self.oem / "nested/not-recursed").write_bytes(b"nested")
        pps = self.root / "ramdisk/pps/iap2"
        pps.mkdir(parents=True)
        os.mkfifo(pps / "device")
        p, out = self.run_capture()
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        saved = out / "oem-error-42/smartphone_integrator_error_42"
        for name in ("fifo", "symlink", "nested"):
            self.assertFalse((saved / name).exists())
        self.assertIn("SKIP non-regular", (out / "progress.txt").read_text())

    def test_skip_oversized_files_without_truncating_archives(self):
        core = self.oem / "huge.core"
        with core.open("wb") as f: f.truncate(67108865)
        p, out = self.run_capture()
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertFalse((out / "oem-error-42/smartphone_integrator_error_42/huge.core").exists())
        self.assertIn("SKIP oversized", p.stdout)

    def test_empty_log_has_no_read_and_no_stale_block_count(self):
        self.iap.write_bytes(b"")
        p, out = self.run_capture()
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertEqual((out / "iap2.log").read_bytes(), b"")
        self.assertIn("initial_bytes=0 max_read=0", p.stdout)

    def test_log_growth_is_bounded_by_initial_size(self):
        self.iap.write_bytes(b"A")
        (self.tools / "dd").unlink()
        wrapper = self.tools / "dd"
        wrapper.write_text(f'''#!/bin/sh
case "$1" in {shlex.quote('if='+str(self.iap))})
    n=0
    while [ "$n" -lt 1000 ]; do printf '0123456789abcdef' >> {shlex.quote(str(self.iap))}; n=$((n+1)); done ;;
esac
exec {shlex.quote(shutil.which('dd'))} "$@"
''')
        wrapper.chmod(0o755)
        p, out = self.run_capture()
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertEqual((out / "iap2.log").stat().st_size, 4096)
        self.assertIn("initial_bytes=1 max_read=4096", p.stdout)

    def test_read_failure_reports_partial_but_preserves_other_evidence(self):
        (self.tools / "dd").unlink()
        wrapper = self.tools / "dd"
        wrapper.write_text(f'#!/bin/sh\ncase "$1" in {shlex.quote("if="+str(self.iap))}) exit 7;; esac\nexec {shlex.quote(shutil.which("dd"))} "$@"\n')
        wrapper.chmod(0o755)
        p, out = self.run_capture()
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("CPMAP_RGI_CAPTURE_PARTIAL=1", p.stdout)
        self.assertTrue((out / "oem-error-42/smartphone_integrator_error_42/iap2-tail.txt").exists())
        self.assertTrue((out / "files/iap2.cfg").is_file())

    def test_missing_oem_dump_is_reported_and_log_still_saved(self):
        shutil.rmtree(self.oem)
        p, out = self.run_capture()
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn("OEM_ERROR_NOT_FOUND id=42", p.stdout)
        self.assertEqual((out / "iap2.log").read_bytes(), self.iap.read_bytes())

    def test_selects_newest_numbered_oem_error_after_b1(self):
        latest = self.oem.parent / "smartphone_integrator_error_43.tar.gz"
        latest.write_bytes(b"synthetic-new-archive")
        (self.oem.parent / "smartphone_integrator_error_bad.tar.gz").write_bytes(b"skip")
        p, out = self.run_capture()
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertEqual((out / "oem-error-43/smartphone_integrator_error_43.tar.gz").read_bytes(), latest.read_bytes())
        self.assertFalse((out / "oem-error-42").exists())

    def test_no_global_mount_listing_or_process_or_recursive_scan(self):
        source = SCRIPT.read_text()
        self.assertNotRegex(source, r"(?m)^\s*(?:date|find|pidin|sloginfo|cat)\s")
        self.assertNotRegex(source, r"(?m)^\s*mount\s*(?:>|2>|$)")
        self.assertNotIn("ls -lnR", source)
        self.assertNotIn("cp -r", source)


if __name__ == "__main__":
    unittest.main(verbosity=2)
