# MU1367 v1.5.3-e — experimental: startup animation, higher bridge priority

**EXPERIMENTAL — TO BE TESTED.** Update of stable **v1.5.2** for **K4525 / P4521 MU1367 +
AID 791**. Not yet tested in a car. Use [v1.5.2](../v1.5.2/README.md) for a stable
installation.

[Complete Toolbox ZIP](https://github.com/tomasz-twardzicki/MHI2-Carplay-Maps/releases/download/MU1367-v1.5.3-e/CarPlay_Maps_VC_MU1367_791_v1.5.3-e.zip) ·
[Install/update/rollback](START_HERE.md) · [Release notes](RELEASE-NOTES.md) ·
[Reader recovery](READER-RECOVERY.md) · [Known issues](KNOWN-ISSUES.md) ·
[Checksums](SHA256SUMS.txt) · [Verification](VERIFICATION.json).

- **Startup animation on the AID.** A 4.2 s App-Connect clip plays when CarPlay takes the
  cluster map, then the live map follows on a fresh key frame. Choose under **App-Connect >
  Virtual Cockpit settings > Startup animation**: **Once per boot** (default), **Every
  connection** or **Off**. Off starts exactly as v1.5.2. With Tuning, this row replaces
  **Wireless CarPlay (test)**, which had no function. Android Auto has no clip.
- **Higher video-bridge priority (14 instead of 10).** With the reverse camera on, the CPU
  reaches 98–100% and the bridge, at the same priority as the navigation renderer, lost the
  CPU long enough to drop frames. It now runs above the navigation threads and below the MOST
  driver and the CarPlay receivers.

Everything else is v1.5.2. Updating uses the checked two-stage update: install → full reboot
→ install again. The final message is
`MU1367_RELEASE_1_5_3_E_EXPERIMENTAL_INSTALLED_FULL_REBOOT_REQUIRED`.
