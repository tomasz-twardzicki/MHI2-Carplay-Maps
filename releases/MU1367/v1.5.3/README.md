# MU1367 v1.5.3 — stable: startup animation, higher bridge priority

**Stable release** for **K4525 / P4521 MU1367 + AID 791**, built from v1.5.3-e after
vehicle tests with good results. Replaces v1.5.2 as the recommended release.

[Complete Toolbox ZIP](https://github.com/tomasz-twardzicki/MHI2-Carplay-Maps/releases/download/MU1367-v1.5.3/CarPlay_Maps_VC_MU1367_791_v1.5.3.zip) ·
[Install/update/rollback](START_HERE.md) · [Release notes](RELEASE-NOTES.md) ·
[Reader recovery](READER-RECOVERY.md) · [Known issues](KNOWN-ISSUES.md) ·
[Checksums](SHA256SUMS.txt) · [Verification](VERIFICATION.json).

- **Startup animation on the AID.** A 4.2 s App-Connect clip plays when CarPlay takes the
  cluster map, then the live map follows on a fresh key frame. Choose under **App-Connect >
  Virtual Cockpit settings > Startup animation**: **Once per boot** (default), **Every
  connection** or **Off**. Off starts exactly as v1.5.2. With Tuning, this row replaces
  **Wireless CarPlay (test)**, which had no function. Android Auto has no clip.
- **Higher video-bridge priority (14 instead of 10).** With the reverse camera on, the CPU
  reaches 98–100%, and the bridge, at the same priority as the navigation renderer, lost the
  CPU long enough to drop frames. It now runs above the navigation threads and below the MOST
  driver and the CarPlay receivers.
- **Everything of v1.5.2:** the steadier CarPlay map (v1.2.2 safe area, 2048-packet bridge
  buffer, no map drop-out after boot), 40 fps / IDR 5 by default, P4521 support and the
  saved-snapshot tuning entries.
- **Android Auto on the AID** (Google Maps picture and native VW arrows from an Android
  phone) is included but **not yet fully tested**.

- **Fix: the live map always follows the clip.** The bridge used to request the phone's
  key frame before noting which frames to skip, so a very fast answer could be skipped and
  the clip's last frame stayed on the AID. Not seen in the car tests; found under heavy
  load on a PC.

Everything else is byte-identical to the tested v1.5.3-e. Updating from v1.5.3-e, v1.5.2 or any earlier supported version uses the
checked two-stage update: install → full reboot → install again. A Startup animation choice
saved under v1.5.3-e is kept. The final message is
`MU1367_RELEASE_1_5_3_INSTALLED_FULL_REBOOT_REQUIRED`.

## Thanks and sources

[omonob](https://github.com/omonob) (original [CarPlay Maps VC](https://github.com/omonob/MHI2-Carplay-Maps)),
[luka-dev](https://github.com/luka-dev) (CarPlay route guidance research),
[chrzanowy](https://github.com/chrzanowy) (Android Auto feeder and route translation),
[MacsInSpace](https://github.com/MacsInSpace) (the `gal` cluster-map hook),
[Mr-MIBonk](https://github.com/Mr-MIBonk) (M.I.B.),
Jille & Olli ([MIB2 Toolbox](https://github.com/jilleb/mib2-toolbox)) and
[Karan](https://t.me/karanldn) for valuable road tests and feedback. Details in the
[release notes](RELEASE-NOTES.md#thanks-and-sources).
