# MU1367 v1.6.5-e-test2

Focused local follow-up to the test1 connection/reconnect capture. Exact K4525/P4521 HW50/HW70 gates and managed recovery remain supported. Vehicle acceptance is pending.

- **BT symbol fix:** resolve native open/write from a named libc.so.3 handle, independently of RTLD_DEFAULT. The captured write-slot address matches the exact firmware libc export; test1 compared it with the wrong lookup authority. Preserve lazy/resolved-slot handling, retries, atomic race protection and refusal of other hooks. Log global/canonical/slot addresses and dladdr object/symbol names. Test2 must still demonstrate BT-off survival on the car.
- **Separate road outputs:** publish the current street through NavSD CurrentPositionInfo (function 19), independently of the next/current/off choice in TurnToInfo (function 20). Both use existing ownership/freshness, clearing, OEM takeover and queue-retry checks. Current remains the dial default. The factory serializer supports independent values; the cluster's choice of consumer field is not established. If it uses TurnToInfo for both labels, this change alone cannot force their visual split.
- **Keep the validated path:** artwork/media, decoder, timing tap, MOST bridge, supervisor and main-screen support JAR remain byte-identical to test1. The user reports seven covers across both sessions on MU and AID. Keep alternate tuning 40/8/150 and native main demand 30 for comparison.

The new recovery root is distinct from test1. The complete installer recognizes test1's exact controller and all previously supported managed versions, preserves snapshots and reboot boundaries, and includes complete OEM restore and combined diagnostics. Road/GPS preferences are layer metadata; select the road mode again after upgrading. Unknown third-party changes are preserved or refused.

**Still open:** pre-acceptance stale-phone paging/last-phone arbitration, the roughly 61-second reconnect, startup/reconnect frame gaps and the MU-only startup freeze. The new BT guard can suppress setup BT activity only after an accepted live session. No stream queue-limit or smoother change is claimed. Wireless-only vehicle GPS still lacks a qualified raw producer/UTC source; keep GPS off.

See [installation and car checks](START_HERE.md), [changes and limits](RELEASE-NOTES.md), [build evidence](BUILD-AND-TEST.md) and [verification](VERIFICATION.json). The sanitized drive review is in research/v165-drive-review. This is a local experimental package, not a public upload.
