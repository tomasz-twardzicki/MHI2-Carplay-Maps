#!/usr/bin/env python3
"""Package installer/recovery fixes on the exact sealed test2 runtime."""
import argparse
import hashlib
import json
import shutil
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sha = lambda b: hashlib.sha256(b).hexdigest()
p = argparse.ArgumentParser()
for name in ('baseline', 'firmware', 'inputs', 'output'):
    p.add_argument('--' + name, type=Path, required=True)
a = p.parse_args()
assert sha(a.baseline.read_bytes()) == '16d7b9f268bb4629a9836df1af9a09056be42aeab98bb3f0b74db25de7da4dba'
out = a.output.resolve()
out.mkdir(parents=True, exist_ok=False)
sd = out / 'sd-card'
with zipfile.ZipFile(a.baseline) as z:
    z.extractall(sd)
    for i in z.infolist():
        if not i.is_dir():
            (sd / i.filename).chmod((i.external_attr >> 16 & 0o777) or 0o644)
custom = sd / 'Custom'
release = custom / 'carplay_mu1367_release'
oem = custom / 'carplay_mu1367_oem_reset'
layer = custom / 'carplay_mu1367_wireless_native'

# Restore exact firmware files, independently of old installed scripts/receipts.
sys.path.insert(0, str(HERE.parents[1] / 'port'))
from firmware import QNX6
stocks = {}
for variant in ('50', '70'):
    image = QNX6(a.firmware / ('MMX2/app/' + variant + '/default/app.img'))
    files = {name: image.get(path) for name, path in {
        'btstack': 'eso/bin/apps/btstack',
        'connectionmanager': 'eso/bin/apps/connectionmanager',
        'bundles': 'eso/hmi/lsd/config/bundles.properties',
        'mmipod': 'armle/usr/sbin/mm-ipod',
        'gal': 'eso/bin/apps/gal',
    }.items()}
    if stocks:
        assert files == stocks, 'Factory HW50/HW70 files must match'
    stocks = files
for name, source in [('connectivity', 'connectivity.json'), ('si', 'smartphone_integrator.json')]:
    stocks[name] = (a.inputs / source).read_bytes()
    proof = json.loads((HERE.parent / 'FIRMWARE-VERIFICATION.json').read_text())
    assert sha(stocks[name]) == proof['production_configs']['50'][source]['sha256'], source
extra_proof = json.loads((HERE / 'FACTORY-EXTRA.json').read_text())
for profile in extra_proof.values():
    for name, path in [('btstack', 'eso/bin/apps/btstack'), ('connectionmanager', 'eso/bin/apps/connectionmanager'),
                       ('bundles', 'eso/hmi/lsd/config/bundles.properties'), ('mmipod', 'armle/usr/sbin/mm-ipod'),
                       ('gal', 'eso/bin/apps/gal')]:
        assert sha(stocks[name]) == profile[path]['sha256']
assert sha(stocks['btstack']) == 'dd80ce8f6d95589cc4db6674150a595b8412d132e2d9e689fbfe9f72e5789251'
assert sha(stocks['connectionmanager']) == '61069e02053104e93f06ee81b26ade79ac0bd1c50907b930ed3b6441a6e533d1'
for name, source in [('bundles', 'bundles.properties'), ('connectivity', 'connectivity.json'), ('si', 'smartphone_integrator.json')]:
    assert stocks[name] == (a.inputs / source).read_bytes()

extra_oem = {
    'btstack': ('/mnt/app/eso/bin/apps/btstack', '755'),
    'connectionmanager': ('/mnt/app/eso/bin/apps/connectionmanager', '755'),
    'bundles': ('/mnt/app/eso/hmi/lsd/config/bundles.properties', '644'),
    'mmipod': ('/mnt/app/armle/usr/sbin/mm-ipod', '755'),
    'gal': ('/mnt/app/eso/bin/apps/gal', '755'),
    'connectivity': ('/mnt/system/etc/eso/production/connectivity.json', '644'),
    'si': ('/mnt/system/etc/eso/production/smartphone_integrator.json', '644'),
}
remove = [
    '/mnt/app/eso/hmi/lsd/jars/' + n + '.jar' for n in (
        'CarPlayNavigationPatch', 'CarPlayMapsG11Navigation', 'VCMirrorRate',
        'VCInformation', 'CarPlayWireless-CP-55915411', 'CarPlayWireless-SI-55915411',
        'CarPlayWireless-Touch-55915411', 'WirelessMapsBootstrap', 'MU1367WirelessPhone')
]
remove += ['/mnt/ota/' + n for n in (
    'btstack_wrap.sh', 'libbtwcp.so', 'wcp_autostart.sh', 'wcp_chansync.sh',
    'wcp_ctl.sh', 'wcp_pf.sh', 'wcp_pfwatch.sh', 'wcp_receiver', 'wcp_video')]
