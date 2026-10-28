# MU1367 / 790: display settings and tuning options

Imported from the sibling `mu1367-790-display` checkout for comparison. The
standalone profile in this worktree retains its original 40 fps core. Use
`MU1367/port/build-display.py` to generate all variants in an isolated output
directory; the integration package carries these variants without changing
the published toolbox. The historical builder below writes baseline files
and is retained as a reference, not the integration build command.

> [!NOTE]
> Not yet tested in a car. The settings are carried over from the MU1427/791 in-car tests ([`../../../MU1427/791_AID12.3/tuning/`](../../../MU1427/791_AID12.3/tuning/)) and scaled to the 790 stream. If the turn card is missing, blank or covered, switch options from the toolbox menu and collect diagnostics.

The MU1367/790 `core.so` is the stock 790 build plus the settings below ([`patch-core-tuning.py`](./patch-core-tuning.py)). The stock 790 build (sha256 `a4bb6ce6…`) is shared byte for byte by MU1102/790, MU1367/790 and MU1440/790. Only the MU1367 profile is changed here.

The 790 `core.so` is not the 791 build with different constants. It is a separate build: no knob HID device, and every offset is different. The 791 patches (and the MU1427 AES fix) don't apply to it as they are.

## Cluster stream geometry

What the 790 `core.so` advertises to the iPhone for the cluster display (type 111), compared with 791:

| | 790 (AID 10.25") | 791 (AID 12.3") |
| --- | --- | --- |
| Stream (`widthPixels` × `heightPixels`) | **1010 × 376** | 800 × 480 |
| Aspect ratio | 2.69 : 1 | 1.67 : 1 |
| `widthPhysical` × `heightPhysical` | 202 × 75 mm | 160 × 96 mm |
| Density | 5 px/mm | 5 px/mm |
| `initialViewArea` | 0,0,1010,376 | 0,0,800,480 |
| Stock `safeArea` (x,y,w,h) | 202,16,606,344 (x 202–808, y 16–360) | 160,20,480,440 |
| Stock `maxFPS` | 40 | 40 |

- The 1010 × 376 stream is fixed: `passive_listener_thread` compares the negotiated stream width with 1010 (`movw r3, #0x3f2` at `0x369c`; the 791 build compares with 800). Only the safe area, frame rate, keyframe interval and cluster URL are changed.
- The physical size is stream geometry, not the panel's size. Both builds use 5 px/mm, so the iPhone should lay out the card at the same pixel scale on both clusters.
- The panel's native resolution is not in `core.so` or the bridge. The bridge, supervisor, jar and installer are identical between the 790 and 791 profiles; only `core.so` differs.

## Options

| Option | Shipped as | maxFPS | Forced keyframe every | Cluster content | Safe area (x,y,w,h) | sha256 |
| --- | --- | --- | --- | --- | --- | --- |
| `default` | profile payload; toolbox "Default" | 30 | 20 frames | map + turn card | 253,16,504,360 | `a9bfe34f…` |
| `wide-card` | toolbox "Map + wide turn card" | 30 | 20 frames | map + turn card | 202,16,606,360 | `a4fe197e…` |
| `low-card` | toolbox "790 only: map + lowered turn card" | 30 | 20 frames | map + turn card | 253,48,504,328 | `ceea20c5…` |
| `no-card` | toolbox "Map only, no turn card" | 30 | 20 frames | map | 202,16,606,344 | `7486c65e…` |
| `stock-40fps` | toolbox "790 only: original core" | 40 | 20 frames | map | 202,16,606,344 | `a4bb6ce6…` |

How the safe areas were chosen:
- **Horizontal.** The stock safe area is centred (x 202–808). `default` halves the width like the 791 default (400 of 800 → 504 of 1010) and keeps the centre at x = 505, so the map centre doesn't move. `wide-card` keeps the stock width.
- **Height.** On 791, shrinking the safe area hid the card: 380 px high worked, 312 gave a blank card, 240 gave none. The 790 stream is only 376 high, and its stock safe area (344) sits between those results. `default` and `wide-card` therefore keep the stock top and extend the bottom to the frame edge (360 high).
- **Clock bar.** On 791 the clock bar covered the card's first line at y = 20, and y = 80 fixed it. Whether the 790 cockpit covers the top of the stream is unknown. `low-card` moves the top down to y = 48 and keeps the bottom at the frame edge (328 high). It may show a blank card for the reason above.
- `stock-40fps` is the unmodified core, as a fallback while the options are untested.

## Patch sites

All values are written as `movw rX, #imm16`, so any value from 0 to 65535 is accepted. The 791 script has to use ARM rotated immediates instead.

- **maxFPS:** `0x257c` in `AirPlayCopyServerInfo`.
- **Forced keyframe:** `0x3b6c` (the check) and `0x3d28` (the log value) in `passive_listener_thread`. The stock interval is already 20, so no option changes it.
- **Cluster content:** the 32-byte string at `0x78c0`, used as `initialURL` and in the `showUI` command from `delayed_alt_activation_thread`. Same URLs as on 791.
- **Safe area:** `create_area()` in `AirPlayCopyServerInfo`: x at `0x26b0`, y at `0x26a0`, w at `0x26a4`, h at `0x26a8`, inside the 1010 × 376 view area.

`passive_listener_thread` and `delayed_alt_activation_thread` are the same code as in the 791 build, moved by −0x804, apart from the width check above.

## Rebuild

- **All files:** `./build-mu1367-790-cores.sh` rebuilds every MU1367/790 `core.so` from the stock 790 build (taken from the unchanged MU1102/790 profile): the profile payload, the toolbox payload and the toolbox options. `--check` verifies the committed files without writing.
- **A single variant:** `python3 patch-core-tuning.py [--max-fps N] [--keyframe-interval N] [--cluster-content map|map-card] [--safe-area X,Y,W,H] in.so out.so`. The input must be the stock 790 build (`a4bb6ce6…`); the script refuses any other file.

## Toolbox menu

The options are on the SD card under `Custom/carplay_maps_vc/tuning/MU1367/790/<option>/core.so`. They are switched from the same menu as MU1427/791 (**Customization > carplay-maps-vc > carplay-maps-vc-tuning**), then reboot. `cpmap_tune.sh` accepts the MU1367/790 and MU1427/791 profiles. The two "790 only" entries fail with `VARIANT_NOT_ON_SD_…` on 791 and change nothing.

## What to check in the car

1. Install 790 (the default option), reboot, start a route in Apple Maps.
2. Is the card shown at all, and is its first line covered at the top? If it is covered, try `low-card`. If it is missing or blank, try `wide-card`.
3. Is the stream smooth at 30 fps? The bridge log (`/ramdisk/altscreen-most-bridge.log`) should show no slow MOST writes or latency resets.
4. Collect diagnostics to SD before each reboot, and take a photo of the cockpit to work out which stream rows are visible.
