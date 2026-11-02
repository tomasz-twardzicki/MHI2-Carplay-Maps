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

## Build

Use JDK 8, ASM 9.7, the matching converted stock JAR and the pinned QNX 6.5
SDK/container environment used by `MU1367/port`. Firmware class hashes are
checked before patching; installed JAR classes target major 46 for factory J9.
The Docker context is `colima-cpmap-rgi`; the SDK image is `cpmap-qnx65-sdp`.
Place outputs in a directory shared with that VM. Host build utilities are not
installed on the unit.

```sh
python3 MU1367/integration/build.py --java-home "$JDK" --stock-jar "$STOCK" \
  --asm-dir "$ASM" --toolchain "$QNX" --output "$BUILD"
python3 MU1367/integration/package.py --runtime "$BUILD" --output "$PACKAGE"
```

`build.py` directly compiles the maintained guidance, artwork, menu and core
sources and requires all six rebuilt outputs to match `RUNTIME.json`. It does
not import successive experiment staging scripts. The v1.4.2 guidance ID is `MU1367-guidance-v1.4.2`; its rebuilt JAR includes the
reviewed U-turn mapping from PR #8. Audio remains `MU1367-artwork-55008dbaf18e`.
The other five runtime payloads retain their v1.4.1 hashes. Release controller
IDs and `MU1367_RELEASE_MANIFEST.json` identify the complete v1.4.3 package.
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
