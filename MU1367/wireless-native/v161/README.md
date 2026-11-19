# v1.6.1-e-test2 wireless integration

The original v1.6.1-e failed the v3 vehicle test. Test2 corrects its launch/PID
race, protects fallback IDR requests, recovers missing avcC and refreshes late
RHD/LHD coding with a last-known boot cache. See [v3 findings](VEHICLE-V3.json)
and [factory command proof](PIDIN-COMPATIBILITY.json). The original ZIP is retained.

The candidate layers native wireless video and guidance over the exact released
v1.5.4 MU1367 / AID 791 package. Installation, tuning and rollback are described
in [TEST-PACKAGE.md](TEST-PACKAGE.md). Existing v1.6.0-e sources and distributions
are retained separately.

`PROVENANCE.json` pins the stable source/ZIP and the V3.1 receiver inputs.
`build-components.py` builds the owned receiver/input tap, launcher, tuning
helper, supervisor, bridge and guidance JAR. `assemble.py` stages them over the
pinned baseline and test1 dependencies with a separate recovery generation.
The final seal checks QNX transaction results and native/J9 reports, embeds the
source/evidence, and verifies every archive entry against its checksum.

The integration changes the receiver's requests in memory; it does not patch
receiver bytes or add another BAP/MOST writer. Third-party native inputs remain
hash-pinned. The same owned preload is explicitly scoped to the receiver and
input adapter, with different roles. Wired/AA retain their existing sources and
component identities.

The v2 logs establish why guidance was absent: the receiver received route and
lane messages on wireless component 1, while the existing adapter read only the
factory wired mailbox and accepted component 16. Short pre-acceptance bursts are
retained in bounded RAM, then published after acceptance at a rate the existing
16-event mailbox can retain for the HMI reader. Loss of acceptance invalidates
route state and the HMI lease expires if the producer stops.

Vehicle validation is still required for the full wireless feature set and the
frame-pacing/latency tradeoff. Native wireless media text and artwork are deferred.
