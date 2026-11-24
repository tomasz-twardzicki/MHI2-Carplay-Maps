# MU1367 / 791 guidance reader recovery test

This reversible test addresses the native worker failure found in the
November 3 export (`cpmap-diag-8654921`). It is a vehicle
validation candidate, not a demonstrated fix for every long-run dropout.

## Install and test

Use `CarPlay_Maps_VC_MU1367_791_v1.4.3-e.zip`. This is the complete v1.4.3-based
release for K4525 and P4521 MU1367/AID 791, with an **experimental reader fix,
to be tested**. P4521 support retains the exact shared-firmware gates and its
experimental status. The v1.4.2 U-turn fix is included.

Disconnect the phone and wireless adapter, fully reboot, refresh Toolbox menus
and scripts, then use **Install / update CarPlay integration (reboot)**. Follow
[START_HERE.md](INSTALL.md) for migration and reboot messages. No separate reader
menu action is needed. Existing v1.4.3 installations also use the checked
retirement/reboot/install boundary. Optional turn-card tuning is handled by
that migration and remains supported after installation.

If the earlier standalone reader test is active, restore it and reboot before
this upgrade. Separate audio R1/R2 test layers must also be restored before
changing the base; their unpromoted runtime is not part of v1.4.3-e.

Exercise native guidance through a phone reconnect, then run for at least
90 minutes. Export diagnostics before reconnecting or rebooting if arrows
stop. If reconnect restores them, export again afterwards. Record the OEM
software train, phone/navigation app and cable/adapter identity.

The normal release transaction replaces `/mnt/app/carplay-mu1367/rgi-observer`
alongside guidance and saves the original reader in
`/mnt/app/carplay-mu1367-guidance-v3/backup/reader`. Java, the iAP driver, video
runtime and audio payloads match v1.4.3. Existing snapshots are retained.

## Recovery behavior

A missing or erroneous device read continues to invalidate output and poll.
For a worker timeout, pipe EOF or pipe-read failure, the parent immediately
publishes inactive guidance and attempts to kill/reap the failed worker.
A replacement is allowed only after reaping confirms no old worker remains.
There are at most **three replacement attempts per reader lifetime**, delayed
by **1, 2 and 4 seconds**. Exhausting the budget, an unconfirmed reap, a
clock/select/spawn failure or a RAM-output failure stops the reader.

Every replacement changes the mailbox instance. The unchanged Java consumer
must accept a validated baseline and then receive a fresh guidance event
before taking output again. An old window or its heartbeat cannot revive the
previous route, including when Java misses the brief invalidation.

The 1500 ms worker deadline and existing stale/OEM-priority behavior are
retained. This is bounded recovery, not a device restart loop or a claim that
the original connection/resource interruption is repaired.

## Diagnostics

The normal export copies the guidance directory, including:

- `status.txt`: original counters plus build, restart count, latest worker
  failure, worker PID, last announced phase and reap state.
- `reader-failure-first.txt`: one bounded numeric first-failure record, under
  1 KiB, preserved through later faults and recovery. It includes subtype,
  errno, monotonic time, last response/age, partial reply bytes, child status,
  kill/wait errors, counters and whether recovery was allowed. No route strings.

Failure causes distinguish `timeout`, `eof`, `pipe-read`, `pipe-select`,
`clock` and `spawn`. Phase values are 1=open, 2=read, 3=close, 4=pipe write,
5=sleep; this is the last announced phase, not a kernel stack trace.
Child status is the raw `waitpid` status; `-1` means unavailable. `errno=0`
on a timeout/EOF means there was no returned syscall errno to record.

The first record is per boot/RAM-directory lifetime. Failure to save it is
itself treated as output failure; recovery is not attempted without writable
output. Logs do not grow per poll or append route history.

## Restore and saved recovery

Use **Recovery > Remove latest update only**, after removing optional turn-card
tuning. The same snapshot restores the reader, guidance runtime and parent
controller; fully reboot afterwards. For an interrupted latest update, use its
saved recovery action. On MMX without the SD:

```sh
/bin/ksh /mnt/app/carplay-mu1367-guidance-v3/control.sh recover
```

A successfully installed update can use `uninstall` instead of `recover`. Keep
all snapshots and stop on a verification failure. To reinstall stable v1.4.3,
first remove this experimental update, fully reboot, then follow the stable SD's
normal installation procedure. Do not point an older installer at the active
experimental controller or delete its backup directories.

The older v1.4.1-only standalone candidate remains historical. If it was
installed, its saved removal controller is
`/mnt/app/carplay-mu1367-reader-recovery/control.sh`; restore that test before
installing v1.4.3-e. Fully reboot after any restoration.

## Engineering validation

Host tests exercise the unchanged MU1367 Java bridge alongside the real native
reader: fresh-data gating, missed invalidation, timeout/EOF/partial replies,
retry exhaustion, unconfirmed reaping, output failure and manual stop. ARM/QNX
checks use factory MU1367 libc and pipe, including normal/daemon operation,
timeout recovery, a new mailbox instance and first-failure retention. Package
checks run the real transaction under firmware ksh/utilities and verify rollback.
These are synthetic process/filesystem tests, not vehicle endurance or proof
of the original proprietary resource-manager failure trigger.

Build/test entry points are `tools/build-reader.py`, `tests/test-reader.py`,
`tests/test-reader-qnx.py` and the integrated `package.py --reader-build`. The source branch in
`src/reader/reader.c` records the original reader hash; the published MU1427
reader and existing release ZIPs are retained byte for byte.
