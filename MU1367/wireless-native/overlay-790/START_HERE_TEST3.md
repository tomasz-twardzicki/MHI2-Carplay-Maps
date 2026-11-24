# 790 playback information and call-handoff test — test 3

Local experiment for MU1367 K4525/P4521, based on v1.6.3-e. Sergey confirmed
that test 2 fixes the cluster map. Test 3 keeps its map receiver, feeder, core,
maps library, bridge, supervisor and geometry, plus the working OEM touch JARs.
It adds a metadata-only observer and an optional call-handoff preference.
The public pre-release is unchanged.

## Upgrade from the working test 2

1. Extract the complete test-3 ZIP to a clean SD root. Refresh both Toolbox
   menus and scripts. Disconnect the phone and fully reboot.
2. In **Customization → carplay-maps-vc-experimental**, select
   **790: maps + playback information + OEM touch**. The first selection
   restores the saved parent files and asks for a full reboot.
3. Reboot with the phone disconnected, select the same 790 action again, and
   wait for installation success.
4. For the call-routing comparison, optionally select
   **790: prefer CarPlay calls and media (test)** while the phone is still
   disconnected. Then fully reboot before reconnecting. Without this choice,
   an absent prior call-handoff preference remains off.

No normal CarPlay Maps installer rerun is needed. Test 1 and test 2 snapshots
are retained; test 3 has its own recovery folder. Do not delete them.

## Playback test

Play music, change tracks, pause/resume, and check title/artist, elapsed time
and artwork in the OEM/cluster playback view. Check the AID map and OEM overlay
touch again. The new observer only reads the receiver's metadata and artwork
callbacks; it does not change the accepted map video path or audio routing.

The new producer reports `WCP790MEDIA1` in `source-status.txt`; the existing
consumer reports `WCPMEDIA2` in `wcp-now-playing.status`. An advancing accepted
source and delivered-track counters establish more than file presence alone.
Artwork remains tied to the current track/session and is cleared on disconnect.

## Cellular-call comparison

Sergey's corrected report is regular cellular calls: the OEM call UI sometimes
appears and audio switches to the iPhone. This is a routing failure, not only
a different screen. The supplied session records music and Siri, with no
CarPlay telephony stream establishing the failing call route.

The optional preference uses the adapter's existing request to release the
matched CarPlay phone's Bluetooth **media and phone profiles** after wireless
entry, allowing a CarPlay call handoff. It is not limited to the call screen.
It does not disconnect other trusted phones or turn off Bluetooth globally.
The preference and request marker do not prove an acknowledged handoff.

Start this comparison with no call in progress. After CarPlay connects, test
an incoming cellular call and check the call UI, speaker route and microphone.
End it, repeat a call, then check disconnect/reconnect. Physical call routing
and mid-call connection/handoff have not been accepted by these bench tests.

If the handoff fails, use **790: keep OEM Bluetooth calls and media**, with the
phone disconnected, then fully reboot. Reconnect the phone in the OEM Phone
menu if necessary. This stops the optional release request; it is not a live
transfer button for an active call.

Export CarPlay diagnostics during or immediately after a failed call, while
the native wireless session is still connected. Note that it was a cellular
call and whether audio stayed on the iPhone. The collector includes the call
preference and request/audio markers. It does not add a copy of the
address-bearing Bluetooth-release request file.

## Geometry and restore

Safe-area controls remain available in the same menu. Test 3 starts at
`202,16,606,344`; record any previous tuning before upgrading. Geometry and
call preference edits require the phone disconnected and a full reboot to
apply. Unknown changed files/preferences are preserved and refused.

**Remove experiment and restore saved 791 runtime** restores the exact parent
files and first-saved call preference; then fully reboot. This does not
reactivate test 2 automatically. Test-3 wrappers retire the child before normal
uninstall or complete OEM restore and enforce each required reboot.

Bench checks cover the real 790 metadata/file-transfer parser, stale-image and
disconnect handling, replay of actual logged metadata, factory imports, shell
transactions, all 17 commit failures/interruption recoveries and migration from
test 2. The call test observes an addressed OEM request, not an actual Bluetooth
disconnect acknowledgement or a successful call in a car.
