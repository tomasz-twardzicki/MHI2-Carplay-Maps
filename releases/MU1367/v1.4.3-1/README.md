# MU1367 / 791 v1.4.3-1 — stable

Stable release of the vehicle-confirmed **v1.4.3-e** guidance-reader fix, for
**K4525 / P4521 MU1367 + AID 791**. P4521 installation retains its experimental
status.

[Release and ZIP](https://github.com/tomasz-twardzicki/MHI2-Carplay-Maps/releases/tag/MU1367-v1.4.3-1) ·
[Install/update/recovery](../v1.4.3-e/START_HERE.md) ·
[Reader recovery](../v1.4.3-e/READER-RECOVERY.md) ·
[Known issues](../v1.4.3-e/KNOWN-ISSUES.md) · [SHA-256](SHA256SUMS.txt) ·
[Verification](../v1.4.3-e/VERIFICATION.json).

The ZIP is **byte-identical** to v1.4.3-e
(`3ecb5304c8a9e85c43a01dd532dfc5c920c3e1a866321a7c1d667d750260afa5`); it was not
rebuilt, so its menu banner, documents and completion message still read
"v1.4.3-e" / "experimental". Those labels refer to the same tested package.

When the native guidance worker fails, the reader clears guidance, confirms the
failed worker has exited and starts a replacement: at most three times per boot,
after 1, 2 and 4 seconds. Guidance returns only after a fresh baseline and new
phone data, and the first failure's details are retained. In a 2 h 30 min
guided drive it recovered twice without user action.

Installation, migration from v1.4.1/v1.4.2/v1.4.3 and known test revisions,
rollback and the independent OEM reset are unchanged from v1.4.3-e. Follow
`START_HERE.md` exactly and preserve all snapshots.
