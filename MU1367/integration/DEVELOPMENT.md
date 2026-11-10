# Source, builds and validation

Current MU1367 development lives here. The older `port`, `settings-v2` and
`lanes` trees retain the published baseline recipes and evidence; previously
shared experimental ZIPs are not rewritten. No step-5/6/7/8 or v3 patch-chain
builder is needed to assemble the current release.

## Layout

- `src/guidance`: canonical route/lane/current-road model, factory bridge,
  progress logic, bounded feed recovery and diagnostic evidence writer.
- `src/audio`: canonical text/identity-bound artwork bridge and bounded cache.
- `src/runtime`: complete normal-aligned map-only core, MU menu and common
  map/mirror runtime sources. `src/card-tuning` contains only the five source
  overrides for optional card support; no duplicate source tree is maintained.
- `src/artwork-native`: supervised fetch/decoder and artwork/identity hooks.
- `tools`: explicit factory patchers, snapshot transaction generator, release
  orchestration and exact legacy controller identities. `migrate.sh` implements
  the checked removal/reboot boundary for known active v3 revisions.
- `toolbox`: pinned complete distribution inputs and internal compatibility
  transactions. These retain the original baseline fingerprints/backup formats;
  they are not exposed as feature-test steps. `toolbox-inputs.json` pins every
  input. `package.py` generates release/tuning transactions and one full-payload
  preflight before writes. Recovery controllers stay on-unit without the SD.
- `tests`: host factory/model regressions, native sanitizer/settings parity,
  filesystem fault/migration tests and real factory-shell QNX tests.
- `evidence`: preceding exact-runtime factory/J9 and reset fault proofs, plus
  adapter firmware/reference analysis. `VERIFICATION.json` identifies which
  proofs cover unchanged bytes and which checks ran on this release package.

The same shared lock, staged replacements, exact firmware/parent gates and
whole-snapshot verification are retained. A failed layer stops the suite; the
suite does not guess a mixed installation or automatically erase lower layers.
Fresh installation internally uses the established transactional baselines.
This preserves compatibility with v1.4.0 backups instead of converting their
formats. There is one user-facing install action, not one unprotected bulk copy.

## Optional artwork test

`src/artwork-test` holds the R3 refresh sources separately from `src/audio` and
`src/artwork-native`, which remain pinned by `RUNTIME.json`. The JAR's pin is
`ARTWORK-R3-RUNTIME.json`. `tools/package-artwork.py` is a post-processor over the
published v1.4.5-e archive: it adds one Tuning layer and leaves every release payload
byte-identical. Build with `tools/build-audio.py` and `tools/build-artwork-native.py`,
test with `tests/test-artwork-native.py`, `test-audio.py`, `test-audio-qnx.py`, then
package and run `test-audio-package-qnx.py` and `test-audio-package.py`. Those tools
need `pyelftools`, the pinned QNX image and the retained R1/R2 test packages.

Later layers' install branches gate on the exact release audio JAR, so they refuse
while this test is active. Promoting it means updating those pins and `RUNTIME.json`.
See [ARTWORK-R3.md](ARTWORK-R3.md).

## Build

`RUNTIME.json` pins the six accepted v1.4.3 runtime payloads (the same
runtime bytes as v1.4.2). This release retains the corresponding v1.4.3
audio sources. The experimental native reader has its separate source and
`READER-RUNTIME.json` identity.

Use JDK 8, ASM 9.7, the matching converted stock JAR and the pinned QNX 6.5
SDK/container environment used by `MU1367/port`. Firmware class hashes are
checked before patching; installed JAR classes target major 46 for factory J9.
The Docker context is `colima-cpmap-rgi`; the SDK image is `cpmap-qnx65-sdp`.
Place outputs in a directory shared with that VM. Host build utilities are not
installed on the unit.

```sh
python3 MU1367/integration/build.py --java-home "$JDK" --stock-jar "$STOCK" \
  --asm-dir "$ASM" --toolchain "$QNX" --output "$BUILD"
python3 MU1367/integration/package.py --runtime "$BUILD" \
  --reader-build "$READER_BUILD" --output "$PACKAGE"
```

