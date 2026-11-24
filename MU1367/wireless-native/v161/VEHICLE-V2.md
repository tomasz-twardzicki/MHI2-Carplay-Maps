# v2 wireless findings

The collector confirms an accepted native session and active AID input after the
alternate-display probe. The user confirms that the map activation fix works.

The receiver logs contain route status (`0x5201`), maneuvers (`0x5202`) and lanes
(`0x5204`). Its subscription uses component **1**. The existing adapter reads the
factory wired mailbox and filters for component **16**, accounting for missing
native wireless guidance even though main-screen CarPlay and AID video work.
The fix therefore needs both the accepted wireless mailbox and a source-specific
component identity. It retains the original iAP2 payloads.

The receiver advertises main-screen maxFPS **30** and alternate-display maxFPS
**40**. The main-screen environment reader also clamps to 30. Updating an FPS
environment variable alone does not establish a different display request.
The owned tap changes the two native display dictionaries before `/info` is
returned; exact 20/25/30/40 results are verified against the unchanged receiver.

The existing input adapter uses arrival time for its ring timestamps and forces
an IDR request every five frames. The new timing sidecar retains the SDK's
phone-derived presentation time; the input preload suppresses only the old
periodic request, leaving recovery requests operational.

`VEHICLE-V2.json` contains counts and the source log's hash, not private payloads.
The v2 capture predates these new runtime changes and is not proof of v1.6.1-e
on-vehicle success. Pacing, native guidance and automatic driving-side behavior
still require the candidate's vehicle acceptance checks.
