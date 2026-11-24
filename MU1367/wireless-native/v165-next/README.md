# MU1367 v1.6.5-e-test1

Local experimental follow-up to the two v1.6.4 drives. Supports the exact K4525/P4521 HW50/HW70 firmware gates used by the complete v1.6.1 package. Vehicle acceptance is pending.

Changes:

- BT guard accepts the pinned add-on's unresolved native PLT target as well as its resolved libc targets. It retries attachment for 60 seconds, reports the failing stage and repairs a known native lazy-resolution overwrite. Competing hooks remain protected. Once a fresh accepted wireless session is established, the existing guard can preserve it on BT-only loss and pause native reconnect/paging/resends. Actual radio behavior still needs testing.
- GEM offers **Dial road label: next / current / off / status**, shared by wired and wireless guidance. Next uses parameter 4 of the exact active manoeuvre. It blanks unknown heads, reroutes and stale routes, retains valid prefetched heads, and respects the existing 75-byte UTF-8 limit. Current remains the default.
- Artwork publication retries the current image when the picture-server instance changes. New diagnostics distinguish stage/server attachment, handle acceptance, publication, metadata-field presence and file-transfer identity. They preserve the existing conservative rules against displaying another track's cover.
- Main-screen ownership and native launch traces record their clocks explicitly, so the reported MU-only startup freeze can be correlated with receive/decode logs. This is diagnostic instrumentation; the startup freeze is not established fixed.
- GPS status now reports actual source/fix health, age, UTC readiness, receiver advertisement/request/submission counts and missing-source reasons. The optional probe retains bounded clock/bootstrap observations and marks map-matched positions as unqualified for raw GNSS.

**Vehicle GPS is not available during wireless-only use in the supplied drives.** DIO is absent, so its passive NMEA capture cannot run. This candidate does not start the USB service, synthesize NMEA from unqualified HMI positions or repeatedly refresh a parked stale fix. The existing experimental source/receiver protocol remains off by default. A qualified wireless producer and UTC source are still required; enabling the option or rebooting alone does not solve this. Wired OEM location behavior is retained. No exclusive iPhone sensor selection is commanded.

The working 40/8/150 alternate-stream defaults, native main-screen demand of 30, timing/IDR reconnect behavior, audio priority, RHD, icon label, ETA/arrival setting and reverse-return behavior are retained. Pre-acceptance Wi-Fi-first/last-phone arbitration, redundant bootstrap starts, track-skip delay and deeper SDK/radio metrics remain open.

The package manages 45 targets and includes installation, previous-layer recovery, complete OEM restore and combined base diagnostics. It recognizes the supported v1.5.3/v1.5.4 paths, stable v1.6.1 and sealed wireless candidates through v1.6.4. Reboot-and-run-again boundaries remain mandatory. GPS/probe/road-label preferences belong to this recovery layer and are archived by OEM restore. Unknown third-party modifications are preserved or refused; this is not a universal uninstaller for arbitrary omonob installations.

See [installation and vehicle tests](START_HERE.md), [release notes](RELEASE-NOTES.md), [progress and limits](PROGRESS.md) and [verification](VERIFICATION.json). Bench records separate host checks, matching factory ARM/J9 execution, native receiver paths and controlled hardware boundaries. The earlier input-preload assertion was traced to ENOSPC in the emulator fixture: cleanup plus the firmware's sync utility lets both released-control and candidate functional tests pass, without changing production input code.
