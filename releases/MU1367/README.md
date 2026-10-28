# MU1367 / AID 791: native guidance, audio and MU settings

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
