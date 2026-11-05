# Known issues and planned work

## Ottocast Mini Pico turn card

The base requests a map-only scene with ETA/card/speed-limit overlays disabled.
Cable behavior follows this request. The Mini Pico may continue displaying its
own turn card, and the MU card setting does not reliably control it.

Offline analysis of the supplied **Mini** firmware found a show-UI handler that
substitutes a fixed `maps:/car/instrumentcluster` URL, plus a separate request-UI
handler that ignores the incoming URL. This is the leading explanation for the
Pico result; the supplied image is a different model/build, so the precise Pico
implementation remains unverified. See `evidence/MINI-FIRMWARE-2026-10-31.md` in
the source tree. No adapter firmware patch is included.

The right-edge safe-area experiment moved part of the card out of view but also
moved the map/car position off-center. v1.4.1 restores the normal safe area. A
safe-area hint does not discard an overlay already encoded into a video frame.
Further suppression work should target the adapter's URL/scene forwarding or a
verified adapter firmware patch rather than compromise the map layout.

## Lane rendering

The user confirmed that blank slots for unused lanes match OEM navigation.
Lane directions/recommendations are retained in the data path and diagnostics,
but drawing outline arrows for every unused lane would require further rendering
work. It is not a missing-data fix or a release acceptance requirement.

## Navigation TODO

- Refine native maneuver symbols for the initial guidance phase. The fallback
  with no maneuver is now the straight DIRECTION_TO_DESTINATION arrow. It cannot
  point at the destination: iAP2 supplies no destination position or bearing.
- v1.4.5-e reroute handling awaits a vehicle check: a reroute (captured as states
  1, 5, 0, 3, 1) shows CALC_ROUTE and holds the distance, bar, road and route totals
  until the phone reports a nonzero distance. That wait is capped at 20 s, or 5 s of
  phone silence, so the calculating text can outlast the phone's real calculation.
  Whether the AID draws the bar on that symbol and how Apple Maps reroutes are both
  unconfirmed.
- Show the road/intersection name above the native arrow when supplied. The
  existing current-road name in the ETA bar is a separate implemented feature.
- Validate Apple Maps and Waze with v1.4.4-e. See the section below.
- Consider custom unused-lane outlines after the OEM rendering path is settled.

## Apple Maps and Waze (v1.4.4-e, to be validated)

Apple Maps sends sparse deltas; v1.4.3-e and earlier reset the route after 5 s
of silence and lost the maneuver until the next one. v1.4.4-e holds the route
for up to 3 minutes of silence. A phone app that stops guiding without sending
a route-end state can therefore leave the last maneuver visible for at most
that time; explicit end, disconnect and OEM navigation still clear immediately.

Captured Waze sessions supplied only 2–3 iAP2 guidance messages in about
7 minutes. v1.4.4-e no longer lets a malformed first message hide them, but if
Waze does not send an active route and maneuvers, native cluster guidance is
not possible for it through this path. `guidance-evidence.txt` will show this.

Video: all captures deliver about 17–19 fps against the requested 30 fps, and
each forced keyframe is followed by an 80–130 ms frame gap. The user reports
Waze as slightly laggier than Google Maps at 30 fps / IDR 5. A 30 fps / IDR 20
comparison has not been made yet. v1.4.5-e adds an optional 25 fps / IDR 5 choice
to compare. Requesting less may not help: two captures requesting 40 fps reached about
27, so the delivered rate may follow the request.

## Validation scope

The user has confirmed road names, progressing arrows, placeholders, native
lanes, music text/artwork over cable and wireless, and successful adapter guidance
in subsequent tests. This release consolidates those runtimes with normal map
alignment. It does not claim that every app, route, endurance scenario or adapter
firmware has passed. The newly consolidated package/migration is verified
separately off-unit; physical storage durability and AID rasterization cannot
be established by host/QNX emulation.

## U-turn lane acceptance

v1.4.2 uses the MU1367 factory U-turn defaults 114 (left) and 146 (right).
The matching firmware constants, decoder, factory builder and serialization
are verified off-unit. PR #8 reports a successful vehicle test on MU1161 +
AID 791; MU1367 vehicle rendering is still awaiting a targeted check. The
reviewed ranges are −180…−170° and 170…179°; exactly +180° selects left
for right-hand traffic. ±169° remains unchanged at 128. This fixes lane
encoding and does not change the main maneuver symbols or Mini Pico card URLs.

## P4521 installation (experimental)

The prior P4521 experimental build was confirmed working in a vehicle by the
user on 2026-11-02. v1.4.3 recognizes P4521 and supplies all current integrated
features, while P4521 installation remains experimental. Acceptance of this
new combined package is distinct from that earlier vehicle result. Use the OEM
reset/reboot path in INSTALL.md when moving from the separate experimental
bundle or dormant upstream menu files; all old layers and snapshots are retained.
