#!/usr/bin/env python3
"""Load the complete settings/guidance/audio stack on exact factory ARM J9.
SPDX-License-Identifier: GPL-3.0-or-later
"""
import argparse
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile
from elftools.elf.elffile import ELFFile
HERE=Path(__file__).resolve().parent
PORT=HERE.parent/'port'
sys.path.insert(0,str(PORT))
from firmware import sha,stage1,image_files

SETTINGS_PROBE='''final class SettingsLoad {
 public static void main(String[] a)throws Exception {
  ClassLoader loader=Class.forName("com.cpmap.audio.CombinedProbe").getClassLoader();
  String[] names={"de.vw.mib.view.internal.AbstractViewHandler","org.omonob.cpmap.ui.IndependentMenuViewBridge","de.esolutions.fw.dsi.keypanel.DSIKeyPanelDispatcher","de.vw.mib.carplay.clustercontrol.Mhi2ClusterControlBridge"};
  for(int i=0;i<names.length;i++)Class.forName(names[i],false,loader).getDeclaredMethods();
  org.omonob.cpmap.ui.DisplaySettings s=new org.omonob.cpmap.ui.DisplaySettings(new java.io.File("/ramdisk/display-test"));
  if(s.read().stream!=0||s.read().layout!=0)throw new Exception("Display defaults");
  s.select(6,1);s.select(7,2);
  if(s.read().stream!=1||s.read().layout!=2||s.read().generation!=2)throw new Exception("Display persistence");
  if(org.omonob.cpmap.ui.DisplaySettings.count(6)!=4||org.omonob.cpmap.ui.DisplaySettings.count(7)!=4)throw new Exception("Display options");
  System.out.println("SETTINGS_J9_PASS classes=4 defaults=1 persistence=1 choices=1");
 }
}'''


