# MU1367 standalone profiles

Exact firmware identity: `/ifs/lsd.jxe` = **55,840,541 bytes**.

The current stable release is **[v1.4.5](../releases/MU1367/v1.4.5/README.md)**, the
[v1.4.5-e integration](./integration/README.md) published with a byte-identical ZIP. It
adds reroute handling, a straight placeholder arrow and an optional 25 fps / IDR 5 map
stream. U-turn lanes in left-hand traffic and Apple Maps on some phone languages are
known issues; see the release page. See the
[release notes](./integration/RELEASE-NOTES.md) and [install guide](./integration/INSTALL.md).
The complete integration supports
K4525 or P4521 MU1367 + AID 791. P4521 installation remains experimental;
the earlier experimental build has been confirmed working in a vehicle. It combines maps, native arrows/progress, current road,
lanes with corrected VW U-turn symbols, music metadata/artwork and reconnect recovery. Fresh defaults are 30 fps /
IDR5 and cards OFF; optional tuning adds card support and its MU controls.

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
