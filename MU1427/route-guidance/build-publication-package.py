#!/usr/bin/env python3
"""Build a private B3/B4 full-toolbox package; preserve existing test packages."""
import argparse
import importlib.util
import json
from pathlib import Path
import shutil
import zipfile

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
TOOLBOX = REPO / 'releases/CarPlay_Maps_VC_Full_Toolboxes/VW_SKODA_ALL_CarPlay_Maps_VC_FULL_MQB_Toolbox_V4'
spec = importlib.util.spec_from_file_location('publication_patch', HERE / 'patch-publication.py')
patch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(patch)


def replace_once(text, before, after):
    if text.count(before) != 1: raise ValueError('base script changed; review B3 rendering')
    return text.replace(before, after)


def installer(manifest):
    revision = manifest['build'].rsplit('-', 1)[1]
    if revision not in ('B3', 'B4'): raise ValueError('unsupported publication revision')
    source = (HERE / 'rg-b1.sh').read_text()
    replacements = {
        'INSTALLER_REVISION=B2-install-r1': f'INSTALLER_REVISION={revision}-install-r1',
        'BUILD_ID=MU1427-iAP2-RGI-B2-0763b7aa': f"BUILD_ID={manifest['build']}-{manifest['patched_sha256'][:8]}",
        'PATCHED_DRIVER_SIZE=741944': f"PATCHED_DRIVER_SIZE={manifest['patched_size']}",
        'case "$D" in "$STOCK_DRIVER_SIZE"|"$PATCHED_DRIVER_SIZE")':
            'case "$D" in "$STOCK_DRIVER_SIZE"|741944|"$PATCHED_DRIVER_SIZE")',
        '[ -s "$ROOT/VERSION" ] && [ "$(cat "$ROOT/VERSION")" = "$BUILD_ID" ] || fail DIFFERENT_BUILD_RESTORE_FIRST':
            '''[ -s "$ROOT/VERSION" ] || fail DIFFERENT_BUILD_RESTORE_FIRST
            case "$(cat "$ROOT/VERSION")" in
                "$BUILD_ID") ;;
                MU1427-iAP2-RGI-B2-0763b7aa)
                    [ "$D" = 741944 ] && [ "$C" = 6006 ] || fail DIFFERENT_BUILD_RESTORE_FIRST ;;
                *) fail DIFFERENT_BUILD_RESTORE_FIRST ;;
            esac''',
    }
    for before, after in replacements.items(): source = replace_once(source, before, after)
    if revision == 'B4':
        source = replace_once(source, '|741944|"$PATCHED_DRIVER_SIZE")', '|741944|743148|"$PATCHED_DRIVER_SIZE")')
        source = replace_once(source, '                *) fail DIFFERENT_BUILD_RESTORE_FIRST ;;',
            '''                MU1427-iAP2-RGI-B3-bfd79ed0)
                    [ "$D" = 743148 ] && [ "$C" = 6006 ] || fail DIFFERENT_BUILD_RESTORE_FIRST ;;
                *) fail DIFFERENT_BUILD_RESTORE_FIRST ;;''')
    return source.replace('# MU1427 B2.', f'# MU1427 {revision}.').replace('; B2 $PATCHED_', f'; {revision} $PATCHED_')


