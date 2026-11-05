# MU1367 / 791 v1.4.4 — stable

Stable release of the **v1.4.4-e** build, for **K4525 / P4521 MU1367 + AID 791**.
P4521 installation retains its experimental status.

[Release and ZIP](https://github.com/tomasz-twardzicki/MHI2-Carplay-Maps/releases/tag/MU1367-v1.4.4) ·
[Install/update/recovery](../v1.4.4-e/START_HERE.md) ·
[Release notes](../v1.4.4-e/RELEASE-NOTES.md) ·
[Reader recovery](../v1.4.4-e/READER-RECOVERY.md) ·
[Known issues](../v1.4.4-e/KNOWN-ISSUES.md) · [SHA-256](SHA256SUMS.txt) ·
[Verification](../v1.4.4-e/VERIFICATION.json).

The ZIP is **byte-identical** to v1.4.4-e
(`264c298ff67ad9bfb4e19793800e1d754942c81c50931b4f5b33caa9e5a2b99f`); it was not
rebuilt, so its menu banner, documents and completion message still read
"v1.4.4-e" / "experimental". Those labels refer to this same package.

## Known issues in this release

- **Apple Maps results vary.** One tester reports Apple Maps working. In another
  test, ETA and road names worked but arrows and lanes did not. That test's phone
  switched source names 13 times ("Mapy Apple", "Apple Maps", "Google Maps"), and
  each switch clears stored maneuvers and lanes. Apple Maps does not resend them,
  so they stay lost until new ones arrive. An offline replay reproduces this
  symptom, but the capture does not show when the switches happened, so the cause
  is not yet confirmed. A fix is not in this release.
- **Waze has no vehicle result.** Earlier captures supplied only 2–3 guidance
  messages per session. `guidance-evidence.txt` will show whether Waze sends an
  active route at all.

If arrows or lanes are missing, export diagnostics while guiding and include the
phone's language and whether it uses USB or a wireless adapter.

Installation, migration from v1.4.3-1 / v1.4.3-e and earlier supported revisions,
rollback and the independent OEM reset are unchanged from v1.4.4-e. Follow
`START_HERE.md` exactly and preserve all snapshots.
