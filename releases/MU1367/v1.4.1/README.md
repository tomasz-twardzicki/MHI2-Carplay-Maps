# MU1367 / 791 v1.4.1

[Release and ready-to-extract full Toolbox ZIP](https://github.com/tomasz-twardzicki/MHI2-Carplay-Maps/releases/tag/MU1367-v1.4.1) ·
[Installation/update/recovery](../../../MU1367/integration/INSTALL.md) ·
[Known issues and TODOs](../../../MU1367/integration/KNOWN-ISSUES.md) ·
[SHA-256](SHA256SUMS.txt).

Exact K4525 MU1367 + AID 791. Includes native arrows with distance progress,
current-road/ETA bar, lane guidance, audio metadata/artwork and reconnect
recovery. Defaults: 30 fps / IDR5, cards OFF with their settings absent. Optional
Tuning installs/removes both card support and its MU controls.

One install/update action, archived settings reset, Diagnostics and Recovery
submenus, and independent OEM reset. Known v3 test installations use a verified
saved removal, full reboot, then the same install action; snapshots are retained.
See the guide before updating. Prior release assets remain unchanged.

Mini Pico may still override map-only URLs and show a card. The failed right-edge
safe-area experiment is removed; normal map alignment is restored. Unused-lane
blanks match OEM behavior. Improved symbols/recalculation/above-arrow names and
Apple Maps/Waze support remain planned work.

The consolidated runtime rebuild matches the previously verified payloads.
Package/migration tests run off-unit; final release packaging is not a claim
of new vehicle testing or coverage of every app/adapter/endurance scenario.
