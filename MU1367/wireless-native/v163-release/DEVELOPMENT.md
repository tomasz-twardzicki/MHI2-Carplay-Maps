# v1.6.3-e packaging and verification

`assemble.py` starts with the SHA-pinned sealed v1.6.3-e-test2 ZIP. It changes
the release orchestrator, forward OEM reset and relevant SD guard scopes.
Every wireless-layer file, controller and recovery ID remains byte-identical
to test2. Later test3/GPS experiments are excluded.

The extended forward OEM reset restores verified firmware bytes rather than
executing upstream scripts or trusting their backup receipts. HW50/HW70 and
K4525/P4521 extra app files are compared in FACTORY-EXTRA.json. The exact
v3.0/v3.1/v3.2 transaction targets are checked in UPSTREAM-RESTORE-AUDIT.json.
Optional addon ancestors may be absent, but existing symlinks/non-directories
are refused before writes. Manager directories are renamed on the app volume;
pairing data remains inert in its existing store. OEM reset also restores gal,
so it does not depend on a working old Android Auto controller.

Example staging (firmware and extracted stock inputs are external):

```sh
python3 MU1367/wireless-native/v163-release/assemble.py \
  --baseline /path/to/CarPlay_Maps_VC_MU1367_791_v1.6.3-e-test2.zip \
  --firmware /path/to/MHI2_ER_VWG13_K4525_1_AIO_MU1367_20230318 \
  --inputs /path/to/verified-stock-inputs --output /tmp/v163e-stage
```

`test-host.py` extends the stable real-controller suite. Use the current
published integration tree for its historical v1.5.3 fixtures. The complete
regression covers four base layouts, earlier wireless migrations, snapshot
preservation, corruption rejection, interrupted commits, clean installation,
upstream forward restore and installation after restore. Final targeted checks
also exercise the active upstream session refusal. Host mounts/sync are inert;
config-patch uses previously verified native-output replay.

`test-qnx.py` executes the actual fresh base/wireless/OEM controllers with
firmware-extracted tools. Only the JXE verifier/stat boundaries and mounts are
fixture substitutes. Production controllers, guard generation, native config
patching, reboot markers, snapshot retention and forward OEM writes execute.
Hardware services are not started. `test-defaults.py` executes the actual four
packaged VCMenu JARs and verifies fresh Off plus explicitly saved On/Off.

`seal.py` requires the passing broad regression, final host/QNX reports and
packaged-JAR tests; it pins controller identities, compares every wireless-layer
file with test2, checks all SD guard references and shell syntax, and hashes
every ZIP entry on readback. It records the historical test2 runtime evidence
separately from this release's installation/recovery checks.

The reported requirement to install v1.5.4 first was not reproduced with the
complete clean package. Both host and factory-shell tests explicitly install
the full base from an empty unit, reboot, then install wireless using the same
SD. No physical vehicle result is inferred from these tests.
