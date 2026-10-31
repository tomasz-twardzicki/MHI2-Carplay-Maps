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

- Refine native maneuver symbols and use suitable OEM symbols for the initial
  guidance phase and a Maps instruction with no directional arrow. The current
  guarded straight-ahead fallback is a placeholder, not the final design.
- Display the OEM “recalculating…” state during rerouting; current transitions
  may show compass/blank instead.
- Show the road/intersection name above the native arrow when supplied. The
  existing current-road name in the ETA bar is a separate implemented feature.
- Add and validate Apple Maps and Waze behavior. Current vehicle feedback is
  primarily Google Maps; app/route/adapter delivery can differ.
- Consider custom unused-lane outlines after the OEM rendering path is settled.

## Validation scope

The user has confirmed road names, progressing arrows, placeholders, native
lanes, music text/artwork over cable and wireless, and successful adapter guidance
in subsequent tests. This release consolidates those runtimes with normal map
alignment. It does not claim that every app, route, endurance scenario or adapter
firmware has passed. The newly consolidated package/migration is verified
separately off-unit; physical storage durability and AID rasterization cannot
be established by host/QNX emulation.
