# MU1367 / 791 integration v1.4.4-e — experimental

This release builds on the vehicle-confirmed **v1.4.3-e** and targets native
guidance from **Apple Maps and Waze**. It is **experimental, to be tested**.

- Quiet Apple Maps routes are held for up to 3 minutes of phone silence instead
  of being reset after 5 seconds, so arrows, distance and lanes no longer drop
  when the phone has nothing new to send.
- A malformed phone message is rejected on its own and no longer blocks the
  following messages. This affected every session's first message and kept
  Waze guidance hidden.
- New bounded `guidance-evidence.txt` names the phone app and records message
  structure, gaps and rejections, without road or destination text.
- The reader recovery budget renews after 10 fault-free minutes (ceiling 64).

Supports **K4525 and P4521 MU1367 + AID 791**. P4521 installation retains its
experimental status. The U-turn lane fix, map-only defaults, **30 fps / IDR5**,
audio, video and menu runtime are unchanged from v1.4.3-e.

- [Install, update and rollback](INSTALL.md)
- [Release notes](RELEASE-NOTES.md)
- [Reader recovery behavior](READER-RECOVERY.md)
- [Apple Maps / Waze capture analysis](evidence/APP-GUIDANCE-2026-11-04.md)
- [Release files](../../releases/MU1367/v1.4.4-e/README.md)
- [Known issues](KNOWN-ISSUES.md)
- [Independent OEM reset](RECOVERY.md)
- [Source, builds and verification](DEVELOPMENT.md)

The normal install/update action replaces guidance and the reader in one
verified snapshot transaction and migrates v1.4.3-e through the established
reboot boundary. Optional turn-card tuning remains available.
