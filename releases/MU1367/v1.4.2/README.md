# MU1367 / 791 v1.4.2

[Release and full Toolbox ZIP](https://github.com/tomasz-twardzicki/MHI2-Carplay-Maps/releases/tag/MU1367-v1.4.2) ·
[Install/update/recovery](../../../MU1367/integration/INSTALL.md) ·
[Known issues](../../../MU1367/integration/KNOWN-ISSUES.md) ·
[SHA-256](SHA256SUMS.txt).

Fixes U-turn lane encoding using the factory VW bytes **114 left / 146 right**,
incorporating [PR #8](https://github.com/tomasz-twardzicki/MHI2-Carplay-Maps/pull/8)
by [@chrzanowy](https://github.com/chrzanowy). Guidance status identifies the
rebuilt runtime as `MU1367-guidance-v1.4.2`. The other five runtime payloads
retain their v1.4.1 hashes.

Exact **K4525 MU1367 + AID 791** only. Includes the complete installation,
optional turn-card runtime/menu, Diagnostics, snapshot-preserving recovery
and independent OEM reset. An active v1.4.1 installation uses the same checked
removal/reboot/install sequence as known v3 test revisions. Read the guide
before updating; keep all snapshots.

Factory constants, host decoding/transport, ARM/J9 execution and QNX transactions
are checked off-unit. MU1367 U-turn rendering and final-package vehicle
acceptance remain pending. The PR reports vehicle success on MU1161 + AID 791.
The reviewed threshold starts at ±170°; ±169° stays at 128 and exactly +180°
selects left for right-hand traffic. Mini Pico card override remains unresolved.
Prior release assets are unchanged.
