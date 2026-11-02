Adds **experimental P4521 support** to the complete **MU1367 + AID 791** Toolbox, based on v1.4.2.

- Recognize **MHI2_ER_VWG13_P4521 MU1367** explicitly and allow the complete integrated installation. K4525 support is retained; exact firmware/hash checks remain in place.
- P4521 receives all current features: maps, native arrows/countdown, ETA/current road, recommended lanes, audio metadata/artwork, MU settings, reconnect recovery, optional turn cards, Diagnostics, rollback and independent OEM reset.
- Retain the **v1.4.2 VW U-turn lane fix** (114 left / 146 right). All six runtime payloads are byte-identical to v1.4.2, so guidance status continues to report `MU1367-guidance-v1.4.2`; the package/menu/controller version is v1.4.3.
- Defaults remain **30 fps / IDR5, turn cards OFF**, with optional card runtime and controls installed together.

**P4521 remains experimental.** The earlier P4521 experimental build has been tested and confirmed working in a vehicle. This does not claim vehicle acceptance of the new combined v1.4.3 package or resolve the existing Mini Pico card override and app-specific limitations.

**Updating from the separate P4521 v1.4.0/v1.4.1 experimental bundle:** refresh both Toolbox menus and scripts from this SD, select **Recovery > Restore complete OEM state**, fully reboot with phone/adapter disconnected, then select **Install / update CarPlay integration (reboot)**. The reset verifies originals and retains old layers, snapshots and saved settings. Use the same reset path for dormant upstream menu JARs. The known P4521 v1.4.1 settings controller is recognized and directs you to recovery before install writes.

**Updating from integrated v1.4.1/v1.4.2 or supported v3 revisions:** run the single install action, reboot when migration requests it, then run the same action again. Final success is `MU1367_RELEASE_1_4_3_INSTALLED_FULL_REBOOT_REQUIRED`; fully reboot again. Read the attached `START_HERE.md` for full instructions.

When RCC train data is available, installation/status reports `P4521_EXPERIMENTAL` or `K4525`. Without RCC data, the identical pinned firmware is reported as `K4525_OR_P4521_HASH_MATCH`. A different reported train or firmware hash is refused.

Verify the archive with the attached `SHA256SUMS.txt`. Earlier releases and assets remain unchanged. Thanks to [@chrzanowy](https://github.com/chrzanowy) for the retained U-turn fix.
