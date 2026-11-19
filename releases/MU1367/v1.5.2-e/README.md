# MU1367 v1.5.2-e — experimental: lighter CarPlay map (v1.2.2 safe area, larger bridge buffer)

**EXPERIMENTAL — TO BE TESTED.** Update of v1.5.1-e, based on stable **v1.4.6**, for
**K4525 / P4521 MU1367 + AID 791**. P4521 installation retains its experimental status.
Use v1.4.6 for a stable CarPlay installation.

[Complete Toolbox ZIP](https://github.com/tomasz-twardzicki/MHI2-Carplay-Maps/releases/download/MU1367-v1.5.2-e/CarPlay_Maps_VC_MU1367_791_v1.5.2-e.zip) ·
[Install/update/rollback](START_HERE.md) · [Release notes](RELEASE-NOTES.md) ·
[Reader recovery](READER-RECOVERY.md) · [Known issues](KNOWN-ISSUES.md) ·
[Checksums](SHA256SUMS.txt) · [Verification](VERIFICATION.json).

- **Taller map safe area, as in v1.2.2 (160,20,480,440).** Since v2.0 the map-only view
  declared a smaller, lower box (200,96,400,364). The map app then framed a wider, denser
  map with much larger frames. This test goes back to v1.2.2's box for a closer, lighter
  map. Some of the map may now sit under the dials.
- **Larger video-bridge buffer: 2048 packets (about 250 ms) instead of 1024.** Big frames at
  27/5 peaked at 1377 queued packets and caused brief resets (lag, stutter, blocky picture)
  even with a healthy MOST link. Applies to every stream setting.
- Everything of v1.5.1-e: the CarPlay map survives the boot-time encoder takeover, and
  Android Auto on the AID.

Updating from v1.5.1-e or v1.5.0-e uses the checked two-stage update: install → full reboot →
install again. Stage 1 also removes the Android Auto layer, stage 2 reinstalls it; all
snapshots are kept.
