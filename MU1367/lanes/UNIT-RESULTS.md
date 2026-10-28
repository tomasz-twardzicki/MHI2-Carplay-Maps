# MU1367 / 791 lane guidance: user test results

On **2026-10-28**, the user confirmed that the lane-guidance setup had been
tested on the car and worked fine, and authorized a regular release:

> I've tested it and it worked fine, you can do a regular release

MU1367 v1.4.0 is promoted from prerelease to a regular release on that basis.
No runtime files, ZIP contents, checksums or release tag are changed by the
promotion. The published package remains build `MU1367-lanes-ac765ddeb391`,
ZIP SHA256 `942c9d2a1b38e7f417f97e1a8806e42559b29565f3605215c92b932d58c1259f`.

The report confirms successful operation of the setup. It does not specify
the exact ZIP used, individual phone apps, a maneuver-by-maneuver acceptance
matrix or an endurance duration. Those details are not inferred from the report.

[VERIFICATION.json](VERIFICATION.json) and the manifests inside the unchanged
ZIP retain their historical build-time `on_unit_validated=false` values.
This user report supplements that offline evidence; it does not rewrite it.
The documents inside the ZIP likewise retain their original pre-test wording.
Use the current [installation and rollback guide](INSTALL.md) for the latest
documentation.
