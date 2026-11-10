# MU1367 v1.4.6 — stable: U-turn lanes, Apple Maps languages, 27 fps and compressed artwork

**Stable release** for **K4525 / P4521 MU1367 + AID 791**, built from v1.4.6-e. P4521
installation retains its experimental status.

[Complete Toolbox ZIP](https://github.com/tomasz-twardzicki/MHI2-Carplay-Maps/releases/download/MU1367-v1.4.6/CarPlay_Maps_VC_MU1367_791_v1.4.6.zip) ·
[Install/update/rollback](START_HERE.md) · [Release notes](RELEASE-NOTES.md) ·
[Reader recovery](READER-RECOVERY.md) · [Known issues](KNOWN-ISSUES.md) ·
[Checksums](SHA256SUMS.txt) · [Verification](VERIFICATION.json).

- **U-turn lanes in left-hand traffic** (UK and similar) show the right U-turn arrow.
- **Apple Maps with any phone language:** arrows and lanes update from the first turn.
- **27 fps / IDR 5 is the default map stream.** The MU menu offers 20, 25, 27, 30 and
  40 fps, all with IDR 5; a saved choice is kept.
- **Compressed album artwork is installed by default.** Lossless (identical pixels),
  usually 1–100 KB instead of 197 KB. **Tuning → Disable compressed album artwork**
  switches it off, and later installs respect that.

Guidance, audio and reader are byte-identical to v1.4.6-e; only the map core and MU menu
change. An installed v1.4.6-e or older goes through the checked removal → full reboot →
install sequence. Before rolling back to v1.4.5 or older, select 30 or 40 fps / IDR 5.

Still open: zooming with the wheel arrows over a wireless adapter also opens the factory
cluster menu, and Waze has no vehicle result.
