# MU1367-P4521 / 791 — v1.4.0 experimental

Separate installation bundle for **MHI2_ER_VWG13_P4521_MU1367** and the
**791 / 12.3-inch** cluster, based directly on `MU1367-v1.4.0`
(`e502f20286b1140c17e297dffb98537ad445a75f`).

Both firmware hardware variants (50 and 70) have identical HMI, iAP2 driver,
accessory config, AirPlay library, boot script and DIO manager bytes to the
K4525 inputs used by v1.4.0. The J9 runtime and pinned stage-1 libraries also
match. `FACTORY.json` records hashes and sizes. No size or hash check was
relaxed; no runtime binary, JAR or transactional controller was changed.

Read [installation and recovery](INSTALL.md). This package retains native
lanes, native guidance/audio text, App-Connect display settings, map/mirror
and Card OFF defaults from v1.4.0. Saved preferences are retained by the
existing controllers. **P4521 vehicle operation has not been validated.**
790 support is outside this release.

The separate repository path is `MU1367-P4521/`; the SD entry point is
`Custom/carplay_mu1367_p4521/install.sh`. Runtime/recovery directories remain
`carplaymaps`, `carplay-mu1367`, `carplay-mu1367-settings` and
`carplay-mu1367-lanes`, because the unchanged v1.4.0 binaries use those paths.
These are alternative firmware bundles, not installations to run side by side.
The supplied inputs cannot distinguish P4521 from K4525 by these file hashes.

Reproduce firmware comparison, packaging and installer tests from the repo:

```sh
python3 MU1367-P4521/prepare-firmware.py /path/to/MHI2_ER_VWG13_P4521_MU1367 /tmp/p4521-inputs
python3 MU1367-P4521/package.py --inputs /tmp/p4521-inputs --output MU1367-P4521/build-package
cc -O2 MU1367/port/verify.c -o /tmp/p4521-verify
python3 MU1367-P4521/test-package.py --package MU1367-P4521/build-package --inputs /tmp/p4521-inputs --verifier /tmp/p4521-verify --output MU1367-P4521/build-tests.json
python3 MU1367-P4521/test-runtime.py --package MU1367-P4521/build-package --java-home /path/to/jdk8 --stock-jar /path/to/converted/stock.jar --output MU1367-P4521/build-runtime-tests
```

`stock.jar` must be converted from the pinned P4521 JXE (identical to K4525),
using the JXE conversion procedure in `MU1367/port/README.md`. The runtime
test pins its class contents. The existing lane fault-injection suite also
accepts this package as both `--base` and `--package`, the extracted P4521
inputs as `--inputs`, and `build-package/sd-card/Custom/carplay_mu1367_lanes`
as `--payload`; see `MU1367/lanes/test-controls.py --help`.

No extracted OEM firmware is committed or included in the release. Existing
v1.4.0 runtime test evidence is retained with its original firmware identity;
new P4521 installer and recovery results are recorded separately.
