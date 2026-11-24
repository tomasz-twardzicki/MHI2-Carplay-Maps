# Pinned BT behavior and required ownership change

Audited library: `libbtwcp.so`, SHA25695a75391792c7266eb8c759c20f3b35745d2cd890b74fad45e2c36a5406e9d4e. Addresses below are ELF virtual addresses within this exact library, not offsets for another vendor release. The read-only disassembly is in ignored `build-v163t3-audit`.

## Existing behavior

- RFCOMM-close path at0x1c494 checks `wcp_cp_session`, then0x1c4b4 checks `wcp_bt_released`. Both present → preserve wireless. Otherwise execution reaches0x1c8d4, rechecks the session flag, logs the teardown, and sends `WC bye` at0x1c91c. So the reported teardown is intentional in this binary, conditional on its profile-release marker—not proof that the Wi-Fi session actually died.
- Helper0x22e54 returns session-flag AND BT-released-flag. RC idle scheduling calls it at0x1ab4c; if true it postpones background work. Without the release marker an accepted Wi-Fi session alone does not enable that guard.
- The resend loop tests `wcp_cp_session` at0x23c20. Without that HMI flag, the `wcp_phone_wifi`/association detection at0x23d5c can lead to another0x4301 after a delay, rather than waiting for a bounded Wi-Fi-first connection attempt to finish. Association and accepted CarPlay are different states.
- `btwcp_rc_skip` is created at0x19150 by the reconnect-crash latch and read at0x1791c/0x19b44 to stop reconnect work for the boot. **Do not use it as a temporary accepted-session pause.**
- `/mnt/persist/btwcp_reconnect_off` is a real user-owned reconnect preference, checked at runtime. Do not create/remove it as a transient session signal.

## Confirmed vehicle trigger

The maintainer triggered both reconnects by toggling iPhone Wi-Fi. Treat the observed teardown as possibly associated with genuine Wi-Fi loss, not proof of a BT-only teardown defect. The current log lacks the per-event timestamps needed to establish that attribution. Subsequent independent testing now confirms that BT-only loss also ends CarPlay with Wi-Fi reported healthy. That separate test establishes the fault; the original Wi-Fi-toggle trace alone did not. After Wi-Fi returns, test association-before-acceptance and successful/failing connection grace periods.

## Required guard semantics

Use a fresh, validated accepted receiver/session identity and ongoing wireless liveness, rather than bare file existence, Wi-Fi association alone or an unrelated BT connection. While that session is accepted/live: stop RC paging absent phones, suppress redundant CarPlayStart, and do not translate loss of the bootstrap RFCOMM transport into wireless `bye`. Log the suppressed reason, owner and monotonic time. Preserve genuine user disconnect and wireless teardown, and resume reconnect policy after the accepted owner expires. A Wi-Fi-associated but not accepted phone gets a bounded attempt/grace period; failures must regain a controlled BT fallback, not remain stuck forever.

The profile-release marker must retain its original meaning. Do not fake `wcp_bt_released` to enter the old guard: that would misreport phone-profile teardown and bypass the separate call-routing/restoration work.

Required cases: BT-first, Wi-Fi-first, simultaneous arrival, accepted Wi-Fi plus RFCOMM close, actual Wi-Fi loss, receiver crash/PID reuse, stale session receipt, repeated reconnect, explicit user disconnect, wired already active/takeover, another paired phone, incoming/outgoing calls and disable/remove/restore. Verify exact native call paths and unchanged unknown-build behavior before integrating a new payload.

## Implemented extension

The vendor library file remains byte-identical. New libcpmap-bt-session.so verifies its exact hash and native contracts, then extends only that DSO's private open/write GOT slots. It does not export global open/write overrides or patch the OEM BT binary. The three boolean probe paths evaluate accepted-session ownership in addition to their original conditions. The shared wcp_bt_released/preference files are untouched; native guard log strings are translated to the actual accepted-owner reason when that new condition applies.

A 100ms worker validates owner/grant/PID and WCPRG1 session records. Ownership requires an advancing counter, with a1500ms freshness limit; a session change requires fresh advancement. Inactive/invalid ownership, missing receiver receipt, disable or wired takeover revokes the lease. A missed atomic snapshot read gets only the remaining lease. No cleanup flag or persistent latch is needed to resume native RC behavior. The original native scheduling delay can still apply after the pause ends.

The checked wrapper pins both libraries before activating the guard. Hash drift falls back to OEM BT without starting the wireless add-on. Native decision-path tests and wrapper/fallback tests are recorded in the new checkpoint. Constructor/radio/control boundaries are explicitly stubbed in the native fixture; physical radio operation, native AirPlay timeout and in-flight races remain car acceptance cases. The first-start/resend logic before acceptance is retained; this does not claim to finish all Wi-Fi-first association arbitration.

