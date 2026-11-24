# v1.6.7-e rebuild scope

User withdrew v1.6.6-e after lag, MU freezes, inability to disconnect and a broken Keep preference. Rebuild from exact v1.6.5-e-test2 ZIP e9b815eb0be0e1b9cf45564278e15b12ddbe4d0436553a40177e54324882fcae. Publish GitHub prerelease when validated. No shared 791 runtime/JAR rebuild or v166 road/clock/BT-release/paging/touch changes. Reuse test2 installed root/build deliberately so compiled preference paths and every managed payload remain byte-identical.

Add isolated, reversible 790 runtime from exact overlay790 test3 ZIP 202ab34e7339324ca204e6ea64ef754d94a1174f76e9d139c41d59bfc28d3359; retain video/metadata binaries. Only necessary 790 launcher ABI support is rebuilt, pinned to test2 BT guard fd8f39c21bf52253bb1a8d222fee7f850fe39a96b3bf16723f9c96cc698c8acc. 790-specific safe-area/card controls may be retained. Never apply merged input JARs globally.

User confirmed: keep test2 input on both profiles; publish baseline/790 first with GPS disabled. Publication is authorized.

GPS service audit/source core is in ../gps-provider, no ASI client yet. Do not claim functioning GPS merely by including source. Published v166 sealed sources/ZIP remain immutable. Existing unrelated MU1427 and PROJECT-STATUS work is excluded.

Current: exact test2 extracted build-v167-baseline-r1. New src/receiver_exec790.c adds only guard-status and the launch-stamp helper from v165-test2. build-launcher.py completed build-v167-launcher-r1. Need assemble profile/recovery wrapper, verify exact 791 payload equivalence, migration from actual v166 child+parent, native 790 launcher/wrapper and profile transactions, host all-child failure/interruption, firmware imports, complete OEM recovery/diagnostics/default-Off checks, seal/checksums, commit/push and public prerelease. Existing main branch is release/mu1367-v1.6.6-e at 009344a; create release/mu1367-v1.6.7-e for new work.
