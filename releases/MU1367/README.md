# MU1367 / AID 791 releases

## v1.4.0 — native lane guidance

[Download the full lane-guidance toolbox ZIP](./v1.4.0/CarPlay_Maps_VC_MU1367_791_Native_Lanes_Test.zip?raw=true)
and verify [SHA256SUMS.txt](./v1.4.0/SHA256SUMS.txt).
[GitHub release](https://github.com/tomasz-twardzicki/MHI2-Carplay-Maps/releases/tag/MU1367-v1.4.0).

Adds native lane order, allowed/best-lane recommendations and branching exits
through the factory cluster renderer. Turn cards default OFF, with the existing
App-Connect ON/OFF control retained. Explicit saved preferences, including
30 fps / IDR5, remain unchanged; select Card OFF once if ON was saved earlier.

For exact K4525 MU1367 + **791** only. Existing v1.3.0 users install **step 4
only**, after refreshing Toolbox menus/scripts, disconnecting the phone and
rebooting. Fresh installs complete steps 1–3 first. Read the
[installation and no-SD rollback guide](../../MU1367/lanes/INSTALL.md).

Build `MU1367-lanes-ac765ddeb391`; ZIP SHA256:
`942c9d2a1b38e7f417f97e1a8806e42559b29565f3605215c92b932d58c1259f`.
The bundle includes all four installation stages and source/build scripts.
[Verification](./v1.4.0/VERIFICATION.json) covers 761 lane assertions,
factory ARM/J9 loading/serialization, Java/C preferences, 19 installer/recovery
tests and a full four-layer OEM restore without SD. The user subsequently
[confirmed successful vehicle operation](../../MU1367/lanes/UNIT-RESULTS.md),
and v1.4.0 is now a regular release. Individual app/route results and an
endurance duration were not supplied. The ZIP and build-time records remain
unchanged; documents inside the ZIP retain their original pre-test wording. The original v1.3.0 payloads are preserved unchanged
inside this bundle; the new runtime is installed only by step 4.

## v1.3.0 — native guidance, audio and MU settings

[Download the tested full toolbox ZIP](./CarPlay_Maps_VC_MU1367_791_MU_Settings_Test.zip?raw=true)
and verify it against [SHA256SUMS.txt](SHA256SUMS.txt).

This is the exact archive tested by the user, preserved without rebuilding:
build `MU1367-settings-v2-2b9533e277a6`, SHA256
`19a136685d1e55d8630bfe38146a75a8b999fad0198a3a0f850f075f631a50b9`.
It includes all three installation stages and the original recovery payloads.
It is specific to K4525 MU1367 and the **791** cluster; the included 790 video
options remain a separate experiment without native guidance/audio integration.

Follow the current [installation and no-SD rollback guide](../../MU1367/settings-v2/INSTALL.md).
The documents inside the unchanged ZIP describe its original pre-test status;
the subsequent [user results](../../MU1367/settings-v2/UNIT-RESULTS.md) are
recorded separately here. Initial operation was reported successful, with
**30 fps / IDR5** preferred over both 40 fps profiles, which showed some stutter.
The initial default remains 30/20: select 30/5 in the native MU settings and
reconnect CarPlay to use the preferred profile.

Included features are described in the [settings overview](../../MU1367/settings-v2/README.md)
and [firmware adapter overview](../../MU1367/port/README.md). Guidance/audio/NAI
are compiled from the exact MU1367 classes. Map/mirror controls use the
paired upstream plaintext v2 runtime, with native selectors for stream cadence
and card layout. Optional N3 capture does not provide cluster cover-art output.

[VERIFICATION.json](VERIFICATION.json) preserves the original build-time
host/factory-QNX/Java/rollback checks; `on_unit_validated=false` in that record
is historical and is not rewritten to turn a user report into a full test
certification. [RESOURCE-VERIFICATION.json](RESOURCE-VERIFICATION.json) records
the later output-failure reproduction and log-limit checks. No extended
vehicle endurance duration or individual acceptance matrix was supplied.

The ZIP includes its source snapshot. Maintained builders and shared source
dependencies are committed under `MU1367/port`, `MU1367/settings-v2`,
`MU1427/route-guidance`, `MU1427/now-playing` and `MU1427/NavActiveIgnore`.
Factory firmware, converted `stock.jar`, private captures and build directories
are external inputs, not repository contents.
