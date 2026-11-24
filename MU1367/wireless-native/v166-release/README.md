# MU1367 v1.6.6-e — experimental prerelease

Complete SD Toolbox for exact K4525/P4521 MU1367 HW50/HW70, with AID 791 and optional AID 790 support. Read [START_HERE.md](START_HERE.md) before installing, updating or restoring.

This release carries the tested overlay790 test3 map backend and OEM-routed touch fix, the newer 791 BT/session, media, road and timing work, guarded optional Bluetooth profile release, and a trusted-phone reconnect fallback. It corrects the 790 wireless navigation safe area to use the same centred rectangle as the map. Fresh turn-card preferences are Off; explicit saved menu choices remain intact. The new 790 wireless profile starts with its map-only URL and provides separate GEM card On/Off controls.

Installation, profile selection and complete OEM restore use retained snapshots and mandatory full reboot boundaries. Existing 790 test1/test2/test3 children are restored before changing the parent. Unknown changed files or controllers are preserved/refused.

Experimental limits: the combined release and new reconnect/call/centering behavior require vehicle acceptance. The 790 backend retains its tested 30 fps request and does not acquire the 791 timing, guidance, IDR or GPS hooks. Raw GNSS/UTC sourcing, full Bluetooth ACL release and the MU startup freeze remain open. Optional profile release does not turn off the whole BT stack. See [RELEASE-NOTES.md](RELEASE-NOTES.md) for details and validation scope.
