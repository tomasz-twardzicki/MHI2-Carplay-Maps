#!/usr/bin/env python3
"""Run the production candidate orchestrator and combined collectors with factory tools."""
from pathlib import Path
source=Path(__file__).resolve().parents[2]/'stable/test-flow-qnx.py'
code=source.read_text().replace('carplay-mu1367-wireless-native-v161t2','carplay-mu1367-wireless-native-v166').replace('release-v161','release-v166').replace('1_6_1','1_6_6_E')
code=code.replace("production_release_controller_sha256=sha((HERE/'control.sh').read_bytes())","production_release_controller_sha256=sha((release/'control.sh').read_bytes())")
code=code.replace(' *oem_reset)\n  [ "$(cat "$M/base")" = OEM ];exit $?;;', ' *oem_reset)\n  [ "$A" != restore ] || echo OEM > "$M/base"\n  [ "$(cat "$M/base")" = OEM ];exit $?;;')
code=code.replace('export CPMAP_TEST_MEDIA=$M/fs/sda0', 'mkdir -p "$M/mnt/icab/persistent/cpmap-ui"\necho PRIVATE_BT_SENTINEL > "$M/mnt/icab/persistent/cpmap-ui/wireless-last-peer.state"\necho PRIVATE_BT_SENTINEL > "$M/ramdisk/cpmap-bt-policy.state"\necho PRIVATE_BT_SENTINEL > "$M/ramdisk/cpmap-bt-release-authorized-peer"\nexport CPMAP_TEST_MEDIA=$M/fs/sda0')
code=code.replace(' test ! -e "$D/wireless/pairing.key"', ' test ! -e "$D/wireless/pairing.key"\n test ! -e "$D/preferences/wireless-last-peer.state"\n test ! -e "$D/ramdisk/cpmap-bt-policy.state"\n test ! -e "$D/ramdisk/cpmap-bt-release-authorized-peer"')
exec(compile(code,str(source),'exec'),dict(__file__=str(source),__name__='candidate_release_qnx'))