remove += ['/mnt/persist/' + n for n in (
    'btwcp_enable', 'btwcp_off', 'btwcp_present_target', 'wcp_autostart',
    'wcp_cp_stage', 'wcp_cp_off', 'wcp_hs_off', 'wcp_alt_off', 'wcp_alt_probe',
    'altscreen.conf', 'altscreen.geom', 'v75-wireless-display.conf',
    'omonob-phone/cluster-profile')]
remove += ['/mnt/app/eso/hmi/engdefs/' + n for n in (
    'WirelessCarPlayMaps.esd', 'CarPlayMapsVCStandalone.esd')]
targets = dict(extra_oem)
for i, path in enumerate(remove):
    targets['addon%02d' % i] = (path, None)
s = (oem / 'control.sh').read_text()
keys = s.split("KEYS='")[1].split("'")[0].split()
oem_keys = s.split("OEM_KEYS='")[1].split("'")[0].split()
remove_keys = s.split("REMOVE_KEYS='")[1].split("'")[0].split()
s = s.replace("KEYS='" + ' '.join(keys) + "'", "KEYS='" + ' '.join(keys + list(targets)) + "'", 1)
s = s.replace("OEM_KEYS='" + ' '.join(oem_keys) + "'", "OEM_KEYS='" + ' '.join(oem_keys + list(extra_oem)) + "'")
s = s.replace("REMOVE_KEYS='" + ' '.join(remove_keys) + "'", "REMOVE_KEYS='" + ' '.join(remove_keys + [k for k in targets if k not in extra_oem]) + "'")
for fn, rows in {
    'target': {k: '"$M' + v[0] + '"' for k, v in targets.items()},
    'mode': {k: v[1] for k, v in extra_oem.items()},
    'expected': {k: sha(v) for k, v in stocks.items()},
}.items():
    start = s.index(fn + '(){')
    end = s.index(' *) return 1;;esac; }', start)
    s = s[:end] + ''.join(' ' + k + ') echo ' + v + ';;\n' for k, v in rows.items()) + s[end:]
for name, data in stocks.items():
    (oem / 'payload' / name).write_bytes(data)

# Optional addon parents can be absent. Reject links/non-directories at every
# existing ancestor; no missing addon directory is created just to remove it.
s = s.replace('safe_file(){ parents "$1" &&', '''optional_parents(){
 case "$1" in /*) ;; *) return 1;;esac
 D=${1%/*}
 while [ -n "$D" ] && [ "$D" != / ];do
  [ ! -L "$D" ] || return 1
  if [ -e "$D" ];then [ -d "$D" ] || return 1;fi
  D=${D%/*}
 done
}
safe_file(){ optional_parents "$1" &&''')
# The management directories are on /mnt/app; same-volume renames retain the
# original feature/manager journals without executing any upstream controller.
archives = ['carplay-mu1367-wireless-media', 'carplay-mu1367-artwork-png',
            'carplay-mu1367-android-auto',
            'eso/hmi/engdefs/scripts/wireless-carplay-maps',
            'eso/hmi/engdefs/scripts/cpmapvc-local',
            'eso/hmi/engdefs/scripts/.wireless-carplay-maps-manager']
start = s.index("LAYERS='") + len("LAYERS='")
end = s.index("'", start)
layers = s[start:end].split() + archives
s = s[:start] + ' '.join(layers) + s[end:]
s = s.replace('safe_dir(){ parents "$1" &&', 'safe_dir(){ optional_parents "$1" &&')
s = s.replace('"$ROOT/archive/$N"', '"$ROOT/archive/$(archive_name "$N")"')
s = s.replace('archive_preflight(){', '''archive_name(){
 case "$1" in
  eso/hmi/engdefs/scripts/wireless-carplay-maps) echo upstream-wireless-manager;;
  eso/hmi/engdefs/scripts/cpmapvc-local) echo upstream-wired-manager;;
  eso/hmi/engdefs/scripts/.wireless-carplay-maps-manager) echo upstream-manager-recovery;;
  *) echo "$1";;
 esac
}
archive_preflight(){''')
s = s.replace('mount -uw /mnt/system || fail SYSTEM_REMOUNT_FAILED_NO_TARGETS_CHANGED', '''mount -uw /mnt/system || fail SYSTEM_REMOUNT_FAILED_NO_TARGETS_CHANGED
mount -uw /mnt/ota || fail OTA_REMOUNT_FAILED_NO_TARGETS_CHANGED
mount -uw /mnt/persist || fail PERSIST_REMOUNT_FAILED_NO_TARGETS_CHANGED''')
s = s.replace('for D in "$APP" "$M/mnt/system/etc/mm";do', 'for D in "$APP" "$M/mnt/system/etc/mm" "$M/mnt/ota" "$M/mnt/persist";do')
s = s.replace("cpmap-new restore new'", "cpmap-new restore new wmaps-new wmaps-restore'")
s = s.replace('EXACT_K4525_MU1367_REQUIRED', 'EXACT_K4525_OR_P4521_MU1367_REQUIRED')
s = s.replace('absent "$M/ramdisk/carplay-altstream.ready" || fail DISCONNECT_PHONE_AND_ADAPTER_FULL_REBOOT_FIRST',
              'for F in "$M/ramdisk/carplay-altstream.ready" "$M/dev/ipod0" "$M/dev/shmem/wcp_cp_session";do\n absent "$F" || fail DISCONNECT_PHONE_AND_ADAPTER_FULL_REBOOT_FIRST\ndone')
