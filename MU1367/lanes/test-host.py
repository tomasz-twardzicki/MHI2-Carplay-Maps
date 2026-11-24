#!/usr/bin/env python3
"""Lane protocol/factory output tests plus the maintained settings regressions.
SPDX-License-Identifier: GPL-3.0-or-later
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import stage
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'port'))
from firmware import sha


def main():
 p=argparse.ArgumentParser(description=__doc__)
 for n in ('build','java-home','stock-jar','output'):p.add_argument('--'+n,type=Path,required=True)
 a=p.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=False);build=a.build.resolve()
 java,javac=(str(a.java_home/'bin'/n) for n in ('java','javac'))
 cp=str(build/'hmi/guidance/tests')+':'+str(build/'hmi/CarPlayMU1367Guidance.jar')+':'+str(a.stock_jar.resolve())
 subprocess.run([javac,'-cp',cp,'-d',str(out),str(HERE/'TestLanes.java')],check=True)
 lanes=subprocess.check_output([java,'-Xverify:all','-cp',str(out)+':'+cp,'com.cpmap.rgi.TestLanes'],text=True).strip()
 runtime=build/'runtime';cp=str(runtime/'VCMenu.jar')+':'+str(a.stock_jar.resolve())
 subprocess.run([javac,'-cp',cp,'-d',str(out),str(HERE/'TestCardDefault.java')],check=True)
 defaults=subprocess.check_output([java,'-Xverify:all','-cp',str(out)+':'+cp,'TestCardDefault',str(out/'card-state')],text=True).strip()
 shared=HERE.parent/'settings-v2/test-host.py';text=shared.read_text()
 matrix=(shared.parent/'test_display.c').read_text()
 seed=''' /* The new default must be map-only. Exercise ON explicitly for the
  * existing 16-case stream/layout matrix, then the transport suite tests
  * repeated live ON/OFF transitions separately. */
 d=create_alt_display();assert(d);assert(!strcmp(string(d,"initialURL"),"maps:/car/instrumentcluster/map"));drop(d);checks++;
 snprintf(path,sizeof(path),"%s/navigation-card.state",root);f=fopen(path,"wb");assert(f);
 {const char *body="format=1\\nposition=2\\ngeneration=1\\n";fprintf(f,"%scrc32=%x\\n",body,(unsigned)cpmap_card_crc((const unsigned char *)body,strlen(body)));}
 assert(!fclose(f));
'''
 matrix=stage.replace(matrix,' for(s=0;s<4;s++)for(l=0;l<4;l++){',seed+' for(s=0;s<4;s++)for(l=0;l<4;l++){')
 text=stage.replace(text,"(HERE/'test_display.c').read_text()",'MATRIX')
 env={'__file__':str(shared),'__name__':'lane_settings_host','MATRIX':matrix};exec(compile(text,str(shared),'exec'),env)
 old=sys.argv;sys.argv=['lane-settings-host','--build',str(runtime),'--java-home',str(a.java_home),'--stock-jar',str(a.stock_jar),'--output',str(out/'settings')]
 try:env['main']()
 finally:sys.argv=old
 result={'passed':True,'files':json.loads((build/'manifest.json').read_text())['files'],'lanes':lanes,'card_defaults':defaults,'settings':json.loads((out/'settings/result.json').read_text()),'test_sha256':sha(Path(__file__).read_bytes()),'on_unit_validated':False}
 (out/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))


if __name__=='__main__':main()
