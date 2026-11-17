# MU1367 standalone profiles

Exact firmware identity: `/ifs/lsd.jxe` = **55,840,541 bytes**.

**Current stable release: [v1.5.4](../releases/MU1367/v1.5.4/README.md)** — v1.5.3 plus
the OEM arrival-time setting on the AID during CarPlay guidance and a Toolbox stream test
(any map rate from 20 to 40 fps, key frame every 5 to 15 frames); these two are not yet
tested in a car. v1.5.3 (vehicle-tested as v1.5.3-e) added a 4.2 s startup animation on
the AID and a higher video-bridge priority for steadier maps while reversing. Like v1.5.2
it has the steadier CarPlay map (v1.2.2 safe area, larger video-bridge buffer, no map
drop-out after boot), 40 fps / IDR 5 by default, P4521 support and the saved-snapshot
tuning entries. It also installs **Android Auto** on the AID (Google Maps picture and
native VW arrows from an Android phone), which is **not yet fully tested**.

The previous stable release is **[v1.5.3](../releases/MU1367/v1.5.3/README.md)**. See the
[release notes](./integration/RELEASE-NOTES.md) and [install guide](./integration/INSTALL.md).
The complete integration supports K4525 or P4521 MU1367 + AID 791, both tested in vehicles.
It combines maps, native arrows/progress, current road, lanes with corrected VW U-turn
symbols, music metadata/artwork and reconnect recovery. Fresh defaults are 40 fps /
IDR 5, compressed artwork and cards OFF; optional tuning adds card support and its MU controls.

The [single install/update guide](./integration/INSTALL.md) covers OEM, v1.4.0, v1.4.1 and
known later test states, with retained snapshots and a reboot boundary for v3
migration. Diagnostics, tuning and recovery have dedicated submenus. The same
SD includes independent full OEM reset. See [known issues and TODOs](./integration/KNOWN-ISSUES.md)
for the unresolved Mini Pico card override, expected OEM unused-lane blanks and
planned navigation/app improvements.

The `port`, `settings-v2` and `lanes` directories document published v1.3.0/v1.4.0
baselines. Their source and original assets remain for compatibility and recovery;
new development belongs in `integration`. The standalone profiles below are
historical video baselines, not the v1.4.5 complete installation package.

| Cluster | Profile files | Display baseline |
| --- | --- | --- |
| 791 AID 12.3 | [`791_AID12.3`](./791_AID12.3/) | 40 fps, navigation centered |
| 790 AID 10.5 | [`790_AID10.5`](./790_AID10.5/) | 40 fps, non-navigation centered, navigation right |

These directories contain only the CarPlay Maps VC project files. They are not complete MQB or M.I.B. Toolbox distributions.

固件识别条件：`/ifs/lsd.jxe` 精确大小为 **55,840,541 bytes**。目录内仅为 CarPlay Maps VC 独立项目文件，不含完整工具箱。
