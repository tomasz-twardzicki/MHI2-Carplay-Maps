# MU1367 v1.5.2 — stable: CarPlay and Android Auto on the AID, 40 fps default

**Stable release** for **K4525 / P4521 MU1367 + AID 791**, built from v1.5.2-e after
vehicle tests with very good results. Replaces v1.4.6 as the recommended release.

[Complete Toolbox ZIP](https://github.com/tomasz-twardzicki/MHI2-Carplay-Maps/releases/download/MU1367-v1.5.2/CarPlay_Maps_VC_MU1367_791_v1.5.2.zip) ·
[Install/update/rollback](START_HERE.md) · [Release notes](RELEASE-NOTES.md) ·
[Reader recovery](READER-RECOVERY.md) · [Known issues](KNOWN-ISSUES.md) ·
[Checksums](SHA256SUMS.txt) · [Verification](VERIFICATION.json).

- **The v1.5.2-e CarPlay map:** v1.2.2's taller safe area for a closer, lighter map, a
  2048-packet video-bridge buffer, and no map drop-out shortly after boot.
- **40 fps / IDR 5 is the default map stream.** The MU UI offers 40, 30 and 25 fps
  (IDR 5); a saved 20 or 27 fps choice now runs as 40 fps.
- **P4521 is supported without the experimental label**; it has been tested in vehicles.
- **New: Tuning → Saved snapshots of earlier installations.** Lists the copies kept by
  earlier installations, rollbacks and OEM resets with their sizes, and removes them one
  at a time or all at once. Installed layers keep their own snapshots, so rollback and
  the OEM reset keep working.
- **Android Auto on the AID** (Google Maps picture and native VW arrows from an Android
  phone) is included but **not yet fully tested**.

Updating from v1.4.6 or any v1.5.x uses the checked two-stage update: install → full
reboot → install again. All snapshots are kept. Before rolling back to v1.4.5 or older,
select 30 or 40 fps again in the MU UI.

## Thanks and sources

[omonob](https://github.com/omonob) (original [CarPlay Maps VC](https://github.com/omonob/MHI2-Carplay-Maps)),
[luka-dev](https://github.com/luka-dev) (CarPlay route guidance research),
[chrzanowy](https://github.com/chrzanowy) (Android Auto feeder and route translation),
[MacsInSpace](https://github.com/MacsInSpace) (the `gal` cluster-map hook),
[Mr-MIBonk](https://github.com/Mr-MIBonk) (M.I.B.),
Jille & Olli ([MIB2 Toolbox](https://github.com/jilleb/mib2-toolbox)) and
[Karan](https://t.me/karanldn) for valuable road tests and feedback. Details in the
[release notes](RELEASE-NOTES.md#thanks-and-sources).