`build.py` directly compiles the maintained guidance, artwork, menu and core
sources and requires all six rebuilt outputs to match `RUNTIME.json`. It does
not import successive experiment staging scripts. The v1.4.2 guidance ID is `MU1367-guidance-v1.4.2`; its rebuilt JAR includes the
reviewed U-turn mapping from PR #8. Audio remains `MU1367-artwork-55008dbaf18e`.
The other five runtime payloads retain their v1.4.1 hashes. Release controller
IDs and `MU1367_RELEASE_MANIFEST.json` identify the complete v1.4.3-e package.
Published v1.4.1 controllers and payloads are retained as exact migration fixtures;
updates retire that layer through the same verified removal/reboot boundary as
older v3 tests, preserving original snapshots.

`tools/build-driver.py STOCK_DRIVER OUTPUT` builds the identity-bound artwork
driver using the shared verified firmware normalization and hook assembler
under `MU1367/port` / `MU1427/now-playing/n3`. `tools/build-fetch.py` rebuilds the
supervised artwork worker and checks imports against the real firmware libc.
The latter preserves the existing decoder assertion filename through a compiler
macro-prefix mapping so source relocation does not change validated bytes.
Original video/mirror/controls/OEM payloads remain pinned compatibility inputs;
their published source recipes are retained in this repository.

The SD carries a source link and notices rather than many nested historical
source dumps. To change runtime behavior, update its source, tests and explicit
payload fingerprints together; do not relax factory or saved-snapshot gates.

## Tests

```sh
python3 MU1367/integration/tests/test-guidance.py --build "$BUILD" \
  --java-home "$JDK" --stock-jar "$STOCK" --output "$MODEL_TESTS"
python3 MU1367/integration/tests/test-runtime.py --build "$BUILD" \
  --java-home "$JDK" --stock-jar "$STOCK" --output "$NATIVE_TESTS"
python3 MU1367/integration/tests/test-package.py --package "$PACKAGE" \
  --inputs "$OEM_INPUTS" --verifier "$HOST_VERIFY" --output "$FILESYSTEM_RESULT"
```

`test-actions-qnx.py` uses the matching firmware-extracted commands and libc,
with no SDK-only utility injection. Its small RAM-disk fixture replaces only
the firmware JXE constant and dependent controller hashes; full real firmware
and full SD inventory checks run on the host. Mounts are mocked, not a test of
physical storage remountability or power-loss durability.

No new target shell commands/options are introduced by release migration.
Required commands are checked before writes. Keep diagnostic files bounded;
never add append-only route histories on the unit's small RAM disk.

The U-turn factory-runtime probe can be rerun with:

```sh
python3 MU1367/integration/tests/test-guidance-qnx.py --build "$BUILD" \
  --java-home "$JDK" --stock-jar "$STOCK" --asm-dir "$ASM" \
  --sysroot "$QNX" --j9-setup "$FIRMWARE_J9_SETUP" --output "$J9_TESTS"
```

The setup contains the matching extracted JRE/JXE, factory libc and previously
validated QNX boot fixture. Outputs must be shared with the build VM. The test
checks left/right U-turn bytes through the decoder, actual factory builder and
serializer under both `-noverify` and `-verify`; it also runs the road/arrow probes.
This establishes runtime compatibility and encoding, while vehicle rendering
remains a separate acceptance check.

## P4521 support in v1.4.3

The six runtime outputs retain their exact v1.4.2 hashes, including the guidance
ID `MU1367-guidance-v1.4.2`. Release/controller IDs identify v1.4.3 separately.
`evidence/p4521-factory.json` pins both P4521 hardware variants and their identical
K4525 HMI, driver, configuration, boot and J9/libc inputs. Recheck them with:

```sh
python3 MU1367/integration/tools/verify-p4521.py /path/to/P4521 /tmp/p4521-inputs
```

The main action reports the actual RCC train when available and always retains
the exact JXE gate. A missing RCC train uses the documented shared-hash identity;
an explicit unsupported train is refused. Recognition adds only shell syntax,
`cat` and `awk`, already verified in the matching firmware command inventory.
The older separate P4521 controller chain uses the independent OEM reset and a
full reboot before integrated installation, preserving archived originals.
v1.4.2 base/card transactions are archived as exact migration fixtures alongside
v1.4.1. `test-p4521.py` checks recognition, unsupported identities, unchanged
runtime bytes, installation/tuning and the old experimental reset/update path.

## Experimental v1.4.3-e reader

Further work uses the v1.4.3 source baseline and exact published archive
`62cd0bb55f874e206f37bfc09952da3bee137421b9fdc695c1a2b1419c0543e3`.
`RUNTIME.json` retains all six v1.4.3 runtime pins; `READER-RUNTIME.json` separately
pins the experimental native reader. The normal main transaction snapshots and
restores `reader` alongside core/menu/guidance/parent. Optional tuning therefore
uses the same ownership/removal chain without an extra reader layer.

