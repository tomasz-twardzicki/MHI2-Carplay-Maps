# MU1367 v1.4.3-e — experimental guidance-reader fix

**EXPERIMENTAL — TO BE TESTED.** This release is based on the published
**v1.4.3** package and supports **K4525 / P4521 MU1367 + AID 791**.
P4521 installation retains its experimental status. There is no vehicle
endurance result for this fix on either train.

[Complete Toolbox ZIP](CarPlay_Maps_VC_MU1367_791_v1.4.3-e.zip) ·
[Install/update/rollback](START_HERE.md) ·
[Recovery behavior and vehicle test](READER-RECOVERY.md) ·
[Checksums](SHA256SUMS.txt) · [Verification](VERIFICATION.json).

The supplied guidance-loss capture ended with native worker failure
(`reason=3`). This candidate preserves its first failure details and allows
three controlled worker replacements, only after confirmed exit, with 1/2/4
second delays. Output stays cleared until a new baseline and fresh guidance
arrive. It does not claim to repair the underlying connection/resource fault.

The normal install/update transaction includes the reader, its rollback backup
and the existing parent guard. The six v1.4.3 runtime payloads are retained byte
for byte, including the U-turn fix. Map-only, 30 fps / IDR5 defaults, optional
turn-card tuning and all v1.4.3 firmware checks remain available.

Integrated v1.4.1/v1.4.2/v1.4.3 installations use the checked retirement, full
reboot and install sequence. Remove a previous standalone reader test before
upgrading. Separate older P4521 experimental bundles use the documented OEM
reset/reboot path. Preserve all snapshots; follow `START_HERE.md` exactly.

Test native guidance for at least 90 minutes. If it stops, export diagnostics
before reconnect/reboot, then export again if reconnect restores it. Include
firmware train, app/phone and cable/adapter identity. Published as an experimental
prerelease; vehicle endurance remains unverified.
