# OEM touch / 790 upstream runtime comparison — test 2

Local experiment for MU1367 K4525/P4521, based on v1.6.3-e. This is a comparison
for Sergey's static-noise report, not an accepted map repair or a new public
release. The published v1.6.3-e asset is unchanged.

## From the installed 790 test 1

1. Extract the complete test-2 ZIP to a clean SD root. Refresh both Toolbox
   menus and scripts. Disconnect the phone and fully reboot.
2. Open **Customization → carplay-maps-vc-experimental** and select
   **790: upstream runtime comparison + OEM touch**. On an installed test-1
   unit this first restores the saved parent files and prints
   `EXPERIMENTAL_PROFILE_REMOVED_FULL_REBOOT_THEN_REPEAT_ACTION`.
3. Fully reboot with the phone disconnected. Select the same **790** action
   again. Wait for success, then fully reboot once more before reconnecting.

The normal CarPlay Maps installation does not need to be rerun if native
v1.6.3-e is already completely installed. Test 2 refuses an incomplete parent
installation. Keep **Startup animation → Off** for the comparison and record
any custom test-1 safe rectangle first: test 2 starts with `202,16,606,344`.

## What changes

Test 1 already used omonob v3.2's exact 790 receiver, launcher, feeder, maps
library and geometry. It retained an older wired 790 core and the v1.6.3-e
bridge/supervisor. Test 2 pairs that same 790 profile with the exact core,
bridge and supervisor shipped together in omonob's v3.2 Standalone package.

The working OEM touch JARs are byte-identical to test 1. The new profile has
its own recovery directory, retains test-1 snapshots, and snapshots all 15
changed targets. Unknown changed files/controllers are preserved and refused.
The upstream bridge has no embedded 800×480 startup clip.

This is still a map experiment. It does not establish custom 791 wireless
guidance/media/timing/RHD/tuning features, call-audio routing, or compatibility
of the retained upstream iPhone 17 Pro Max profile with every other phone.
It also uses upstream bridge recovery behavior during the comparison; the
newer custom bridge's recovery and timing changes are not part of test 2.

## Check and capture

Connect native wireless CarPlay and display the AID map. Record whether the
noise changes and check OEM overlay touch again. If it fails, export ordinary
CarPlay diagnostics while connected and the noise is visible, before removing
the experiment. The export includes both test generations' receipts. No new
video-capture tool is required for this first comparison.

Safe-area actions remain in the same experimental menu. They only change
framing; they are not a treatment for static noise. Disconnect and reboot
before tuning and fully reboot again to apply it.

## Restore

Use **Remove experiment and restore saved 791 runtime**, then fully reboot.
This restores the exact parent files, not the failed test-1 790 runtime.
Keep both recovery folders. Test-2 SD wrappers also retire the experiment
before normal uninstall/OEM restore, with the required reboots at each layer.

Bench evidence covers real shell transactions, all 15 commit failures and
interruptions, legacy migration, OEM restoration, factory-shell compatibility,
factory ARM/J9 verification of the unchanged input classes and native import
resolution on both supported firmware trains. These do not establish physical
MOST output, cluster decoding or a noise fix.
