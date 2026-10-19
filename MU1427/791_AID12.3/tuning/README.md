# MU1427 / 791: display settings and tuning options

The MU1427/791 `core.so` is the MU1367/791 build with the AES key fix ([`../patch-core-mu1427.py`](../patch-core-mu1427.py), sha256 `46da2689…`) plus the settings below ([`patch-core-tuning.py`](./patch-core-tuning.py)).

| Option | Shipped as | maxFPS | Forced keyframe every | Cluster content | Safe area (x,y,w,h) | sha256 |
| --- | --- | --- | --- | --- | --- | --- |
| `default` | profile payload; toolbox "Default" | 30 | 20 frames | map + turn card | 200,96,400,364 | `173eac54…` |
| `wide-card` | toolbox "Map + wide turn card" | 30 | 20 frames | map + turn card | 160,96,480,364 | `644fd17a…` |
| `no-card` | toolbox "Map only, no turn card" | 30 | 20 frames | map | 200,80,400,380 | `e8cc5019…` |

For comparison, the AES-fixed build alone has 40 fps, a keyframe every 20 frames, map only, and a safe area of 160,20,480,440.

## Patch sites

- **maxFPS:** `0x2a70` in `AirPlayCopyServerInfo`, advertised to the iPhone for the cluster display (type 111).
- **Forced keyframe:** `0x4370` (the check) and `0x452c` (the log value) in `passive_listener_thread`. `core.so` sends `forceKeyFrame` whenever `frame_count % N == 0`. Bridge-requested IDRs after latency recovery are unaffected.
- **Cluster content:** the 32-byte string at `0x8130`. It is both the cluster display's `initialURL` and the URL in the `showUI` command that `delayed_alt_activation_thread` sends when the stream starts.
  - `map` is `maps:/car/instrumentcluster/map`.
  - `map-card` is `maps:/car/instrumentcluster`, which the iPhone renders as the map with Apple's turn card on it.
  - A third URL, `…/instructioncard` (card only), doesn't fit in place.
  - The URLs come from the DiPlay project's notes ([PR #47](https://github.com/shihabal3amri/DiPlay/pull/47)), not from Apple documentation.
- **Safe area:** `create_area()` in `AirPlayCopyServerInfo`: x at `0x2ba4`, y at `0x2b94`, w at `0x2b98`, h at `0x2b9c`, inside the 800×480 view area.
  - The iPhone lays out the map, the car marker and the turn card inside it. The card hangs from the top-left corner.
  - Values must be ARM rotated immediates: any value from 0 to 255, multiples of 4 up to 1020, and so on. The script refuses anything else.

## Rebuild

- **All files:** `./build-mu1427-cores.sh` rebuilds every MU1427/791 `core.so` from the MU1367/791 build: the profile payload, the toolbox payload and the toolbox options. `--check` verifies the committed files without writing.
- **A single variant:** `python3 patch-core-tuning.py [--max-fps N] [--keyframe-interval N] [--cluster-content map|map-card] [--safe-area X,Y,W,H] in.so out.so`. The input must be the AES-fixed build (`46da2689…`); the script refuses any other file.

## Toolbox menu

The MQB Toolbox ships the options on the SD card under `Custom/carplay_maps_vc/tuning/MU1427/791/<option>/core.so`. Switch in **Customization > carplay-maps-vc > carplay-maps-vc-tuning**, then reboot.

- The entry runs `cpmap_tune.sh`. It works only on an installed MU1427/791 profile.
- On the first swap it backs up the installed core as `/mnt/app/carplaymaps/core.so.pre-tuning`.
- It replaces `core.so` by renaming a new copy over it, never by rewriting it in place, because the running `dio_manager` has it mapped.
- It leaves a `CORE_VARIANT-<name>` marker file. "Show CarPlay Maps VC status" and the diagnostics show the active option.
- "Install 791" always installs `default` and clears the marker.

## Test history (iPhone19,2, iOS build 24A437)

**2026-10-13, stream.**
- 30 fps removed the stutter and lag.
- A keyframe every 120 frames made direction changes appear too late, so it stays at 20.
- Bridge logs at 30 fps showed no slow MOST writes, no latency resets, and 8–11 dropped frames per drive.

**2026-10-13, turn card, original safe area (160,20,480,440).**
- The card hangs from the safe area's top-left corner, and the clock bar covered its first line.
- With the full frame (0,0,800,480), the card sat behind the left dial.
- The photos show the cockpit displays only about frame rows 80–400 (about 2.5 photo px per frame px).

**2026-10-14, position.**
- With the top at y = 120, the card was fully visible but too low.
- At 400 px wide it was narrower than at 480.
- Of y = 80, 88 and 96 with the bottom at 460, y = 80 was chosen.

**2026-10-14, height.** Shrinking the safe area's height does not make the card smaller:
- 312 high (bottom at row 400): a blank card.
- 240 high: no card at all.
- 160 high at 480 wide: no card, and the map centre moved up.

The card's size is decided by the iPhone from the guidance content (start-of-route text, distance, lane guidance, a "then" maneuver). Anchoring it at the top lets extra rows grow down into the map.

Variants used in these tests can be rebuilt with `patch-core-tuning.py`; their toolbox menu entries are in the git history of this directory and of `Toolbox/GEM/carplay-maps-vc-tuning.esd`.

**Final guidance layout:** the safe-area top moves from row 80 to 96 to
clear the native route distance/time bar. The bottom stays at row 460; both
narrow and wide cards retain their existing widths. Map-only keeps its
previous safe area. This 16-pixel shift
needs a visual check with the final installed layout.