Build the reader with `tools/build-reader.py`, using a verified QNX/factory-libc
setup; run `tests/test-reader.py` against the v1.4.3 guidance JAR and
`tests/test-reader-qnx.py` with matching firmware libc/pipe. Package with
`package.py --runtime BASE_RUNTIME --reader-build READER_BUILD --output PACKAGE`.
`BASE_RUNTIME` may contain the six exact payloads extracted from the verified
published v1.4.3 ZIP; the builder checks each against `RUNTIME.json`.

Release validation includes full host transactions, all v1.4.3 migration variants,
P4521 identity/install/reset checks and factory-shell QNX transactions. Tests
mock mounts and do not establish vehicle endurance or power-loss durability.
The earlier v1.4.1-only standalone reader test is historical; this experimental
release uses the integrated builder above.

## Stable v1.4.6

Built from v1.4.6-e (verified package `a33c03d4…`, published ZIP `d38a53b3…`).

- `display_settings.h` (base and tuning) and `DisplaySettings.DEFAULT_STREAM` use stream
  value 6, 27 fps / IDR 5, when nothing is saved. Stored values keep their meaning.
  Guidance, audio and reader are byte-identical to v1.4.6-e (`verify.py` pins them).
- Compressed artwork is built into the package: `package.py --artwork-png-build
  --artwork-png-host` calls `tools/package-artwork-png.py:add_layer`. The suite install
  runs that layer after the main layer unless its state is `removed` (user opt-out);
  uninstall/recover and the menu OEM reset remove it first; an install archives a layer
  left `installed` without its helper (OEM reset run outside the menu).
- v1.4.6-e controllers are migration fixtures (`tests/revisions/release-v1.4.6-e`).
- The test fixture needs the factory `proc/boot/libz.so.2` in its inputs.

## Experimental v1.4.6-e U-turn side, Apple names, streams and artwork

Based on the published v1.4.5 archive
`80e38ec252a8bf84af628e450af80e6a992319315aa8e4be4c66837fb61f4826`. The guidance JAR
(`MU1367-guidance-v1.4.6-e`) and both base and tuning `core.so` and `VCMenu.jar` change;
the audio JAR and reader match v1.4.5.

- `LaneData` marks lanes and branches decoded from exactly ±180° as unsided (byte 114).
  `LiveModel.frame()` resolves them with `forSide()` from the current maneuver's
  driving side (`0x5202` key 8: 0 right-hand, 1 left-hand traffic), else the last one
  seen. `map()` applies the same rule to an exact ±180° U-turn angle. `TestUturnSide`.
- `LiveModel.sameSource()` merges source names containing the word "Apple";
  `GuidanceEvidence` reports clears by cause and the first/latest name flips.
  `TestSourceName`.
- Stored stream values keep their meaning: 0 and 3 (former IDR 20) now use IDR 5, 4 is
  25 fps and the default, 5 is 20 fps and 6 is 27 fps. `DisplaySettings` maps menu
  positions 20/25/27/30/40 to values 5/4/6/2/1.
- `src/artwork-png` is the release `fetch.c` with the R3 lossless zlib writer; build it
  with `tools/build-artwork-png.py` (needs `pyelftools` and the K4525 firmware image) and
  test with `tests/test-artwork-png-native.py`. After `package.py` and `verify.py`,
  `tools/package-artwork-png.py` adds the optional Tuning layer and the final archive is
  checked again with `tests/test-artwork-png-qnx.py`, the host suites and the
  firmware-shell actions. The pinned base `src/artwork-native` is unchanged.
- v1.4.5 controllers/payloads are archived under `tests/revisions/release-v1.4.5-e` and
  registered in `legacy-revisions.json`.

## Experimental v1.4.5-e reroute handling and stream option

Based on the published v1.4.4 archive
`264c298ff67ad9bfb4e19793800e1d754942c81c50931b4f5b33caa9e5a2b99f`. The guidance JAR
(`MU1367-guidance-v1.4.5-e`) and both base and tuning `core.so` and `VCMenu.jar` change.
`verify.py` requires the audio JAR and reader to match v1.4.4. The reader keeps its
`MU1367-reader-v1.4.4-e` identity. The reroute analysis is in
`evidence/REROUTE-2026-11-05.md`.

- `LiveModel` treats a transition from guiding to loading or rerouting, with the same
  source and destination, as one episode. Maneuvers and lanes are dropped because the
  new route reuses indexes; counters are held until the first nonzero distance.
