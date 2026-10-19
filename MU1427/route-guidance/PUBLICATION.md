# B3/B4 bounded driver publication

**B4 bounded publication validated on-unit.** Four snapshots show enabled,
advancing events, stop clearing and a new allocation on a later connection,
with no producer fault. See [B4-RESULTS.md](./B4-RESULTS.md), the earlier
[B3 activation defect](./B3-RESULTS.md) and the
[TEST-B4.md](./TEST-B4.md) install/restore procedure. B3 extends
the working B2 receive path with a read-only virtual file:
`/dev/ipod0/rgi-events`. The SD collector reads it once, and the host reader
checks its format and event sequence. No native cockpit/HMI output is enabled.

This uses the driver's existing resource-manager filesystem instead of writing
PPS from its receive thread. A future consumer can poll this interface and
publish state independently; a blocked consumer cannot hold an iAP2 receive
buffer or a producer lock. No new background thread, import, writable ELF
mapping, file descriptor or OS call is added to reception. The B2 logger still
runs as before; this change does not remove its existing synchronous logging.

## Verified native interfaces

The input driver is the exact factory MU1427 SHA-256 recorded in
[B2-RESULTS.md](./B2-RESULTS.md). Relevant disassembly:

| Function / location | Verified behavior |
| --- | --- |
| `fsys_init_entries`, `0x8d24` | Root array at driver `+0x114`, count at `+0x118`; entries are `0x88` bytes |
| Entry `+0x70/+0x74/+0x78` | Kind, index, name; kind 0 is an ordinary named root entry |
| Entry `+0x7c/+0x80` | Child pointer/count; B3 uses pointer for its pool and leaves count zero |
| Entry `+0x84` | Unused extension word; B3 tag `0x3349` |
| `fsys_find_attr_by_name`, `0x90b4` | Resolves name from the root array; existing lookup unchanged |
| `fsys_read`, `0x9260` | `(driver, ctp, io_read_t, ocb)`; OCB attr pointer at 0, private offset at `+0x80`; read size at message `+4`, xtype at `+8` |
| `iofunc_attr_init` PLT `0x494c` | Stock file mode `0x8124` (`S_IFREG | 0444`) |
| `iofunc_read_verify` PLT `0x4bb0` | Used before the custom read, with the stock argument layout |
| `MsgReply` PLT `0x4cf4` | `(rcvid, byte-count status, buffer, byte count)`; stock `_RESMGR_NOREPLY=0x80000000` |
| `wait_for_state`, `0x10ab4` | `clock_gettime(2, timespec)`; two 32-bit seconds/nanoseconds words |
| PPS helpers, `0x1faac/0x1fc5c` | Call synchronous `write` PLT `0x4a54`; unsuitable as a new receive-thread publication call |

`publication-hooks.S` calls only the original allocation/memory/iofunc/reply/
clock PLT entries. Initialization adds a root entry before exposure, preserving
the old entries and mount pointer. Failed allocation or clock read leaves the
original driver available without the new file. New buffers belong to the
driver allocation/process lifetime; no separate process survives its unload.
Repeated publication initialization is not a supported operation.

The factory caller is `iap2_start_features` at `0x6394`: filesystem creation
occurs **after identification**, not before it. B3 tried to enable the channel
at identification while the pool was absent. B4's `publication-activation.S`
wrapper at `0x909c` calls initialization and then enables the new pool before
the unchanged `0x63f0` start-message hook. `patch-activation.py` reproduces the
fingerprinted B3 image and adds this wrapper plus B4 log labels. The remaining
producer/read code and handoff format are unchanged.

Additional hooks:

| Address | B3 action |
| --- | --- |
| `0x909c` | After successful stock filesystem initialization, allocate pool and append read-only entry; retain stock epilogue/result |
| `0xe138` | Start a fresh publication session before the B2 identification component hook |
| B2 `receive_guidance` (`0xb5120`) | After B2 frame validation, copy the TLVs and resume its existing log/dispatch/cleanup |
| `0x9260` | Serve only the exact tagged publication entry; other files execute the original read prologue/path |
| `0x10ba8` | Disable/empty publication before native link destruction, then execute the original prologue |

