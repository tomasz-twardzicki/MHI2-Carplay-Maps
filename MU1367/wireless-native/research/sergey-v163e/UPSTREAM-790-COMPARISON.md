# omonob v3.2 / our 790 test 1: implementation comparison

Reviewed the exact Standalone release ZIP, not a newer repository snapshot.
Upstream ZIP SHA-256: `5b31522046f1abf397fc62723dc7a4a1c3a37e90559d3d48409c8e322b1a9cce`.
Our test-1 ZIP: `72b8a568f84ad361bb54505e866987d8588599f2e18554737b597c40cfe11f71`.
Machine evidence: [UPSTREAM-790-COMPARISON.json](UPSTREAM-790-COMPARISON.json).

The [public release](https://github.com/omonob/VW-MHI2-Wireless-Carplay-Maps/releases/tag/v3.2)
does not attach a separate implementation-source archive. This comparison uses
its actual installation scripts, configuration and packaged ARM binaries.
It does not claim a complete clean-source receiver rebuild.

| Map component | Our test 1 compared with omonob v3.2 |
| --- | --- |
| 790 receiver, launcher, feeder and maps library | All four byte-identical |
| 790 display config, cluster marker, altscreen config and geometry | All four byte-identical |
| Transport shim and common primary-video helpers | All five byte-identical |
| Wired 790 core | Older core `a4bb6ce6…`, instead of upstream `97ccb829…` |
| Raw TS/MOST bridge | Our v1.6.3-e `f1e7cefc…`, instead of upstream `6c5210ca…` |
| Cluster supervisor | Our v1.6.3-e `e525fb5b…`, instead of upstream `d078bd32…` |

The test-1 description of a “complete upstream 790 backend” was too broad: the
790 producer/profile was copied, while three map-runtime components came from
other generations. The comparison gives a concrete integration difference to
isolate, not evidence that any one component causes Sergey's noise.

The custom launcher removes the 791 receiver tap, verifies the exact 790 feeder,
and gives its PID/log a 790-specific name. The renamed log still contains
upstream `OMONOB_791_INPUT_*` text: both profiles use that source family. That
label is not evidence that the wrong feeder was installed. Disassembly of the
790 and 791 feeders confirms a byte-identical shared-ring publisher. Their
`flush_au` difference includes the periodic keyframe-request interval; it is
not a conversion from 1010×376 to 800×480.

The 790 producer advertises 1010×376, with a default `202,16,606,344` safe area.
Sergey's capture confirms both that negotiation and a matching High-profile,
level-3.1 SPS. The retained 791 bridge has a generic TS muxer; its embedded
startup clip is 800×480. Sergey reports that disabling the animation did not
remove the noise. There is no new capture to verify the saved policy, so that
observation is recorded as user-reported, without repeating the same test.

`check-790-mux.py` now exercises the actual retained bridge's AVCC-to-Annex-B
conversion and PES/TS builders using 60 synthetic 1010×376 High-profile frames.
FFmpeg decodes all 60 output frames byte-identically to the input under address
and undefined-behavior sanitizers. The tested source hash equals the exact
source shipped in test 1. This rules out a general inability of these software
builders to mux that size/profile; it does not exercise the live phone sample,
writer scheduling, the MOST link or the cluster decoder.

The upstream profile is explicitly `AID10.5-17PM`; the old 16e entry redirects
to that retained profile. The upstream [development notes](https://github.com/omonob/VW-MHI2-Wireless-Carplay-Maps/blob/main/docs/WIRELESS_DEVELOPMENT.zh-CN.md)
also distinguish pixel dimensions, physical dimensions, view/safe areas and
actual decoding. A successful install or negotiated width alone is not proof
of iPhone 16 Pro Max / reported iOS 27.3 video acceptance.

## Controlled comparison: test 2

Test 2 replaces all three map-runtime differences with their exact counterparts
from the same upstream v3.2 ZIP. It keeps the same 790 receiver/profile and
unchanged OEM-routed touch JARs. It has a new child root and first restores the
exact test-1 snapshot before installation, with a full reboot between them.
Unknown saved controllers and changed target files remain refusal cases.

This comparison removes the mixed map-runtime variable. It is not a confirmed
noise fix and does not port the separate 791 mirror renderer or custom 791
guidance/media/timing/RHD/tuning extensions to 790. If it still produces noise,
a captured live elementary stream and decoder/MOST evidence remain necessary;
additional safe-area changes would not distinguish those failure layers.

2026-11-23 follow-up: Sergey confirms that test 2's cluster navigation works.
This accepts the three-component runtime pairing as a vehicle result for his
setup; it does not identify which individual component caused test 1's noise.
The next investigation covers missing playback metadata and intermittent
cellular-call handoff. See [TEST2-FOLLOWUP.md](TEST2-FOLLOWUP.md).