- `STOP_GRACE_MS` (1.5 s) makes a stop inside that episode provisional. `RECOVER_MS`
  (20 s) and the reader's STALE record bound the wait.
- `ArrowProgress` keeps the bar on `CALC_ROUTE`; the factory whitelist is unchanged.
- Stream choice 4 is 25 fps / IDR 5 in `DisplaySettings` and `display_settings.h`.
- v1.4.4 controllers/payloads are archived under `tests/revisions/release-v1.4.4-e`,
  named after the byte-identical ZIP's original build, and registered in
  `legacy-revisions.json`.

The input reconstruction and test sequence below still apply.

## Experimental v1.4.4-e guidance and reader

Based on the published v1.4.3-e archive
`3ecb5304c8a9e85c43a01dd532dfc5c920c3e1a866321a7c1d667d750260afa5`. Only the
guidance JAR (`MU1367-guidance-v1.4.4-e`) and reader (`MU1367-reader-v1.4.4-e`)
change; `RUNTIME.json` and `READER-RUNTIME.json` pin them, and `verify.py`
requires the other five runtime payloads to match v1.4.3-e. The capture analysis
is in `evidence/APP-GUIDANCE-2026-11-04.md`.

- `LiveModel.HOLD_MS` (180 s) replaces every former 5-second guidance gate.
  The reader's STALE record no longer invalidates the Java model. Producer
  heartbeat (1.5 s), session, explicit-end and OEM gates are unchanged.
- A semantic decode fault rejects that message only; an unreadable route update
  invalidates route state. Envelope/order/overlap faults still fail the snapshot.
- `GuidanceEvidence` writes `guidance-evidence.txt` from the background thread.
- `reader.c` renews its three-attempt budget after `RESTART_WINDOW_MS`
  (600,000 ms) without a fault since the latest replacement, bounded by
  `MAX_TOTAL_RESTARTS` (64). Tests compile the same source with a 1.5 s window.
- v1.4.3-e controllers/payloads are archived under
  `tests/revisions/release-v1.4.3-e` and registered in `legacy-revisions.json`.

macOS temporary-file cleanup had emptied the previous `/private/tmp` JDK, venv
and host QNX sysroot. Reconstruct inputs in an ignored local directory:
JDK 8 (Zulu 8.0.412), ASM 9.7, the converted stock JAR, QNX headers copied from
the pinned `cpmap-qnx65-sdp` image (`93b565ff63ba`), `pyelftools` 0.31, the MU1367
J9 boot fixture (`port/build-qnx-final/j9`), a reader setup with MU1367 factory
libc/pipe, the firmware command set and the host-test OEM inputs/`verify.c`.
Verify unchanged-source rebuilds reproduce the published pins before changing
code: all six v1.4.3-e payloads and reader `b2d8d608…` were reproduced exactly.

```sh
python3 build.py --java-home "$JDK" --stock-jar "$STOCK" --asm-dir "$ASM" --toolchain "$QNX" --output "$RUNTIME"
python3 tools/build-reader.py --setup "$READER_SETUP" --output "$READER"
python3 tests/test-guidance.py --build "$RUNTIME" --java-home "$JDK" --stock-jar "$STOCK" --output "$GUIDANCE"
python3 tests/test-guidance-qnx.py --build "$RUNTIME" --java-home "$JDK" --stock-jar "$STOCK" --asm-dir "$ASM" --sysroot "$QNX" --j9-setup "$J9" --output "$J9_OUT"
python3 tests/test-reader.py --guidance "$RUNTIME/CarPlayMU1367Guidance.jar" --stock "$STOCK" --java "$JDK" --output reader-host.json
python3 tests/test-reader-qnx.py --build "$READER" --setup "$PIPE_SETUP" --reader-setup "$READER_SETUP" --output "$READER_QNX"
python3 package.py --runtime "$RUNTIME" --reader-build "$READER" --output "$PACKAGE"
python3 tests/test-actions-qnx.py --package "$PACKAGE" --reader-setup "$READER_SETUP" --toolchain "$QNX" --firmware "$K4525_FIRMWARE" --firmware-commands "$COMMANDS" --output "$ACTIONS"
```

Run `test-package.py`, `test-release-reader-transaction.py`, `test-p4521.py` and
`test-payload-checks.py` in the disposable Debian/ksh93 container without network,
then `verify.py` with every proof. The factory-J9 guidance run now includes
`TestQuietQnx`; the host programs include `TestQuietHold`.
