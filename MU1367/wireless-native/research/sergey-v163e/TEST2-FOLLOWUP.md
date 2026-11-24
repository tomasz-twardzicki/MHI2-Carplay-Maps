# Test 2 vehicle result and playback/cellular-call follow-up — 2026-11-23

Private evidence: `Sergey/test2/Log2.rar`, safely extracted outside the repo to
`/tmp/cpmap-sergey-790-test2-20261123`; contains `cpmap-diag-18231391`.
The archive and raw logs are not part of a deliverable.

Sergey confirms that cluster navigation works. The active child receipt is
`MU1367-input-profile-790-77fadbb7bea6`, and the feeder reports 12,241 frames,
69 keys and no rejected input. Touch uses `oem-dsi`, with 15 routed events and
no failures. The map now has vehicle acceptance on this reported setup.

The receiver logs 869 now-playing CSM messages (`0x5001`), while the custom
playback producer files are absent. The HMI consumer reports zero metadata
polls/queued tracks; the artwork worker never receives a wireless cover.
This is the known missing producer in the 790 comparison, not evidence of a
new map or OEM-touch regression. Test 2 intentionally omits the 791 tap.

Of the complete packets recoverable from the diagnostic hex dumps, 112 pass
both iAP2 checksums and the CSM length checks. All 112 parse successfully under
ASan/UBSan with the existing metadata decoder; 110 carry a retained title and
artist, and all carry a playback position. Only counts/checksums are retained
in the replay report, not music text, images or phone identifiers.

For test 3, the exact 790 receiver's metadata dispatch, file-transfer code,
format strings, subscription IDs and transfer-buffer fields were compared with
the previously audited 791 receiver. All eight checked interface regions are
byte-identical. A media-only observer now executes successfully against the
actual 790 parser/file-transfer code on QNX: pre-grant filtering, accepted
metadata, immutable artwork, empty/late artwork, malformed messages and
disconnect clearing pass. Only exact `fprintf`/`memcpy` callers are observed.
No video/send/display-info/cadence/scheduling hooks are introduced.

The current 790 launcher verifies receiver, transport, maps library and observer
before enabling it, preserving the original 790 scope and 30-FPS bootstrap.
The working test-2 map binaries, geometry, input JARs and playback consumer JAR
are retained. The new producer supplies the same existing WNP1/WCA1 protocol.

The call report was corrected during this investigation: it is **regular
cellular calls**, and the calls showing the OEM UI **switch audio to the
iPhone**. The earlier statement that audio/microphone worked is superseded.
This is a routing defect requiring a real call test, not just UI preference.

The supplied session logs `bt audio kept (release is off)` and no CarPlay
telephony audio stream or phone owner other than `n/a`. Music and Siri are
visible. The trace therefore does not establish the failed call's full path
or prove a microphone defect. Do not attribute the unrelated `hs auto skip`
licensing line to HFP: it comes from `WcpHotspot`, the hotspot helper.

The existing adapter has an opt-in matched-phone A2DP/HFP release path.
The matching OEM firmware defines service `3600032` as `ASL_PHONE_DISCONNECT_BT`:
field 0 is the phone MAC, boolean 1 selects media profiles, boolean 2 phone
profiles. The OEM handler filters by that address and requests the selected
services; it is not a global Bluetooth-off operation. The adapter only emits
the request after matching the marker address to its trusted-phone list.

Test 3 exposes this existing preference as an explicit experimental menu action,
defaulting off when no prior flag exists. Its bytes/absence are managed as
mutable, bounded data in the child transaction, preserving the first snapshot.
Unknown data and live-session changes are refused. Selection requires a reboot;
the call test must begin with no call already in progress.

The ARM/J9 contract fixture relocates only three file-path constants, uses the
real adapter method and actual OEM field definitions, supplies synthetic
trusted-device/configuration/persistence/logger state, and observes the emitted
service request. It does not simulate an acknowledged profile disconnect,
telephone audio or a successful in-car call. The adapter's release marker is
written for a request before an ACK; it cannot be treated as proof of handoff.

Next vehicle check: playback title/artist/progress/cover; unchanged map/touch;
optional call handoff followed by incoming cellular calls, speaker route and
microphone verification; export while still connected during/immediately after
a failure. Use the menu's Bluetooth-default action and reboot to revert the
call preference. No blanket phone-UI suppression or forced live-call transfer
is included.
