# MU1367 / AID 791: initial user test results

Reported on 2026-10-28 for the combined MU1367 integration and native settings
bundle. This is a user observation, separate from the original build-time
host/QNX evidence in `VERIFICATION.json`.

The user reports that everything appears in order, tested both 40 fps
settings, and selected **30 fps / IDR5** because the 40 fps choices showed
some stutter.

| Profile | Reported result |
| --- | --- |
| 40 fps / IDR5 | Tested; some stutter |
| 40 fps / IDR20 | Tested; some stutter |
| 30 fps / IDR5 | User-selected preferred configuration |
| 30 fps / IDR20 | No separate comparison result supplied in this report |

The native settings selection and profile comparison have been exercised.
The general positive report is not a step-by-step certification of every
guidance, audio, mirroring, layout, rollback or optional artwork scenario.
No exact run duration, measured FPS, app/phone versions, CPU measurements,
diagnostic export or 90-minute endurance result accompanied this report.
MU1367/790 remains experimental and unvalidated by this result.

The tested archive is preserved without rebuilding or changing defaults:

```text
CarPlay_Maps_VC_MU1367_791_MU_Settings_Test.zip
SHA256 19a136685d1e55d8630bfe38146a75a8b999fad0198a3a0f850f075f631a50b9
Build  MU1367-settings-v2-2b9533e277a6
Parent MU1367-integration-7262b3242a11
```

Its first-install default is still 30 fps / IDR20 with the narrow layout.
Choose 30 fps / IDR5 in App-Connect's Virtual Cockpit settings and reconnect
CarPlay to use the preferred configuration. Existing saved preferences are
retained by the installer/removal procedures.

For the earlier MU1427 loss of native guidance after roughly 40 minutes,
see the [RAM-output failure analysis](../../MU1427/route-guidance/HMI-OUTPUT-FAILURE-2026-10-28.md).
The MU1367 settings layer includes bounded video/bridge logging, and its
host resource tests passed. Extended on-unit verification of that mitigation
is still needed; this user report does not establish that the endurance
issue has been resolved in every configuration.
