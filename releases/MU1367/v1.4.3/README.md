# MU1367 / 791 v1.4.3 — P4521 support

[Release and full Toolbox ZIP](https://github.com/tomasz-twardzicki/MHI2-Carplay-Maps/releases/tag/MU1367-v1.4.3) ·
[Install/update/recovery](../../../MU1367/integration/INSTALL.md) ·
[Known issues](../../../MU1367/integration/KNOWN-ISSUES.md) ·
[SHA-256](SHA256SUMS.txt).

Supports **K4525 and P4521 MU1367 + AID 791** with all current integrated
features and the v1.4.2 U-turn lane fix. **P4521 installation remains experimental.**
The earlier P4521 experimental build has been confirmed working in a vehicle;
acceptance of this new combined package remains separate.

The six runtime payloads are byte-identical to v1.4.2, including the guidance
status ID `MU1367-guidance-v1.4.2`. Package/menu/controller IDs identify v1.4.3.
Fresh defaults remain 30 fps / IDR5 with turn cards OFF; optional tuning installs
the card runtime and controls together.

From a separate P4521 experimental bundle, use the new SD's **Recovery > Restore
complete OEM state**, reboot disconnected, then the normal install action.
Snapshots, old layers and settings are retained. Integrated v1.4.1/v1.4.2 and
known v3 revisions use the checked removal/reboot/install migration. Read the
installation guide before updating. Earlier release assets remain unchanged.
