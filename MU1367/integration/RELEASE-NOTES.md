Complete Toolbox for **K4525 MU1367 + AID 791**. Other firmware, including P4521,
and AID 790 require their own packages.

- Consolidated maps, native arrows with distance progress, current-road/ETA bar,
  lane guidance, music metadata/artwork and reconnect recovery.
- Fresh default **30 fps / IDR5**; valid saved choices are preserved. MU UI
  settings reset archives the previous store.
- Map-only base with turn cards disabled and card settings absent. **Tuning**
  adds/removes card support and its MU UI controls together.
- One install/update action; useful Diagnostics and Recovery submenus, including
  exact-firmware OEM reset that retains snapshots.
- Normal map alignment restored after the right-edge safe-area experiment.
  Canonical feature sources replace the incremental experiment build chain.

**Updating from v3 / v3r2 / v3r3 / v3r4:** disconnect and fully reboot, refresh
both Toolbox menus and scripts, then run Install / update. The first invocation
validates and removes the known test revision through its saved controller,
retaining backups. Fully reboot again and run the same action to finish v1.4.1.
Do not delete recovery directories or force version markers. OEM/v1.4.0 and other
supported baselines follow the same action without that retirement stage.
Read `START_HERE.md` in the ZIP for exact messages, recovery and compatibility.

**Known issue:** Ottocast Mini Pico can still show its turn card. The supplied
Mini firmware has fixed-URL scene handling; exact Pico internals remain
unverified. No adapter firmware patch is included. Inactive-lane blank slots
match OEM navigation and are no longer treated as a missing-outline bug.

**Planned:** better initial/no-direction maneuver symbols, OEM “recalculating…”
message, road/intersection name above the native arrow, and Apple Maps/Waze
support. The existing current-road name in the ETA bar is included.

Runtime bytes match the validated feature builds, and host/factory-QNX
installation, migration and recovery checks are recorded with the release.
The final combined package has not received a separate vehicle acceptance run;
this does not claim all apps, adapters or endurance scenarios have passed.
Verify the ZIP with the attached `SHA256SUMS.txt` before use. Previous releases
and their assets remain unchanged.
