# Independent MU1367 vehicle-location source

The exact K4525/P4521 HW50/HW70 binaries confirm that DIO uses the ordinary
**`asi.navigation.esoposproviderfull.EsoPosProviderFull`** service. A separate
client is a viable replacement for the USB-dependent source. It is an ASI/COMM
RPC interface, not a device that accepts `read()` calls or a raw NMEA socket.

This directory contains the firmware contract and a tested WGPS source core.
**It does not yet contain a running ASI client or an installable GPS fix.**
GPS remains off by default in v1.6.7-e. This work is source-only and is not installed by that package. Historical sealed sources/packages are unchanged.

## Verified binding

| Item | Exact MU1367 value |
| --- | --- |
| Service | `asi.navigation.esoposproviderfull.EsoPosProviderFull` |
| Reply | `asi.navigation.esoposproviderfull.EsoPosProviderFullReply` |
| DIO's service instance | `3a8ac390-4251-11e3-9434-000c29e68a4a` |
| Service interface key | `995a4140-c7f3-5205-8335-d13059867b08` |
| Reply interface key | `2c5da29e-82ab-5b99-8f06-68cfdd97c847` |
| Generated factory | `/eso/lib/factories/libasimmxesoposproviderfullproxy.so` |
| Config RPC method | `15` (`0x0f`) |
| Data callback RPC method | `25` (`0x19`), `updatePosition` |

`updatePosition` contains three optional reference-counted values: a vector of
`CIString` NMEA sentences, an `sPosition`, and a vector of predicted
`sPosition` values. The native representation uses 12-byte `CIPtr`/shared-pointer
elements and `UnicodeString8` strings. These are ABI objects, not bytes that can
be cast to `char **` across a process boundary. The actual factory performs
presence/count/string/structure serialization and dispatch. Use that factory and
the matching COMM runtime; a standalone raw-socket parser would need the entire
COMM framing, registration and lifecycle protocol as well.

The provider keeps a client-indexed state/configuration tree. Full-service
`setConfig` at `0x121950` looks up the calling client before storing its mode,
period and flags. Its output workers and pending updates are also per-client.
The independent reader should configure its own registration and leave the VW
navigation client's configuration, GNSS device and DRController untouched.
This is supported by static code; simultaneous real-client operation is still
a required native/vehicle acceptance check.

## Correction to the old DIO source

The old capture's vtable slots 12/42 point to `0x1649c0`/`0x1649b8`. Their real
callback is **`updateASIVersion`**. Its own native log says `ASI version: %s,
is valid:%d`; the arguments are the interface-version string and validity.
They are not NMEA data. Being in `CNMEAProvider` was insufficient evidence.

The actual `updatePosition` implementation is `0x163920` (thunk `0x163918`);
it iterates the first callback argument's NMEA string vector. Earlier tests of
the capture core with injected NMEA strings did not prove this native callback
binding. Starting DIO without USB would therefore not repair the existing hook.

`audit-firmware.py` checks these log references, the old slots, actual callback,
factory RPC anchors, provider config branches and hashes on all four firmware
profiles. Results are in [FIRMWARE-CONTRACT.json](FIRMWARE-CONTRACT.json).

## Initial source configuration and unchanged receiver

Start with the per-client 32-byte `sConfig` equivalent to:

| Offset | Initial value | Meaning/evidence |
| --- | --- | --- |
| 0 | 1000 | Update period in milliseconds |
| 4 | 0 | Prediction length, byte field |
| 8 | 0 | Prediction duration |
| 12 | 0 | Required zero in the accepted provider branch; semantics not yet named |
| 16 | 0 | Dead reckoning disabled for the raw-GNSS trial |
| 20 | 0 | Map positioning disabled |
| 24 | 1 | Retain DIO's first output-selection flag |
| 28 | 0 | Retain DIO's second output-selection flag |

Do not label the two output flags as independently verified controls until
their factory round trip and actual output have been tested. The configuration
must be acknowledged before the source becomes eligible to publish.

With map/DR disabled, the provider accepts only a 1000 ms period. DR enabled,
map disabled allows 100–1000 ms; the map-positioning branch requires 1000 ms.
Prediction duration/length must remain zero outside the map-positioning branch.
The provider has its own GNSS UTC qualification (`Got GNSS time fix, UTC
timestamp is valid now`) and GGA/RMC generators. No HMI clock or map-matched
`PosPosition` is needed to construct those original sentences.

[source_core.h](source_core.h) copies original qualified GGA/RMC into the
existing 320-byte WGPS v1 snapshot. It requires an acknowledged raw-source
configuration and fresh valid sentences of both types. Capture time is
monotonic arrival time; the NMEA UTC/date and sentence bytes are never invented
or rewritten. Heartbeats do not refresh sentence timestamps. Disconnect,
invalid/no-fix data, repeated UTC and expiration invalidate the source lease.
The receiver's checksum/fix/time validation and serial iAP2 sender are unchanged.

The current receiver advertises location only when a valid source already
exists at IdentificationInformation. Start/qualify the client before connecting
CarPlay. If the source becomes ready afterward, reconnect CarPlay. A source
process restart changes its owner epoch and also needs fresh identification.
Do not require wireless acceptance to start this source: that would create a
startup dependency loop.

## Remaining implementation and car acceptance

1. Bind a separate typed ASI/COMM client with its own reply registration,
   bounded reconnect, config ACK and callback lifetime handling. Hash-gate the
   runtime/factory and verify actual factory encode/decode and two independent
   client configurations in QNX. No provider/DRController preload is proposed.
2. Add opt-in startup before receiver identification, exclusive ownership of
   the WGPS mailbox, invalidation on service loss, and clean shutdown on USB
   takeover/disable. Keep the broken passive DIO publisher from competing.
3. Export source registration/config/UTC readiness, callback rates and receiver
   `advertised/requested/sent` separately. A running PID or rising source
   heartbeat alone does not prove valid GNSS or phone delivery.
4. In a wireless-only car test, establish UTC/fix first, reconnect CarPlay and
   confirm source readiness followed by advertisement, phone request and sent
   packets. Check native navigation still works, then service/session loss and
   wired takeover. Those counters prove offered/transmitted data, not the
   iPhone's internal sensor-fusion choice.

Tunnel behavior is a later stage. WGPS v1 has two records and the receiver
advertises GGA/RMC only. Its validator deliberately rejects RMC estimated mode
`E` and estimated/manual GGA fixes. PASCD/PAGCD/PAACD/GPHDT are recognized by the
OEM iAP2 driver but are not emitted by this WGPS/receiver implementation.
Supporting them needs additional verified source/receiver capability, framing
and validity handling; a tunnel test is not a valid acceptance criterion for
the initial raw-GNSS-only source.

## Reproduce the checks

Run `audit-firmware.py --k4525 K_FIRMWARE --p4521 P_FIRMWARE --output REPORT.json`
with the existing pyelftools environment. This reads firmware images without
mounting, executing or modifying them.

Run `tests/test-source.py --output NEW_BUILD_DIRECTORY` on the build host. It
checks the consumer files against the sealed v1.6.6-e source hashes, exercises
the actual Identification/StartLocation/Data path and malformed/stale/replayed/
estimated/no-fix cases under AddressSanitizer and UndefinedBehaviorSanitizer.
[SOURCE-VERIFICATION.json](SOURCE-VERIFICATION.json) records 50,051 passing
checks, including 50,000 malformed inputs. This is source/protocol-core evidence;
`independent_client_implemented` and `on_unit_validated` remain false.