`patch-publication.py` reproduces and fingerprints B2 first, then extends the
same RX mapping and changes fixed-width log labels to B3. Original mappings,
QNX note, dynamic tables, relocations, protocol bytes and config are preserved.
The B2 patch source, binary and tested toolbox ZIP remain available unchanged.

## Memory and consistency

The pool is **33,088 bytes**: a 64-byte header and sixteen 2,064-byte slots.
Each slot stores a 16-byte record header and up to **2,048 TLV bytes**. Receive
does one exclusive-access lock attempt, writes one bounded slot, advances the
sequence, and releases. It never spins, allocates, opens, writes or waits.

This is a rolling history, not an unbounded reliable queue. Old entries are
overwritten once sixteen newer events arrive. A reader detects missing
sequences and invalidates old guidance. If a producer cannot acquire the lock,
sees an oversized payload or exhausts sequence space, a **sticky fault** marks
the channel invalid. Identification starts a new session and clears history;
it does not clear a fault. Recover a fault with a fresh driver process/full
reboot. The iAP2 packet still follows B2's normal return/recycle path.

Snapshot reads run on the existing resource-manager request thread. They
allocate one temporary copy, make at most **three** seqlock attempts, reply,
then free it. A changing/busy writer returns `EAGAIN` (11); allocation failure
returns `ENOMEM` (12). No producer lock is taken by a reader. Requests below
33,088 bytes return `EINVAL` (22); a second read on the same open returns EOF.
Read once with the firmware-verified `dd` operands, reopening for each poll:

```sh
dd if=/dev/ipod0/rgi-events of=/tmp/rgi-events.bin bs=65536 count=1
```

On the unit prefer the packaged C3 collector, which uses the SD path and checks
the output size. The virtual file's stat size is zero; normal size-based file
capture would produce an empty file. Reading `/net/mmx/dev/ipod0/rgi-events`
from RCC uses the same handler. QNX resource-manager registration, allocation
behavior were exercised by the B3/B4 C3 captures. Their summaries show reads
on MMX directly; Qnet reads from RCC remain unvalidated. B4's active pool/data
path is validated by all four binary snapshots and exact log-payload matches.

## Wire format (little-endian handoff header)

The enclosed iAP2 TLVs keep their original **big-endian** encoding.

| Byte offset | u32 field |
| ---: | --- |
| 0 | ASCII `RGI1` |
| 4 / 8 | Version 1 / total bytes 33,088 |
| 12 | Even snapshot version; odd while a producer is modifying the pool |
| 16 | Identification session counter |
| 20 / 24 | Last event sequence / retained count (maximum 16) |
| 28 | Sticky loss/fault (0 or 1) |
| 32 | Producer lock; copied snapshots require zero |
| 36 | Enabled (0 or 1) |
| 40 / 44 | Allocation's monotonic seconds/nanoseconds, identifying its lifetime |
| 48–63 | Reserved zero |

Slot `(sequence - 1) & 15`, at `64 + slot * 2064`:
u32 sequence, u16 message ID, u16 TLV length, u32 session, u32 reserved zero,
then TLV bytes. Sequence starts at 1 per identification session. Disabled
snapshots have zero last sequence/count. Old unused slot bytes are retained
but are not valid events; snapshots therefore still contain private data.

The allocation timestamp distinguishes new driver lifetimes on the running
unit; it is not a persistent identity across boots. A consumer must reconnect
and invalidate across unit reboot, device removal and any stale-data deadline.

## Reader and model

