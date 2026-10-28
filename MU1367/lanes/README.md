# MU1367 / 791 native lane guidance

Optional fourth layer over the published MU1367 v1.3.0 settings bundle.
It adds phone lane instructions to the factory cluster lane-guidance path,
including left-to-right order, allowed/best lanes and branching exits.
The factory lane-display setting, six-lane window and BAP request/array
handling remain in use. Turn cards default to **OFF**; the existing
App-Connect **Virtual Cockpit settings** Card ON/OFF row remains available.

This is a **vehicle test build**. Offline checks exercise the exact MU1367
factory interfaces and ARM/J9 runtime; phone/app delivery of lane data and
the physical cluster layout still require testing. Historical captures did
not contain lane geometry. No lane layout is inferred from maneuver arrows.

Read [installation, acceptance and rollback](INSTALL.md) and the
[protocol and implementation review](RESEARCH.md). Scope: exact
MU1367 K4525 firmware and **791** cluster; this is not a 790 or MU1427 patch.
The existing v1.3.0 release ZIP is unchanged.

Only the guidance JAR, menu JAR and video core change. The native driver,
reader, audio/NAI adapters, boot prepend and logging limits are retained.
The installer snapshots all replaced files and both guarded parent
controllers. Saved stream/layout/card preferences are retained; an existing
explicit Card ON remains ON until you select OFF once. Your selected
30 fps / IDR5 remains selected.
