# MU1367 OEM input routing and experimental 790 profile

Isolated follow-up to Sergey's v1.6.3-e feedback. See [START_HERE.md](START_HERE.md)
for the test procedure, rollback and feature limits. No published asset is
replaced by this candidate.

Vehicle follow-up: Sergey reports that OEM touch is fixed, but the 790 map
shows static noise. The capture confirms a 1010×376 live stream preceded by
the retained 800×480 startup clip. See
[790-NOISE.md](../research/sergey-v163e/790-NOISE.md) for the evidence and the
**Startup animation → Off** comparison, which Sergey reports did not fix the
noise. Test 1 is not accepted. See the
[upstream comparison](../research/sergey-v163e/UPSTREAM-790-COMPARISON.md)
and [test-2 procedure](START_HERE_TEST2.md) for the next isolated comparison.

2026-11-23: Sergey confirms that test 2's 790 map works. The subsequent report
identifies missing playback information and intermittent cellular calls that
use the OEM UI and fall back to iPhone audio. Test 3 adds the 790 metadata port
and an opt-in, addressed Bluetooth-profile handoff comparison. See
[START_HERE_TEST3.md](START_HERE_TEST3.md). New playback/call behavior still
requires vehicle confirmation; the accepted test-2 map stack is retained.

The input change restores the exact factory `updateTouchInput` method while
retaining the wireless bootstrap. The fake wireless DSI service forwards
only post-hit-test `postTouchEvent` touchscreen press/release messages using
the pinned receiver's WT1 packet format. It does not use the foreground flag
to intercept all raw touches. Host tests exercise the real CP dispatcher and
loopback UDP; the matching factory ARM/J9 loads/verifies both patched classes.

Test 1 uses the SHA-pinned upstream 790 receiver/profile without the 791 tap,
but retains an older wired core and the custom v1.6.3-e bridge/supervisor.
`package.py --upstream-790-runtime` stages test 2 with all three matching
runtime components from the same upstream v3.2 ZIP. Child transactions snapshot all modified
files, preserve the parent recovery identity, validate mutable geometry as
data, restore before profile changes/removal, and retain collecting/prepared
snapshots safely. Safe-area edits are bounded to a 1010×376 stream.

`build.py` creates the input JARs; `package.py` stages the full test SD;
`tests/test-profiles.py`, `tests/test-qnx.py`, `tests/test-j9.py` and
`tests/native-audit.py` verify the separate runtime boundaries. `seal.py`
requires passing reports and checks the complete deliverable on readback.

The 790 producer omits the custom 791 guidance/media/timing extensions. The
single-contact input limitation and call transport still need acceptance
before promotion; Sergey's OEM overlay touch fix is user-confirmed. The initial diagnostics were
captured outside the failing native-wireless session and cannot prove its
live call-audio ownership.
