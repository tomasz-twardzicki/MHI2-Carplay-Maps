# Review of omonob plaintext v2.0.0

Reviewed release: [toolbox-plaintext-v2.0.0](https://github.com/omonob/MHI2-Carplay-Maps/releases/tag/toolbox-plaintext-v2.0.0),
commit `2f5fd58b63b48b807d59c5f79795847fc8c50d05`.
The downloaded `VW_SKODA_ALL_CarPlay_Maps_VC_FULL_MQB_Toolbox_V4-2` supplies
the runtime binaries, checked byte-for-byte against that tag's standalone
MU1367 payload and pinned by SHA256 in `package.py`.

Upstream's 791 core declares 40 fps, requests an IDR every five received
frames, and advertises a 360 x 348 safe area at (220,65). Its scene URL asks
for top-aligned maneuvers with ETA and speed limit hidden. The new menu is an
independent native settings page appended to App-Connect setup; its existing
four rows cover maps, mirroring, wireless testing and turn-card ON/OFF.
Upstream describes its offline checks; this is not recorded vehicle validation.

Our adaptation keeps that UI/policy and paired map/mirror runtime, adds two
selectors for stream and layout, and rebuilds the core from the supplied
source. Defaults preserve our 30/20 narrow configuration. Independent settings
allow comparison of FPS and IDR cadence without replacing core.so from GEM.
One compact option moves y from 65 to 96 to clear the native guidance bar.
Both compact choices use upstream's scene URL. Existing layouts retain our
original scene URL.

The upstream 790 stream is a different 60 fps / IDR180 experiment. Its
`VCMirrorRate.jar` changes the stock mirroring rate request from 10 to 30;
it is not needed for this 791 map-stream adaptation. This port does not
claim to implement 790 menu integration.

The upstream generic navigation patch is not a substitute for the exact
MU1367 NAI adapter prepared in `../port/`. Installing both would duplicate
stock-class overrides. This package keeps our matched NAI and does not copy
the upstream universal installer or that JAR. It also preserves the matched
B4/N3 native drivers, route-guidance/audio JARs and reader.

Mirroring needs more than a UI toggle: the supervisor/bridge and DIO preload
wrapper differ from the old runtime. The layer therefore snapshots and
installs the paired v2 binaries together. `vendor/vc-runtime` contains their
released corresponding source; the wrapper is delivered as shell source.
Each of those binaries is pinned to the original release, not rebuilt or
claimed as newly validated against the real display hardware. The core's
strong imports are checked against factory libc/socket, and its dlopen is
tested under factory QNX. These checks do not exercise proprietary DMDT
rendering, MOST output or the phone encoder.

Map priority prevents simultaneous CarPlay map and CarPlay mirror output;
the UI's confirmation/conflict policy is preserved. AA and CarLife entries
do not install corresponding engines. The wireless selector is explicitly
a test interface with no service actions. A 40 fps declaration and frequent
IDR requests may trade smoothness against bandwidth/load; no measured
improvement or resolution of earlier Waze freezing is asserted.
