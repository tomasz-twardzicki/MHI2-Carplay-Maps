# MU1367 wireless CarPlay development

Current experimental release: [v1.6.6-e, AID 790/791](v166-release/README.md). Use the [published package guide](../../releases/MU1367/v1.6.6-e/START_HERE.md) and [release notes](v166-release/RELEASE-NOTES.md). The 790 profile source is [overlay-v166](overlay-v166/README.md).

The following earlier notes and sealed test directories are retained for evidence and recovery.

> **Current stable release: [v1.6.1](stable/README.md).** [Install/update/OEM restore](stable/START_HERE.md). Stable promotes the vehicle-confirmed test2 runtime with a unified reboot-aware installer and combined diagnostics; earlier experimental evidence remains below.

> **Next vehicle-test candidate: [v1.6.5-e-test2](v165-test2/README.md).** Explicit-libc BT resolution and independent current-road/turn-to fields. [Test/recovery instructions](v165-test2/START_HERE.md). Managed migration/OEM restore and component bench checks pass; physical BT-off survival and cluster field selection require a car test. Artwork and stream binaries retain the test1 bytes that worked on the car.

> **Latest drive review:** [v1.6.5-e-test1 evidence and worklist](research/v165-drive-review/REVIEW.md), [current progress and limits](v165-test2/PROGRESS.md). Startup MOST recovery, pre-acceptance stale-phone paging and wireless-only GPS remain open. Earlier sealed packages remain available.

# MU1367 wireless-native

Native wireless CarPlay integration for MU1367, built over the exact published
v1.5.3 baseline as experimental candidate `v1.6.0-e-test1`.

- [`FEASIBILITY.md`](FEASIBILITY.md) — the November 2026 offline comparison
  against OEM firmware `K4525` and the v1.5.3 release: what the port needs, that
  the HMI side is portable, and the open blockers.
- [`RELEASE-PLAN.md`](RELEASE-PLAN.md) — November 17 V3.1 follow-up: receiver
  licence behavior, baseline corrections, integration work and acceptance tests.
- [`UPSTREAM.json`](UPSTREAM.json) — immutable upstream revision and reviewed
  input hashes for MU1367/791.
- [`RECEIVER-AUDIT.json`](RECEIVER-AUDIT.json) — host audit result; no QNX or
  vehicle execution is claimed by this original, narrow input/licence audit.
- [`FIRMWARE-VERIFICATION.json`](FIRMWARE-VERIFICATION.json) — subsequent direct
  K4525 checks against both firmware variants, Bluetooth signatures, ELF imports,
  HMI contracts and passing QNX configuration/receiver/J9 load checks.
- [`P4521-COMPATIBILITY.json`](P4521-COMPATIBILITY.json) — matching P4521 JXE,
  Bluetooth binaries and production configs for variants 50/70; limited scope.
- [`TEST-PACKAGE.md`](TEST-PACKAGE.md) — test1 scope, installation, vehicle test
  sequence and recovery. Read this before using the generated SD package.
- [`TEST1-VERIFICATION.json`](TEST1-VERIFICATION.json) — sealed local test1 ZIP
  checksum, baseline preservation, 35 rollback + 35 interrupted recovery cases,
  17 session checks and 32 video-input checks with 126 frames. The input check
  ran on a separate fresh boot after correcting the directory/RAM-disk fixture.
- [`collect-wireless.sh`](collect-wireless.sh) — included in the rebuilt SD
  package and exposed by **Wireless-CarPlay-Test → Collect wireless diagnostics
  to SD (no reboot)**. Refresh Toolbox menus/scripts from the new SD; an
  existing wireless installation does not need to be reinstalled for collection.
- [`VEHICLE-30117947.md`](VEHICLE-30117947.md) — follow-up vehicle capture:
  session accepted, listener up, but no alternate display advertised. The exact
  receiver gate now has [eight passing QNX checks](RECEIVER-ALT-GATE.json).
  GEM provides **Enable AID display probe (until reboot)** to confirm activation
  without changing installed files; persistent activation awaits that result.

## Status

The pinned V3.1 payload has now been checked directly against the supplied
K4525 MU1367 firmware (variants 50/70), with passing targeted static and QNX
emulation checks. Its pinned 791 receiver already
omits the startup application-licence call; retained licence strings do not
mean that call still executes. Matched receiver and HMI loading were verified
in QNX. Test1 adds a checked transaction, separate phone-support JAR and a
wireless session predicate in the v1.5.3 supervisor. The DIO wrapper, bridge,
core, MU menu and existing wired/Android Auto payloads retain their published
bytes. The upstream autostart is adapted to preserve the active firewall/NAT
policy. The first snapshot supports removal back to the installed v1.5.3 state.

