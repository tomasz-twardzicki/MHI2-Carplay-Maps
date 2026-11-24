# Sergey: 790 static-noise follow-up

Evidence: private `cpmap-diag-17240135`, supplied after applying the local
overlay/790 test 1. Raw logs remain outside the repository. The user confirms
that OEM touch now works, but the cluster video shows static noise.

The saved child receipt identifies the expected 790 experiment, and the live
receiver fingerprints match its pinned upstream 790 entry, receiver, launcher
and maps library. `ROUTED_TOUCH1 path=oem-dsi raw_intercept=0 routed=17
rejected=0 failures=0` confirms use of the new input path. This does not establish
the audio route or every gesture/overlay case.

The alternate display negotiates 1010×376. Both VideoConfig and the phone's
High-profile level-3.1 SPS report that size repeatedly. The main-screen decoder's
1264×640 log describes the infotainment screen, not the AID. Safe-area changes
cannot address a transport/decoder failure.

The input feeder reports 6,579 frames, 39 keys and no rejected frames. The MOST
bridge reports 6,312 live frames, 36 keys, three drops, no slow writes and no
latency resets. These are producer/write counters, not proof of successful
cluster decoding. The EAGAIN at shutdown follows the supervisor's menu/session
stop; it does not establish the cause of the preceding static noise. Repeated
isoTX2 open/close attempts are also a documented existing OEM encoder behavior.

## Resolution transition to isolate first

The bridge used by test 1 is still the v1.6.3-e 791 bridge. It logs
`intro-policy=every-connect`, then emits all 126 startup frames before accepting
the live map. Extracting its exact embedded `cpmap_intro_clip.h` bytes and probing
them with ffprobe confirms Constrained Baseline, level 3.1, **800×480**. The live
map is **1010×376**, High profile, level 3.1. Thus this session changes both
resolution and coding profile on the same cluster transport. The 790 selector
did not account for the incompatible startup clip.

This is a concrete integration mismatch and a plausible cause, not an accepted
root cause: there is no cluster decoder trace or raw live video sample in the
export. Successful byte writes and an SPS announcement cannot prove that the
cluster decodes the stream.

First vehicle comparison: in **App-Connect → Virtual Cockpit settings → Startup
animation**, select **Off**; disconnect the phone, fully reboot, and reconnect.
Keep the current 790 profile and touch patch. No reinstall or new safe-area
change is needed. The existing policy reader applies this choice before sending
any startup frames. If noise remains, export diagnostics during that session;
verify `intro-policy=off`, no `intro-start` and `intro_frames=0` before ruling
the transition out. Do not attribute a successful repair until this is tested.

If the comparison fixes the map, a subsequent candidate should suppress the
800×480 clip in 790 mode (or supply a separately validated 790 clip), while
preserving 791 preferences. If it does not, investigate the 790 live elementary
stream and MOST/decoder compatibility independently of touch and safe area.

Follow-up: Sergey reports that the noise remains with Startup animation Off.
There is no new capture from that comparison. Treat the animation hypothesis
as insufficient, not as a fix. The packaged upstream implementation comparison
and next candidate are recorded in
[UPSTREAM-790-COMPARISON.md](UPSTREAM-790-COMPARISON.md).
