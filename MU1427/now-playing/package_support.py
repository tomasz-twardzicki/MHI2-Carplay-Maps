"""Shared N0 package rendering, used by controller tests and the builder.
SPDX-License-Identifier: GPL-3.0-or-later
"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
JAR = 'CarPlayNowPlayingObserverN0.jar'
PAYLOAD = 'Custom/carplay_audio_n0'


def controller(build_id, size, phase='N0'):
    text = (HERE / 'control.sh').read_text()
    for key, value in {'BUILD_ID': build_id, 'JAR_SIZE': str(size)}.items():
        token = '@' + key + '@'
        if text.count(token) != 1:
            raise ValueError('controller template mismatch')
        text = text.replace(token, value)
    if phase == 'N1':
        text = text.replace('CarPlayNowPlayingObserverN0.jar', 'CarPlayNowPlayingTextN1.jar').replace('n0', 'n1').replace('N0', 'N1')
        text = text.replace('N1 observation only; no cluster text/artwork output', 'N1 native title/artist/album text; no cover artwork')
        conflict = '''
    absent "$APP/eso/hmi/lsd/jars/CarPlayNowPlayingObserverN0.jar" || fail REMOVE_N0_AND_REBOOT_FIRST
    absent "$M/ramdisk/carplay-now-playing-n0.status" || fail N0_RUNTIME_PRESENT_REBOOT_FIRST
    [ "$(awk '/CarPlayNowPlayingObserverN0.jar/{n++} END{print n+0}' "$LSD")" = 0 ] || fail REMOVE_N0_BOOT_ENTRY_AND_REBOOT
'''
        text = text.replace('if [ "$ACTION" = install ]; then\n', 'if [ "$ACTION" = install ]; then\n' + conflict, 1)
    elif phase != 'N0':
        raise ValueError('unsupported phase')
    return text


def scripts(phase='N0'):
    prefix = '''#!/bin/ksh
# SPDX-License-Identifier: GPL-3.0-or-later
M=${CPMAP_TEST_ROOT:-}
if [ -z "$M" ] && { [ ! -s /ifs/lsd.jxe ] || [ ! -d /mnt/app ]; }; then M=/net/mmx; fi
S=$M/mnt/app/carplay-now-playing-n0/control.sh
[ -s "$S" ] || S=$M/mnt/app/eso/hmi/engdefs/scripts/mqb/cpmap_audio_n0.sh
'''
    sd = '''VOL=""
if [ -n "${CPMAP_TEST_SD:-}" ]; then VOL=$CPMAP_TEST_SD
else
    for V in /net/mmx/fs/sda0 /net/mmx/fs/sdb0 /fs/sda0 /fs/sdb0; do
        if [ -s "$V/Custom/carplay_audio_n0/VERSION" ]; then VOL=$V; break; fi
    done
fi
[ -n "$VOL" ] || { echo "CPMAP_AUDIO_N0_FAIL=SD_PAYLOAD_NOT_FOUND"; exit 1; }
'''
    export = '''if [ -z "${CPMAP_TEST_ROOT:-}" ]; then
    case "$VOL" in /net/mmx/*) on -f mmx mount -uw "${VOL#/net/mmx}" >/dev/null 2>&1 ;;
        *) mount -uw "$VOL" >/dev/null 2>&1 ;; esac
fi
[ ! -L "$VOL/Log" ] || { echo "CPMAP_AUDIO_N0_FAIL=LOG_SYMLINK"; exit 1; }
mkdir -p "$VOL/Log" || exit 1
for I in 01 02 03 04 05 06 07 08 09 10 11 12 13 14 15 16; do
    OUT=$VOL/Log/cpmap-audio-N0-$I
    if [ ! -e "$OUT" ] && [ ! -L "$OUT" ]; then
        /bin/ksh "$S" export "$OUT"; exit $?
    fi
done
echo "CPMAP_AUDIO_N0_FAIL=EXPORT_SLOTS_FULL_PRESERVE_OLD_EXPORTS"
exit 1
'''
    result = {
        'install': prefix + sd + '/bin/ksh "$S" install "$VOL/Custom/carplay_audio_n0"\n',
        'status': prefix + '/bin/ksh "$S" status\n',
        'export': prefix + sd + export,
        'remove': prefix + '/bin/ksh "$S" uninstall\n',
    }
    if phase == 'N1':
        return {k: v.replace('n0', 'n1').replace('N0', 'N1') for k, v in result.items()}
    return result


def menu(phase='N0'):
    labels = {'install': 'Install N0 audio observer (MU1427 research, reboot)',
              'status': 'Show N0 audio observer status',
              'export': 'Export N0 audio snapshot to SD',
              'remove': 'Remove N0 audio observer (reboot)'}
    text = '\n# CarPlay audio N0 research; no cluster audio output\n' + ''.join(
        '\nscript\n    value   sys 1 0x0100 "/eso/hmi/engdefs/scripts/mqb/cpmap_audio_n0_' + action + '.sh"\n'
        '    label   "' + label + '"\n' for action, label in labels.items())
    if phase == 'N1':
        text = text.replace('n0', 'n1').replace('N0', 'N1').replace('audio observer', 'audio text test').replace('research; no cluster audio output', 'native text test; no cover art')
    return text
