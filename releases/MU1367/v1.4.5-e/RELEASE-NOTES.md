# MU1367 v1.4.5-e — experimental reroute handling and 25 fps test option

**EXPERIMENTAL — TO BE TESTED.** Based on the stable v1.4.4 release, for
**K4525 / P4521 MU1367 + AID 791**. P4521 installation remains experimental. This
package has no vehicle result yet. Use v1.4.4 for a stable installation.

The guidance JAR, map core and MU menu change, in both the base and the optional
turn-card runtime. Audio, reader, driver and other runtime bytes match v1.4.4.

## Reroute handling

- **"Calculating route" during a reroute.** A reroute now shows the factory
  calculating symbol (`CALC_ROUTE`, main element 9) with its text in the car's
  language. Previously the output was released and came back with a placeholder.
- **The countdown no longer restarts.** In every reroute in the available captures,
  the phone sends states 1, 5, 0, 3, 1 within about half a second, then restarts
  its maneuver list at a start-route step reporting 0 m. That was treated as a new
  trip. It is now one episode: distance, progress bar, current road and arrival data
  keep their values until the phone reports a real distance again. See
  [the capture analysis](evidence/REROUTE-2026-11-05.md).
- **Bounds.** The wait ends after 20 s or 5 s of phone silence. A stop inside a
  reroute ends guidance within 1.5 s of the next phone message, or at that 5 s
  silence. A normal route end, a new destination, disconnect and OEM navigation still
  clear immediately.

## Placeholder arrow

With an active route and no maneuver yet, the cluster now shows the straight
`DIRECTION_TO_DESTINATION` arrow instead of a straight turn arrow. It always points
straight: iAP2 supplies no destination position or bearing, so the true direction
cannot be calculated.

## 25 fps test option

**App-Connect > Virtual Cockpit settings > Map stream** has a new choice,
**25 fps / IDR 5 (test)**. Reconnect after changing it. **30 fps / IDR 5 stays the
default**, and saved choices are preserved.

Captures show the phone delivering about 17–19 fps when 30 is requested, close to the
link's bandwidth at peaks. Requesting 25 may remove the occasional stutter. It may
also lower the delivered rate, because two captures requesting 40 fps reached about
27. Please compare the same app and route at both settings.

**Before rolling back to v1.4.4 or older, select another map stream.** Older menus
do not recognize this choice and can refuse the saved settings. If that happens, use
**Reset saved MU UI settings (reboot)**.

# Earlier: v1.4.4-e — experimental Apple Maps / Waze guidance handling

**EXPERIMENTAL — TO BE TESTED.** Based on the vehicle-confirmed v1.4.3-e release,
for **K4525 / P4521 MU1367 + AID 791**. P4521 installation remains experimental.
Only the guidance JAR and native reader change; audio, driver, menu and video
runtime bytes match v1.4.3-e.

## Native guidance

- **Quiet routes are held.** Apple Maps sends sparse deltas and can be silent for
  longer than 5 s while stopped or between distance steps. Previously the reader's
  5-second STALE record reset the whole route model and the bridge dropped output
  after 5 s; Apple Maps does not resend maneuvers it already sent, so the arrow
  and lanes stayed lost until the next maneuver. An active route is now held while
  the reader heartbeat, phone session and route state remain valid, for at most
  **3 minutes** of complete phone silence. Explicit route end, cancellation,
  invalidation, session change, disconnect and OEM navigation priority still
  clear immediately.
- **A malformed message is rejected alone.** Every captured MU1367 session's
  first route message failed validation. Because the 16-message window was
  validated as one unit, that message blocked all guidance until 16 newer
  messages arrived. Google Maps recovered within seconds; Waze, which sent only
  2–3 messages per session, never displayed anything. Envelope, ordering and
  overlap checks still reject a whole snapshot. An unreadable route update clears
  route state rather than being guessed.
- **Structural guidance evidence.** `guidance-evidence.txt` records message
  counts, route states, maneuver types, components, gaps between messages,
  rejected-message shapes (keys/sizes only) and the phone app's source name.
  It contains no road or destination text, is bounded to 4 KiB and is included
  in the normal diagnostics export and the Status action.

Waze's delivery remains unverified. The captured Waze sessions supplied only
2–3 iAP2 guidance messages in about 7 minutes, against hundreds for Google Maps.
If the new evidence shows that Waze sends no active route or maneuvers, its
native cluster guidance is not possible through this path.

## Reader recovery budget

v1.4.3-e allowed three worker replacements per reader lifetime (one boot).
After **10 minutes** of fault-free operation since the latest replacement, the
budget now returns to three attempts with the initial 1-second backoff. Rapid
faults still stop recovery after three replacements (1/2/4-second delays).
A lifetime ceiling of **64** replacements bounds a reader regardless. Status
adds `total_restarts` and `budget_resets`; the first-failure record is unchanged
apart from an appended `total_restarts` field.

## Installer output and reboot

The installer no longer shows a "reboot required" line after every internal
layer. It prints the planned step count, one numbered `[n/N]` line per completed
layer and a single reboot request at the end. A new **Reboot unit (after install
completes)** entry in the main menu refuses while an installation runs, then
uses the Toolbox's own reboot helper. Migration from an older integrated
revision still needs the existing reboot between its two stages.

## Install

Use the normal **Install / update CarPlay integration (reboot)** action.
v1.4.3-e is recognised by its exact saved controller and backups and uses the
established two-stage retirement/reboot/install path, preserving its snapshot.
All earlier supported revisions are unchanged. Expect
`MU1367_RELEASE_1_4_4_E_EXPERIMENTAL_INSTALLED_FULL_REBOOT_REQUIRED` in that package.

Test Apple Maps and Waze with active routes, including stops at lights, then
Google Maps for regression. Export diagnostics while guiding and record which
app each export belongs to (the evidence file now names it).

---

# MU1367 v1.4.3-e — experimental guidance-reader recovery

**EXPERIMENTAL FIX — TO BE TESTED.** Based on the published v1.4.3 release,
for **K4525 / P4521 MU1367 + AID 791**. P4521 installation remains experimental.

The new capture of disappearing native guidance ended with worker failure
(`reason=3`), a different path from the earlier RAM-output failure. This build
adds a bounded first-failure record and controlled native-worker recovery.
It does not establish that the original connection/resource interruption is
fixed or that long vehicle sessions now pass.

- At most three replacements per reader lifetime, after confirmed worker exit,
  with 1/2/4-second delays. Unconfirmed exit or exhausted budget stops recovery.
- Guidance stays inactive until a new mailbox baseline and fresh event arrive.
- The first worker failure retains numeric timing, phase, errno and child status.
- The normal release transaction installs/restores the reader alongside guidance;
  there is no separate reader-test installation step.
- Preserves the v1.4.3 P4521 gates, U-turn lane fix, runtime defaults and optional
  turn-card tuning. Java, audio, driver and video runtime bytes match v1.4.3.

Use the normal **Install / update CarPlay integration (reboot)** action.
Integrated v1.4.1, v1.4.2, v1.4.3 and known v3 revisions use the existing checked
retirement/reboot/install boundary, preserving original snapshots. If the older
standalone reader test was installed, restore it first using its saved controller
and reboot. Separate older P4521 bundles use the documented OEM reset first.

The user later confirmed v1.4.3-e working in a vehicle; a 2 h 30 min drive with
active guidance recorded two worker replacements.

## Optional artwork refresh test

Not part of the normal install. **Tuning > Install artwork test** speeds up cover refresh and compresses the cover PNG. See [ARTWORK-R3.md](ARTWORK-R3.md).