`rgi_publication.py` validates the complete snapshot before applying events to
the [guidance cache](./DECODER.md). It deduplicates overlapping polls, checks
instance/session/slot identities and invalidates on gaps, faults, disconnect
or malformed data. A late first reader reports the missing history; absence of
an older maneuver record remains unknown rather than selecting a different
cached maneuver. This host reader is a contract/test tool, not an installed
polling service. [C4](./OBSERVER.md) adds a manually started diagnostic recorder
with a stale-data deadline. Its [first on-unit recording](./C4-RESULTS.md)
retained 236 of 237 events across reconnect; one startup burst exceeded the
ring. The [C4-2 follow-up](./C4-2-RESULTS.md) retains all 240 published events,
with fresh current-maneuver selection and distance progression, route-stop
clearing and normal reconnect. Arbitrary bursts can still exceed the bounded
ring. No PPS/HMI consumer or automatic reader startup is installed.

`Consumer.consume(..., emit=callback)` optionally emits state after each new
message, including selection that is subsequently cleared within the same
window. The entire window is validated before any callback. Repeated polls
emit no already-processed events; a reset can cause retained events to be
processed/emitted again. Output is detached from the cache and uses the same
privacy defaults as the window summary. C4 exposes this as `--messages` on
the host.

```sh
python3 MU1427/route-guidance/rgi_publication.py "$CAPTURE/rgi-events.bin"
python3 MU1427/route-guidance/rgi_publication.py "$FIRST/rgi-events.bin" "$SECOND/rgi-events.bin"
```

Default output omits route text, distances and times. `--include-private`
explicitly includes them. Keep binary captures and private output outside git.
The normal log decoder also accepts B3's labels for a full-session replay.
It now also accepts B4. For active-route captures use `--expect-publishing`:
the CLI then fails an initialized-but-disabled/all-zero buffer instead of
accepting structural validity as evidence that publication started.

## Offline checks and next test

Historical B3 checks passed 22 ARM and 25 installer tests but missed native
initialization ordering. B4 adds the lifecycle regression and a real B3
route/lane replay. The decoder suite has 47 tests, the publication reader 13
(including the disabled-buffer acceptance check), and the unchanged C3
collector 11. The installer suite
uses only the base toolbox utilities in PATH. C3 uses the existing verified
`dd` operands and makes one snapshot read, with no retry loop.

The ARM suite executes publication plus native lookup/readdir/receive/recycle
branches at two load addresses. OS allocation, clock, iofunc verification and
reply are mocked; the ARM instructions, exclusive accesses and barriers execute.
It covers bounded reader/writer failure paths, initialization failure, session
reset, native-file fallback and 1,000 received guidance frames at each address.

Optional private integration replay feeds all **167 real B2 guidance messages**
through the ARM driver, obtains a snapshot reply after each, and compares the
consumer state with direct decoding after every event. No input data is printed
or committed. Set `CPMAP_PRIVATE_B2_LOG` when running `test-publication.py` to
include it; the ordinary suite requires only the fingerprinted factory driver.

Use [TEST-B4.md](./TEST-B4.md) for the tested on-unit package and rollback.
[B4-RESULTS.md](./B4-RESULTS.md) records the successful bounded transport test
before a continuously polling runtime consumer is added. The active snapshot
also demonstrates that a late sixteen-event window can contain only route
deltas and miss the current maneuver's earlier record. The [C4 diagnostic recorder](./OBSERVER.md) is implemented to test polling
cadence/bursts, detect gaps, and clear stale state on device loss or deadline
expiry. [C4-RESULTS.md](./C4-RESULTS.md) records its first hardware result;
[TEST-C4.md](./TEST-C4.md) includes the follow-up before any HMI output.
The next consumer may read this file directly or publish PPS outside iAP2;
neither requires adding synchronous PPS writes to reception.

The [native bridge model](./NATIVE-BRIDGE.md) now defines descriptor/distance
replacement and independent ownership/freshness guards on the host, using
the exact MU1427 service contracts. It publishes no PPS/HMI data; the live
consumer and Java adapter remain a separate integration stage.
