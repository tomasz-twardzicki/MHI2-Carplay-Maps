# MU1367 standalone profiles

Exact firmware identity: `/ifs/lsd.jxe` = **55,840,541 bytes**.

The separate [MU1367 / 791 integration test](./port/README.md) adds turn-card
and 30 fps variants, firmware-matched native guidance/audio/navigation-active
HMI adapters, and optional N3 artwork capture. It includes exact-hash gates,
verified backups and [no-SD recovery](./port/INSTALL.md). See its
[verification record](./port/VERIFICATION.json) and subsequent
[user test results](./settings-v2/UNIT-RESULTS.md).
The standalone profiles below retain their existing baseline payloads.

The optional [native MU settings layer](./settings-v2/README.md) integrates
omonob's plaintext v2 UI and paired map/mirror runtime with that integration.
It adds selectable FPS/IDR cadence and compact card layouts in App-Connect,
with a separate complete test bundle and [reverse-order rollback](./settings-v2/INSTALL.md).
MU1367/791 only. The user reports successful initial operation and prefers
30 fps / IDR5; both 40 fps profiles showed some stutter. Extended endurance
and detailed acceptance checks remain unrecorded.

| Cluster | Profile files | Display baseline |
| --- | --- | --- |
| 791 AID 12.3 | [`791_AID12.3`](./791_AID12.3/) | 40 fps, navigation centered |
| 790 AID 10.5 | [`790_AID10.5`](./790_AID10.5/) | 40 fps, non-navigation centered, navigation right |

These directories contain only the CarPlay Maps VC project files. They are not complete MQB or M.I.B. Toolbox distributions.

固件识别条件：`/ifs/lsd.jxe` 精确大小为 **55,840,541 bytes**。目录内仅为 CarPlay Maps VC 独立项目文件，不含完整工具箱。
