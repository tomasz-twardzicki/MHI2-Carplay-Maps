# Native guidance loss after approximately 40 minutes

Reviewed capture:
`/Users/tomasz/Documents/github/personal/Logs/HMIcrashing/cpmap-diag-15220818`.

The capture establishes that the native guidance reader terminated because
it could not write its RAM output. RAM-disk exhaustion is the leading cause,
supported by a later explicit QNX `ENOSPC` error and several truncated outputs.
The evidence does not demonstrate a Java/JVM crash or a fixed 40-minute timeout.

## Evidence

| File | Observation | Meaning |
| --- | --- | --- |
| `ramdisk/carplay-route-guidance/status.txt` | `status=ended polls=22447 valid=22116 invalid=331 sequence=2684 bytes=32 reason=4` | The reader's `OUTPUT_FAILED` exit path, after substantial successful operation |
| `ramdisk/carplay-route-guidance/latest.bin` | 32-byte `RGM1`, serial 4651, kind 5, detail 4 | A terminal END record carrying the same output-failure reason |
| `ramdisk/carplay-route-guidance/adapter-status.txt` | build `7aa249357413c8a7`, `mode=0 context=0 releases=1 failures=0 error=0` | Last saved adapter status is inactive with an ownership release, under otherwise eligible OEM/CarPlay context |
| `ramdisk/carplay-route-guidance/adapter-status.tmp` | Empty | A later adapter-status write did not complete; saved counters need not describe subsequent activity |
| `ramdisk/carplay-now-playing-n1.status.new` | Empty | A separate writer was also unable to complete its status update |
| `ramdisk/carplay-cluster-supervisor.log` | `t_us=2744588000 event=diagnostics-mkdir-failed value1=28` | About 45:44.6 after boot, creating a directory on the same RAM disk failed with QNX errno 28 (`ENOSPC`) |
| `summary.txt` | J9 still listed; ring is 16,779,024 bytes | HMI process still exists in the export; video ring alone consumes approximately 16 MiB of RAM-file space |

The captured video log is 2,510,848 bytes, bridge log 1,389,056 bytes, and
session log 121,856 bytes. Those three logs total **3.84 MiB**; with the video
ring they account for **19.84 MiB**, before other RAM files. All three logs
end partway through a line. The last video-log timestamp is 39:38.747 after
boot and the last session-log timestamp is 39:47.628. This agrees with the
reported approximate failure time.

There is no `df` output or full RAM-disk inventory in this export. The exact
filesystem capacity, free blocks/inodes at the initial failure, first failed
write operation and its errno cannot be reconstructed. In particular,
19.84 MiB is a subtotal, not a claim that the RAM disk has a 20 MiB capacity.
The later explicit ENOSPC makes exhaustion a strong inference, while
`reason=4` alone only establishes an output operation failure.

## Why guidance disappears while CarPlay video continues

The released [reader](release/reader.c) exits on a failed mailbox write,
atomic rename, or status write. It kills its device worker and attempts to
publish an END record with detail `OUTPUT_FAILED=4`. This exact terminal
record is present in the capture.

[MailboxReader](bridge/MailboxReader.java) consumes END, marks the producer
ended and invalidates its model. [LiveBridge](bridge/LiveBridge.java) then
sets `mode=0`, relinquishes its native output and clears/restores the stock
state. The independent AltScreen pipeline can continue using its existing
mapped ring and MOST path. It does not need a fresh guidance mailbox or a
successful diagnostic write for every video frame.

The release reader's continuous mode has no 40-minute duration cap. Its
terminal reason is output failure rather than duration, worker timeout,
driver read failure or an overflow. No timer-width change is justified by
this capture.

The log ends with USB teardown at 45:39 and ignition/standby changes around
45:41; it does not contain the successful reconnect described by the user.
The standard reader's terminal END state does not restart itself on a phone
reconnect. Reconnect recovery may involve another lifecycle action or a
different instance of the symptom; this export cannot establish which.
Do not rely on reconnect alone to restart an ended reader.

## Consequences for MU1367 testing

The MU1367 integration uses the same reader source, so it shares this
fail-closed behavior when RAM output cannot be written. Its earlier video
baseline alone should not be treated as protected against growing logs.

The already prepared **settings-v2 step 3** replaces that video runtime with
the paired upstream v2 core/bridge/supervisor. Its source includes:

- Video-log limit: **256 KiB**.
- Bridge-log limit: **128 KiB**.
- Small managed-log limit: **64 KiB**, with periodic supervisor checks of
  its named auxiliary paths.
- Truncation of the same inode and append writes, rather than rotating an
  open writer into a deleted file that still consumes space.

These limits directly address the two largest growing logs in this capture.
They do not reserve space for guidance, bound every other process's RAM use,
or make the reader automatically recover from future output failures.
The 16 MiB ring is retained; its protocol/size has not been changed.

The existing full test ZIP remains unchanged, SHA256
`19a136685d1e55d8630bfe38146a75a8b999fad0198a3a0f850f075f631a50b9`.
No Java adapter or native payload was changed during this investigation.
Complete step 3 and reboot before the extended run; retain the earlier
installation, backup and rollback procedures.

## Reproduction and verification

Added [test-resources.py](../../MU1367/settings-v2/test-resources.py) and
[RESOURCE-VERIFICATION.json](../../MU1367/settings-v2/RESOURCE-VERIFICATION.json).
The test deliberately injects ENOSPC into only its temporary reader process;
it does not fill a real filesystem.

1. Mailbox payload write, mailbox rename and status-file creation failures
   each reproduce `status=ended reason=4` and the same terminal END record.
2. The actual MU1367 Java mailbox reader accepts both the captured record
   and the reproduced one as inactive, then returns unchanged on a repeated
   read; no malformed-record exception is required to explain disappearance.
3. The actual rebuilt core's logger and upstream shared logging helper were
   stressed through 120,000 completed writes/size checks. Observed high
   watermarks were 262,080 bytes for video and 131,072 for bridge logging.
   Another two checks verify that an existing writer still appends correctly
   after a separate descriptor truncates its inode.

This is accelerated host testing of the production source. It is not a
40-minute/90-minute vehicle endurance run or execution of the proprietary
MOST/DMDT hardware path. The audit pins the current bundle/runtime hashes
and the supplied input logs. Existing factory-QNX/Java checks remain in the
main [verification record](../../MU1367/settings-v2/VERIFICATION.json).

## Next vehicle check

With the complete new bundle installed, collect RAM usage shortly after
connecting, near 30/40 minutes, and after at least 90 minutes. On MMX:

```sh
df -k /ramdisk
ls -ln /ramdisk/carplaymaps-video.log /ramdisk/altscreen-most-bridge.log
cat /ramdisk/carplay-route-guidance/status.txt
cat /ramdisk/carplay-route-guidance/adapter-status.txt
```

From RCC, run the commands through `on -f mmx`. Capture diagnostic exports
before rebooting if the fault returns. Check that log sizes periodically
drop/stay bounded and the reader continues to report a non-ended state.
If it reports `ended ... reason=4`, preserve the logs and RAM usage first,
then fully reboot rather than repeatedly reconnecting or deleting arbitrary
RAM files. Never unlink the active mapped video ring to reclaim space.
