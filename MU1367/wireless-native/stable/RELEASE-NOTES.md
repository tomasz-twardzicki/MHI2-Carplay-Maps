# v1.6.1 — stable native wireless CarPlay

- Promotes the vehicle-confirmed test2 runtime: wireless maps on the AID,
  native route/lane guidance, RHD/LHD coding refresh/cache and automatic
  alternate-display activation. Wired CarPlay and v1.5.4 ETA/arrival behavior
  remain included.
- Wireless defaults: 40 FPS request, IDR8, 150 ms adaptive smoothing. GEM has
  independent FPS, IDR and smoothing choices. Startup preserves the receiver
  PID through preflight/exec, retains fallback IDR requests until receiver
  cadence is active and requests recovery when decoder configuration is absent.
- One normal install/update flow supports v1.5.3, v1.5.4 and known earlier
  wireless candidates. Saved layers are restored in order, snapshots retained,
  and a full reboot is enforced between incompatible stages. The same SD can
  resume; no previous candidate SD is required.
- Complete OEM restore unwinds wireless first, then restores factory base/AA
  files and archives all wireless recovery roots. Repeated OEM resets retain
  completed earlier snapshots without overwriting them.
- The standard diagnostics export now includes wireless evidence. Its collector
  remains available after removing the wireless layer.

Native components are unchanged from the successful v1.6.1-e-test2 vehicle
test. Internal build IDs remain unchanged; stable version metadata is 1.6.1.
Wireless media text/artwork remains pending. Android Auto remains included but
not fully validated. This release does not claim exhaustive endurance/tuning
tests. See START_HERE.md for the reboot sequence and recovery limits.

Thanks to [omonob](https://github.com/omonob) for the receiver/maps implementation,
the contributors credited in BASELINE_RELEASE-NOTES.md and the maintainers and
drivers supplying vehicle logs and testing. Upstream permissions, hashes and
source history are retained in the wireless layer's source bundle.
