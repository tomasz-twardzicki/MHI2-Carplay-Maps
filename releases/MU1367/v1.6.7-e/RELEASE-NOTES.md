# MU1367 v1.6.7-e

Experimental prerelease: recover the **v1.6.5-e-test2** runtime and add optional **AID 790** support without the shared changes introduced in withdrawn v1.6.6-e.

- Exact test2 parent runtime, input JARs, media, BT guard and installed recovery paths on both profiles. Existing tested 791 wireless timing, IDR, audio, reverse return and artwork behavior is retained.
- Optional reversible 790 layer uses the tested overlay790 test3 video/metadata backend. Its launcher implements only test2 wrapper compatibility. Its wireless map and turn-card safe areas are aligned at `202,16,606,344`; map-only URL and fresh card-Off defaults are retained.
- SD-only migration restores recognized v166 child and parent layers in order, retaining snapshots and enforcing a full reboot between stages. Existing test2 migration from v1.5.3/v1.5.4 and stable v1.6.1 remains available.
- Complete managed OEM restoration retains test2's algorithm and payloads, with added archive coverage for new/retired receipts. Base and standalone wireless diagnostics include the optional 790 layer and input evidence.
- GPS remains disabled by default. The raw GNSS/UTC provider audit and source-core work are recorded separately; the standalone ASI listener is not implemented or installed.

**Excluded:** v166 merged OEM touch/call changes, newer Bluetooth profile-release/Keep controls, trusted/last-phone pre-acceptance paging and Wi-Fi-first policy, road-label cache changes and timestamp changes. Original test2 accepted-session BT guard remains on the 791 runtime. Pre-acceptance stale-address paging, MU startup freeze and raw GPS sourcing remain open.

v1.6.6-e was withdrawn after reported Keep/disconnect failures, lag and MU freezes. The cause is unconfirmed. This release restores the earlier runtime rather than claiming a diagnosis of that regression.

Validation covers exact baseline equivalence, actual saved-controller migration from both v166 profiles, all 14 child commit failure/interruption sites, native QNX profile/launcher/OEM recovery, four firmware import profiles, card defaults and read-only diagnostics. Emulator mounts and radio hardware are not exercised. The new 790/test2-input combination and physical call/touch/reconnect behavior still need car acceptance. The SD version is 1.6.7-e; runtime diagnostics deliberately identify test2.

See [START_HERE.md](START_HERE.md) for staged recovery, profile selection and restore limits, and [VERIFICATION.json](VERIFICATION.json) for precise evidence and limitations.
