# v1.6.3-e-test2 vehicle review — 2026-11-20

Three exports from one boot: cold wireless connection plus two reconnects,40/8/150. All fingerprints match the sealed test2 package (SHA25616d7b9f268bb4629a9836df1af9a09056be42aeab98bb3f0b74db25de7da4dba). Receiver PID2089072/nonce620417200 remain constant, accepted RG sessions2/4/6 and HMI source epochs1/2/3 advance. The supplied captures are read-only inputs. The maintainer subsequently confirmed that both reconnects were triggered by toggling Wi-Fi on the iPhone; this is a Wi-Fi-loss/rejoin test, not an isolated BT-only disconnect test.

## Close the confirmed fixes

- User reports timing7039/0,2197/1,1357/0 matches/misses, IDR approximately1:8 for each session, and reverse return on both reverses. Timing/IDR survive reconnects; do not treat the old dead-timing regression as still open.
- The reverse-return HMI event2910012 is observed. Keep the prior-owner/manual-exit guards.
- User reports no reverse audio stutter. Receiver-audio-102 priority10→14 is observed; native60 is preserved where already higher.
- Receiver-alt is already60 and stays60. **Remove raising receiver-alt priority from the open worklist.** Retain the harmless floor that preserves60; do not lower it to14.
- User reports pts_clamps=0 and pts_rebases=20 through zoom activity, and PF readiness before discovery. These checks passed in this boot; the rebase count alone is not a visible-delay measurement.

## Session2 degradation

Receiver end statistics in the final export show session1 RTT0/109/13ms and session2 RTT0/605/123ms min/max/average. User-reported median rates are main2339→444kbit/s and alt1758→738kbit/s, with session2 about14fps main/19fps alt. A reconnect clears the reported degradation. Both displays are affected, upstream of the AID smoothing bridge. These captures support a degraded transport/phone encoding session; they do not establish BT paging as its sole cause.

The BT log repeatedly attempts the absent paired devices after the phone's RFCOMM close. It also records resend1/2, the667→333 transmit chunk fallback, and a refused open. These are event-order observations: the BT log has no usable monotonic timestamp on each event, so do not invent exact overlap with RTT spikes. A delete-old-pairings A/B test is useful; keep40/8/150 and capture both starts and reconnects. Wi-Fi RSSI, PHY rate, retries, loss and channel-busy counters are not supplied by the current network export.

## Reconnect trigger clarification

Both reconnects were initiated by toggling iPhone Wi-Fi. Genuine Wi-Fi transport loss is a valid reason to end the old CarPlay session. The observed `WC bye` therefore cannot by itself be classified as an erroneous teardown of an otherwise healthy Wi-Fi session. The untimestamped BT log also does not prove which RFCOMM close followed which user action.

Keep two cases separate: BT-only RFCOMM loss while a validated accepted Wi-Fi session remains live should preserve CarPlay; actual Wi-Fi loss should retire the old owner and permit reconnect. On Wi-Fi return, association may precede acceptance, so suppress duplicate starts only for a bounded connection attempt and retain fallback if acceptance fails. Degraded session2 still followed a genuine Wi-Fi reconnect; session3 recovered after another Wi-Fi toggle. This confirmation narrows the tested reconnect path and does not establish BT paging as the cause of the degraded session.

## Subsequent BT-only test and implemented guard

The maintainer then tested Bluetooth and Wi-Fi loss independently, in both orders. BT-only loss also ended CarPlay and logged WC bye while Wi-Fi remained healthy. This resolves the earlier ambiguity: the BT-only teardown fault is separately confirmed; genuine Wi-Fi-loss teardown is still expected.

The follow-up now implements a private exact-add-on GOT extension for its open/write probes, activated only through the checked BT wrapper. It accepts an advancing receiver/session heartbeat only with the existing live owner/grant/PID contract and no wired takeover. The addon-only guards preserve the live session on BT close, pause outbound RC checks and guard accepted-session resend probes. No global file interposition, release marker, crash latch or reconnect-preference change is made. Inactive or expired ownership returns the original behavior. AirPlay/control-close/keepalive remains the teardown authority.

