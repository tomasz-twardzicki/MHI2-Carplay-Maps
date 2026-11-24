# MU1367 CarPlay location source — 2026-11-19

OEM wired CarPlay has a vehicle-location path. The MU1367 iAP2 configuration enables `[location]`, with GPGGA/GPRMC NMEA sentences. The exact OEM driver implements location subscriptions and `gps_info_send`; its identification table defines parameter 22 as `LocationInformationComponent`. OEM `dio_manager` contains the NMEA provider and iAP2 GPS-send handling.

The current native wireless receiver does not advertise that location component. An isolated QNX test executed the unmodified pinned receiver's actual iAP2 parser and captured its generated IdentificationInformation response. It advertised parameters 0–9, 12, 13 and 24; parameter 22 was absent. Its outgoing/incoming message lists cover authentication, NowPlaying and guidance, with no location-message support. The owned wireless extension also has no vehicle-location producer. This applies to the receiver shipped in stable v1.6.1 and experimental v1.6.2-e-test1.

Consequently, the current wireless implementation relies on iPhone positioning. OEM wired CarPlay can supply the car's position to the iPhone. This is not an exclusive GPS-source switch: Apple describes vehicle satellite data as an additional input alongside iPhone sensors. See [Apple's CarPlay sensor explanation](https://developer.apple.com/videos/play/wwdc2016/722/?time=774).

The existing logs do not show live wired NMEA output or iOS's internal fusion decisions. Confirming rates and freshness on the car would require observing the outbound location packets. The wireless omission itself is verified by the actual receiver's advertised capabilities, not inferred solely from missing log entries.

[Machine-readable evidence](GPS-SOURCE-AUDIT.json). This investigation leaves the sealed test package unchanged.
