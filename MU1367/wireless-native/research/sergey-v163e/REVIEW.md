# Sergey: OEM overlays/calls and AID 790 — 2026-11-22

Reported setup: iPhone 16 Pro Max, iOS 27.3, native wireless CarPlay, AID 790.
Inputs: supplied 25.77-second video and `cpmap-diag-2961479`. Raw private logs
and video remain outside the repository and are not included in the candidate.

The user confirmed the diagnostics were captured before native wireless
installation finished or after its removal. The export shows the v1.5.4 base,
`MU1367/791`, no saved native wireless layer, no receiver flags/binaries and no
active wireless receiver. This is not evidence of an installation failure
during the video and cannot identify the active call-audio route.

The video shows CarPlay remaining visible beneath seat-heater and drive-mode
overlays while their touch targets fail to operate normally. This matches an
input-routing defect visible in the shipped native adapter: its raw
`TouchInputDeviceImpl.updateTouchInput` hook invokes `CpWcpTouch.onTouch` before
normal listeners and returns early when that hook reports foreground CarPlay.
That bypasses OEM widget hit-testing. Its foreground probe is based on canvas
visibility; a still-visible canvas does not establish ownership of every
pixel when a partial overlay is present.

The candidate restores the factory method and forwards touches from the OEM
CarPlay DSI event path instead. The actual MU1367 ASL handler maps touchscreen
press/release to DSI states 1/0; the candidate maps those to receiver WT1
gestures 4/3. The host test sends real packets through the patched service;
factory-J9 tests verify the replacement classes. Physical hit-testing remains
unverified. No blanket BT/HFP profile release or forced call-audio takeover is
introduced from this incomplete capture.

The export also references generic `NavActiveIgnore.jar` before the maintained
firmware adapter. It does not include enough JAR evidence to show that the
generic file existed or was loaded. The maintained installer refuses that
file when present; the reference alone is insufficient to attribute the fault
or justify deleting files on the unit.

AID 790 needs a real 1010×376 producer/profile, not a safe-area change to the
791 800×480 handshake. The first 790 candidate therefore switches the complete
upstream profile and the matching historical wired core, with bounded safe-area
tuning and exact rollback. It intentionally remains a map experiment rather
than claiming the custom 791 guidance/media/timing features on an unaudited
receiver. The selector, tuning and recovery are covered by real-controller
host/factory-shell tests; native imports are checked on K4525/P4521 HW50/HW70.

Next vehicle evidence: ordinary main-screen touch, both overlays, incoming-call
UI/answer/audio/microphone, reverse return, 790 map framing/reconnect and an
export from the active failing native session. `cpmap-touch.status` records
the candidate route/counters without logging touch coordinates or phone data.
