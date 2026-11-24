# v1.6.5-e-test1 review — 2026-11-23

Five overlapping exports from one boot, covering connection and reconnect tests. [Analysis](analyse.py), [sanitized evidence](EVIDENCE.json) and [factory fields/symbols](FACTORY-API.json). All exported checked runtime fingerprints match sealed test1 (`af2ef5f8…98e4eca`). Counters from different exports are snapshots, not independent drive totals.

## Confirmed improvements

The user reports artwork on MU and AID every time, with seven covers across the two sessions. The three standard captures show successively 3, 5 and 6 fetches with zero errors; the final standalone export is later. This validates the reported end-to-end improvement, while avoiding summing overlapping counters. Keep media and decoder bytes unchanged.

Timing matches are complete in retained summaries: session 1 ends at 4,174/0 matches/misses; session 3's last retained minute reports 2,738/0. Thirty-one unique retained audio samples have output equal to MPL5 writes and no inactive/error counts. The user supplies the longer continuous-audio observation. PTS gaps and smoothing demand are not wall-clock presentation latency.

## BT: wrong symbol authority confirmed

Test1 rejects the resolved write slot on every recorded attempt. The last status is installed=0, timed_out=1, attempts=56. The captured open address `0x101ae18` minus the matching firmware libc's open offset `0x1ae18` gives base `0x1000000`. Captured write `0x101d1a4` minus its libc write offset `0x1d1a4` gives exactly the same base. The write slot is therefore consistent with the actual pinned libc export, not an arbitrary nearby function. The global lookup address/name was not recorded; the exact source of that mismatch remains unproven.

Test2 resolves both canonical targets from a named `libc.so.3` handle, checks their audited relative contract, and compares slots only against those native targets, the known resolver or our own hook. It logs global, canonical and slot addresses plus dladdr object/symbol identities. Real competing hooks remain refused. The native QNX test intentionally makes RTLD_DEFAULT write differ from libc, verifies native call-through, and exercises the pinned close/reconnect/resend decisions. Physical BT-off survival still needs acceptance.

The retained btwcp history contains two failed ACL attempts and OEM ACL reuse afterward, consistent with the reported long reconnect. Accepted-session suppression starts only after a fresh live owner; it cannot repair the pre-acceptance stale-phone order. That remains separate work.

## Road text: separate producer fields exist; consumer selection unknown

Exact MU1367 NavSD has CurrentPositionInfo (function 19, positionInfo, 97-byte BAPString) and TurnToInfo (function 20, turnToInfo, 76-byte BAPString). Test1 only overrides the latter, so next-road selection goes everywhere the cluster consumes that field. Test2 adds independently refreshed current-road output on function 19 while retaining next/current/off on function 20. Both use existing route/source ownership and freshness gates; queue rejection and clear/OEM takeover are handled separately.

Factory ARM/J9 tests prove the two actual stages emit different strings. They cannot establish how the cluster firmware chooses the middle and dial labels. If both remain tied to TurnToInfo, a transmitter-only NavSD change cannot force different text into those two consumers. Test on the car before claiming the requested split works.

## Startup and reconnect timing remain open

The retained first-session detail reports `MOST write failed: Not enough memory` before the queue grows through 1,076 and 1,863 packets. Existing startup recovery reclaims/reopens the MOST channel at uptime 117.229 s. This is a driver-write ENOMEM result, not proof that all system RAM is exhausted. It then shows an actual queue-limit recovery at sequence 622 (`queued=2078`, limit 2048), followed by a second recovery at sequence 631 with no queued packets. The summary reaches queue_hi_total=2078, two resets and timestamp rebases. The second reset is explicitly `most-reclaim-resync`, so these are not two independent overflows. Session 1 bridge stop is at 283.223 s boot uptime; session 3 starts later after reconnect. The next bridge start is at 344.351 s, a 61.128-second gap. Retained first-minute PTS step is 374 ms for session 3; later complete-minute maxima are 175 ms or less. These are PTS intervals, not direct screen presentation measurements. Seven unique decoded-cover events are retained across sessions 1 and 3.

Do not raise the queue limit, bypass recovery or alter the working smoother on that evidence alone. Keep 40/8/150 and the bridge/tap bytes for the BT/road comparison. Missing physical presentation timing and pre-acceptance phone arbitration remain open. GPS raw-source/UTC qualification is unchanged and forwarding stays off by default.