s = s.replace('BUILD=MU1367-oem-reset-4000ba50437c', 'BUILD=MU1367-oem-reset-v163e-' + sha(s.encode())[:12])
(oem / 'control.sh').write_text(s)
om = json.loads((oem / 'manifest.json').read_text())
om['targets'].update({k: v[0].lstrip('/') for k, v in targets.items()})
om['oem_sha256'].update({k: sha(v) for k, v in stocks.items()})
om.update(build_id=s.split('BUILD=')[1].split('\n')[0],
          controller_sha256=sha(s.encode()), layers_archived=layers,
          additional_factory_files={k: {'target': extra_oem[k][0], 'sha256': sha(v)} for k, v in stocks.items()},
          additional_removed_files=remove,
          upstream_scope='Public plaintext wired releases and wireless v3.0/v3.1/v3.2 on exact MU1367 firmware; forward factory restore, journals retained.')
(oem / 'manifest.json').write_text(json.dumps(om, indent=2) + '\n')

s = (release / 'control.sh').read_text().replace('1.6.3-e-test2', '1.6.3-e').replace('1_6_3_E_TEST2', '1_6_3_E')
s = s.replace('# Stable v1.6.3-e:', '# Experimental v1.6.3-e:')
s = s.replace('release-v163t2', 'release-v163e')
# Completed old resets must also be retained before a fresh installation.
s = s.replace('  mark_reboot\n  if base_ready;then', '  retain_completed_oem\n  mark_reboot\n  if base_ready;then')
s = s.replace('/bin/ksh "$BASE/actions.sh" restore-oem "$BASE"',
              '/bin/ksh "$OEM/control.sh" restore "$OEM"')
(release / 'control.sh').write_text(s)
top = json.loads((sd / 'MU1367_RELEASE_MANIFEST.json').read_text())
top.update(version='1.6.3-e', experimental=True, prerelease=True,
           runtime_promoted_without_rebuild=True, baseline_version='1.6.3-e-test2',
           baseline_archive_sha256=sha(a.baseline.read_bytes()),
           oem_restore='Saved local wireless rollback and full reboot, then forward factory reset including upstream v3.2 and earlier plaintext releases.')
(sd / 'MU1367_RELEASE_MANIFEST.json').write_text(json.dumps(top, indent=2) + '\n')
(out / 'manifest.json').write_text(json.dumps(top, indent=2) + '\n')
(sd / 'WIRELESS_VERSION').write_text('1.6.3-e\n')
for f in (sd / 'Toolbox/GEM').glob('carplay-maps-vc*.esd'):
    f.write_text(f.read_text().replace('v1.6.3-e-test2', 'v1.6.3-e experimental'))
for name in ('README.md', 'START_HERE.md', 'RELEASE-NOTES.md'):
    (sd / name).write_bytes((HERE / name).read_bytes())
shutil.copytree(HERE, release / 'source/v163-release', ignore=shutil.ignore_patterns('__pycache__', 'VERIFICATION.json'))

lines = []
for f in sorted(custom.rglob('*')):
    if (f.is_file() and f.name != 'payload-check.sh'
            and 'source' not in f.relative_to(custom).parts
            and f.relative_to(custom).parts[0].startswith('carplay_')):
        lines.append('"$P/verify" "$CUSTOM_CHECK/' + f.relative_to(custom).as_posix() + '" ' + sha(f.read_bytes()) + ' || return 1')
body = 'CUSTOM_CHECK=${P%/*}\n' + '\n'.join(lines) + '\n'
for f in custom.glob('*/payload-check.sh'):
    if f.parent != layer:
        f.write_text(body)
print(json.dumps({'staged': str(out), 'version': '1.6.3-e', 'wireless_runtime_unchanged': True}))
