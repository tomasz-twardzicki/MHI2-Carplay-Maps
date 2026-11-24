# v1.6.2-e-test1: four exports, one wireless session

Reviewed 2026-11-20. The directory is named `v1.6.3-e-test1`, but the installed generation, launcher and tap fingerprints identify the sealed **v1.6.2-e-test1** ZIP. The four exports are snapshots of one boot/session, not four independent drives. Previous v1.6.1 drive feedback is reviewed separately in `../v162-drive-review/REVIEW.md`.

| Finding | Evidence / interpretation | Development action |
| --- | --- | --- |
| Input priority improved | Reported priority14 readback and no repeat of the 821 ms AID reverse freeze; second-reverse maximum reported164 ms. | Retain. These observations do not establish all receiver/audio thread priorities. |
| Timing never published | Every ring has magic0, PID1757290, sequence0. Same accepted RG session2. No IDR receipt. Last bridge totals19,285 frames/3,759 keys. | The previously reproduced sender-object offset bug applies to this installed tap. The development fix executes the exact native sender with the unrelated parent field zero and restores correlation/IDR. No evidence proves pthread interposition caused this failure. |
| Media capture succeeds but delivery fails | Last capture np5001=1585, cover_copied5; WCPMEDIA1 tracks14/covers21/errors0. TextBridge tracks0/covers0 and artwork attempts0. | Newly fixed: a constructor-selected dispatcher has a different listener list. Route notifications through the factory ASL DSIProxyTarget event path, as the registered wireless service does. Remove constructor interception; report queued and delivered counts separately. |
| Valid image blocked behind empty model | Completed JPEG exists; no fetch attempts. CoverBridge requires live matching text/track metadata. | Fix the shared notification gap first; keep identity/session guards. Native JPEG decoding and complete worker flow pass on factory J9 in the bench. |
| Reverse audio stutters | Every reverse reportedly stutters; output threads remain at10 under HMI13. | The previously implemented MainHigh/type102 output floor14 applies here. SDK receive workers already request61 in the pinned binary; do not lower them or claim their live schedule is established by this capture. |
| Reverse return fails | Borrow856121, hidden864861, unborrow866130, hidden866213; no enter event before manual selection. | Newly fixed: remember pre-borrow ownership. Restore through existing HMI event2910012 after unborrow only for a fresh registered session. Duplicate borrows preserve original ownership; explicit take, user exit and session teardown cancel. |
| BT audio profile release off | CP log explicitly says release off. | Remains unchanged/opt-in. A controlled profile-release A/B test and call-routing restoration audit are still needed. No blanket BT shutdown. |

## Prior work already present in development

The sender-base/timing fix, accepted-PID ring replacement, capture-clock continuity, alternate-only FPS selection, native audio-output floor, exact video lifecycle matching, PF readiness serialization and bounded log retention were implemented against the earlier v1.6.1 captures. This v162 capture does not contain those development binaries and cannot establish their vehicle result.

New media tests reproduce the disconnected-dispatcher gap with two independently constructed instance0 objects. The replacement executes the factory event creator, method lookup and real listener invoker with the event-loop boundary controlled by the fixture. Both text and artwork subscribers receive the notifications. Factory ARM J9 runs verify both normal and strict verification modes, including the native cover decoder. This does not emulate the whole vehicle ASL registry, radio, MFi, MOST or audio hardware.

Screen tests execute the patched service's actual request tracking and HMI event submission. They cover duplicate borrows, OEM ownership, manual-leave events, stale session receipts and missing registration. A structural check verifies that the hook lies inside the worker loop back edge.

## Next candidate and remaining work

The candidate is called **v1.6.3-e-test2** to avoid reusing the input directory's misleading test1 label. It uses its own recovery root and recognizes the exact sealed v162 generation. Migration, interrupted recovery, OEM restore and combined diagnostics must pass before sealing its SD ZIP.

Vehicle checks: advancing timing magic/sequence after cold connection and reconnect; IDR receipt; visible text and matching artwork; reverse audio/AID gaps; return to the previous screen; RHD/VW label; wired media/maps/guidance. Keep40/8/150 for comparable captures.

Still open: Wi-Fi-first handoff arbitration and BT coexistence/calls; SDK jitter counters and timestamped skip/flush tracing; navigation-card default/menu reconciliation; car-GNSS forwarding; actual PF parser/application on vehicle interfaces. Main display30 is retained intentionally from the verified native display contract; AID supports the separate40 demand.
