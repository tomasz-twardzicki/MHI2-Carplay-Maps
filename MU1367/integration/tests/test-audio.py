#!/usr/bin/env python3
"""Exercise progress registration/wire format plus text and faster artwork hooks."""
import argparse,hashlib,json,subprocess
from pathlib import Path
HERE=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser(description=__doc__)
 for n in ('build','java-home','stock-jar','output'):p.add_argument('--'+n,type=Path,required=True)
 a=p.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
 jar=a.build.resolve()/'CarPlayMU1367Audio.jar';stock=a.stock_jar.resolve();cp=str(jar)+':'+str(stock)
 revision=json.loads((a.build/'manifest.json').read_text()).get('revision','r2')
 names=['TestText','TestCover','TestProgress' if revision=='r2' else 'TestArtworkR3'];sources=[(HERE/'artwork-test/java' if revision!='r2' else HERE/'java')/(n+'.java') for n in names]
 subprocess.run([str(a.java_home/'bin/javac'),'-source','7','-target','7','-Xlint:-options','-bootclasspath',str(stock),'-cp',cp,'-d',str(out),*map(str,sources)],check=True)
 results={n:subprocess.check_output([str(a.java_home/'bin/java'),'-Xverify:all','-cp',str(out)+':'+cp,'com.cpmap.audio.'+n],text=True).strip() for n in names}
 r={'passed':True,'audio_sha256':sha(jar),'results':results,'test_sha256':sha(Path(__file__)),'source_sha256':{str(f.relative_to(HERE)):sha(f) for f in sources},'on_unit_validated':False}
 (out/'result.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r))
if __name__=='__main__':main()
