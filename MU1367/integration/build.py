#!/usr/bin/env python3
"""Build canonical MU1367 runtime sources against pinned factory classes (GPL-3.0+)."""
import argparse, hashlib, json, shutil, struct, subprocess, zipfile
from pathlib import Path
HERE = Path(__file__).resolve().parent

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def run(*args):
    subprocess.run(list(map(str, args)), check=True)

def jar(path, root, day):
    with zipfile.ZipFile(path, 'w') as z:
        for f in sorted(root.rglob('*.class')):
            raw = f.read_bytes()
            assert struct.unpack_from('>H', raw, 6)[0] == 46, f
            i = zipfile.ZipInfo(str(f.relative_to(root)), (2026, 10, day, 0, 0, 0))
            i.compress_type = zipfile.ZIP_DEFLATED
            i.external_attr = 0o100644 << 16
            z.writestr(i, raw)

def main():
    p = argparse.ArgumentParser(description=__doc__)
    for n in ('java-home', 'stock-jar', 'asm-dir', 'toolchain', 'output'):
        p.add_argument('--'+n, type=Path, required=True)
    a = p.parse_args(); out = a.output.resolve(); out.mkdir(parents=True, exist_ok=False)
    java = a.java_home/'bin/java'; javac = a.java_home/'bin/javac'
    stock = str(a.stock_jar.resolve())
    asm = ':'.join(str((a.asm_dir/n).resolve()) for n in ('asm-9.7.jar', 'asm-tree-9.7.jar'))
    factory = json.loads((HERE/'FACTORY.json').read_text())
    pins = dict(factory['classes'])
    pins.update(json.loads((HERE/'ARTWORK-FACTORY.json').read_text())['classes'])
    pins['de/vw/mib/bap/mqbab2/navsd/functions/TurnToInfo.class'] = '7cfee871de95fb35732fb278ada65035700d40a551e9807f3e53c6278b087430'
    pins['de/vw/mib/view/internal/AbstractViewHandler.class'] = '7afadc2e226ef2b3444ea0e138e82fda5d839401d58e2beb0bcc00170972ddd6'
    with zipfile.ZipFile(a.stock_jar) as z:
        for name, h in pins.items():
            raw = z.read(name); assert hashlib.sha256(raw).hexdigest() == h, name
            f = out/'stock'/name; f.parent.mkdir(parents=True, exist_ok=True); f.write_bytes(raw)
    for feature in ('guidance', 'audio'):
        w = out/feature
        for d in ('helpers', 'tools', 'patched'): (w/d).mkdir(parents=True)
        run(javac, '-source', '7', '-target', '7', '-Xlint:-options', '-bootclasspath', stock,
            '-cp', stock, '-d', w/'helpers', *sorted((HERE/'src'/feature).glob('*.java')))
        names = ['PatchLive'] if feature=='guidance' else ['PatchTextObserver', 'PatchText', 'PatchCover']
        run(javac, '-cp', asm, '-d', w/'tools', *[HERE/'tools'/(n+'.java') for n in names])
        cmd = [java, '-cp', str(w/'tools')+':'+asm]
        if feature=='guidance':
            run(*cmd, 'PatchLive', out/'stock', w/'helpers', w/'patched')
        else:
            for name in pins:
                if '/navsd/' in name or '/view/' in name: continue
                tool = 'PatchTextObserver' if name.endswith('HsmTarget.class') else 'PatchText' if name.endswith('CurrentStationInfo.class') else 'PatchCover'
                run(*cmd, tool, out/'stock'/name, *([w/'helpers'] if tool=='PatchTextObserver' else []), w/'patched')
        jar(out/('CarPlayMU1367'+feature.title()+'.jar'), w/'patched', 27 if feature=='guidance' else 29)
    for mode in ('base', 'tuning'):
        w = out/mode; w.mkdir()
        shutil.copytree(HERE/'src/runtime', w/'src')
        if mode=='tuning':
            for f in (HERE/'src/card-tuning').rglob('*'):
                if f.is_file(): shutil.copy2(f, w/'src'/f.relative_to(HERE/'src/card-tuning'))
        for d in ('classes','tools','menu'): (w/d).mkdir()
        run(javac, '-encoding', 'UTF-8', '-g:none', '-source', '7', '-target', '7', '-Xlint:-options',
            '-bootclasspath', stock, '-cp', stock, '-d', w/'classes', *sorted((w/'src/vc-menu/src').rglob('*.java')))
        run(javac, '-cp', asm, '-d', w/'tools', HERE/'tools/PatchSettings.java')
        cmd = [java, '-cp', str(w/'tools')+':'+asm, 'PatchSettings']
        run(*cmd, 'helpers', w/'classes', w/'menu')
        run(*cmd, 'menu', out/'stock/de/vw/mib/view/internal/AbstractViewHandler.class', w/'menu')
        jar(w/'VCMenu.jar', w/'menu', 28)
        native = w/'src/card-core/source'; root = a.toolchain.resolve()/'sdp/target/qnx6'
        flags = ['--target=armv7-none-eabi','-D__QNXNTO__','-D__QNX__','-D__ARM__','-D__LITTLEENDIAN__',
            '--sysroot='+str(root),'-isystem',str(root/'usr/include'),'-march=armv7-a','-mfloat-abi=softfp',
            '-mno-unaligned-access','-fno-short-enums','-fno-stack-protector','-fno-builtin','-std=gnu99','-O2',
            '-Wall','-Wextra','-Werror','-Wno-unused-function','-fPIC','-DCPMAP_FIRMWARE=1367','-DCPMAP_CLUSTER=791',
            '-include',str(native/'profile_card.h')]
        run('clang', *flags, '-c', native/'altscreen_handshake_probe.c', '-o', w/'core.o')
        lib='/opt/qnx650/target/qnx6/armle-v7/lib'
        run('docker','--context','colima-cpmap-rgi','run','--rm','--pull=never','--network=none','-v',str(w)+':/w',
            'cpmap-qnx65-sdp','arm-unknown-nto-qnx6.5.0eabi-ld','-m','armnto','-shared','-L'+lib,
            lib+'/crti.o',lib+'/crtbegin.o','/w/core.o','-lsocket','-lc',lib+'/crtend.o',lib+'/crtn.o','-o','/w/core.so')
    expected=json.loads((HERE/'RUNTIME.json').read_text())
    for name,h in expected['rebuild'].items(): assert sha(out/name)==h, name
    (out/'manifest.json').write_text(json.dumps({'passed':True,'version':'1.4.2','files':expected['rebuild'],
        'source_sha256':{str(f.relative_to(HERE)):sha(f) for f in (HERE/'src').rglob('*') if f.is_file()}},indent=2)+'\n')
    print('Canonical source rebuild matches all six validated runtime payloads.')
if __name__=='__main__': main()
