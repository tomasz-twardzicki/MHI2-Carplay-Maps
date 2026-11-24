# GPS implementation worklog — 2026-11-20

Version v1.6.4-e-test1 is built separately from sealed v1.6.3-e-test3. All earlier package archives remain unchanged.

Implemented passive exact-executable NMEA capture with bounded memory-only callbacks; Unicode temporary lifetime follows OEM disassembly, including short-string storage at offset 12. A worker publishes a fixed 320-byte WGPS snapshot. The protocol core validates original GPGGA/GPRMC bytes and fix age, preserves phone-controlled subscriptions and submits location on the receiver native serial queue. Identification uses capability IDs 17/18, distinct from start-request IDs 1/2.

GEM options are canonical preferences inside the installed recovery directory. GPS is off by default; asset mismatch falls back to normal launch. One RAM claim per boot prevents repeated experimental source launches if DIO restarts. Both wrapper copies and the source library are managed targets; preference metadata does not alter installed receipts. Diagnostic exports include source/receiver state, the optional HMI probe and the boot-attempt marker.

Evidence includes host sanitizer cases, actual ARM source capture/publisher execution, factory J9 dispatcher/listener tests with and without verification and class-49 rejection, actual receiver parser/serial-queue/framing execution, all four firmware import profiles, launcher/wrapper checks, diagnostic export and complete installer/recovery fixtures. Tests control the Unicode conversion boundary, receiver queue UDP wakeups and absent remote phone. Vehicle NMEA availability and phone acceptance remain open.

Retained failures include earlier receiver fixture setup attempts, an unsupported implicit compiler-runtime import (removed by explicit memcpy), wrong fixture capture return address (corrected), and missing native networking on the virtual board. The input preload self-test fails with both exact published control and GPS candidate; restoring its test-thread priority also did not resolve it. Its comparison is diagnostic only. Plain input self-test and the separate production receiver timing/media/RHD/audio regression pass. Earlier host fixture setup used the wrong baseline integration checkout and omitted the factory zlib seed; final migrations use the saved v1.5.4 baseline fixture, without weakening production gates.

If the passive callback does not receive NMEA in the car, the next implementation is an OEM read-only service client, not fabricated coordinates or forced sensor settings. A late first fix currently requires reconnect.

Final review added an SD-side GEM helper that checks the installed layer, requires the existing factory mount command and remounts /mnt/app writable before preference mutations. Status remains read-only; a failed remount prevents preference writes. This is tested with the actual native tuning tool and an explicit QNX mount stand-in. Managed payload/controller bytes are unchanged by this SD-only addition.
