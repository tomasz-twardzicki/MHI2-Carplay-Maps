# MU1367 target command compatibility

Current development is based on the published v1.4.3 integration, including
P4521 recognition and the v1.4.2 U-turn fix. v1.4.3-e adds experimental reader
recovery to that baseline (vehicle-confirmed); v1.4.4-e builds on v1.4.3-e with
Apple Maps/Waze guidance handling and a renewable reader-recovery budget, published
as stable v1.4.4 with the same ZIP. v1.4.5-e adds reroute handling and a 25 fps option (stable as v1.4.5). v1.4.6-e adds driving-side U-turn lanes, Apple Maps name merging, the 25 fps default and optional compressed artwork. Stable v1.4.6 makes 27 fps / IDR 5 the default and installs compressed artwork by default. v1.5.0-e adds Android Auto as its own layer, installed by the same action (`carplay-mu1367-android-auto`, gal wrapper). Stable v1.5.2 (from vehicle-tested v1.5.2-e) makes 40 fps / IDR 5 the default, drops the P4521 experimental label and adds saved-snapshot list/remove actions (factory `ls`/`awk` only; the unit has no `du` or `rmdir`). Experimental v1.5.3-e embeds a startup clip in the CarPlay bridge (`cpmap_intro_clip.h`, never in the Android Auto build) with an MU UI selector (field 8; replaces the no-op wireless row in tuning) and runs both bridges at priority 14. Stable v1.5.3 is v1.5.3-e plus one bridge fix: after the clip, the ring head is recorded before the IDR request (intro_skip_and_request_idr), so a fast answer is never skipped. Stable v1.5.4 adds the OEM arrival-time setting (guidance ArrivalClock: HMI clock datapool + remaining time) and the Toolbox stream test (stream-test.conf, fps 20-40, IDR 5-15); the firmware has no printf/sleep/tail, so Toolbox shell code must use builtins only. Use the current integration sources and release
manifests for further changes; the v1.4.1-only reader add-on is historical.
Keep both K4525 and P4521 support, exact firmware gates and snapshot recovery.

Before introducing a shell command or a new command option for the unit, verify
it against the actual matching firmware or a captured live-unit availability
check. An SDK installation or an emulator augmented with SDK-only utilities is
not evidence that the unit provides it.

Check required commands before persistent writes. Treat optional diagnostic
commands as optional. Run QNX compatibility tests with firmware-extracted
utilities; do not add unavailable commands to make a test pass. The OEM reset's
`COMMANDS.json`, `audit_commands.py` and read-only `check-tools` action provide
the current command inventory and live check.
