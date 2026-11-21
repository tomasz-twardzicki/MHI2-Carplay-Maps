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
echo pairing-secret > "$R/mnt/persist/wcp/pairing.key"
mkdir -p "$R/fs/sda0/Log/cpmap-diag-test"
CPMAP_TEST_ROOT="$R" /bin/ksh /proc/boot/collector.sh /fs/sda0 "$R/fs/sda0/Log/cpmap-diag-test/wireless"
test "$(cat "$R/fs/sda0/Log/cpmap-diag-test/wireless/logs/wcp.log.1")" = prior-receiver-log
test "$(cat "$R/fs/sda0/Log/cpmap-diag-test/wireless/logs/ramdisk-cpmap-wireless-summary.log")" = drive-summary
test ! -e "$R/fs/sda0/Log/cpmap-diag-test/wireless/pairing.key"
rm -f "$R/dev/shmem/wcp.log.1" "$R/ramdisk/cpmap-wireless-summary.log"
# Standalone GEM collector mode still succeeds when optional histories are absent.
CPMAP_TEST_ROOT="$R" /bin/ksh /proc/boot/collector.sh /fs/sda0 > /ramdisk/collector.out
grep WIRELESS_DIAG_OK /ramdisk/collector.out
echo COLLECTOR_QNX_PASS rotation_1=1 summaries=1 optional_absence=1 combined_and_standalone=1
'''
fixture.PASS_MARKER='COLLECTOR_QNX_PASS'
fixture.EVIDENCE=dict(collector_sha256=hashlib.sha256(collector.read_bytes()).hexdigest(),
    factory_utilities=True,exported_rotation='wcp.log.1')
fixture.main()
