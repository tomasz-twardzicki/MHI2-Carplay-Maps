#!/usr/bin/env python3
"""ASan/UBSan CF transport/default tests plus Java/C persistence parity."""
import argparse,hashlib,json,subprocess
from pathlib import Path
HERE=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    p=argparse.ArgumentParser()
    for n in ('build','java-home','stock-jar','output'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=False);results={}
    helper=(HERE/'test_display.c').read_text().split('int main(')[0]
    (out/'display-helper.h').write_text(helper)
    (out/'TestDisplay.java').write_text((HERE/'TestDisplay.java').read_text().replace('store.read().stream==0&&','store.read().stream==2&&'))
    for mode,build in [('base',a.build.resolve()/'base'),('tuning',a.build.resolve()/'tuning')]:
        work=out/mode;work.mkdir();source=build/'src/card-core'
        cp=str(build/'VCMenu.jar')+':'+str(a.stock_jar.resolve())
        subprocess.run([str(a.java_home/'bin/javac'),'-cp',cp,'-d',str(work),str(out/'TestDisplay.java')],check=True)
        java=[str(a.java_home/'bin/java'),'-Xverify:all','-cp',str(work)+':'+cp,'TestDisplay']
        text=subprocess.check_output([*java,str(work/'prefs')],text=True).strip()
        subprocess.run([*java,str(work/'cross'),'0','2'],check=True,capture_output=True)
        body='#define FIXTURE "'+str(source/'tests/test_scene_contract.original.c')+'"\n#define DISPLAY_HELPER "/w/display-helper.h"\n#define MAP_ONLY '+('1' if mode=='base' else '0')+'\n'+(HERE/'test_runtime.c').read_text()
        (work/'check.c').write_text(body)
        script='set -eu\nexport ASAN_OPTIONS=halt_on_error=1:detect_leaks=1 UBSAN_OPTIONS=halt_on_error=1\ncc -std=gnu99 -O1 -g -Wall -Wextra -Werror -Wno-unused-function -fsanitize=address,undefined -DCPMAP_FIRMWARE=1367 -DCPMAP_CLUSTER=791 -pthread -include "'+str(source/'source/profile_card.h')+'" /w/'+mode+'/check.c -ldl -o /w/'+mode+'/check\n/w/'+mode+'/check\n/w/'+mode+'/check /w/'+mode+'/cross\n'
        (work/'run.sh').write_text(script)
        r=subprocess.run(['docker','--context','colima-cpmap-rgi','run','--rm','--pull=never','--network=none','-v',str(out)+':/w','-v',str(a.build.resolve())+':'+str(a.build.resolve())+':ro','cpvc-settings-host-tests','sh','/w/'+mode+'/run.sh'],capture_output=True,text=True)
        (work/'run.log').write_text(r.stdout+r.stderr)
        if r.returncode:raise RuntimeError(r.stdout+r.stderr)
        assert 'GUIDANCE_V3_CF_PASS' in r.stdout and r.stdout.strip().endswith('5,2,2')
        code=subprocess.check_output([str(a.java_home/'bin/javap'),'-p','-c','-classpath',str(build/'VCMenu.jar'),'org.omonob.cpmap.ui.IndependentMenuViewBridge'],text=True)
        rows=code[code.index('static {};'):];assert ('iconst_4' if mode=='base' else 'bipush        6') in rows
        results[mode]={'java':text,'native':r.stdout.strip(),'core_sha256':sha(build/'core.so'),'menu_sha256':sha(build/'VCMenu.jar')}
    r={'passed':True,'core_sha256':results['base']['core_sha256'],'menu_sha256':results['base']['menu_sha256'],'results':results,'on_unit_validated':False,'test_sha256':sha(Path(__file__))}
    (out/'result.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r))
if __name__=='__main__':main()
