#!/usr/bin/env python3
"""Exercise real menu classes, Java persistence, routing and CF declarations.
SPDX-License-Identifier: GPL-3.0-or-later
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'port'))
from firmware import sha


def main():
 p=argparse.ArgumentParser(description=__doc__)
 for n in ('build','java-home','stock-jar','output'):p.add_argument('--'+n,type=Path,required=True)
 a=p.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
 java,javac=(str(a.java_home/'bin'/n) for n in ('java','javac'))
 build=a.build.resolve();stock=a.stock_jar.resolve();cp=str(build/'VCMenu.jar')+':'+str(stock)
 tests=build/'src/vc-menu/tests';names=['CardPositionSettingsTest','Card791OptionsTest','MapSwitchSettingsTest','ProjectionSettingsTest','WirelessCarPlaySettingsTest','ProjectionPolicyTest','FeatureFlowTest','PublicProfileTest']
 subprocess.run([javac,'-source','7','-target','7','-Xlint:-options','-cp',cp,'-d',str(out),*[str(tests/(n+'.java')) for n in names],str(HERE/'TestDisplay.java')],check=True)
 results={}
 for name in names+['TestDisplay']:
  r=subprocess.run([java,'-Xverify:all','-Dcpvc.offline=1','-Dcpmap.ui.cluster=791','-cp',str(out)+':'+cp,name,str(out/('state-'+name))],check=True,capture_output=True,text=True);results[name]=r.stdout.strip()
 routing=str(build/'CarPlayClusterControls.jar')+':'+cp
 subprocess.run([javac,'-cp',routing,'-d',str(out),str(tests/'ActualControlHookTest.java')],check=True)
 results['routing']=subprocess.check_output([java,'-Xverify:all','-cp',str(out)+':'+routing,'ActualControlHookTest',str(out/'state-routing')],text=True).strip()
 # Native ARM Linux ASan/UBSan avoids x86 emulation and macOS dyld differences.
 native=build/'src/card-core';matrix=out/'matrix.c'
 matrix.write_text('#define main ignored_original_main\n#include "'+str(native/'tests/test_scene_contract.original.c')+'"\n#undef main\n'+(HERE/'test_display.c').read_text())
 flags='-std=gnu99 -O1 -g -Wall -Wextra -Werror -Wno-unused-function -fsanitize=address,undefined -DCPMAP_FIRMWARE=1367 -DCPMAP_CLUSTER=791 -pthread'
 script='set -eu\nexport ASAN_OPTIONS=halt_on_error=1:detect_leaks=1 UBSAN_OPTIONS=halt_on_error=1\n'
 for source,name in ((matrix,'native-display'),(native/'tests/test_card_transport.c','transport')):
  script+='cc '+flags+' -include "$SRC/source/profile_card.h" "'+str(source)+'" -ldl -o /w/'+name+'\n/w/'+name+'\n'
 (out/'test-native.sh').write_text(script)
 docker=['docker','--context','colima-cpmap-rgi','run','--rm','--pull=never','--network=none','-v',str(out)+':/w','-v',str(out)+':'+str(out),'-v',str(build)+':'+str(build)+':ro','-e','SRC='+str(native),'cpvc-settings-host-tests']
 r=subprocess.run([*docker,'sh','/w/test-native.sh'],capture_output=True,text=True,timeout=120)
 (out/'native.log').write_text(r.stdout+r.stderr)
 if r.returncode:raise RuntimeError(r.stdout+r.stderr)
 results['native']=r.stdout.strip()
 # Read a Java-written envelope using the actual C reader in another process.
 fixture=out/'cross-language';subprocess.run([java,'-cp',str(out)+':'+cp,'TestDisplay',str(fixture),'1','2'],check=True,capture_output=True)
 r=subprocess.check_output([*docker,'/w/native-display','/w/cross-language'],text=True)
 if r.strip()!='1,2,2':raise ValueError('Java/C preference parity failed')
 results['cross_language']=r.strip()
 result={'passed':True,'files':json.loads((build/'manifest.json').read_text())['files'],'results':results,'test_sha256':sha(Path(__file__).read_bytes()),'on_unit_validated':False}
 (out/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))


if __name__=='__main__':main()
