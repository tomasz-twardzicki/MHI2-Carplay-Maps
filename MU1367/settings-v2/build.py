#!/usr/bin/env python3
"""Build the MU1367/791 settings extension from pinned upstream source.
SPDX-License-Identifier: GPL-3.0-or-later
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import zipfile

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[1]
sys.path.insert(0,str(HERE.parent/'port'))
from firmware import sha
from build_support import load


def replace(text,old,new,count=1):
    if text.count(old)!=count:raise ValueError('Upstream source seam changed: '+old[:80])
    return text.replace(old,new)


def stage_sources(out):
    upstream=json.loads((HERE/'UPSTREAM.json').read_text())
    for name,digest in upstream['source_files'].items():
        if sha((HERE/'vendor'/name).read_bytes())!=digest:raise ValueError('Pinned source changed: '+name)
    src=out/'src';shutil.copytree(HERE/'vendor',src)
    java=src/'vc-menu/src/org/omonob/cpmap/ui'
    shutil.copy2(HERE/'DisplaySettings.java',java/'DisplaySettings.java')
    p=java/'IndependentMenuViewBridge.java';s=p.read_text()
    s=replace(s,'FIELDS={0,1,3,5}','FIELDS={0,1,3,5,6,7}')
    for name,kind in [('rows','ButtonModel'),('names','TextAreaModel'),('values','TextAreaModel')]:
        s=replace(s,name+'=new '+kind+'[4]',name+'=new '+kind+'[FIELDS.length]')
    s=replace(s,'new WidgetModel[4]','new WidgetModel[FIELDS.length]')
    s=replace(s,'for(int i=0;i<4;i++)','for(int i=0;i<FIELDS.length;i++)',2)
    s=replace(s,'action>=0 && action<4','action>=0 && action<FIELDS.length')
    s=replace(s,'        cardStore.read();','        cardStore.read();DisplaySettings.systemStore().read();')
    s=replace(s,'names[i].set_text(field<2?', 'names[i].set_text(field>=6?DisplaySettings.name(field):field<2?')
    s=replace(s,'choice(field,field<2?', 'choice(field,field>=6?DisplaySettings.systemStore().read().choice(field):field<2?')
    s=replace(s,'current=activeField<2?', 'current=activeField>=6?DisplaySettings.systemStore().read().choice(activeField):activeField<2?')
    s=replace(s,'        if(field==5)return MenuClusterProfile.cardLabel', '        if(field>=6)return DisplaySettings.label(field,value);\n        if(field==5)return MenuClusterProfile.cardLabel')
    s=replace(s,'        if(field==5){','        if(field>=6){DisplaySettings.systemStore().select(field,selected);closePopup();refresh();return;}\n        if(field==5){')
    s=replace(s,'return field==5?MenuClusterProfile.cardCount()', 'return field>=6?DisplaySettings.count(field):field==5?MenuClusterProfile.cardCount()')
    s=s.replace('fields=4','fields=6');p.write_text(s)
    native=src/'card-core/source';shutil.copy2(HERE/'display_settings.h',native/'display_settings.h')
    p=native/'altscreen_handshake_probe.c';s=p.read_text()
    s=replace(s,'#include "navigation_card_scene.h"','#include "display_settings.h"\n#include "navigation_card_scene.h"')
    s=replace(s,'    card_refresh_preference();position=card_snapshot().position;','    cpvc_display_refresh();card_refresh_preference();position=card_snapshot().position;')
    s=replace(s,'set_int(display,"maxFPS",ALTSCREEN_DISPLAY_MAX_FPS)','set_int(display,"maxFPS",cpvc_display_fps())')
    s=replace(s,'static void *passive_listener_thread(void *context)\n{','static void *passive_listener_thread(void *context)\n{\n    const unsigned int configured_idr=(unsigned int)cpvc_display_idr();')
    s=replace(s,'(frames % ALTSCREEN_FORCE_KEYFRAME_INTERVAL)', '(frames % configured_idr)')
    s=replace(s,'(int)ALTSCREEN_FORCE_KEYFRAME_INTERVAL,','(int)configured_idr,')
    p.write_text(s)
    p=native/'navigation_card_scene.h';s=p.read_text()
    s=replace(s,' (void)index;return r;',' cpvc_display_area(&r.x,&r.y,&r.width,&r.height);(void)index;return r;')
    # Preserve our existing scene URL for the two existing layouts. The compact
    # choices use upstream's topAligned/no-ETA/no-speed-limit scene request.
    s=replace(s,' return position==CPMAP_CARD_OFF?"maps:/car/instrumentcluster/map":"maps:/car/instrumentcluster?showETA=no&maneuverLayout=topAligned&showSpeedLimit=no";',
        ' if(position==CPMAP_CARD_OFF)return "maps:/car/instrumentcluster/map";\n return cpvc_display_snapshot().layout<2?"maps:/car/instrumentcluster":"maps:/car/instrumentcluster?showETA=no&maneuverLayout=topAligned&showSpeedLimit=no";')
    p.write_text(s)
    return src


def write_jar(path,root):
    with zipfile.ZipFile(path,'w',compression=zipfile.ZIP_DEFLATED) as z:
        for p in sorted(root.rglob('*.class')):
            data=p.read_bytes()
            if struct.unpack_from('>H',data,6)[0]!=46:raise ValueError('Non-CDC class')
            info=zipfile.ZipInfo(str(p.relative_to(root)),(2026,10,28,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o100644<<16;z.writestr(info,data)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('java-home','stock-jar','asm-dir','toolchain','output'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=False);src=stage_sources(out)
    factory=json.loads((HERE.parent/'port/FACTORY.json').read_text());base=load('base_hmi',HERE.parent/'port/build-hmi.py')
    content=load('base_content',REPO/'MU1427/route-guidance/build-live-bridge.py').stock_content(a.stock_jar)
    if content!=factory['stock_content_sha256']:p.error('Exact MU1367 classes required')
    java,javac=(str(a.java_home/'bin'/n) for n in ('java','javac'))
    asm=':'.join(str((a.asm_dir/n).resolve()) for n in ('asm-9.7.jar','asm-tree-9.7.jar'))
    for n in ('classes','tools','menu','controls','stock'):(out/n).mkdir()
    stock=str(a.stock_jar.resolve())
    subprocess.run([javac,'-encoding','UTF-8','-g:none','-source','7','-target','7','-Xlint:-options','-bootclasspath',stock,'-cp',stock,'-d',str(out/'classes'),*[str(f) for f in (src/'vc-menu/src').rglob('*.java')]],check=True)
    subprocess.run([javac,'-cp',asm,'-d',str(out/'tools'),str(HERE/'PatchSettings.java')],check=True)
    tool=[java,'-cp',str(out/'tools')+':'+asm,'PatchSettings']
    target='de/vw/mib/view/internal/AbstractViewHandler.class'
    with zipfile.ZipFile(a.stock_jar) as z:(out/'stock/AbstractViewHandler.class').write_bytes(z.read(target))
    subprocess.run([*tool,'helpers',str(out/'classes'),str(out/'menu')],check=True)
    subprocess.run([*tool,'menu',str(out/'stock/AbstractViewHandler.class'),str(out/'menu')],check=True)
    write_jar(out/'VCMenu.jar',out/'menu')
    baseline=REPO/'MU1367/791_AID12.3/payload/common/CarPlayClusterControls.jar'
    if sha(baseline.read_bytes())!='c8ceaad026c2efa20ec190260cb0ba7c982ccf7f1b3754c31c1930fa461ac032':p.error('Published controls baseline required')
    with zipfile.ZipFile(baseline) as z:
        for name in z.namelist():
            if name.endswith('.class'):
                file=out/'controls'/name;file.parent.mkdir(parents=True,exist_ok=True);file.write_bytes(z.read(name))
    bridge=out/'controls/de/vw/mib/carplay/clustercontrol/Mhi2ClusterControlBridge.class'
    subprocess.run([*tool,'controls',str(bridge),str(out/'controls')],check=True)
    subprocess.run([*tool,'legacy',str(out/'controls'),str(out/'controls')],check=True)
    for f in (out/'menu/org/omonob/cpmap/ui').glob('*.class'):
        if f.name.startswith(('ClusterCommandRouter','ProjectionRuntimePolicy','ProjectionSettings','MapSwitchSettings')):
            dest=out/'controls/org/omonob/cpmap/ui'/f.name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(f,dest)
    write_jar(out/'CarPlayClusterControls.jar',out/'controls')
    sysroot=a.toolchain.resolve()/'sdp/target/qnx6';core=src/'card-core/source'
    flags=['--target=armv7-none-eabi','-D__QNXNTO__','-D__QNX__','-D__ARM__','-D__LITTLEENDIAN__','--sysroot='+str(sysroot),'-isystem',str(sysroot/'usr/include'),'-march=armv7-a','-mfloat-abi=softfp','-mno-unaligned-access','-fno-short-enums','-fno-stack-protector','-fno-builtin','-std=gnu99','-O2','-Wall','-Wextra','-Werror','-Wno-unused-function','-fPIC','-DCPMAP_FIRMWARE=1367','-DCPMAP_CLUSTER=791','-include',str(core/'profile_card.h')]
    subprocess.run(['clang',*flags,'-c',str(core/'altscreen_handshake_probe.c'),'-o',str(out/'core.o')],check=True)
    lib='/opt/qnx650/target/qnx6/armle-v7/lib'
    subprocess.run(['docker','--context','colima-cpmap-rgi','run','--rm','--pull=never','--network=none','-v',str(out)+':/w','cpmap-qnx65-sdp',
        'arm-unknown-nto-qnx6.5.0eabi-ld','-m','armnto','-shared','-L'+lib,lib+'/crti.o',lib+'/crtbegin.o','/w/core.o','-lsocket','-lc',lib+'/crtend.o',lib+'/crtn.o','-o','/w/core.so'],check=True)
    manifest={'firmware':'MU1367','cluster':'791','upstream_commit':json.loads((HERE/'UPSTREAM.json').read_text())['commit'],'stock_content_sha256':content,'view_handler_sha256':sha((out/'stock/AbstractViewHandler.class').read_bytes()),'files':{n:sha((out/n).read_bytes()) for n in ('VCMenu.jar','CarPlayClusterControls.jar','core.so')},'defaults':{'stream':0,'layout':0,'max_fps':30,'idr_interval':20,'safe_area':[200,96,400,364]},'source_sha256':{str(f.relative_to(HERE)):sha(f.read_bytes()) for f in HERE.iterdir() if f.is_file() and f.suffix in ('.py','.java','.h')},'on_unit_validated':False}
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');print(json.dumps(manifest))


if __name__=='__main__':main()
