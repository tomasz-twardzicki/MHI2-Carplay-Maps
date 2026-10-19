# B3 on-unit result (2026-10-17)

**Read-only file registration and C3 reads worked; event publication did not.**
All three captures contain the exact B3 driver, valid OEM backups and complete
33,088-byte snapshots. Every snapshot is a newly initialized, disabled buffer:
session/sequence/count/snapshot-version/fault all zero. Guidance reception and
the existing CarPlay link continued. B4 corrects the activation ordering;
see [TEST-B4.md](./TEST-B4.md).

The user reports the first navigation attempt lacked the route line on the
AID map and the turn card did not update with distance. The second attempt
and third attempt after reconnecting looked normal. The captures remain
useful despite differing from the requested test sequence.

## Private inputs and reception

Inputs under `Logs/B3/`; raw logs/snapshots are not included in the repository.

| Capture | iAP2 log bytes | Route `5201` | Maneuver `5202` | Lane `5204` | Full-log final state |
| --- | ---: | ---: | ---: | ---: | --- |
| `cpmap-navrecon-C3-3698755` | 158,133 | 17 | 24 | 12 | Guiding |
| `cpmap-navrecon-C3-5058682` | 499,635 | 221 | 38 | 18 | Stopped |
| `cpmap-navrecon-C3-7049344` | 398,621 | 254 | 12 | 4 | Guiding, after reconnect |

The first log is an exact prefix of the second; do not add their counts.
The third log starts a fresh identification/start cycle. Across the second
and third logs there are **547 distinct received guidance records**:
475 route, 50 maneuver and **22 lane** records. Source is **Google Maps**.
Every record passes the current decoder's bounds and field-width checks;
lane information is still preserved as opaque nested TLVs rather than mapped
to cockpit graphics.

Each log contains one accepted identification and one successful B3 `5200`
submission. All three contain zero `Invalid packet`, `Failed to send packet`,
`No packets in receive list` or `IdentificationRejected` messages. In the first
capture, another 318 location messages and 318 incoming ACKs follow the final
guidance update. In the second, guidance ends with state-zero updates and 38
more location messages/ACKs. There is no B1-style receive-pool stall.

All active drivers match B3 SHA-256
`bfd79ed0c1a86d7ed48837d6ec4c766f2be024366d8376ceb730a1403854741d`.
Active config and both backups match the B2/OEM fingerprints in
[B2-RESULTS.md](./B2-RESULTS.md). All C3 summaries report zero read failures and
all progress files finish with `CPMAP_RGI_CAPTURE_OK`. The OEM archive is still
the exact historical error 42 from B1; it is not a new B3 failure.

## Publication defect and corrected ordering

The first two snapshots are byte-identical, with allocation timestamp
`(54, 241000000)`. The third has timestamp `(415, 194000000)`, distinguishing
the later allocation. All three have:

```text
magic=RGI1 version=1 bytes=33088
snapshot_version=0 session=0 sequence=0 retained=0
fault=0 writer_lock=0 enabled=0
```

This is not an overwritten rolling window, a short read or a sticky producer
fault: the channel was never enabled. A structurally valid empty snapshot does
not satisfy active-navigation publication acceptance.

The factory code establishes the ordering:

1. Identification invokes the `0xe138` hook. B3 tries to enable publication,
   but `publication_find` cannot find the not-yet-created file/pool.
2. After authentication/identification, `iap2_start_features` calls
   `fsys_init_entries` at **`0x6394`**, targeting `0x8d24`.
3. The hook at **`0x909c`** appends the new entry and allocates the pool, but
   B3's initializer leaves it disabled.
4. The feature epilogue at **`0x63f0`** submits `5200`. Incoming guidance logs
   correctly, while `publication_enqueue` sees enabled zero and returns.

The B3 tests initialized the pool and then explicitly enabled it. That sequence
tested the handoff but missed the real lifecycle. The earlier description that
filesystem initialization preceded identification was incorrect.

B4 changes only the filesystem-completion wrapper: after a successful native
initialization it allocates the entry/pool and **then enables that pool**, before
the unchanged feature epilogue sends `5200`. Its regression executes identify
before filesystem creation, reproduces B3's zero header, and checks that B4
publishes/recycles the first frame at two load addresses. Initialization failure
still preserves the stock success path without inventing a publication file.
The new driver does not change video or add a rendering consumer.

## First-session visual symptoms

The first capture contains only one maneuver-distance field, with no sequence
of changing maneuver distances. That is compatible with the reported stale
turn card, but **does not establish causation**: the third capture also has
only one such field despite navigation looking normal. iAP2 guidance and the
iPhone-rendered video/card are separate outputs.

The first capture's video bridge remains active and keeps forwarding frames;
the captures do not record whether the route line/card pixels were correct.
The `patch_failed_fingerprint` session-log entry also appears in both successful
B2 captures, so its presence alone is not a new B3 regression. The supervisor's
later stream-timeout fallback/restart occurs around the reconnect, rather than
establishing a first-attempt iAP2 crash. The visual issue remains unassigned.

New data for the future state/renderer work: current-road text is now nonempty,
per-maneuver distance is present in a few records, lane information contains
index/status/angle/highlight fields, and current maneuver lists include index
65535 alongside another index. Repeated state-zero/loading transitions and
incomplete later deltas can leave the conservative host cache without a current
maneuver even while route state is 1. These need interpretation before an HMI
consumer is enabled; a missing head must not become a guessed maneuver.

## Input integrity

SHA-256 of each `iap2.log`, in table order:

- `852c825e0d5879462c3afc50fcb658d96a65514db1b0f4239dd99c9e47643309`
- `9ac30a3ad414b2046592888bb7fcf0ba6808db613fe59120209ebe94185c3f26`
- `338f52bba05ea5dba7490c53c834a44e9d02561cf9458c115f96ca20a1e16bff`

Snapshot SHA-256: first/second
`9142832367b982e7ce0da8594e8ba42fc685f49fe039f3d8292b0d788743a759`;
third `ab01e83d1693569018ed6ae562d9941f613a168ad5a981a7a0e0fe56ccaf36cb`.
