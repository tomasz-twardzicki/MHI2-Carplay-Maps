#!/usr/bin/env python3
"""Build a separate MU1367 artwork test or reproduce the historical R2 audio probe."""
import argparse,hashlib,json,subprocess,sys,zipfile
from pathlib import Path
HERE=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(HERE));from build import jar
def sha(b):return hashlib.sha256(b).hexdigest()
def main():
 p=argparse.ArgumentParser(description=__doc__)
 for n in ('java-home','stock-jar','asm-dir','output'):p.add_argument('--'+n,type=Path,required=True)
 p.add_argument('--candidate',action='store_true',help='Build unpinned candidate; exact factory class gates still apply')
 p.add_argument('--revision',choices=('artwork-r3','r2'),default='artwork-r3')
 a=p.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
 source=HERE/('tests/revisions/audio-r2/src' if a.revision=='r2' else 'src/artwork-test/audio')
 pins=json.loads((HERE/'AUDIO-PROGRESS-FACTORY.json').read_text())['classes']
 if a.revision!='r2':pins={k:v for k,v in pins.items() if k.endswith(('HsmTarget.class','CurrentStationInfo.class','CurrentStationHandle.class','CoverArt.class'))}
 asm=':'.join(str((a.asm_dir/n).resolve()) for n in ('asm-9.7.jar','asm-tree-9.7.jar'))
 stock=str(a.stock_jar.resolve());java=a.java_home/'bin/java';javac=a.java_home/'bin/javac'
 for d in ('stock','helpers','tools','patched'):(out/d).mkdir()
 with zipfile.ZipFile(stock) as z:
  for name,h in pins.items():
   b=z.read(name);assert sha(b)==h,name
   dest=out/'stock'/name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(b)
 def run(*args):subprocess.run(list(map(str,args)),check=True)
 run(javac,'-source','7','-target','7','-Xlint:-options','-bootclasspath',stock,'-cp',stock,'-d',out/'helpers',*sorted(source.glob('*.java')))
 names=['PatchTextObserver','PatchText','PatchCover']+(['PatchProgress'] if a.revision=='r2' else [])
 run(javac,'-cp',asm,'-d',out/'tools',*[HERE/'tools'/(n+'.java') for n in names])
 for name in pins:
  tool='PatchTextObserver' if name.endswith('HsmTarget.class') else 'PatchText' if name.endswith('CurrentStationInfo.class') else 'PatchProgress' if name.endswith(('FunctionList.class','BAPAudioSDDataPool.class','BAPServiceProxy.class','BAPDispatcherTarget.class')) else 'PatchCover'
  run(java,'-cp',str(out/'tools')+':'+asm,tool,out/'stock'/name,*([out/'helpers'] if tool=='PatchTextObserver' else []),out/'patched')
 jar(out/'CarPlayMU1367Audio.jar',out/'patched',29)
 manifest={'passed':True,'test_build':True,'revision':a.revision,'on_unit_validated':False,'jar_sha256':sha((out/'CarPlayMU1367Audio.jar').read_bytes()),'factory_classes':pins,
  'source_sha256':{str(f.relative_to(HERE)):sha(f.read_bytes()) for f in [*sorted(source.glob('*.java')),*[HERE/'tools'/(n+'.java') for n in names]]}}
 pin=HERE/('AUDIO-PROGRESS-R2-RUNTIME.json' if a.revision=='r2' else 'ARTWORK-R3-RUNTIME.json')
 assert a.candidate or pin.is_file() and manifest['jar_sha256']==json.loads(pin.read_text())['jar_sha256'],'Update the explicit audio test fingerprint after validating runtime changes'
 (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');print(json.dumps(manifest))
if __name__=='__main__':main()
