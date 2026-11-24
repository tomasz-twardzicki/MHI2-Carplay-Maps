# OEM overlay / experimental 790 test 1

For K4525/P4521 MU1367. This is a local test candidate based on the complete
v1.6.3-e package. The published pre-release is unchanged.

## Install and select a profile

1. Extract the complete ZIP to a clean SD root and refresh both Toolbox menus
   and scripts. Disconnect the phone and fully reboot.
2. If native wireless installation is incomplete, use the normal CarPlay Maps
   **Install/update**, reboot, and repeat until v1.6.3-e is installed. The
   experiment refuses a base-only installation before changing files.
3. Open **Customization → carplay-maps-vc-experimental**.
4. Select **790: experimental map profile + OEM touch** for Sergey's 790 unit.
   For an overlay-only comparison using the existing 791 backend, select
   **791: OEM overlay touch test**. Wait for the final result and fully reboot.

The 790 choice installs a complete 1010×376 receiver/input/geometry profile
and the original MU1367-compatible 790 wired core. It changes more than a safe
rectangle on the 800×480 profile. Switching profiles first restores the saved
parent runtime and requests a reboot; repeat the selected action after reboot.

## Tuning the 790 safe area

The same experimental menu offers X/Y/width/height changes in 10-pixel steps,
**Show 790 safe area**, and **Reset safe area**. Default: `202,16,606,344`.
Disconnect and fully reboot before changing settings; fully reboot again to
apply them. Invalid/out-of-frame rectangles are refused without changing the
current setting. The upstream alternate navigation X offset is kept at X−160.

An exact rectangle can also be set from an MMX shell, with this SD mounted at
`/fs/sda0`:

```sh
/bin/ksh /fs/sda0/Custom/carplay_mu1367_input_profile/tune.sh set /fs/sda0/Custom/carplay_mu1367_input_profile/790 202 16 606 344
```

## What this test changes

The input patch removes the global raw-touch interception and restores the
factory touchscreen listener dispatch. It forwards touchscreen events from
the native CarPlay DSI path after OEM widget hit-testing. Heater, drive-mode
and OEM phone overlays should therefore receive their own touches. Physical
hit-testing and main-screen touch operation need vehicle confirmation.

Only single-contact touchscreen press/release is forwarded by this candidate.
Two-contact/touchpad events are rejected. This limitation must be checked
before considering it a replacement for the published build.

The 790 backend is the exact upstream public v3.2 `AID10.5-17PM` implementation,
with configurable geometry for this experiment. **790 mode is a map experiment:
the custom 791 wireless guidance/media/timing/RHD/tuning extensions are not
included in this backend.** It has not been accepted on Sergey's 16 Pro Max /
reported iOS 27.3 combination. Existing user preferences are retained.

This input patch does not change HFP/cellular-call audio ownership. It may fix
an unresponsive OEM answer button, but a switch of call audio/UI to CarPlay
is not established by the available capture or bench tests.

## Recovery

Use **Remove experiment and restore saved 791 runtime**, then fully reboot.
This restores exact pre-test files, including the previous PROFILE and
geometry, and retains snapshots. Use this test SD for ordinary removal or
complete OEM restore: its wrappers remove the experiment first and enforce
each reboot before parent wireless/base removal. Keep all recovery folders.

## Vehicle checks and useful capture

- Confirm ordinary CarPlay tapping, dragging and release first.
- Open heater controls and drive-mode overlays. Verify their buttons work and
  the map beneath does not react to those touches. Close the overlay and check
  CarPlay touch again; check reverse-camera return too.
- Test an incoming call: answer from the visible OEM or CarPlay UI, note which
  UI appears, which device carries audio, and whether the microphone works.
- On 790, confirm the AID map appears, its framing, route-stop clearing and
  reconnect after a cold boot. Record the chosen safe rectangle.
- Export standard CarPlay diagnostics **while native wireless is connected and
  the problem is present**, before uninstalling. The test collector includes
  `cpmap-touch.status`, the wireless CP/touch logs and active profile receipts.

Bench checks cover transactions, bounds, packet serialization, factory-J9
class loading and firmware import resolution. They do not establish actual
radio, MOST, video output, calls, or OEM overlay behavior in the vehicle.