def main():
 p=argparse.ArgumentParser(description=__doc__)
 for n in ('runtime','parent-hmi','parent-native','setup','firmware','toolchain','java-home','stock-jar','output'):p.add_argument('--'+n,type=Path,required=True)
 a=p.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
 runtime=json.loads((a.runtime/'manifest.json').read_text())
 # Verify all strong native imports against the actual MU1367 libraries.
 files=image_files(stage1(a.firmware/'MMX2/mifs-stage1/50/default/mifs-stage1.img'));exports=set()
 for name,data in files.items():
  if name.endswith(('libc.so.3','libsocket.so.3')):
   elf=ELFFile(io.BytesIO(data));dyn=next(s for s in elf.iter_segments() if s['p_type']=='PT_DYNAMIC')
   exports.update(s.name for s in dyn.iter_symbols() if s['st_shndx']!='SHN_UNDEF')
 with (a.runtime/'core.so').open('rb') as f:
  elf=ELFFile(f);tags=list(elf.get_section_by_name('.dynamic').iter_tags())
  if any(t.entry.d_tag in ('DT_TEXTREL','DT_RPATH','DT_RUNPATH') for t in tags):raise ValueError('Unsafe core dynamic tags')
  imports={s.name for s in elf.get_section_by_name('.dynsym').iter_symbols() if s.name and s['st_shndx']=='SHN_UNDEF' and s['st_info']['bind']!='STB_WEAK'}
  if imports-exports:raise ValueError('Core imports unavailable: '+str(sorted(imports-exports)))
 compatible=out/'hmi';compatible.mkdir();parent=json.loads((a.parent_hmi/'manifest.json').read_text())
 features=dict(parent['features'])
 for v in features.values():shutil.copy2(a.parent_hmi/v['jar'],compatible/v['jar'])
 for key,name in [('menu','VCMenu.jar'),('controls','CarPlayClusterControls.jar')]:
  shutil.copy2(a.runtime/name,compatible/name);features[key]={'jar':name,'sha256':runtime['files'][name]}
 (compatible/'manifest.json').write_text(json.dumps({'features':features}))
 # Small factory-libc loader probe; no DIO, phone or video service is started.
 c=out/'core-check.c';c.write_text('''#include <dlfcn.h>
#include <stdio.h>
#include "display_settings.h"
int main(int argc,char **argv){struct cpvc_display_settings s;void *h=dlopen("/proc/boot/settings-core.so",RTLD_NOW|RTLD_LOCAL);(void)argv;if(!h){puts(dlerror());return 1;}if(!dlsym(h,"AirPlayCopyServerInfo"))return 2;
if(argc>1){if(cpvc_display_read("/ramdisk/display-test",&s)!=1||s.stream!=1||s.layout!=2||s.generation!=2)return 3;puts("SETTINGS_C_FACTORY_PREFS_PASS");}
else{if(cpvc_display_read("/ramdisk/display-test",&s)!=0||s.stream!=0||s.layout!=0||s.generation!=0)return 4;puts("SETTINGS_CORE_DLOPEN_PASS");}return 0;}
''')
 root=a.toolchain.resolve()/'sdp/target/qnx6'
 flags=['--target=armv7-none-eabi','-D__QNXNTO__','-D__QNX__','-D__ARM__','-D__LITTLEENDIAN__','--sysroot='+str(root),'-isystem',str(root/'usr/include'),'-march=armv7-a','-mfloat-abi=softfp','-fno-short-enums','-fno-builtin','-fno-stack-protector','-std=gnu99','-O2']
 subprocess.run(['clang',*flags,'-I',str(HERE),'-c',str(c),'-o',str(out/'core-check.o')],check=True)
 lib='/opt/qnx650/target/qnx6/armle-v7/lib'
 subprocess.run(['docker','--context','colima-cpmap-rgi','run','--rm','--pull=never','--network=none','-v',str(out)+':/w','cpmap-qnx65-sdp','arm-unknown-nto-qnx6.5.0eabi-ld','-m','armnto','-Qy','--dynamic-linker','/usr/lib/ldqnx.so.2','-L'+lib,lib+'/crt1.o',lib+'/crti.o',lib+'/crtbegin.o','/w/core-check.o','-lc',lib+'/crtend.o',lib+'/crtn.o','-o','/w/core-check'],check=True)
 shared=PORT/'test-qnx.py';text=shared.read_text()
 text=text.replace("with zipfile.ZipFile(jar, 'w') as dst:","seen=set()\n    with zipfile.ZipFile(jar, 'w') as dst:")
 text=text.replace('                    dst.writestr(name, src.read(name))','                    if name not in seen:\n                        dst.writestr(name, src.read(name));seen.add(name)')
 text=text.replace('AudioLoad.main(a); NavLoad.main(a);','AudioLoad.main(a); NavLoad.main(a); SettingsLoad.main(a);')
 text=text.replace("+ stock_probe + '\\n' + audio_probe + '\\n' + nai_probe)","+ stock_probe + '\\n' + audio_probe + '\\n' + nai_probe + '\\n' + SETTINGS_PROBE)")
 # Reset only this synthetic probe's own RAM preference between the two modes.
 # It tests both initial defaults and saved reload without touching user paths.
 probe=SETTINGS_PROBE.replace('org.omonob.cpmap.ui.DisplaySettings s=', 'new java.io.File("/ramdisk/display-test/display.state").delete();new java.io.File("/ramdisk/display-test/display.previous").delete();\n  org.omonob.cpmap.ui.DisplaySettings s=')
 # Extend the maintained factory harness's generated C/IFS inputs.
 needle="    env = {'__file__': str(shared), '__name__': 'mu1367_combined_qnx'}"
 hook='''    text=text.replace("shutil.copy2(jar, work / 'observer.jar')", "shutil.copy2(jar, work / 'observer.jar')\\n    shutil.copy2(Path(CORE_PATH), work / 'settings-core.so')\\n    shutil.copy2(Path(CHECK_PATH), work / 'core-check')")
    text=text.replace('j9-probe\\\\nverify\\\\nprobe.jar', 'j9-probe\\\\nverify\\\\nsettings-core.so\\\\ncore-check\\\\nprobe.jar')
    text=text.replace(' puts("@@N0-NOVERIFY@@");',' char *core[]={"/proc/boot/core-check",0,0}; puts("@@CORE-CHECK@@");launch(core); puts("@@CORE-END@@");\\n puts("@@N0-NOVERIFY@@");')
    text=text.replace(' puts("@@N0-NEGATIVE@@");',' core[1]="saved";puts("@@C-PREFS-CHECK@@");launch(core);puts("@@C-PREFS-END@@");\\n puts("@@N0-NEGATIVE@@");')
'''.replace('CORE_PATH',repr(str((a.runtime/'core.so').resolve()))).replace('CHECK_PATH',repr(str(out/'core-check')))
 text=text.replace(needle,hook+needle)
 env={'__file__':str(shared),'__name__':'settings_qnx_adaptation','SETTINGS_PROBE':probe}
 exec(compile(text,str(shared),'exec'),env)
 old=sys.argv;sys.argv=['settings-qnx','--firmware',str(a.firmware),'--toolchain',str(a.toolchain),'--java-home',str(a.java_home),'--stock-jar',str(a.stock_jar),'--hmi',str(compatible),'--native',str(a.parent_native),'--setup',str(a.setup),'--output',str(out/'run')]
 try:env['main']()
 finally:sys.argv=old
 log=(out/'run/j9/qemu.log').read_text(errors='replace')
 if log.count('SETTINGS_J9_PASS')!=2 or 'SETTINGS_CORE_DLOPEN_PASS' not in log or 'SETTINGS_C_FACTORY_PREFS_PASS' not in log:raise RuntimeError('Settings J9/native loading checks failed; inspect qemu.log')
 result={'passed':True,'files':runtime['files'],'combined_parent_settings_j9':True,'settings_checks_per_mode':7,'class_major':46,'class49_negative_rejected':True,'core_factory_dlopen':True,'java_c_preferences_factory_verified':True,'core_imports_verified':sorted(imports),'test_sha256':sha(Path(__file__).read_bytes()),'qemu_log_sha256':sha((out/'run/j9/qemu.log').read_bytes()),'on_unit_validated':False}
 (out/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))


if __name__=='__main__':main()
