# MU1367 v1.6.7-e — test2 baseline, AID 790/791

Experimental recovery release based on the exact vehicle-tested **v1.6.5-e-test2** SD archive. Both cluster profiles retain **test2 input handling**. GPS forwarding stays disabled by default; the independent raw-GNSS/UTC client is not included.

[Installation and recovery](START_HERE.md) · [Release notes](RELEASE-NOTES.md) · [Verification](VERIFICATION.json)

v1.6.6-e was withdrawn after reports of broken Keep behavior, lag, MU freezes and inability to disconnect. The cause has not been isolated. This package discards its shared runtime changes rather than carrying them forward.

| Profile | Runtime |
| --- | --- |
| 791 (default) | Exact test2 runtime and JARs; existing 40 fps / IDR8 / 150 ms wireless tuning options; native guidance, text and artwork |
| 790 (optional) | Tested overlay790 test3 video/metadata backend, test2 input JARs; its own 30 fps map path; centred wireless safe area and card On/Off controls |

The 790 launcher adds only the ABI helpers required by test2's unchanged BT wrapper. The 790 profile does not acquire the custom 791 guidance, smoothing, IDR or GPS hooks. The combined 790 backend with test2 input needs vehicle acceptance. Fresh turn cards default to Off; existing saved choices are preserved.

The SD package identifies as **1.6.7-e**. The installed parent intentionally retains build `MU1367-wireless-native-v165t2-8ebe482b1961` and recovery root `/mnt/app/carplay-mu1367-wireless-native-v165t2`. This preserves compiled preference paths and exact runtime bytes. A test2 runtime version in diagnostics is expected.

Only exact supported MU1367 K4525/P4521 HW50/HW70 firmware is accepted. Retain this complete SD and all recovery snapshots. This is not a general third-party uninstaller.
