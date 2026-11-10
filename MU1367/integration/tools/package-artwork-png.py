#!/usr/bin/env python3
"""Add the optional compressed-artwork Tuning layer to the built release archive (GPL-3.0+).

package.py builds and verify.py proves the release; this step then adds one recoverable
layer that swaps only the artwork helper. Every release payload stays byte-identical.
"""
import argparse,hashlib,json,shutil,subprocess,zipfile
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from payload_checks import write_payload_checks
HERE=Path(__file__).resolve().parent.parent
CUSTOM='carplay_mu1367_artwork_png'
LIVE='carplay-mu1367-artwork-png'
ARTWORK_PARENT='MU1367-artwork-f353117dbe5c'
LABELS={'install':'Enable compressed album artwork (reboot)','uninstall':'Disable compressed album artwork (reboot)',
        'status':'Show compressed artwork status','recover':'Recover interrupted artwork change (reboot)'}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def add_layer(sd,native,native_host,default=True):
 """Build the compressed-artwork layer into an SD tree; returns its manifest record.
 Since v1.4.6 the suite install action installs it by default; the Tuning entries switch it."""
 nm=json.loads((native/'manifest.json').read_text());fetch=native/'artwork-fetch';f=sha(fetch)
 assert nm['passed'] and nm['sha256']==f
 for name,digest in nm['sources'].items():assert sha(HERE/name)==digest,name
 nh=json.loads(native_host.read_text());assert nh['passed']
 for name,digest in nh['source_sha256'].items():assert sha(HERE/name)==digest,name
 art=sd/'Custom/carplay_mu1367_artwork';root=sd/'Custom'/CUSTOM;root.mkdir()
 assert (art/'VERSION').read_text().strip()==ARTWORK_PARENT
 control=(HERE/'tools/transaction.sh').read_text()
 control=control.replace('# SPDX-License-Identifier: GPL-3.0-or-later','# SPDX-License-Identifier: GPL-3.0-or-later\n# MU1367 optional compressed album artwork (lossless PNG via factory zlib)')
 control=control.replace('carplay-mu1367-lanes',LIVE).replace('MU1367_LANES','MU1367_ARTWORK_PNG').replace('.lanes-new','.artwork-png-new')
 control=control.replace('for K in parent settings;do','for K in $GUARDS;do')
 status='  if regular "$M/ramdisk/cpmap-artwork.status";then cat "$M/ramdisk/cpmap-artwork.status";fi'
 needle='  echo "Cards: App-Connect > Virtual Cockpit settings > navigation card ON/OFF; reconnect after changing"';assert control.count(needle)==1
 control=control.replace(needle,status)
 marker=' [ "$(cat "$P/VERSION" 2>/dev/null)" = "$BUILD" ] || fail PAYLOAD_VERSION';assert control.count(marker)==1
 gates=' [ "$(cat "$APP/carplay-mu1367-artwork/STATE" 2>/dev/null)" = installed ] && [ "$(cat "$APP/carplay-mu1367-artwork/VERSION" 2>/dev/null)" = '+ARTWORK_PARENT+' ] || fail EXACT_ARTWORK_PARENT_REQUIRED\n'
 gates+=' check "$M/proc/boot/libz.so.2" '+nm['factory_libraries']['libz.so.2']+' || fail FACTORY_ZLIB_CHANGED\n'
 control=control.replace(marker,gates+marker)
 guard='# Disable compressed artwork before changing the artwork layer.\n'
 build='MU1367-artwork-png-'+f[:12]
 table="KEYS='fetch'\nFILES='fetch'\nGUARDS=''\nGUARD_SHA="+hashlib.sha256(guard.encode()).hexdigest()+'\n'
 table+='PARENT_BUILD='+(sd/'Custom/carplay_mu1367/VERSION').read_text().strip()+'\nSETTINGS_BUILD='+(sd/'Custom/carplay_mu1367_settings/VERSION').read_text().strip()+'\n'
 table+='target(){ case "$1" in fetch) echo "$APP/carplay-mu1367-artwork/artwork-fetch";; *) return 1;; esac; }\n'
 table+='payload(){ case "$1" in fetch) echo artwork-fetch;; *) return 1;; esac; }\n'
 table+='expected(){ case "$1" in fetch) echo '+f+';; *) return 1;; esac; }\n'
 table+='before(){ case "$1" in fetch) echo '+sha(art/'artwork-fetch')+';; *) return 1;; esac; }\n'
 (root/'control.sh').write_text(control.replace('@BUILD@',build).replace('@TABLE@',table))
 (root/'VERSION').write_text(build+'\n');(root/'guard').write_text(guard)
 shutil.copy2(fetch,root/'artwork-fetch');shutil.copy2(art/'verify',root/'verify')
 tuning=sd/'Toolbox/GEM/carplay-maps-vc-tuning.esd'
 with tuning.open('a') as menu:menu.write('\nkeyValue\n    value String sys 0x00000000 0\n    label "Optional compressed album artwork"\n    poll 0\n')
 template=(sd/'Toolbox/scripts/cpmap_suite_install.sh').read_text()
 for action,label in LABELS.items():
  code=template.replace('carplay_mu1367_guidance_v3/actions.sh',CUSTOM+'/control.sh').replace('carplay_mu1367_guidance_v3;',CUSTOM+';').replace('"$P/actions.sh" install','"$P/control.sh" '+action).replace('MU1367_OEM_RESET_','MU1367_ARTWORK_PNG_')
  assert '"$P/control.sh" '+action+' "$P"' in code and CUSTOM+'/control.sh' in code
  wrapper=sd/'Toolbox/scripts'/('cpmap_artwork_png_'+action+'.sh');wrapper.write_text(code);wrapper.chmod(0o755)
  with tuning.open('a') as menu:menu.write('\nscript\n    value sys 1 0x0100 "/eso/hmi/engdefs/scripts/mqb/'+wrapper.name+'"\n    label "'+label+'"\n')

 for script in [root/'control.sh',*(sd/'Toolbox/scripts').glob('cpmap_artwork_png_*.sh')]:subprocess.run(['/bin/ksh','-n',str(script)],check=True);script.chmod(0o755)
 return {'layer':CUSTOM,'build_id':build,'fetch_sha256':f,'replaces_fetch_sha256':sha(art/'artwork-fetch'),'factory_zlib_sha256':nm['factory_libraries']['libz.so.2'],'installed_by_default':default,'lossless':True,'on_unit_validated':False}
