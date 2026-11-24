# Build and validate v1.6.6-e

The combined release uses `v166-release` and `overlay-v166`. Earlier trees and
ZIPs are immutable inputs. `BASELINE.json` pins the stable SD seed, accepted 790
backend, previous wireless candidate and newer OEM-reset module. Build with the
MU1367 firmware extracts, converted stock archive, QNX 6.5 toolchain and Java 8
host tools; host paths are arguments, not on-unit requirements.

The ARM build uses the offline `cpmap-qnx65-sdp` image, pinned to
`sha256:93b565ff63ba51c470c1a1e70a6d16607d36df502dfb20ae63a69911f8529bea`.
The canonical converted stock archive content digest is
`37bb839fb026bd1d5c0cb5066d189bd58bbde93f5d355eac8473809799f10a48`.
Factory JAR classes remain version 46/Foundation 1.1. The exact firmware gates
are in `FACTORY.json`, `GPS-FACTORY.json` and the native source checks.

1. Run `build-components.py --tools TOOLS --base-package STABLE_ZIP --output COMPONENTS`.
   This builds the shared CP/touch merge, guidance, media and native components.
   Run `../overlay-v166/build.py --components COMPONENTS --baseline STABLE_ZIP
   --tools TOOLS --output INPUT_COMPONENTS` to verify the real OEM touch dispatcher.
2. Run `../overlay-v166/media/build.py --upstream UPSTREAM_32_ZIP --tools TOOLS
   --guard-components COMPONENTS --output MEDIA790_COMPONENTS`. Its receiver
   anchors are compared across both receiver binaries. It retains the old
   metadata-parser source under `v162-next/src/native`; it adds no video hooks.
   The launcher implements the shared guard-status and bounded launch-stamp ABI.
3. Use `assemble.py --help` for the explicit prior-package migration inputs.
   Include the real original v1.6.0 test1/v1.6.1-e archives in test fixtures;
   substituting a later test archive is not migration evidence. The assembler
   takes the exact published v1.6.3-e OEM-reset module via `--oem-package`.
4. ZIP the assembler's `sd-card` as an interim input. Use
   `../overlay-v166/package.py --baseline INTERIM_ZIP --baseline-sha256 SHA256
   --tested-overlay TESTED_790_ZIP --components INPUT_COMPONENTS --upstream
   UPSTREAM_32_ZIP --upstream-790-runtime --media790-components
   MEDIA790_COMPONENTS --output COMBINED_BUILD`.
5. Run the component and installation suites listed by
   `record-verification.py`. Current report directories and payload pins are in
   `DEVELOPMENT-VERIFICATION.json`. Each runner exposes its fixture/tool inputs
   through `--help`. `tests/release-host.py` runs real migration/OEM controllers
   across four base layouts. `../overlay-v166/tests/test-profiles.py` exercises
   the combined profile, all 17 child failure/interruption sites, actual tested
   test3 migration and snapshot preservation. Profile groups use one base
   layout; the parent suite independently covers all four.
6. Native tests use the pinned QNX emulator and firmware-extracted utilities.
   Run `tests/transactions.py` for the 45-target parent, six failure/interruption
   keys and real input assertion; `../overlay-v166/tests/test-qnx.py` for profile
   selection/tuning/recovery; `tests/full-flow-qnx.py --oem-only` for the actual
   forward OEM reset. `tests/release-qnx.py` checks orchestration and actual
   combined diagnostics, using explicit child stand-ins. Limit concurrency to
   two VMs. The actual 790 parser/observer test also executes its new launcher
   against the shared BT wrapper and tests hash-drift fallback.
7. Run main `tests/native-audit.py` and profile `tests/native-audit.py` with
   pyelftools against K4525/P4521 HW50/HW70 firmware extracts. An SDK library is
   not evidence of on-unit imports or commands. Collector, tools, GPS and PF
   audits retain their exact firmware command inventory.
8. Run `record-verification.py --build COMBINED_BUILD --components COMPONENTS`,
   then `seal.py --build COMBINED_BUILD --output OUTPUT`. The recorder currently
   names the release's report directories deliberately: a rebuild must rerun
   and bind its own reports rather than silently borrowing a previous seal.
   The seal refuses an existing output, refreshes source/proofs, preserves tested
   installed payloads/controllers, validates all guards and shell syntax, then
   hashes and reads back every ZIP entry. `SHA256SUMS.txt` covers the archive and
   accompanying release documents.

The first release-host run passed six groups before a missing CLI fixture ZIP
caused an error; the corrected run passed the remaining six, and combined
private-export handling was rerun after its last change. These runs remain
distinct in the evidence. The inherited profile host report labels its version
1.6.1; actual v1.6.6-e controller and complete child-manifest hashes identify
the tested inputs.

The 256 MiB SDK transaction fixture exhausted RAM. A narrowly matched SDK
virtual-board RAM declaration was increased to 512 MiB for that fixture; all
six rollback/resume pairs then passed. This is not a unit-firmware patch.
The larger full fresh native-stack image could not boot. No full fresh native
pass is claimed: actual full-stack host controllers and separate native parent,
child and OEM transactions provide the recorded coverage. Failed results and
the boot-shutdown log remain in the verification bundle.

Hardware presentation, RF paging/reconnect latency, microphone/call routing,
NavSD consumer field selection and the combined release still need car tests.
Use `START_HERE.md`. GPS remains off without qualified raw GNSS/UTC; no startup
freeze or full ACL release fix is claimed.
