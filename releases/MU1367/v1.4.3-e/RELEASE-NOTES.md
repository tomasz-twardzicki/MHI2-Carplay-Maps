# MU1367 v1.4.3-e — experimental guidance-reader recovery

**EXPERIMENTAL FIX — TO BE TESTED.** Based on the published v1.4.3 release,
for **K4525 / P4521 MU1367 + AID 791**. P4521 installation remains experimental.

The new capture of disappearing native guidance ended with worker failure
(`reason=3`), a different path from the earlier RAM-output failure. This build
adds a bounded first-failure record and controlled native-worker recovery.
It does not establish that the original connection/resource interruption is
fixed or that long vehicle sessions now pass.

- At most three replacements per reader lifetime, after confirmed worker exit,
  with 1/2/4-second delays. Unconfirmed exit or exhausted budget stops recovery.
- Guidance stays inactive until a new mailbox baseline and fresh event arrive.
- The first worker failure retains numeric timing, phase, errno and child status.
- The normal release transaction installs/restores the reader alongside guidance;
  there is no separate reader-test installation step.
- Preserves the v1.4.3 P4521 gates, U-turn lane fix, runtime defaults and optional
  turn-card tuning. Java, audio, driver and video runtime bytes match v1.4.3.

Use the normal **Install / update CarPlay integration (reboot)** action.
Integrated v1.4.1, v1.4.2, v1.4.3 and known v3 revisions use the existing checked
retirement/reboot/install boundary, preserving original snapshots. If the older
standalone reader test was installed, restore it first using its saved controller
and reboot. Separate older P4521 bundles use the documented OEM reset first.

Test cable and adapter sessions, cancellation/reroute and OEM navigation priority,
then run for at least **90 minutes**. Export diagnostics **before reconnect or
reboot** after a failure, and again if reconnect restores guidance. Record the
OEM train, app/phone and connection type. The archive is a local experimental
release candidate; published stable releases are unchanged.
