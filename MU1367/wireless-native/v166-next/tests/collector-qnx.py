#!/usr/bin/env python3
"""Run the next collector using the existing factory-utility QNX image."""
import hashlib
import importlib.util
from pathlib import Path
HERE=Path(__file__).resolve().parent
collector=HERE.parent/'src/runtime/collect-wireless.sh'
spec=importlib.util.spec_from_file_location('fixture',HERE.parents[1]/'tests/receiver-alt-gate.py')
fixture=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixture)
fixture.SOURCE='int unused_collector_fixture;\n'
fixture.EXTRA_FILES={'collector.sh':collector}
fixture.IFS_EXTRA='[type=file]\ncollector.sh\n'
fixture.RUN_SCRIPT='''#!/bin/ksh
set -eu
export PATH=/proc/boot:/bin LD_LIBRARY_PATH=/proc/boot
R=/ramdisk/capture-root
mkdir -p "$R/ifs" "$R/dev/shmem" "$R/ramdisk" "$R/fs/sda0/Log" "$R/mnt/app" "$R/mnt/persist/wcp"
echo firmware > "$R/ifs/lsd.jxe"
echo current-receiver-log > "$R/dev/shmem/wcp.log"
echo prior-receiver-log > "$R/dev/shmem/wcp.log.1"
echo drive-summary > "$R/ramdisk/cpmap-wireless-summary.log"
echo artwork-current > "$R/ramdisk/cpmap-artwork.log"
echo artwork-prior > "$R/ramdisk/cpmap-artwork.log.1"
echo bt-current > "$R/ramdisk/cpmap-bt-session.log"
echo bt-prior > "$R/ramdisk/cpmap-bt-session.log.1"
echo bt-status > "$R/ramdisk/cpmap-bt-session.status"
mkdir -p "$R/ramdisk/wcp-location" "$R/ramdisk/wcp-rg" "$R/mnt/app/carplay-mu1367-wireless-native-v165t2"
echo road-current > "$R/ramdisk/cpmap-road-output.log"
echo road-prior > "$R/ramdisk/cpmap-road-output.log.1"
echo release-status > "$R/ramdisk/cpmap-bt-release.status"
echo command-status > "$R/ramdisk/wcp-rg/bt-request.status"
echo private-device-id > "$R/ramdisk/wcp-rg/bt-request.state"
echo private-authorized-peer > "$R/ramdisk/cpmap-bt-release-authorized-peer"
echo profiles > "$R/mnt/app/carplay-mu1367-wireless-native-v165t2/bt-release.mode"
echo main-screen > "$R/ramdisk/cpmap-main-screen.log"
echo main-screen-prior > "$R/ramdisk/cpmap-main-screen.log.1"
echo media-event > "$R/ramdisk/cpmap-media-events.log"
echo media-event-prior > "$R/ramdisk/cpmap-media-events.log.1"
echo launch-clock > "$R/ramdisk/cpmap-native-launch.log"
echo gps-launch > "$R/ramdisk/cpmap-gps-launch.log"
echo gps-init > "$R/ramdisk/cpmap-gps-source-startup.status"
echo next > "$R/mnt/app/carplay-mu1367-wireless-native-v165t2/road-label.mode"
echo nmea-snapshot > "$R/ramdisk/wcp-location/latest.bin"
echo source-status > "$R/ramdisk/wcp-location/source.status"
echo receiver-location > "$R/ramdisk/wcp-rg/location.status"
echo boot-attempt > "$R/ramdisk/cpmap-gps-dio-attempt.state"
echo probe-current > "$R/ramdisk/cpmap-gps-probe.txt"
echo 1 > "$R/mnt/app/carplay-mu1367-wireless-native-v165t2/gps.enabled"
echo pairing-secret > "$R/mnt/persist/wcp/pairing.key"
mkdir -p "$R/fs/sda0/Log/cpmap-diag-test"
CPMAP_TEST_ROOT="$R" /bin/ksh /proc/boot/collector.sh /fs/sda0 "$R/fs/sda0/Log/cpmap-diag-test/wireless"
test "$(cat "$R/fs/sda0/Log/cpmap-diag-test/wireless/logs/wcp.log.1")" = prior-receiver-log
test "$(cat "$R/fs/sda0/Log/cpmap-diag-test/wireless/logs/ramdisk-cpmap-wireless-summary.log")" = drive-summary
test "$(cat "$R/fs/sda0/Log/cpmap-diag-test/wireless/logs/ramdisk-cpmap-artwork.log")" = artwork-current
test "$(cat "$R/fs/sda0/Log/cpmap-diag-test/wireless/logs/ramdisk-cpmap-artwork.log.1")" = artwork-prior
test "$(cat "$R/fs/sda0/Log/cpmap-diag-test/wireless/logs/ramdisk-cpmap-bt-session.log")" = bt-current
test "$(cat "$R/fs/sda0/Log/cpmap-diag-test/wireless/logs/ramdisk-cpmap-bt-session.log.1")" = bt-prior
test "$(cat "$R/fs/sda0/Log/cpmap-diag-test/wireless/state/cpmap-bt-session.status")" = bt-status
test "$(cat "$R/fs/sda0/Log/cpmap-diag-test/wireless/state/cpmap-bt-release.status")" = release-status
test "$(cat "$R/fs/sda0/Log/cpmap-diag-test/wireless/state/wcp-rg-bt-request.status")" = command-status
test "$(cat "$R/fs/sda0/Log/cpmap-diag-test/wireless/logs/ramdisk-cpmap-road-output.log")" = road-current
test "$(cat "$R/fs/sda0/Log/cpmap-diag-test/wireless/logs/ramdisk-cpmap-road-output.log.1")" = road-prior
test "$(cat "$R/fs/sda0/Log/cpmap-diag-test/wireless/preferences/bt-release.mode")" = profiles
test ! -e "$R/fs/sda0/Log/cpmap-diag-test/wireless/state/wcp-rg-bt-request.state"
test ! -e "$R/fs/sda0/Log/cpmap-diag-test/wireless/state/cpmap-bt-release-authorized-peer"
test "$(cat "$R/fs/sda0/Log/cpmap-diag-test/wireless/logs/ramdisk-cpmap-main-screen.log")" = main-screen
test "$(cat "$R/fs/sda0/Log/cpmap-diag-test/wireless/logs/ramdisk-cpmap-main-screen.log.1")" = main-screen-prior
test "$(cat "$R/fs/sda0/Log/cpmap-diag-test/wireless/logs/ramdisk-cpmap-media-events.log")" = media-event
test "$(cat "$R/fs/sda0/Log/cpmap-diag-test/wireless/logs/ramdisk-cpmap-media-events.log.1")" = media-event-prior
test "$(cat "$R/fs/sda0/Log/cpmap-diag-test/wireless/logs/ramdisk-cpmap-native-launch.log")" = launch-clock
test "$(cat "$R/fs/sda0/Log/cpmap-diag-test/wireless/logs/ramdisk-cpmap-gps-launch.log")" = gps-launch
test "$(cat "$R/fs/sda0/Log/cpmap-diag-test/wireless/state/cpmap-gps-source-startup.status")" = gps-init
test "$(cat "$R/fs/sda0/Log/cpmap-diag-test/wireless/preferences/road-label.mode")" = next
test ! -e "$R/fs/sda0/Log/cpmap-diag-test/wireless/pairing.key"
test "$(cat "$R/fs/sda0/Log/cpmap-diag-test/wireless/state/wcp-location-latest.bin")" = nmea-snapshot
test "$(cat "$R/fs/sda0/Log/cpmap-diag-test/wireless/state/wcp-location-source.status")" = source-status
test "$(cat "$R/fs/sda0/Log/cpmap-diag-test/wireless/state/wcp-rg-location.status")" = receiver-location
test "$(cat "$R/fs/sda0/Log/cpmap-diag-test/wireless/state/cpmap-gps-dio-attempt.state")" = boot-attempt
test "$(cat "$R/fs/sda0/Log/cpmap-diag-test/wireless/state/cpmap-gps-probe.txt")" = probe-current
test "$(cat "$R/fs/sda0/Log/cpmap-diag-test/wireless/preferences/gps.enabled")" = 1
rm -f "$R/dev/shmem/wcp.log.1" "$R/ramdisk/cpmap-wireless-summary.log"
# Standalone GEM collector mode still succeeds when optional histories are absent.
CPMAP_TEST_ROOT="$R" /bin/ksh /proc/boot/collector.sh /fs/sda0 > /ramdisk/collector.out
grep WIRELESS_DIAG_OK /ramdisk/collector.out
echo COLLECTOR_QNX_PASS rotation_1=1 artwork_history=1 bt_history=1 summaries=1 optional_absence=1 combined_and_standalone=1
'''
fixture.PASS_MARKER='COLLECTOR_QNX_PASS'
fixture.EVIDENCE=dict(collector_sha256=hashlib.sha256(collector.read_bytes()).hexdigest(),
    factory_utilities=True,exported_rotation='wcp.log.1')
fixture.main()
