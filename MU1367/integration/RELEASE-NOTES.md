Fixes U-turn lane directions in the complete Toolbox for **K4525 MU1367 + AID 791**, incorporating [PR #8](https://github.com/tomasz-twardzicki/MHI2-Carplay-Maps/pull/8).

- Emit the factory VW U-turn lane bytes: **114 left / 146 right**, replacing the ambiguous 128 in the reviewed U-turn range.
- Rebuild the maintained guidance JAR; status now reports **`MU1367-guidance-v1.4.2`**. The video core, MU menus, audio and optional card runtime retain their v1.4.1 bytes.
- Retain complete installation, Diagnostics, tuning, rollback and independent OEM reset, with exact v1.4.1 upgrade recognition and retained snapshots.

**Updating from v1.4.1 or v3 / v3r2 / v3r3 / v3r4:** disconnect the phone/adapter and fully reboot, then refresh both Toolbox menus and scripts from this SD. Run **Install / update CarPlay integration (reboot)**. The first invocation verifies the saved controller and backups, removes matching optional tuning and the preceding release/test layer, and requests a reboot. **Fully reboot disconnected, then run the same action again** to install v1.4.2. Final success: `MU1367_RELEASE_1_4_2_INSTALLED_FULL_REBOOT_REQUIRED`; fully reboot once more. Snapshots are retained. Read `START_HERE.md` for the complete procedure and supported baselines.

**Validation and limits:** the matching MU1367 firmware has the same 114/146 defaults; host tests exercise the actual decoder, factory lane builder and serializer. The PR reports successful vehicle rendering on MU1161 + AID 791. MU1367 U-turn rendering and final-package vehicle acceptance remain pending. The reviewed mapping covers −180…−170° and 170…179°; exactly +180° selects left for right-hand traffic. ±169° retains its previous encoding.

The unresolved Mini Pico card override and other documented limitations remain. Other firmware (including P4521), AID 790 and MU1427 require their own packages. Verify the ZIP using the attached `SHA256SUMS.txt`. Earlier release assets are preserved.

Thanks to [@chrzanowy](https://github.com/chrzanowy) for the U-turn fix and MU1161 vehicle test.
