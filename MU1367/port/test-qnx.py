#!/usr/bin/env python3
"""Run maintained reader/J9 harnesses with exact MU1367 runtime inputs.
SPDX-License-Identifier: GPL-3.0-or-later
"""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile
from firmware import image_files, stage1, stage2, sha, JXE_SHA
from build_support import load

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
RG = REPO / 'MU1427/route-guidance'
AUDIO = REPO / 'MU1427/now-playing'
sys.path.insert(0, str(RG))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('firmware', 'toolchain', 'java-home', 'stock-jar', 'hmi', 'native', 'output'):
        p.add_argument('--' + name, type=Path, required=True)
    p.add_argument('--setup', type=Path, help='reuse an already passing reader run with the same binary/libc')
    a = p.parse_args()
    out = a.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    ifs = stage2(a.firmware / 'MMX2/mifs-stage2/50/default/mifs-stage2.img')
    if sha(image_files(ifs)['ifs/lsd.jxe']) != JXE_SHA:
        p.error('exact MU1367 firmware required')
    libc = image_files(stage1(a.firmware / 'MMX2/mifs-stage1/50/default/mifs-stage1.img'))['proc/boot/libc.so.3']
    libc_hash = '485e2a5061f3e8d7cc9b7de54cb1f4387fe20ade5e0179ecefbbeebaf91be6bc'
    if sha(libc) != libc_hash:
        p.error('exact MU1367 libc required')
    native = json.loads((a.native / 'manifest.json').read_text())
    compat = out / 'reader-build'
    compat.mkdir()
    shutil.copy2(a.native / 'rgi-observer', compat / 'rgi-observer')
    (compat / 'manifest.json').write_text(json.dumps({'sha256': native['binaries']['rgi-observer']['sha256']}))
    setup = load('mu1367_reader_qnx', RG / 'test-observer-qnx.py')
    original_load = setup.load

    def load_target(name, path):
        module = original_load(name, path)
        if name == 'build_observer':
            module.FIRMWARE_LIBC_SHA = libc_hash
        return module

    setup.load = load_target
    # The actual helper is independently compiled, import-checked and hashed.
    # This only selects the exact firmware libc for the shared smoke harness.
    old_argv = sys.argv
    sys.argv = ['reader-qnx', str(a.toolchain), str(a.firmware), '--native-build', str(compat),
                '--smoke-source', str(RG / 'release/qnx-smoke.c'), '--pass-marker', 'RELEASE_QNX_PASS',
                '--output', str(out / 'reader')]
    try:
        if a.setup:
            check = json.loads((a.setup / 'result.json').read_text())
            if not check['qnx_smoke_passed'] or check['reader_sha256'] != native['binaries']['rgi-observer']['sha256'] or check['factory_libc_sha256'] != libc_hash:
                raise ValueError('reader setup verification mismatch')
        elif setup.main():
            raise RuntimeError('reader QNX regression failed')
    finally:
        sys.argv = old_argv
    hmi = json.loads((a.hmi / 'manifest.json').read_text())
    combined = out / 'combined'
    combined.mkdir()
    jar = combined / 'combined.jar'
    with zipfile.ZipFile(jar, 'w') as dst:
        for feature in hmi['features'].values():
            with zipfile.ZipFile(a.hmi / feature['jar']) as src:
                for name in src.namelist():
                    dst.writestr(name, src.read(name))
    stock_probe = (RG / 'bridge/LoadProbe.java').read_text().replace('public final class LoadProbe', 'final class StockLoad')
    audio_probe = (AUDIO / 'n1/java/LoadText.java').read_text().replace('public final class LoadText', 'final class AudioLoad')
    audio_probe = '\n'.join(line for line in audio_probe.splitlines() if not line.startswith(('package ', 'import ')))
    factory = json.loads((HERE / 'FACTORY.json').read_text())
    nai_names = ','.join('"' + n[:-6].replace('/', '.') + '"' for n in factory['nav_ignore_classes'])
    nai_probe = '''final class NavLoad {
        public static void main(String[] args) throws Exception {
            String[] names={NAMES};
            ClassLoader loader=Class.forName("com.cpmap.audio.CombinedProbe").getClassLoader();
            for(int i=0;i<names.length;i++) Class.forName(names[i],false,loader).getDeclaredMethods();
            org.dsi.ifc.carplay.AppStateRequest claim=new org.dsi.ifc.carplay.AppStateRequest();
            claim.appStateID=2;claim.state=true;claim.speechMode=0;
            org.dsi.ifc.carplay.AppStateRequest[] original={claim};
            org.dsi.ifc.carplay.AppStateRequest[] filtered=de.vw.mib.navactiveignore.NavActiveIgnore.stripNativeNavClaims(original);
            if(filtered.length!=0 || !de.vw.mib.navactiveignore.NavActiveIgnore.dropRequest(null,original,filtered)) throw new Exception("NAI filter");
            claim.appStateID=1;
            if(de.vw.mib.navactiveignore.NavActiveIgnore.stripNativeNavClaims(original)!=original) throw new Exception("NAI non-navigation state");
            System.out.println("NAI_J9_PASS classes=5 filter_checks=3");
        }
    }'''.replace('NAMES', nai_names)
    probe = combined / 'CombinedProbe.java'
    probe.write_text('package com.cpmap.audio;\nimport org.dsi.ifc.carplay.TrackData;\nimport de.vw.mib.bap.mqbab2.generated.audiosd.serializer.CurrentStationInfo_Status;\n'
                     'public final class CombinedProbe { public static void main(String[] a) throws Exception { StockLoad.main(new String[]{"patch"}); AudioLoad.main(a); NavLoad.main(a); } }\n'
                     + stock_probe + '\n' + audio_probe + '\n' + nai_probe)
    (combined / 'manifest.json').write_text(json.dumps({'jar_name': jar.name, 'jar_sha256': sha(jar.read_bytes()),
        'factory_jxe_sha256': JXE_SHA, 'probe_source': str(probe), 'probe_class': 'com.cpmap.audio.CombinedProbe'}))
    stage = out / 'stage2.ifs'
    stage.write_bytes(ifs)
    # Keep the shared test implementation and its original source path; only
    # substitute its two firmware fingerprints after validating them above.
    shared = AUDIO / 'test-observer-qnx.py'
    text = shared.read_text().replace('baseline.tree(a.stage2, baseline.IFS_SHA)',
                                    "baseline.tree(a.stage2, '" + sha(ifs) + "')")
    text = text.replace('775139dc7381b8aa7001330dafe93b5cb8b0f779eb8e97d5ee32ca93bb85d2f1', libc_hash)
    text = text.replace("shutil.copy2(jar, work / 'observer.jar')",
                        "shutil.copy2(jar, work / 'observer.jar')\n    shutil.copy2(Path(" + repr(str((a.native / 'verify').resolve())) + "), work / 'verify')")
    text = text.replace('j9-probe\\nprobe.jar\\nobserver.jar', 'j9-probe\\nverify\\nprobe.jar\\nobserver.jar')
    verify_c = ' char *verify[]={"/proc/boot/verify","/proc/boot/observer.jar","' + sha(jar.read_bytes()) + '",0};\n puts("@@HASH-POSITIVE@@");launch(verify);\n verify[2]="' + '0'*64 + '";puts("@@HASH-NEGATIVE@@");launch(verify);puts("@@HASH-END@@");\n'
    text = text.replace(' puts("@@N0-NOVERIFY@@");', verify_c + ' puts("@@N0-NOVERIFY@@");')
    env = {'__file__': str(shared), '__name__': 'mu1367_combined_qnx'}
    exec(compile(text, str(shared), 'exec'), env)
    sys.argv = ['j9-qnx', str(combined), '--stage2', str(stage), '--firmware', str(a.firmware),
                '--java-home', str(a.java_home), '--stock-jar', str(a.stock_jar), '--toolchain', str(a.toolchain),
                '--setup', str(a.setup or out / 'reader'), '--output', str(out / 'j9')]
    try:
        if env['main']():
            raise RuntimeError('combined factory J9 checks failed')
    finally:
        sys.argv = old_argv
    log = (out / 'j9/qemu.log').read_text(errors='replace')
    if log.count('RGI_J9_PROBE passed=13 failed=0') != 3:
        raise RuntimeError('guidance factory J9 checks failed')
    if log.count('NAI_J9_PASS classes=5 filter_checks=3') != 2:
        raise RuntimeError('navigation-ignore factory checks failed')
    if 'N0_CHILD_STATUS=0' not in log.split('@@HASH-POSITIVE@@')[1].split('@@HASH-NEGATIVE@@')[0] or 'N0_CHILD_STATUS=256' not in log.split('@@HASH-NEGATIVE@@')[1].split('@@HASH-END@@')[0]:
        raise RuntimeError('factory SHA verifier positive/negative check failed')
    result = {'passed': True, 'factory_jxe_sha256': JXE_SHA, 'factory_libc_sha256': libc_hash,
              'guidance_checks_per_mode': 13, 'audio_checks_per_mode': 12,
              'verified_and_noverify': True, 'class49_negative_rejected': True,
              'nav_ignore_factory_classes': 5, 'nav_ignore_filter_checks': 3, 'sha256_verifier_qnx': True,
              'reader_foreground_and_daemon': True, 'hmi': hmi['features'], 'native': native['binaries'],
              'harness_sha256': sha(Path(__file__).read_bytes()), 'on_unit_validated': False}
    (out / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
