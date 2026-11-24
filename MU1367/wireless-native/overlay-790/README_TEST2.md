# MU1367 OEM touch / 790 upstream runtime comparison

See [START_HERE.md](START_HERE.md) for installation from test 1 and recovery.
This is a local experimental comparison; the 790 static-noise cause is not
confirmed. There is no change to the published v1.6.3-e release.

The 790 producer/profile files match omonob's public v3.2 Standalone package.
Test 2 also uses that package's matching 790 core, shared TS/MOST bridge and
wireless-aware supervisor, rather than test 1's mixed runtime. The OEM-routed
touch JARs are unchanged. A separately named transaction preserves test-1 and
parent snapshots and requires restoration/reboot before installing test 2.

The 791 choice retains the existing test-1 overlay-only path. Normal install,
uninstall, recovery and OEM-restore wrappers remove either test generation
first and retain exact firmware and controller gates.

The package includes verification reports and its complete file hashes. Passing
software conversion tests, firmware imports and transaction checks does not
prove that the car's decoder accepts the stream. Vehicle comparison is required.
