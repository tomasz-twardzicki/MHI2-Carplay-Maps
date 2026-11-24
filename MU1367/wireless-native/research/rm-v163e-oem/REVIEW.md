# RM post-OEM cluster map reload review — 2026-11-23

The user confirms that the instrument-cluster map disappears/reloads with the
map left selected and untouched, including after the package's OEM restore.
The reported possible onset after omonob v3.1 is history, not a proven cause.

## Captures and restore evidence

Inputs are the two original `.7z` archives under
`/Users/tomasz/Documents/github/personal/Logs/wireless/v1.6.3-e pre-release/RM/OEMrestore`.
They were extracted into a temporary review directory, leaving inputs intact.
Hashes and exact evidence lines are recorded in `EVIDENCE.json`.

These are two snapshots of the same boot. The first slog is an exact prefix
of the second; HMI PID 962618 is unchanged. They end at uptime 77 s and 166 s.

Both summaries are consistent with removal of the addon runtime:

- All listed integration/guidance/native-wireless management layers are absent.
- `/mnt/app/carplaymaps` and `CarPlayClusterControls.jar` are absent.
- `dio_manager` is an ELF executable, 684305 bytes, instead of our wrapper.
- `gal` is an ELF-sized executable, 1269211 bytes, instead of the addon wrapper.
- The displayed HMI launch commands have no addon bootclasspath prepend.
- No projection supervisor, video bridge, RG reader or wireless receiver is
  shown; their runtime logs/owner/session markers are absent.

The standard export does not include the OEM reset verification result,
reset journal or hashes of restored target files. Therefore these captures
support a restored runtime but do not independently prove every restore target
matches its factory hash. Factory `libcgdrv.so`/`libecpp-ne.so.4` preloads in the
HMI launch excerpt are not evidence of a remaining CarPlay addon hook.

## What happens to the OEM video stream

The later slog records this sequence on `isoTX2` and the OEM video encoder:

| Uptime | Observation |
| --- | --- |
| 38 s | Encoder/transport starts during startup. |
| 40 s | Encoder closes successfully and immediately starts again. |
| 115 s (1:55) | Transport closes; encoder, muxer and worker shut down successfully. |
| 133 s (2:13) | Encoder and transport start again. |
| 162 s (2:42) | Transport closes; another successful encoder shutdown. |

The non-startup stop/start/stop sequence is compatible with the reported
automatic map disappearance. Exact visible-event correlation is not recorded.
The log does not identify the requester or shutdown reason. Successful cleanup
does not establish that the triggering request or upstream state was correct.

There is one navigation startup and no logged subsequent navigation/HMI crash
or restart. Later `AS_RUNNING requested` startup notifications and
`Change NavStateOfOperation to 5` alone are not proof of a navigation restart.
At 107/157 s, CPU is 32/24 percent with 910/906 MB free RAM, respectively.
There is no contemporaneous out-of-memory, storage-full or MOST-link failure
reported in this capture. This does not exclude faults in uncaptured modules.

The repeated `isoTX*` open/close probes at 77/166 s coincide with diagnostic
export and must not be counted as independent map failures.

## v3.1 and restore scope

The cached original v3.1 archive matches the already-audited SHA-256
`99fcf7b32485253fcd346758736a2c7b11085b2d86c23ac7671132c4a12872c0`.
Its managed transaction paths are covered by the v1.6.3-e OEM reset audit.
Inspection of its installer shell scripts found no coding/EEPROM/dataset
write operation. This is not a complete audit of every packaged native/JAR
runtime or evidence of the exact package installed on this particular unit.

Our OEM restore replaces known addon-modified files and removes known hooks;
it is not a firmware reflash, coding/dataset reset, cluster reset or wipe of
all OEM persistent HMI/navigation user state. Thus persistent state or a fault
outside the restore's scope remains possible. No supplied evidence singles
out such a state or establishes that v3.1 damaged the unit.

## Next discriminating capture

1. Save the existing **Diagnostics > Verify restored OEM files** and
   **Inspect OEM reset state (read only)** results. No further reset is needed
   just to obtain these results.
2. On MMX, capture DisplayManager information while the map is visible and
   while it has disappeared: `/eso/bin/apps/dmdt gd`, `gc`, and `gs`.
   `gd` lists clients, `gc` contexts, and `gs` displays/system information.
   These are query commands verified in the matching K4525 firmware executable
   (SHA-256 `b6aafec2707f2e5c90c54900b6d69d66aefdb8590bbd76f9cb0707f3fe991a74`).
   Use the factory runtime environment, including
   `IPL_CONFIG_DIR=/etc/eso/production` and `LD_LIBRARY_PATH=/eso/lib`.
3. Correlate those snapshots and MMX/RCC logs with a timestamped observation
   of an untouched map dropout. The current exporter supplies MMX slog and
   addon evidence, not the missing cluster/RCC control history.
4. Save a read-only fault scan of 5F and 17 before clearing anything. This can
   distinguish reported communication/decoder faults from a display request
   being withdrawn. Compare coding/adaptations to a pre-issue backup only if
   one exists; the current logs do not establish a coding error.

No runtime patch or change to sealed release packages is justified yet. The
useful narrowing is an OEM cluster-video stream being stopped and restarted
with the addon runtime absent; the cause of those transitions remains open.

## Subsequent antenna photo and fault-scan screenshot

The supplied photo shows a generic GPS antenna labelled 1575.42 MHz,
3.0–5.0 V, with a blue coaxial connector. Its appearance supports an
aftermarket/replacement antenna, but does not prove that the navigation unit
or whole system was retrofitted.

The scan header identifies 5F as 3G0035043E / 1367 / H55. Visible fault text:

- Check Software Version Management (SVM).
- GPS antenna: Open circuit.
- Optical data bus for display in instrument cluster: Sporadic disruption.
- Fiber Optic MOST Data Bus: Open circuit.

The screenshot crops the full DTC identifiers; do not assign numeric codes
from similar wording in reference material. These faults are not time-aligned
with the earlier same-boot slog captures. The unit is photographed pulled out,
so disconnection during handling is a possible source of stored faults.

The cluster optical-bus fault is now a stronger lead for the disappearing map
than the antenna alone. It is consistent with an interruption in the delivery
path, but does not distinguish a connector/fiber fault, another MOST node,
power interruption or a software/receiver fault. Save the complete scan, test
with all connections restored, reproduce untouched, and rescan to establish
which faults recur. Inspect new/altered fiber connections and use optical-bus
diagnostics where supported before attributing the problem to an addon build.

References checked on 2026-11-23:

- Ross-Tech GPS antenna diagnostic guidance notes antenna/wiring/connectors
  and compatibility after a retrofit:
  <https://wiki.ross-tech.com/wiki/index.php/00862>.
- Ross-Tech optical databus guidance specifically includes new/altered
  connections after retrofits:
  <https://wiki.ross-tech.com/wiki/index.php/00384>.
- Optical-bus diagnostics can narrow the location of a network break:
  <https://www.ross-tech.com/vcds/tour/optical-bus.html>.

Those reference code pages explain the fault categories; they do not establish
the numeric DTCs cropped out of this user's screenshot.
