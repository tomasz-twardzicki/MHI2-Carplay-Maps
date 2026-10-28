# MU1367 / AID 791 integration test

This is a separate firmware-matched test package for
`MHI2_ER_VWG13_K4525_1_AIO_MU1367_20230318`, including both MMX `50` and `70`
variants. Subsequent testing of the combined integration/settings bundle is
recorded in [the user results](../settings-v2/UNIT-RESULTS.md); it reports
successful initial operation and a preference for 30 fps / IDR5. The original
build-time evidence below predates that report. Existing
MU1367 standalone profiles and published MU1427 payloads are preserved.

| Feature | Included behavior | MU1367 evidence |
| --- | --- | --- |
| Cluster map and steering controls | Existing video bridge/controls, 30 fps, keyframe every 20 frames | Existing baseline; new display layout needs unit testing |
| Phone turn card | Narrow/wide card and map-only options; original 40 fps core retained | Exact original 791 core with display changes only; AES offset remains `0x1c8` |
| Native guidance | Arrows/maneuver distance on AID/HUD; route distance and remaining travel time on AID | MU1367-derived Java classes; inherited B4 executable code; host and factory-runtime checks |
| CarPlay audio text | Title/artist/album, reconnect clearing and OEM audio-source priority | MU1367-derived target and audio BAP class; maintained N1 model |
| Navigation-active HMI adapter | Firmware-matched rev-3 NavActiveIgnore behavior; no stream-rate override | Five MU1367 factory classes, property IDs 2910009 / 2910005 |
| N3 artwork experiment | Optional owned image extraction and supervised manual JPEG/PNG decode/export | Same executable code as existing N3; **off by default, no cluster cover display** |
| MU1367 / 790 | All five existing experimental display variants | Reproduces sibling checkout exactly; native/audio installer refuses 790 |

Clock-time ETA, native street/lane graphics, Android Auto guidance and cluster
cover-art output were not completed in the earlier work and are not added by
this port. The generic toolbox `NavActiveIgnore.jar` must be removed with its original
uninstaller and a full reboot before this integration. This package rebuilds
that behavior as `CarPlayMU1367NavIgnore.jar` from MU1367 classes, preserving
the factory six-argument CarPlay constructor and Exbox interfaces. It retains
stock stream-rate sequencing and external-box guidance behavior.

## Firmware findings

`FACTORY.json` pins the JXE, converted class contents, thirteen replaced HMI
classes, native driver, accessory configuration and AirPlay library.
`prepare-firmware.py` reads the supplied package without mounting or writing
it and checks both firmware variants. Extracted JXE/classes remain private.

The native driver differs from MU1427 at exactly 20 bytes in non-allocated
`QNX_info` and `.gnu_debuglink`, outside all program segments. `build-driver.py`
checks the complete original hashes and metadata locations, reproduces the
maintained B4/N3 patch chain, restores MU1367's metadata, and checks every
program segment against the reference output. It does not relax any hook
fingerprint or replace firmware identity by a size-only check.

Four guidance classes are identical to MU1427; `ManeuverDescriptor` and
`LaneGuidance` differ. Both audio classes differ. `build-hmi.py` patches the
actual MU1367 converted classes with the maintained assertion-based patchers.
All installed classes target major 46 and the three feature JARs have no
overlapping classes. The navigation-active adapter uses MU1367's actual property IDs 2910009
(CarPlay) and 2910005 (Android Auto), with exact instruction-pattern checks.
The firmware libc also differs, so each native helper's
imports are checked against MU1367's own libc.

The new `iap2.cfg` preserves the MU1367 model, serial, firmware version and
external accessory protocols. Only the guidance `[ident]` section is appended.
Neither the MU1427 configuration nor its AES correction is copied onto MU1367.

## Build

Use fresh output directories. The pinned toolchain/parser commits are the
ones documented under `MU1427/route-guidance`; use JDK 8, ASM 9.7,
Python with pyelftools/Unicorn, liblzo2, `/bin/ksh` and the existing offline
`cpmap-qnx65-sdp` / `cpmap-qemu-arm` Docker images. Set `FW`, `INPUTS`, `JAVA8`,
`PARSER`, `ASM`, `QNX` and `PYTHON` to local paths. `INPUTS` must be outside Git.

```sh
python3 MU1367/port/prepare-firmware.py "$FW" "$INPUTS"
python3 "$PARSER/src/jxe2jar.py" "$INPUTS/lsd.jxe" "$INPUTS/stock.jar" > "$INPUTS/conversion.log"
python3 MU1367/port/build-hmi.py --java-home "$JAVA8" --stock-jar "$INPUTS/stock.jar" --jxe "$INPUTS/lsd.jxe" --asm-dir "$ASM" --output MU1367/port/build-hmi
"$PYTHON" MU1367/port/build-driver.py "$INPUTS/driver" MU1367/port/build-B4.so
"$PYTHON" MU1367/port/build-driver.py --artwork "$INPUTS/driver" MU1367/port/build-N3.so
"$PYTHON" MU1367/port/build-native.py --toolchain "$QNX" --firmware "$FW" --output MU1367/port/build-native
python3 MU1367/port/build-display.py MU1367/port/build-display
"$PYTHON" MU1367/port/test-qnx.py --firmware "$FW" --toolchain "$QNX" --java-home "$JAVA8" --stock-jar "$INPUTS/stock.jar" --hmi MU1367/port/build-hmi --native MU1367/port/build-native --output MU1367/port/build-qnx
python3 MU1367/port/build-package.py --hmi MU1367/port/build-hmi --native MU1367/port/build-native --display MU1367/port/build-display --inputs "$INPUTS" --qnx MU1367/port/build-qnx --b4 MU1367/port/build-B4.so --n3 MU1367/port/build-N3.so --output MU1367/port/build-package
```

The package builder requires passing factory-runtime evidence for the exact
HMI/native artifacts. Generated archives, firmware and temporary builds are
ignored. The standalone baseline directories are not overwritten.

See [installation and recovery](./INSTALL.md). Baseline: omonob (QCDWJ);
MU1427/native guidance and this port: tomasz-twardzicki. Retain LuKa's protocol
and maneuver attribution and GPL-3.0-or-later notices in the shared sources.
