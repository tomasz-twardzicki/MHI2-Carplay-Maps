# v1.6.1-e-test2 correction record

The original v1.6.1-e failed the v3 vehicle test. Its sealed ZIP is retained.
Test2 uses a separate v161t2 recovery generation over the same exact v1.5.4
base. The original v161 layer must first be removed/recovered and rebooted.

Changes: nonblocking launcher; full-name controller checks preserving its PID
through preflight/exec and supporting stop during preflight; strict accepted
session checks retained; old periodic input IDR suppressed only with fresh proof
of actual receiver cadence; bounded bridge IDR retry while avcC is absent;
OEM coding cached independently of pairing and refreshed on /info requests.
Live coding overrides cache. First uncached boot can require one reconnect
once HMI coding is available; no unverified side is guessed.

The native dictionary test uses the receiver's own plist parser with server
options=0 and its actual RHD /info tail. A full /info builder call before
receiver main reaches hardware-dependent CF preferences and cannot complete in
this isolated fixture; no full HTTP/phone negotiation is claimed. The delayed
launcher fixture uses real QNX names, PID-preserving exec, exact factory pidin,
ksh, grep and sleep, plus hardware-free child executables. It caught pidin's
18-character default truncation and verified the explicit full-name format and
trailing-space handling against matching K4525/P4521 HW50/70 utility bytes.
Factory-J9 checks cover file sync/rename and preserving cache for unknown coding;
RAM and persist use separate fixture paths, as on the car.

Final sources/components and all evidence are recorded in generated
VERIFICATION.json and the ZIP's WIRELESS-VERIFICATION.json. Vehicle validation
of test2 remains pending. No commit, tag or publication is performed.

---

The following is the historical original v1.6.1-e implementation record, whose
component paths/hashes describe that earlier candidate:

# v1.6.1-e implementation record

The local experimental candidate is based on the exact released v1.5.4 ZIP
(c56fa5187ad11895d29ac5c61ae9b29a963bf4b1fc552ea14fe06f23e4e48ba0),
source commit 97bcb04. The prior test1 sources/distribution remain intact.

Final components are built in `build-v161-components-r8`; an independent
`build-v161-components-repro` rebuild is byte-identical. The full staged SD is
`build-v161-stage-r4`, build ID **MU1367-wireless-native-v161-9fa71c6f6dcb**.

Implemented: automatic AID activation; OEM RHD/LHD forwarding with a RAM-only
per-unit config merge; native wireless route/lane publication and source-specific
component1 selection; 40 FPS/IDR8/150ms defaults; GEM tuning and collector support;
phone-derived timestamp matching and adaptive smoothing before TS muxing; safe
late skipping through a queued IDR; preservation of recovery keyframe requests;
separate v161 snapshot recovery restoring the v1.5.4 base.

v2 explains the missing guidance: 47 route updates, 18 maneuver messages and six
lane messages were received on component1, while the adapter read the wired
mailbox and selected component16. Raw messages are retained unchanged. A bounded
pre-grant queue and initial empty heartbeats protect source acquisition and the
initial maneuver burst. Native wireless media text/artwork are deferred.

Verification completed:

- Exact receiver parser/display/queue/CF routines under factory QNX, production
  ARM shim and complete owned/transport/maps preload chain. Pre-grant retention,
  disconnect clearing, timestamp identity, 20/25/30/40 requests, selected IDR8
  cadence, recovery-request preservation and RHD/LHD merge checks passed.
- Native imports resolved against fresh K4525 and P4521 firmware, both HW50/70.
- Exact MU1367 ARM/J9 with verification on/off: component1, implicit lane
  component, wired/AA isolation, lease, factory builder/serializer regressions.
- All 19 stable guidance regression programs, including ETA/arrival, plus
  ASan/UBSan policy checks and C mailbox -> Java -> factory lane output.
- Native tuning persistence/default recovery, four launcher hash pins,
  rejected inherited preload, scoped pre-exec contract (exec stubbed, no receiver
  hardware main), explicit alt-off policy, and plain/scoped input selftests.
- All39 final transaction targets passed injected rollback and simulated-power-
  loss recovery, exact preimage checks, old snapshot preservation and drift/
  corrupt-backup rejection. Clean reports are final-batch0/1/2a/2b/3. Larger
  repeated-install fixture runs hit VM memory limits, so clean coverage uses
  fresh boots. The fixture substitutes only its fake JXE gate; production keeps
  the exact firmware gate. A real vehicle installation is not claimed.
- v154 retained-session archive collision checks passed with factory utilities.

The seal verifies all results and guard/menu/checksum paths, bundles sources and
reports, then reads back every ZIP entry. `VERIFICATION.json` is generated from
those reports. No commit, tag, publication or on-vehicle validation is claimed.
See TEST-PACKAGE.md for the required remove-test1 -> install-v154 -> enable-v161
reboot sequence and the remaining vehicle acceptance checks.
