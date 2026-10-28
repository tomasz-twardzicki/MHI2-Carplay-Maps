# A0: N0 audio input works; no artwork callback observed

The user followed the N0 procedure with **Apple Music and Spotify** and
reports no status errors or impact on other services. The seven exports in
the private `Logs/A0` directory match build marker
`MU1427-AUDIO-N0-2676bca31ba1`. The observer installed, loaded on the unit,
received valid track/playback callbacks and detached/attached across the
reported reconnect. This accepts N0's input observation for this run.

**No cover-art callback arrived.** All six runtime snapshots have
`covers=0`, `valid_covers=0`, `cover_urls=0` and `cover_ids=0`. A working DSI
subscription does not establish native artwork delivery on this firmware.
This result does not rule out artwork in the native iAP2 file-transfer path.

## Captured evidence

| Export | Epoch / attached | Tracks / valid | Nonempty title / artist / album | Playback state | Valid positions | Writer count |
| --- | --- | --- | --- | --- | --- | --- |
| 01 | No runtime status yet | — | — | — | — | — |
| 02 | 1 / yes | 7 / 7 | 6 / 6 / 6 | Playing | 160 | 77 |
| 03 | 1 / yes | 7 / 7 | 6 / 6 / 6 | Paused | 206 | 125 |
| 04 | 1 / yes | 8 / 8 | 7 / 7 / 7 | Playing | 267 | 225 |
| 05 | 1 / yes | 8 / 8 | 7 / 7 / 7 | Playing | 405 | 288 |
| 06 | 1 / no | 9 / 9 | 7 / 7 / 7 | Unknown after detach | 459 | 337 |
| 07 | 2 / yes | 3 / 3 | 2 / 2 / 2 | Playing | 39 | 375 |

Do not add counters from every row: each epoch is cumulative. The final
retained counters for epochs 1 and 2 sum to **12 valid track callbacks**,
**9 nonempty title, artist and album fields each**, **10 playback callbacks
(9 valid/known)** and **498 valid position callbacks**. One playback callback
was not valid/known under the observer's flag/null/state checks; that is not
an observer exception. Every reported exception, subscription, clear and
I/O failure counter is zero.

Export 01's missing runtime status is consistent with service initialization
on phone connection. Export 03→04 records paused→playing. Export 06→07
records detach→new epoch. The writer reaches 375 iterations with a nominal
one-second sleep between writes, consistent with operation beyond five
minutes; the exports contain no exact timestamps or route-duration trace.

The user reports following the procedure and no impact on other services.
The snapshots do not independently identify each test step, audio app,
navigation state, source selection or uninstall/reboot outcome. They do not
contain the actual strings, so text accuracy remains a display-test check.
Build markers identify the reported build; no installed-JAR dump was exported
for an independent device-side binary fingerprint.

## Development consequence

Proceed with N1 title/artist/album text using the demonstrated native DSI
input and the factory MQBAB2 `CurrentStationInfo` path. Preserve explicit
invalid/empty clearing, source ownership, pause/resume and reconnect state.
Track metadata must not expire merely because a song produces no text
update for several seconds.

Artwork needs separate native investigation. Inspect how MU1427 receives
and exposes iAP2 artwork before adding a picture producer or assuming a
CarPlay resource locator exists. The user has already demonstrated OEM
cover display from another source on this AID 791.

The original N0 package and its host/factory verification records remain
historical evidence. The review adds no runtime change to that package.
Raw exports stay outside Git; [A0 verification](./A0-VERIFICATION.json)
contains structural counts and individual input hashes only.

Reproduce the structural review from the repository root:

```sh
python3 MU1427/now-playing/review-capture.py "$A0_CAPTURE" \
  --build MU1427-AUDIO-N0-2676bca31ba1 \
  --output /tmp/audio-A0-review.json
```
