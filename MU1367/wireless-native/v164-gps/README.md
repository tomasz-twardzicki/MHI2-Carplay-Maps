# MU1367 v1.6.4-e-test1 — experimental vehicle GPS

This local test package adds an optional vehicle-location feed to v1.6.3-e-test3. GPS forwarding and the passive HMI GPS probe are off by default. Existing stable v1.6.1 and sealed test packages are unchanged.

The path is `OEM CNMEAProvider → WGPS RAM snapshot → accepted wireless session → receiver native serial iAP2 queue → LocationInformation (0xFFFB)`.

The source preserves original GPGGA/GPRMC sentences, checksums and UTC. It observes two NMEA callbacks in the exact K4525/P4521 DIO executable. It does not change sensor settings, OEM subscriptions, serial-port ownership or the wired driver. The phone must request location information after negotiation. This provides another location input; it does not force iOS to select an exclusive GPS source.

The receiver excludes malformed, duplicate, stale, future-dated, estimated and invalid-fix sentences. Producer PID/epoch, capture age, control context and accepted-session checks prevent old fixes crossing source/session replacements. The snapshot heartbeat does not refresh an old fix.

The package manages 45 targets, including the source library and both DIO wrapper copies. Its own GPS preferences live inside its recovery directory. Included removal restores the previous layer; complete OEM restore proceeds through the existing reboot boundaries and archives those preferences. This applies to recognized managed installations, not arbitrary third-party modifications.

Static firmware checks cover K4525/P4521 HW50/HW70. Verification records distinguish host tests, actual ARM/J9 execution, native receiver framing, controlled boundaries and vehicle checks still required. The source fixture controls native Unicode conversion/lifetime; the receiver fixture uses QNX pipes for internal UDP wakeups and has no phone endpoint. The published-control and candidate input preload self-tests both fail the same bounded fixture; that comparison is retained and is not reported as a functional pass. The separate receiver timing/media/RHD/audio regression passes.

Live passive NMEA availability during wireless, the native Unicode ABI on the vehicle, phone receipt and navigation accuracy remain unverified. A fresh valid fix is required during identification. Reconnect after a late first fix or producer replacement. If callbacks remain zero, a proper read-only OEM NMEA service client is the next step. The optional HMI probe is observational and never synthesizes NMEA.

See [installation and vehicle tests](START_HERE.md), [release notes](RELEASE-NOTES.md), [firmware evidence](FIRMWARE-GPS-VERIFICATION.json) and [verification](VERIFICATION.json).
