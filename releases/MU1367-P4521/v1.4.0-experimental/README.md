# MU1367-P4521 v1.4.0 experimental / 791

Separate experimental release for `MHI2_ER_VWG13_P4521_MU1367`, based directly
on `MU1367-v1.4.0` (`e502f20286b1140c17e297dffb98537ad445a75f`).

[Download ZIP](./CarPlay_Maps_VC_MU1367_P4521_791_v1.4.0_Experimental.zip?raw=true),
[checksums](./SHA256SUMS.txt), [verification](./VERIFICATION.json),
[installation and recovery](../../../MU1367-P4521/INSTALL.md).

The dedicated P4521 entry point verifies six OEM originals by SHA-256 before
writing. Hardware variants 50/70 match K4525 in every pinned input and runtime;
no OEM size or hash check was relaxed. All 392 original `Custom/` files,
including runtime payloads and transaction controllers, are unchanged.
The P4521 bundle provides a separate SD/repository installation path while
retaining the runtime/recovery paths required by the unchanged binaries.
It is an alternative bundle, not a second simultaneous installation.

Passed: 1,895 archive/installation/rollback checks (including modified OEM
rejection and full four-layer OEM restore without SD), 19 recovery/fault
injection tests, 761 lane assertions, 123 guidance assertions, Card OFF
persistence and Java class-version checks. Factory ARM/J9 evidence is inherited
from v1.4.0 with matching firmware/runtime hashes; it was not rerun because
the Docker test context is unavailable. **P4521 vehicle testing remains pending.**

791 / 12.3-inch only. Includes all four steps, native lanes, audio text,
App-Connect settings, map/mirror and Card OFF defaults. Read the dedicated
P4521 installation guide first; inherited K4525 documents remain historical.

ZIP SHA-256: `50874f22997df6a048ed79eed3d1c9c43ff75a2c4bffbccd8658b7102102fae3`.
