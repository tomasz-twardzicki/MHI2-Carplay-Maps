# MU1367 profiles and integrated releases

The current experimental release is **[v1.6.6-e for AID 790/791](../releases/MU1367/v1.6.6-e/README.md)**. Follow its [complete installer/recovery guide](../releases/MU1367/v1.6.6-e/START_HERE.md). The 790 selection retains the tested overlay backend, adds the shared OEM touch and guarded call/media preference, and corrects wireless navigation centring. Fresh turn-card defaults are Off. See [release notes](../releases/MU1367/v1.6.6-e/RELEASE-NOTES.md) for the feature differences and remaining experimental limits.

[Stable v1.6.1 for 791](../releases/MU1367/v1.6.1/README.md) and all historical packages remain unchanged. New wireless release sources are in [wireless-native/v166-release](wireless-native/v166-release/README.md); [integration](integration/README.md) retains the wired base sources and recovery history.

Exact firmware identity: `/ifs/lsd.jxe` = **55,840,541 bytes**.

Historical v1.4.3 development is **[v1.4.3-e experimental integration](./integration/README.md)**,
based on the published v1.4.3 release, with reader recovery awaiting vehicle testing.
Use the [experimental test guide](./integration/READER-RECOVERY.md) for the new candidate.
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
historical video baselines, not the v1.4.3 complete installation package.

| Cluster | Profile files | Display baseline |
| --- | --- | --- |
| 791 AID 12.3 | [`791_AID12.3`](./791_AID12.3/) | 40 fps, navigation centered |
| 790 AID 10.5 | [`790_AID10.5`](./790_AID10.5/) | 40 fps, non-navigation centered, navigation right |

These directories contain only the CarPlay Maps VC project files. They are not complete MQB or M.I.B. Toolbox distributions.

固件识别条件：`/ifs/lsd.jxe` 精确大小为 **55,840,541 bytes**。目录内仅为 CarPlay Maps VC 独立项目文件，不含完整工具箱。