def collector():
    source = (HERE / 'capture-rgi.sh').read_text()
    source = replace_once(source, 'REVISION=C2', 'REVISION=C3')
    anchor = 'capture "$M/dev/shmem/iap2.log" "$OUT/iap2.log" 8388608'
    extra = '''

# B3's virtual regular file reports no on-disk size. Its custom handler accepts
# one full snapshot read and returns EOF; do not use the normal file-size path.
PUB=$M/dev/ipod0/rgi-events
progress "BEGIN publication $PUB (one bounded read, no retry loop)"
if [ -f "$PUB" ] && [ ! -L "$PUB" ]; then
    if dd "if=$PUB" "of=$OUT/rgi-events.bin" bs=65536 count=1 2>> "$OUT/copy-errors.txt"; then
        PUB_STAT=$(ls -ln "$OUT/rgi-events.bin" 2>/dev/null)
        set -- $PUB_STAT
        if [ "$#" -ge 5 ] && [ "$5" = 33088 ]; then
            progress "DONE publication bytes=33088"
        else FAILED=$((FAILED+1)); progress "FAILED publication snapshot size"; fi
    else FAILED=$((FAILED+1)); progress "FAILED publication read (possibly EAGAIN)"; fi
else FAILED=$((FAILED+1)); progress "MISSING publication file (B3 init not confirmed)"; fi
'''
    return replace_once(source, anchor, anchor + extra)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stock_driver', type=Path)
    parser.add_argument('stock_config', type=Path)
    parser.add_argument('--revision', choices=('B3', 'B4'), default='B3')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    config = args.stock_config.read_bytes()
    if patch.b2.sha(config) != 'ce05524385ccae1167966d45c52ff60ac0c70fe0f46ac98d77a75f109a6bfa6c':
        parser.error('exact factory config required')
    builder = patch
    if args.revision == 'B4':
        spec = importlib.util.spec_from_file_location('activation_patch', HERE / 'patch-activation.py')
        builder = importlib.util.module_from_spec(spec); spec.loader.exec_module(builder)
    driver, manifest = builder.build(args.stock_driver.read_bytes())
    verified = {'B3': (743148, 'bfd79ed0c1a86d7ed48837d6ec4c766f2be024366d8376ceb730a1403854741d'),
                'B4': (743196, '3760797aed4886a6c4480e3a8de79be427a3d8587450a56c424721306ca15d8b')}
    if (manifest['patched_size'], manifest['patched_sha256']) != verified[args.revision]:
        parser.error('driver changed; revalidate and update the verified fingerprint before packaging')
    out = (args.output or HERE / f'build-{args.revision}').resolve()
    stage = out / 'sd-card'
    if stage.exists(): parser.error('choose a fresh output directory')
    shutil.copytree(TOOLBOX, stage)
    payload = stage / 'Custom/route_guidance_b1'
    payload.mkdir()
    (payload / 'ipod-drvr-iap2.so').write_bytes(driver)
    # Byte-identical to B1/B2, including the historical comment.
    (payload / 'iap2.cfg').write_bytes(config.rstrip(b'\n') + b'\n\n# Experimental MU1427 route guidance B1\n[ident]\nsendmsgs=0x5200,0x5203\nrecvmsgs=0x5201,0x5202,0x5204\n')
    assert (payload / 'iap2.cfg').stat().st_size == 6006
    manifest['config_stock_sha256'] = patch.b2.sha(config)
    manifest['config_patched_sha256'] = patch.b2.sha((payload / 'iap2.cfg').read_bytes())
    manifest['installer_revision'] = f'{args.revision}-install-r1'
    (payload / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    (payload / 'VERSION').write_text(f"{manifest['build']}-{manifest['patched_sha256'][:8]}\n")
    scripts = stage / 'Toolbox/scripts'
    (scripts / 'cpmap_rgi_b1.sh').write_text(installer(manifest))
    (scripts / 'cpmap_navrecon.sh').write_text(collector())
    for action in ('install', 'status', 'restore'):
        wrapper = '''#!/bin/ksh
S=/mnt/app/eso/hmi/engdefs/scripts/mqb/cpmap_rgi_b1.sh
[ -f "$S" ] || S=/net/mmx/mnt/app/eso/hmi/engdefs/scripts/mqb/cpmap_rgi_b1.sh
'''
        if action == 'install':
            wrapper += '''for V in /net/mmx/fs/sda0 /net/mmx/fs/sdb0 /fs/sda0 /fs/sdb0; do
    P=$V/Custom/route_guidance_b1
    if [ -s "$P/VERSION" ]; then /bin/ksh "$S" install "$P"; exit $?; fi
done
echo "CPMAP_RGI_FAIL=SD_PAYLOAD_NOT_FOUND"
exit 1
'''
        else: wrapper += f'/bin/ksh "$S" {action}\n'
        (scripts / f'cpmap_rgi_{action}.sh').write_text(wrapper)
    for name in ('cpmap_rgi_b1.sh', 'cpmap_navrecon.sh', 'cpmap_rgi_install.sh', 'cpmap_rgi_status.sh', 'cpmap_rgi_restore.sh'):
        (scripts / name).chmod(0o755)
    menu = stage / 'Toolbox/GEM/carplay-maps-vc.esd'
    data = menu.read_bytes().replace(b'Collect navigation research data to SD (Log/cpmap-navrecon-*)', b'Capture route-guidance data to SD (C3)')
    restore_label = 'B1/B2/B3/B4' if args.revision == 'B4' else 'B1/B2/B3'
    for action, label in (('install', f'EXPERIMENTAL MU1427: install route guidance {args.revision}'),
                          ('status', f'Route guidance {args.revision} status'),
                          ('restore', f'Restore factory iAP2 driver and config ({restore_label})')):
        data += f'\r\nscript\r\n    value   sys 1 0x0100 "/eso/hmi/engdefs/scripts/mqb/cpmap_rgi_{action}.sh"\r\n    label   "{label}"\r\n'.encode()
    menu.write_bytes(data)
    source = payload / 'source'
    source.mkdir()
    for name in ('driver-hooks.S', 'patch-driver.py', 'publication-hooks.S', 'patch-publication.py',
                 'build-publication-package.py', 'rg-b1.sh', 'capture-rgi.sh', 'test-driver.py',
                 'test-publication.py', 'test-install.py', 'test-install-b3.py', 'test-capture.py',
                 'test-capture-b3.py', 'rgi_decode.py', 'test-rgi-decode.py', 'rgi_publication.py',
                 'test-rgi-publication.py', 'DECODER.md', 'PUBLICATION.md', 'TEST-B3.md',
                 'TEST-B1.md', 'TEST-B2.md', 'B1-RESULTS.md', 'B2-RESULTS.md', 'README.md'):
        shutil.copy2(HERE / name, source / name)
    if args.revision == 'B4':
        for name in ('publication-activation.S', 'patch-activation.py', 'test-activation.py',
                     'test-install-b4.py', 'B3-RESULTS.md', 'TEST-B4.md'):
            shutil.copy2(HERE / name, source / name)
    shutil.copy2(REPO / 'LICENSE', source / 'LICENSE')
    archive = out / f'MU1427-route-guidance-{args.revision}-toolbox.zip'
    with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED) as z:
        for p in sorted(stage.rglob('*')):
            if p.is_file(): z.write(p, p.relative_to(stage))
    digest = patch.b2.sha(archive.read_bytes())
    (out / 'SHA256SUMS.txt').write_text(f'{digest}  {archive.name}\n')
    print(archive)
    print('sha256=' + digest)
    print('driver=' + manifest['patched_sha256'])


if __name__ == '__main__':
    main()
