# MU1367 next prototype — not an installable release

This work follows the eight v1.6.5-e-test2 exports. See [the reviewed evidence and ordered work](../research/v165t2-review/REVIEW.md), [current progress](PROGRESS.md) and [checkpoint verification](CHECKPOINT.json).

Implemented in source and bench tested:

- Optional phone-requested BT profile release, with accepted-session/guard/identity/trust/idle-call checks, a five-second stabilization period, bounded retries and a short-failure circuit breaker. GEM choices are keep, profiles and status. Confirmation follows OEM profile state rather than asynchronous request dispatch.
- Retain unused prefetched manoeuvre roads through head changes. Trace actual f19/f20 submitted text, accepted/rejected status and blank reasons from the reader worker.
- Separate clock-repair attribution from correlation misses and PCR-lead rebases; retain the working smoothing and timing decisions.
- Export the new status and road histories in combined and standalone diagnostics. Private BT command/authorized-peer files are excluded.

Full ACL release, stale-address/last-phone fallback, reason-aware Wi-Fi-first reconnect, raw GNSS/UTC and the main-screen startup freeze remain open. This prototype does not establish complete BT-stack shutdown or solve reconnect ordering.

Build/recovery/version metadata still contains copied test2 placeholders. Do not install or package this directory. A candidate needs a distinct recovery root, exact test2 migration, firmware and complete install/remove/OEM-restore validation. Sealed test2 and stable release sources and ZIPs remain unchanged.
