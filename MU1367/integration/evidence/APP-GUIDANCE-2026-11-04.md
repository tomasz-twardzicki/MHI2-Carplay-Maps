# Apple Maps and Waze native guidance — capture analysis, 2026-11-04

Inputs: private diagnostic exports in the user's `Logs/applemaps` folder
(two own Apple Maps tests, one user-supplied Apple Maps export, two Waze exports)
and earlier MU1367/MU1427 exports for comparison. Raw captures stay outside Git.
No export records which app was active; the folders are the only app label.
v1.4.4-e adds the phone's source app name to `guidance-evidence.txt` for this.

## Runtime in the exports

The Apple Maps exports ran older test guidance (`663717fd678b`, lane v2, and
`4cfed248ab4a`); the Waze exports ran `31dfc8d5a6f2` (v3r3), not the v1.4.3
release. The responsible logic is unchanged in v1.4.3 and v1.4.3-e.

## Apple Maps: guidance goes on and off

The bridge's ownership history repeats one pattern: output is taken, then
released about 5 s after the last phone message. Releases use reason 8
(frame older than 5 s) or reason 4 (feed not live after the reader's STALE
record, mailbox kind 3). One test recorded only 23 guidance messages in about
three minutes.

Two 5-second rules caused this:

- The reader writes STALE after 5 s without a new message. The Java mailbox
  reader treated STALE as an invalidation and cleared route state, the maneuver
  cache and lanes.
- The bridge, feed, lane, progress-bar and road-name gates required a message
  younger than 5 s.

Google Maps re-sends about once a second and never reached either limit.
Apple Maps sends deltas and does not resend maneuvers already sent, so after a
reset the route returned with a placeholder arrow and no lanes until the next
maneuver ("only some features").

## Waze: no native guidance

| Export | Reader polls (100 ms) | Guidance messages | Feed errors | Proposals |
| --- | ---: | ---: | ---: | ---: |
| Waze 1 | 4,128 | 2 | 10 | 0 |
| Waze 2 | 4,406 | 3 | 15 | 0 |
| Other MU1367 exports (primarily Google Maps, not app-labelled) | 1,384–22,447 | 124–2,684 | 0–18 | 72–2,372 |

Waze delivered almost no iAP2 guidance. Both Waze exports also retain the same
first failure: `message=20993` (RouteGuidanceUpdate) `field=1`, `sequence=1`.
**Every** MU1367 export with `failure-first.txt` (ten, including sessions where
guidance worked) shows this identical first-message fault. The decoder
validated the 16-message window as one unit, so this message blocked every
snapshot until 16 newer messages pushed it out. Google recovered within seconds;
Waze never sent 16 messages, so even valid Waze messages were discarded.

MU1427 raw journals show the first message as `{components=[0x10], state=0}`,
which decodes; the exact MU1367 first-message shape is unconfirmed. v1.4.4-e
records rejected shapes (keys, sizes and component/state values only).

Whether Waze's 2–3 messages contained an active route cannot be determined from
these exports: the retained mailbox held only the stale header. If v1.4.4-e
evidence shows no active route or maneuvers from Waze, cluster guidance for
Waze is not possible through the iAP2 route-guidance path.

## Video comparison

Across 40 captured video logs, the phone delivered about 17–19 fps with
`maxFPS` 30 regardless of IDR interval; two `maxFPS` 40 captures reached about
27 fps. Each forced keyframe is followed by an 80–130 ms frame gap against
about 50 ms normally. The MOST bridge showed no sustained drops or queue growth
in the Apple Maps captures. An earlier MU1427 Waze capture peaked at 11.8 Mbit/s
encoded input against a fixed 12.2 Mbit/s output. The user later reported Waze
at 30 fps / IDR 5 as only slightly laggier than Google Maps. No video change is
made; a 30 fps / IDR 20 comparison is the next low-cost check.

## Changes in v1.4.4-e

- STALE no longer resets the model; the active route is held for at most
  `HOLD_MS` = 180,000 ms of complete phone silence, with the existing 1.5 s
  producer heartbeat, session, OEM-priority and explicit-end gates unchanged.
- A semantically invalid message is rejected alone; an unreadable route update
  clears route state. Envelope, ordering and overlap failures still reject the
  snapshot and use feed recovery.
- `guidance-evidence.txt` (≤ 4 KiB) adds message counts, route states,
  maneuver types, component IDs, gap statistics, rejection shapes and source
  app names.
