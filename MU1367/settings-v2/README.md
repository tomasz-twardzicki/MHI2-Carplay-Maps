# MU1367 / AID 791: native settings integration

This optional layer integrates [omonob's plaintext v2 release](https://github.com/omonob/MHI2-Carplay-Maps/releases/tag/toolbox-plaintext-v2.0.0)
with our [MU1367 guidance/audio integration](../port/README.md). It targets the
exact K4525 MU1367 firmware and **791 cluster only**. Initial user testing is
recorded in [UNIT-RESULTS.md](UNIT-RESULTS.md): 30 fps / IDR5 is the preferred
setting; both 40 fps profiles showed some stutter. This remains a test build.
Host and factory-runtime checks do not establish vehicle safety,
actual frame rate, menu rendering, or compatibility with a particular phone/app.

The complete SD bundle is generated at
`build-package/CarPlay_Maps_VC_MU1367_791_MU_Settings_Test.zip`, with an adjacent
`SHA256SUMS.txt`. The exact tested archive is also committed under
[releases/MU1367](../../releases/MU1367/). The previous integration ZIP and standalone profiles remain
separate. See [installation and recovery](INSTALL.md),
[upstream review](UPSTREAM-REVIEW.md), and [verification](VERIFICATION.json).

Under **App-Connect > Settings > Virtual Cockpit settings** (localized upstream
section name), the native MU page has these six selectors:

| Selector | Behavior |
| --- | --- |
| Maps | Select CarPlay maps or OEM; upstream map-priority policy |
| Mirroring | Upstream CarPlay mirroring, enabled only when its map source is released; other advertised engines are unavailable |
| Wireless CarPlay test | Persisted test interface only; does not add wireless CarPlay |
| Turn card | Live ON/OFF on 791 using upstream single-view scene transitions |
| Map stream (reconnect) | 30 fps / IDR20, 40 fps / IDR5, 30 fps / IDR5, 40 fps / IDR20 |
| Turn-card layout (reconnect) | Existing narrow, existing wide, compact below route bar, upstream compact |

The new stream/layout labels use English fallback. Upstream's existing 31-locale
text and firmware fonts are retained. The OEM MirrorLink entry is preserved.
Factory widget donors are used; successful rendering on the real MU is still
an acceptance test. No native widgets are constructed during the QNX load test.

| Layout | Safe area (x, y, width, height) | Scene request |
| --- | --- | --- |
| Existing narrow (default) | 200, 96, 400, 364 | Existing instrument-cluster URL |
| Existing wide | 160, 96, 480, 364 | Existing instrument-cluster URL |
| Compact, below route bar | 220, 96, 360, 348 | Top aligned, no ETA/speed-limit request |
| Upstream compact | 220, 65, 360, 348 | Top aligned, no ETA/speed-limit request |

The canvas remains **800 x 480**. A safe area is an advertised phone layout,
not a guaranteed final card bounding box. Upstream compact starts above our
native bar's y=96 boundary and may overlap it. Test the below-bar choice first.
With no existing preferences, stream/layout default to **30 fps / IDR20 and
existing narrow**. Selecting 40/5 changes the advertised maximum FPS and the
received-frame IDR request interval; it does not guarantee 40 rendered fps or
that the phone will honor each request. These choices affect the map stream,
not the separate mirroring stream's frame-rate control.

Stream and layout apply when CarPlay reconnects and the display declaration
is negotiated again. No native library is overwritten by a UI selection.
Card ON/OFF retains upstream's live scene-switch behavior. Maps/mirror routing
uses the paired v2 supervisor, bridge, tap, query helper, canvas, and wrapper.

Our MU1367 B4/N3 drivers, guidance/audio/NAI JARs and reader are unchanged.
The upstream generic `CarPlayNavigationPatch.jar` and 790-only
`VCMirrorRate.jar` are not installed. N3 capture remains an optional experiment;
album-art decoding/output is not added by this layer. MU1367/790's prior
experimental package remains separate.

Preferences are stored under `/mnt/icab/persistent/cpmap-ui`. Stream/layout
have their own bounded CRC envelope (`display.state`, `display.previous`) and
do not rewrite upstream map/mirror/card preferences. Both Java and C validate
the same canonical format; corrupt primary data falls back to the previous
copy. If both copies are damaged, the menu refuses an overwrite and the native
core retains the last valid in-process settings (defaults on first startup).
Removal preserves these preferences.

Source is GPL-3.0-or-later, with original attribution in `vendor/`; its exact
upstream file hashes are in `UPSTREAM.json`. The build stages a copy and applies
counted source edits. It compiles against the actual MU1367 factory classes,
patches that firmware's `AbstractViewHandler`, preserves the original steering
key-state implementation and routes its final commands through v2 policy.
All installed Java classes are major 46 for the factory CDC runtime.

Build and test entry points are `build.py`, `test-host.py`, `test-qnx.py`,
`package.py`, `test-controls.py`, and `test-package.py`; use `--help` for inputs.
They use the existing `../port/` firmware extractor, toolchain and factory
test harnesses. Factory firmware/`stock.jar`, JDK8, ASM9.7 and the QNX6.5 SDK
are external inputs, not supplied here. Host ASan/UBSan runs in the native ARM
`cpvc-settings-host-tests` image built with `Dockerfile.tests`; Docker test
runs use `--network=none`. QNX uses the existing local `cpmap-qnx65-sdp` and
`cpmap-qemu-arm` images. Runtime manifests pin artifacts; packaging requires
passing host and factory-runtime results for those exact hashes.