def main():
 """Historical v1.4.6-e flow: add the layer (not installed by default) to an already built archive."""
 p=argparse.ArgumentParser(description=__doc__)
 for n in ('package','native','native-host','output'):p.add_argument('--'+n,type=Path,required=True)
 a=p.parse_args()
 base=json.loads((a.package/'manifest.json').read_text());source=a.package/base['archive_name']
 assert sha(source)==base['archive_sha256'],'package archive changed after packaging'
 out=a.output.resolve();out.mkdir(parents=True,exist_ok=False);sd=out/'sd-card';sd.mkdir()
 with zipfile.ZipFile(source) as z:
  for name in z.namelist():
   dest=sd/name;assert dest.resolve().is_relative_to(sd)
   if name.endswith('/'):dest.mkdir(parents=True,exist_ok=True);continue
   dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(z.read(name));dest.chmod((z.getinfo(name).external_attr>>16)&0o777 or 0o644)
 release=json.loads((sd/'MU1367_RELEASE_MANIFEST.json').read_text())
 record=release['optional_artwork_png']=add_layer(sd,a.native,a.native_host,False)
 (sd/'MU1367_RELEASE_MANIFEST.json').write_text(json.dumps(release,indent=2)+'\n')
 write_payload_checks(sd/'Custom')
 inv={str(q.relative_to(sd)):sha(q) for q in sorted(sd.rglob('*')) if q.is_file() and q.name!='FILES_SHA256.json'};(sd/'FILES_SHA256.json').write_text(json.dumps(inv,indent=2)+'\n')
 archive=out/base['archive_name']
 with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
  for q in sorted(sd.rglob('*')):
   if q.is_file():z.write(q,q.relative_to(sd))
 manifest=dict(release,archive_sha256=sha(archive),archive_bytes=archive.stat().st_size,verified_package_archive_sha256=base['archive_sha256'])
 (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');(out/'SHA256SUMS.txt').write_text(sha(archive)+'  '+base['archive_name']+'\n')
 print(json.dumps({'passed':True,'archive_sha256':manifest['archive_sha256'],'build_id':record['build_id']}))
if __name__=='__main__':main()
