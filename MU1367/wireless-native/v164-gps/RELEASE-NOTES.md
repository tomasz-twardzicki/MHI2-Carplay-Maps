# v1.6.4-e-test1

Experimental vehicle GPS forwarding, disabled by default. The receiver advertises the exact OEM location component and GPGGA/GPRMC capabilities only with a fresh valid source, honors phone Start/Stop requests and sends original NMEA on its native serial queue. Fix validity, monotonic age, UTC progression and source/session ownership are checked.

Adds hash-gated passive DIO capture, atomic RAM snapshots, once-per-boot source attempt protection, GEM GPS on/off/status and a separate passive GPS diagnostic probe. Both DIO wrapper copies and the source library participate in managed backup/restore. The normal and wireless diagnostic exports include GPS evidence. GPS preferences belong to the recovery layer and are archived by complete OEM restore.

Retains test3 BT session guard, artwork diagnostics, native timing/IDR reconnect fixes, reverse return, audio/input priority changes, RHD layout, OEM icon label and existing guidance/media integration. BT profile release remains opt-in. No additional fix is claimed for Wi-Fi-first arbitration, track skip delay, radio jitter or native main-screen frame demand.

Vehicle acceptance remains open: passive NMEA availability without wired CarPlay, native callback ABI, phone subscription/receipt, stale-fix behavior and positioning accuracy. Fresh fix at identification is required; late fix/producer replacement requires reconnect. Controlled emulator boundaries and the shared baseline input self-test failure are recorded in verification data. No public upload is made by this build.
