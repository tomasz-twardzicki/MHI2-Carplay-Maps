# MU1367 / AID 791 v1.6.1 — stable

Complete wired and native wireless CarPlay package for K4525/P4521 MU1367 and
the 12.3-inch AID 791. Includes the v1.5.4 base, ETA/arrival-time selection,
wireless AID maps, native route/lane guidance, OEM RHD/LHD forwarding and GEM
stream tuning. Android Auto remains included with its existing testing limits.

Start with [START_HERE.md](START_HERE.md). The same Install action handles
v1.5.3, v1.5.4 and the earlier wireless candidates. It restores a known saved
layer when necessary, requires a full reboot, then resumes from this SD.
Complete OEM restore follows the same safe order. Standard diagnostics now
includes wireless logs, session/cadence state, coding, tuning and timing data.

The native runtime is byte-identical to the successful v1.6.1-e-test2 vehicle
test. Internal component build IDs and the wireless snapshot directory are
retained for traceability and safe adoption. Existing test2 installations are
checked and adopted without replacing their runtime or snapshots.

See [release notes](RELEASE-NOTES.md), `MU1367_RELEASE_MANIFEST.json`,
`VERIFICATION.json` and `SHA256SUMS.txt` alongside the download.
