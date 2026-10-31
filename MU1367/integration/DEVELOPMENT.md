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
not import successive experiment staging scripts. IDs intentionally remain
`MU1367-guidance-31dfc8d5a6f2` and `MU1367-artwork-55008dbaf18e`, preserving the
validated runtime bytes. Release controller IDs and `MU1367_RELEASE_MANIFEST.json`
identify v1.4.1 packaging separately.

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