**This is a connection/video test, not full wireless feature parity.** Wireless
guidance, media text and artwork still need event integration. Enable/remove
controls live in Green Menu; a native settings switch is pending. Actual MFi,
radio, phone, audio/video and vehicle lifecycle acceptance remain untested.
The maintained v1.5.3 source is in the sibling `-aa` worktree; the older
integration in this checkout is not the release baseline.

Generated packages live in ignored `dist/`; each includes its complete checksum
manifest, exact input provenance, factory-QNX transaction/session results and
explicit verification limits. `package.py` refuses to seal a candidate unless
all 35 commit points pass automatic rollback and interrupted-install recovery,
all 17 session checks pass, and the upstream input self-test passes. Those
emulation checks do not establish a working real-phone connection.

## Build and verify

Use the pinned upstream snapshot, published baseline ZIP and baseline source
commit recorded in `src/PROVENANCE.json`. Host prerequisites are Python 3,
Apple CLT clang, the QNX headers/toolchain and the pinned Docker SDK image in
`build.py`. The QNX test harness also requires the firmware-extracted setup
from the prior direct audit and the existing `cpmap-qemu-arm` image.

```sh
python3 MU1367/wireless-native/build.py \
  --baseline-zip /path/to/CarPlay_Maps_VC_MU1367_791_v1.5.3.zip \
  --baseline-source /path/to/v1.5.3-source \
  --upstream-root /path/to/upstream-snapshot \
  --toolchain /path/to/tools/qnx --python /path/to/python \
  --output MU1367/wireless-native/build-candidate

python3 MU1367/wireless-native/tests/test-qnx.py \
  --build MU1367/wireless-native/build-candidate \
  --firmware /path/to/K4525-firmware --setup /path/to/verified-qnx-setup \
  --toolchain /path/to/tools/qnx --h264-fixture /path/to/intro.h264 \
  --output MU1367/wireless-native/build-qnx-candidate

/path/to/python-with-pyelftools MU1367/wireless-native/tests/native-check.py \
  --build MU1367/wireless-native/build-candidate \
  --firmware /path/to/K4525-firmware

python3 MU1367/wireless-native/package.py \
  --build MU1367/wireless-native/build-candidate \
  --qnx-result MU1367/wireless-native/build-qnx-candidate/result.json \
  --archive-result MU1367/wireless-native/build-qnx-archive/result.json \
  --baseline-zip /path/to/CarPlay_Maps_VC_MU1367_791_v1.5.3.zip \
  --output MU1367/wireless-native/dist/v1.6.0-e-test1
```

Before packaging, run the focused archive regression with a prepared transaction
fixture as `--setup`:

```sh
python3 MU1367/wireless-native/tests/archive-qnx.py \
  --build MU1367/wireless-native/build-candidate \
  --setup MU1367/wireless-native/build-qnx-candidate \
  --output MU1367/wireless-native/build-qnx-archive
```

The November 18 package fixes an inherited base-installer archive-name collision:
QNX can reuse a PID after reboot, so `.removed-$$` may already exist. The three
base archive helpers now select an unused numeric suffix while preserving prior
archives; their payload checks are refreshed. This is a script-only patch over
the stable ZIP. OEM/runtime binaries and the wireless transaction are unchanged.
The factory-QNX regression reproduces the old failure and checks repeat naming,
directory/symlink preservation and damaged-snapshot rejection. It does not rerun
the complete base migration.

The native check records `native-check.json` from the supervisor's strong imports
against the factory libc. The packager checks that report against the built
supervisor hash. Build/test
outputs must be new directories. Nothing is uploaded or published by these tools.

Run the host-only audit against an unpacked upstream snapshot at the revision
in `UPSTREAM.json` and the published v1.5.3 ZIP:

```sh
python3 MU1367/wireless-native/audit-upstream.py \
  --upstream-root /path/to/upstream-snapshot \
  --baseline-zip /path/to/CarPlay_Maps_VC_MU1367_791_v1.5.3.zip
```

Unknown inputs fail the audit. It reads payloads without executing or modifying
them. The pins cover the receiver review, not every file needed for a release.

## What is not in Git

Firmware bytes, extracted OEM files, and the converted class archive stay outside
the repository, the same as `MU1367/port`. The `jxe2jar` conversion is pinned at
commit `9eeb45bbf14bf8afe3452c7be96a4d1f0206a286` (see `MU1367/port/README.md`).
