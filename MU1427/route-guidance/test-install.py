#!/usr/bin/env python3
"""Run B2 installation AND local rollback using only base-toolbox commands.

Usage: python test-install.py STOCK_DRIVER STOCK_CONFIG BUILT_SD_PAYLOAD
All invocations have a closed PATH: ls cp cat mv mkdir rm sync. Host tests
compare actual bytes and modes; on-unit checks intentionally use OEM sizes.
"""
from pathlib import Path
import os
import re
import shlex
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest

STOCK_DRIVER, STOCK_CONFIG, PAYLOAD = map(lambda p: Path(p).resolve(), sys.argv[1:4])
del sys.argv[1:4]
SCRIPT = Path(os.environ.get("CPMAP_INSTALL_TEST_SCRIPT", Path(__file__).with_name("rg-b1.sh"))).resolve()
REVISION = re.search(r"(?m)^INSTALLER_REVISION=(\S+)$", SCRIPT.read_text())[1]
SHELL = shutil.which("ksh")
TOOLS = ("ls", "cp", "cat", "mv", "mkdir", "rm", "sync")


class InstallTests(unittest.TestCase):
    def setUp(self):
        self.work = tempfile.TemporaryDirectory(prefix="mu1427-rgi-install-")
        self.addCleanup(self.work.cleanup)
        self.root = Path(self.work.name)
        self.driver = self.root / "mnt/app/armle/lib/dll/ipod-drvr-iap2.so"
        self.config = self.root / "mnt/system/etc/mm/iap2.cfg"
        self.backup = self.root / "mnt/app/route-guidance-b1"
        self.lock = self.root / "ramdisk/.route-guidance-b1-lock"
        self.lock.parent.mkdir()
        for p, source, mode in ((self.driver, STOCK_DRIVER, 0o777), (self.config, STOCK_CONFIG, 0o755)):
            p.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, p)
            p.chmod(mode)  # Actual modes in the Phase A ls -ln capture.
        self.jxe = self.root / "ifs/lsd.jxe"
        self.jxe.parent.mkdir()
        with self.jxe.open("wb") as f: f.truncate(52751492)
        self.tools = self.root / "base-bin"
        self.tools.mkdir()
        for name in TOOLS:
            (self.tools / name).symlink_to(shutil.which(name))
        self.assertFalse(any((self.tools / x).exists() for x in ("cksum", "tr", "wc", "cmp", "awk", "rmdir")))

    def invoke(self, action, payload=PAYLOAD, stubs=None, script=SCRIPT, clean=True):
        env = dict(os.environ, CPMAP_TEST_ROOT=str(self.root), PATH=str(self.tools))
        if stubs: env["PATH"] = f"{stubs}:{self.tools}"
        p = subprocess.run([SHELL, str(script), action, str(payload)], env=env, text=True, capture_output=True)
        if clean:
            self.assertFalse(self.lock.exists(), p.stdout + p.stderr)
            self.assertEqual(list(self.driver.parent.glob(".ipod-drvr-iap2.b1-*")), [])
            self.assertEqual(list(self.config.parent.glob(".iap2.cfg.b1-*")), [])
            self.assertEqual(list((self.root / "mnt/app").glob(".route-guidance-b1-backup-*")), [])
        return p

    def installed(self):
        self.assertEqual(self.driver.read_bytes(), (PAYLOAD / "ipod-drvr-iap2.so").read_bytes())
        self.assertEqual(self.config.read_bytes(), (PAYLOAD / "iap2.cfg").read_bytes())
        self.modes()

    def stock(self):
        self.assertEqual(self.driver.read_bytes(), STOCK_DRIVER.read_bytes())
        self.assertEqual(self.config.read_bytes(), STOCK_CONFIG.read_bytes())
        self.modes()

    def modes(self):
        self.assertEqual(stat.S_IMODE(self.driver.stat().st_mode), 0o777)
        self.assertEqual(stat.S_IMODE(self.config.stat().st_mode), 0o755)

    def install(self):
        p = self.invoke("install")
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn("CPMAP_RGI_INSTALL_OK", p.stdout)
        self.assertIn(REVISION, p.stdout)
        self.installed()

    def restore(self, **kwargs):
        p = self.invoke("restore", payload="/missing/sd", **kwargs)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn("CPMAP_RGI_RESTORE_OK", p.stdout)
        self.stock()

    def fault(self, command, body):
        stubs = self.root / "fault-bin"
        stubs.mkdir(exist_ok=True)
        stub = stubs / command
        stub.write_text("#!/bin/sh\n" + body + f'\nexec {shlex.quote(shutil.which(command))} "$@"\n')
        stub.chmod(0o755)
        return stubs

    def test_install_repeat_status_local_restore_and_reinstall(self):
        with self.driver.open("rb") as old_inode:
            self.install()
            self.assertEqual(old_inode.read(), STOCK_DRIVER.read_bytes())
        self.install()
        self.assertEqual((self.backup / "stock-driver.so").read_bytes(), STOCK_DRIVER.read_bytes())
        self.assertEqual((self.backup / "stock-iap2.cfg").read_bytes(), STOCK_CONFIG.read_bytes())
        self.assertEqual(self.invoke("status").returncode, 0)
        self.restore(script=self.backup / "rg-b1.sh")
        self.restore(script=self.backup / "rg-b1.sh")
        self.install()

    def test_wrong_or_missing_firmware_refused_without_backup(self):
        with self.jxe.open("wb") as f: f.truncate(55840541)
        p = self.invoke("install")
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("WRONG_FIRMWARE", p.stdout)
        self.stock()
        self.jxe.unlink()
        p = self.invoke("install")
        self.assertIn("FIRMWARE_STAT_FAILED", p.stdout)
        self.assertFalse(self.backup.exists())

    def test_missing_or_truncated_payload_refused_before_backup(self):
        for path in ("/missing", self.root):
            self.assertNotEqual(self.invoke("install", payload=path).returncode, 0)
            self.stock()
        damaged = self.root / "damaged-payload"
        shutil.copytree(PAYLOAD, damaged)
        for name in ("ipod-drvr-iap2.so", "iap2.cfg"):
            target = damaged / name
            original = target.read_bytes()
            target.write_bytes(b"truncated")
            p = self.invoke("install", payload=damaged)
            self.assertNotEqual(p.returncode, 0)
            self.stock()
            target.write_bytes(original)
        self.assertFalse(self.backup.exists())

    def test_unknown_current_sizes_and_missing_original_backups_refused(self):
        self.config.write_bytes(b"custom config")
        p = self.invoke("install")
        self.assertIn("CURRENT_CONFIG_SIZE_UNSUPPORTED", p.stdout)
        self.assertEqual(self.config.read_bytes(), b"custom config")
        shutil.copyfile(STOCK_CONFIG, self.config)
        shutil.copyfile(PAYLOAD / "ipod-drvr-iap2.so", self.driver)
        p = self.invoke("install")
        self.assertIn("STOCK_DRIVER_BACKUP_INVALID", p.stdout)
        self.assertFalse(self.backup.exists())

    def test_truncated_backups_refused_without_touching_active_files(self):
        self.install()
        for name, original in (("stock-driver.so", STOCK_DRIVER), ("stock-iap2.cfg", STOCK_CONFIG)):
            backup = self.backup / name
            backup.write_bytes(b"truncated backup")
            for action in ("install", "restore"):
                p = self.invoke(action)
                self.assertNotEqual(p.returncode, 0)
                self.assertIn("BACKUP_INVALID", p.stdout)
                self.installed()
            shutil.copyfile(original, backup)

    def test_rollback_recovers_missing_and_damaged_active_files(self):
        self.install()
        for missing, damaged in ((self.driver, self.config), (self.config, self.driver)):
            missing.unlink()
            damaged.write_bytes(b"broken active file")
            self.restore(script=self.backup / "rg-b1.sh")
            self.install()

    def test_rollback_recovers_either_partial_two_file_commit(self):
        self.install()
        for target, original in ((self.driver, STOCK_DRIVER), (self.config, STOCK_CONFIG)):
            shutil.copyfile(original, target)
            self.restore()
            self.install()

    def test_rollback_needs_no_payload_version_or_old_checksum_manifest(self):
        self.install()
        (self.backup / "VERSION").unlink()
        (self.backup / "checksums.txt").write_text("obsolete unusable manifest\n")
        self.restore(script=self.backup / "rg-b1.sh")
        self.install()

    def test_local_rollback_after_reboot_clears_interrupted_operation_lock(self):
        self.install()
        self.driver.write_bytes(b"interrupted driver")
        self.config.unlink()
        self.lock.mkdir()
        shutil.rmtree(self.lock.parent)  # Simulate reboot clearing /ramdisk.
        self.lock.parent.mkdir()
        self.restore(script=self.backup / "rg-b1.sh")

    def test_adopts_rolled_back_b1_backups_without_overwriting_originals(self):
        self.install()
        self.restore()
        (self.backup / "VERSION").write_text("MU1427-iAP2-RGI-B1-7c51c1f3\n")
        (self.backup / "rg-b1.sh").write_text("obsolete local restore script\n")
        before = [(self.backup / name).read_bytes() for name in ("stock-driver.so", "stock-iap2.cfg")]
        self.install()
        self.assertEqual([(self.backup / name).read_bytes() for name in ("stock-driver.so", "stock-iap2.cfg")], before)
        self.assertIn(REVISION, (self.backup / "rg-b1.sh").read_text())
        self.restore(script=self.backup / "rg-b1.sh")

    def test_active_old_b1_is_refused_but_new_rollback_can_restore_it(self):
        self.install()
        self.driver.write_bytes(bytes(741796))  # Size of the rejected B1 driver.
        (self.backup / "VERSION").write_text("MU1427-iAP2-RGI-B1-7c51c1f3\n")
        p = self.invoke("install")
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("CURRENT_DRIVER_SIZE_UNSUPPORTED", p.stdout)
        self.restore(script=self.backup / "rg-b1.sh")

    def test_backup_copy_failure_leaves_stock_and_allows_retry(self):
        stubs = self.fault("cp", 'case "$3" in */stock-iap2.cfg) exit 1;; esac')
        p = self.invoke("install", stubs=stubs)
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("CONFIG_BACKUP_FAILED", p.stdout)
        self.stock()
        self.assertFalse(self.backup.exists())
        self.install()

    def test_config_staging_failure_never_changes_driver(self):
        stubs = self.fault("cat", 'case "$1" in */iap2.cfg) exit 1;; esac')
        p = self.invoke("install", stubs=stubs)
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("CONFIG_STAGE_FAILED", p.stdout)
        self.stock()
        self.restore(script=self.backup / "rg-b1.sh")

    def test_truncated_stage_detected_before_any_activation(self):
        stubs = self.fault("cat", 'case "$1" in */ipod-drvr-iap2.so) echo truncated; exit 0;; esac')
        p = self.invoke("install", stubs=stubs)
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("DRIVER_STAGE_SIZE_INVALID", p.stdout)
        self.stock()

    def test_first_activation_rename_failure_leaves_stock(self):
        stubs = self.fault("mv", f'if [ "$2" = {shlex.quote(str(self.driver))} ]; then exit 1; fi')
        p = self.invoke("install", stubs=stubs)
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("DRIVER_REPLACE_FAILED", p.stdout)
        self.stock()
        self.restore()

    def test_second_activation_rename_failure_rolls_both_files_back(self):
        once = shlex.quote(str(self.root / "failed-once"))
        stubs = self.fault("mv", f'if [ "$2" = {shlex.quote(str(self.config))} ] && [ ! -f {once} ]; then echo failed > {once}; exit 1; fi')
        p = self.invoke("install", stubs=stubs)
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("CONFIG_REPLACE_FAILED_STOCK_RESTORED", p.stdout)
        self.stock()
        self.restore(script=self.backup / "rg-b1.sh")

    def test_failed_automatic_rollback_retains_backups_and_can_retry(self):
        stubs = self.fault("mv", f'if [ "$2" = {shlex.quote(str(self.config))} ]; then exit 1; fi')
        p = self.invoke("install", stubs=stubs)
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("CONFIG_REPLACE_FAILED_STOCK_ROLLBACK_FAILED_RETRY_RESTORE", p.stdout)
        self.assertTrue((self.backup / "stock-driver.so").is_file())
        self.restore(script=self.backup / "rg-b1.sh")

    def test_restore_copy_failure_changes_neither_active_file(self):
        self.install()
        stubs = self.fault("cp", 'case "$2" in */stock-iap2.cfg) exit 1;; esac')
        p = self.invoke("restore", stubs=stubs)
        self.assertNotEqual(p.returncode, 0)
        self.installed()
        self.restore()

    def test_restore_second_rename_failure_can_be_retried(self):
        self.install()
        stubs = self.fault("mv", f'if [ "$2" = {shlex.quote(str(self.config))} ]; then exit 1; fi')
        p = self.invoke("restore", stubs=stubs)
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("STOCK_RESTORE_FAILED_RETRY_RESTORE", p.stdout)
        self.assertEqual(self.driver.read_bytes(), STOCK_DRIVER.read_bytes())
        self.assertEqual(self.config.read_bytes(), (PAYLOAD / "iap2.cfg").read_bytes())
        self.restore(script=self.backup / "rg-b1.sh")

    def test_missing_backups_and_concurrent_lock_refused(self):
        self.assertNotEqual(self.invoke("restore").returncode, 0)
        self.stock()
        self.lock.mkdir()
        p = self.invoke("install", clean=False)
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("ANOTHER_OPERATION_OR_STALE_LOCK", p.stdout)
        self.assertTrue(self.lock.exists())
        self.stock()

    def test_installer_has_only_base_command_dependencies(self):
        source = SCRIPT.read_text()
        self.assertNotRegex(source, r"\b(?:cksum|tr|wc|cmp|awk|rmdir)\b")
        declared = re.search(r"for tool in (.*?); do", source)[1].split()
        self.assertEqual(tuple(declared), TOOLS)

    def test_native_mount_dispatch_matches_base_local_and_rcc_paths(self):
        body = re.search(r"(?m)^native\(\) \{\n(.*?)^\}", SCRIPT.read_text(), re.S | re.M)[1]
        log = self.root / "native.log"
        stubs = self.fault("mount", f'echo "mount $*" >> {shlex.quote(str(log))}\nexit 0')
        (stubs / "on").write_text(f'#!/bin/sh\necho "on $*" >> {shlex.quote(str(log))}\nshift 2\nexec "$@"\n')
        (stubs / "on").chmod(0o755)
        for prefix in ("", "/net/mmx"):
            log.write_text("")
            harness = f'M={shlex.quote(prefix)}\nnative() {{\n{body}}}\nnative mount -uw /mnt/app\nnative mount -uw /mnt/system\n'
            env = dict(os.environ, CPMAP_TEST_ROOT="", PATH=f"{stubs}:{self.tools}")
            p = subprocess.run([SHELL], input=harness, env=env, capture_output=True, text=True)
            self.assertEqual(p.returncode, 0, p.stderr)
            lines = log.read_text().splitlines()
            expected = []
            for partition in ("/mnt/app", "/mnt/system"):
                if prefix: expected.append(f"on -f mmx mount -uw {partition}")
                expected.append(f"mount -uw {partition}")
            self.assertEqual(lines, expected)


if __name__ == "__main__":
    unittest.main(verbosity=2)
