# MU1367 v1.4.4-e — experimental Apple Maps / Waze guidance

**EXPERIMENTAL — TO BE TESTED.** Based on the vehicle-confirmed **v1.4.3-e**
package, for **K4525 / P4521 MU1367 + AID 791**. P4521 installation retains its
experimental status. This package has no vehicle result yet.

[Complete Toolbox ZIP](CarPlay_Maps_VC_MU1367_791_v1.4.4-e.zip) ·
[Install/update/rollback](START_HERE.md) · [Release notes](RELEASE-NOTES.md) ·
[Reader recovery](READER-RECOVERY.md) · [Checksums](SHA256SUMS.txt) ·
[Verification](VERIFICATION.json).

- Apple Maps routes are held through quiet periods (up to 3 minutes of phone
  silence) instead of being reset after 5 seconds.
- A malformed phone message is rejected on its own. Previously every session's
  first message blocked guidance until 16 more arrived, which hid Waze entirely.
- `guidance-evidence.txt` in the diagnostics export names the phone app and
  records message structure, gaps and rejections, without road text.
- The reader's three-attempt recovery budget renews after 10 fault-free minutes,
  with a lifetime ceiling of 64 replacements.

Only the guidance JAR and native reader change. Audio, driver, menu and video
runtime match v1.4.3-e, including map-only and 30 fps / IDR5 defaults, the
U-turn lane fix and optional turn-card tuning.

An installed v1.4.3-e uses the checked retirement, full reboot and install
sequence, as do all earlier supported revisions. Preserve all snapshots and
follow `START_HERE.md` exactly.

Test Apple Maps with stops longer than 5 seconds, Waze with an active route and
Google Maps for regression. Export diagnostics while guiding. If Waze shows no
active route in `guidance-evidence.txt`, it is not sending cluster guidance.
