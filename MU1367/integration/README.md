# MU1367 / 791 integration v1.4.3-e — experimental

This release adds bounded guidance-reader recovery and retained first-failure
information to the published **v1.4.3** baseline. It is an **experimental fix,
to be tested**, for native guidance disappearing after extended operation.
The supplied capture showed worker failure; the original interruption's cause
and vehicle endurance of this recovery remain unverified.

Supports **K4525 and P4521 MU1367 + AID 791**. P4521 installation retains its
experimental status. The v1.4.2 VW U-turn lane fix (114/146), complete v1.4.3
feature set, map-only defaults and **30 fps / IDR5** are retained.

- [Install, update and rollback](INSTALL.md)
- [Experimental recovery behavior and vehicle test](READER-RECOVERY.md)
- [Release files](../../releases/MU1367/v1.4.3-e/README.md)
- [Known issues](KNOWN-ISSUES.md)
- [Independent OEM reset](RECOVERY.md)
- [Source, builds and verification](DEVELOPMENT.md)

The normal install/update action includes the new reader in the same verified
snapshot transaction as native guidance. Optional turn-card tuning remains
available. No separate reader add-on action is needed. Audio retains the v1.4.3
runtime and source. Mini Pico card overrides, unused-lane blank slots and
navigation-app limitations remain documented known issues.
