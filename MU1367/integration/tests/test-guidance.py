#!/usr/bin/env python3
"""Exercise actual release adapters and factory serializers on the host VM."""
import argparse,json,subprocess,hashlib
from pathlib import Path
HERE=Path(__file__).resolve().parent
p=argparse.ArgumentParser()
for n in ('build','java-home','stock-jar','output'):p.add_argument('--'+n,type=Path,required=True)
a=p.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
cp=':'.join(map(str,[out,a.build.resolve()/'CarPlayMU1367Guidance.jar',a.build.resolve()/'CarPlayMU1367Audio.jar',a.stock_jar.resolve()]))
sources=list((HERE/'java').glob('*.java'))
subprocess.run([str(a.java_home/'bin/javac'),'-cp',cp,'-d',str(out),*map(str,sources)],check=True)
results={}
for name,args in [('TestLive',[]),('TestLanes',[]),('TestUturn',[]),('TestUturnQnx',[]),('TestRecovery',[str(out/'recovery')]),('TestRoad',[]),('TestLaneOutlines',[]),('TestArrow',[]),('TestArrowQnx',[]),('TestSessions',[str(out/'sessions')]),('TestLaneCanonical',[str(out/'evidence')]),('TestPlaceholder',[]),('TestLaneWindow',[]),('TestNormalLanes',[]),('TestCover',[]),('TestText',[])]:
 package='audio' if name in ('TestCover','TestText') else 'rgi'
 results[name]=subprocess.check_output([str(a.java_home/'bin/java'),'-Xverify:all','-cp',cp,'com.cpmap.'+package+'.'+name,*args],text=True).strip()
r={'passed':True,'results':results,'guidance_sha256':hashlib.sha256((a.build/'CarPlayMU1367Guidance.jar').read_bytes()).hexdigest(),'on_unit_validated':False}
(out/'result.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r))