The QNX fixture executes native BT-close/RC/resend decision code with explicit constructor/radio/control boundaries stubbed. It reproduces the original bye before a valid lease and preserves the session after lease acceptance. This is bench evidence, not a physical Bluetooth/AirPlay timeout result. Test3 packaging/recovery checks are tracked in v163-next/PROGRESS.md.

## Artwork: separate three different gates

| Export / session | Attempts / fetches / worker errors | Current native UID / generation | Current cover | Saved JPEG envelope |
| --- | --- | --- | --- | --- |
|21598302 /2 |1 /1 /1 |0 /10, known12 |0 bytes |generation7, valid nonzero UID |
|25096290 /4 |3 /3 /2 |nonzero /3, known13 |116087 bytes |same generation/UID |
|28536926 /6 |4 /4 /3 |0 /6, known12 |0 bytes |generation5, valid nonzero UID |

Media delivery is fixed: final TextBridge tracks29/covers47 and WCPMEDIA2 delivered counters agree. `delivered_covers` counts locator notifications, including clear/null notifications; it does not mean47 decoded images. Native cover_copied8 likewise does not establish that the latest track has an image.

Sessions1/3 end with no current UID/cover. Reusing the previous JPEG would show artwork for another track generation. The current parser intentionally clears metadata identity for a title change without a supplied UID; artist/album changes can also advance its generation. Existing logs show successive artist/album updates, including a Lossless annotation. The current capture lacks the complete per-track raw metadata/FT timeline needed to distinguish legitimate track changes, partial metadata and late/missing cover transfers. Do not retain an old UID/image across a changed track just to increase fetch counts.

The worker error counter is cumulative and rises1,2,3 across sessions. It does **not** establish an exception after nearly every decode. The old catch discards the exception, so its class/message and phase are unknown. A demonstrable code issue is the inactive-wireless fallback to wired PPS: while USB is absent, an expired wireless lease/reconnect can try opening a nonexistent wired PPS file and enter that catch. This has been corrected in the isolated follow-up tree. It is not proof that every reported worker error has this cause.

## Implemented first follow-up batch

`v163-next` now also contains the BT guard and test3 package preparation. The artwork batch adds:

- Bounded `/ramdisk/cpmap-artwork.log` plus `.1`, exception class/message, operation phase, timestamp and error sequence.
- Gate transitions with source/live/epoch/connected, keep/text-match, USB/wireless ownership, generation, UID-known/nonzero, art/cover and model revision. Track text and image bytes are excluded from these new logs.
- Decode acceptance/rejection details and useful last-error/gate fields in the existing artwork status.
- No wired PPS fallback when USB is absent. Existing wired metadata handling remains available when USB owns the source.
- Collection of both trace files in combined and standalone wireless exports.

Host parser/decoder/media tests and factory ARM J9 pass, including normal/strict verification, native JPEG decode, actual skip/reconnect decode, a deliberately injected metadata exception and original wired regressions. This instrumentation does not claim to repair missing phone metadata/cover transfers or all artwork failures.

## Remaining work order before another SD package

1. **BT/Wi-Fi ownership policy:** the scoped guard and native decision-path tests are implemented; finish package gates and vehicle acceptance, including in-flight/radio behavior. See BT-POLICY.md. Do not repurpose crash latches or pretend the BT profiles were released. Preserve initial Bluetooth pairing, explicit disconnect, wired takeover, calls and resume on actual wireless loss.
2. **Artwork identity/FT timeline:** correlate each title/artist/album/UID/art change with FT declaration/completion and HMI gates. Add bounded field-presence/identity-transition diagnostics if needed. Keep the stale-image guards. The next car capture must establish the actual exception class and blocked gate per track.
3. **Link and audio timing:** audit read-only Wi-Fi counter commands against exact K4525/P4521 firmware, then collect association/RSSI/rate/retry/loss with monotonic timestamps. Add accessible SDK jitter and button→phone-command→new-audio timing; do not force an unverified flush.
4. **Package integration:** use a new recovery generation recognizing test2, integrate any BT payload and artwork collector, rerun migration/OEM/interruption gates and seal. The previous test2 ZIP/source evidence remain unchanged.
