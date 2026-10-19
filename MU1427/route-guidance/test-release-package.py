#!/usr/bin/env python3
"""Final ZIP menus, core patch bounds, and rendered installation/recovery."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import shutil
import struct
import subprocess
from types import SimpleNamespace
import zipfile

HERE=Path(__file__).resolve().parent


def sha(b):return hashlib.sha256(b).hexdigest()
def immediate(b,at):
    instruction=struct.unpack_from('<I',b,at)[0]
    n=instruction&255;r=((instruction>>8)&15)*2
    return ((n>>r)|(n<<(32-r)))&0xffffffff if r else n


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('archive',type=Path)
    p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    spec=importlib.util.spec_from_file_location('controls',HERE/'test-release-control.py')
    c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c)
    c.ARGS=SimpleNamespace(hmi=HERE/'build-release-hmi',native=HERE/'build-release-native')
    with zipfile.ZipFile(a.archive) as z:
        assert z.testzip() is None
        menu=z.read('Toolbox/GEM/carplay-maps-vc.esd').decode()
        assert 'Baseline author: omonob (QCDWJ)' in menu
        assert 'MU1427 author: tomasz-twardzicki' in menu
        assert 'Install full native guidance (MU1427 only)' in menu
        assert not re.search(r'label\s+"[A-D][0-9]|SHADOW|navrecon|cpmap_rgi_',menu)
        for menu_name in ('carplay-maps-vc.esd','carplay-maps-vc-tuning.esd'):
            text=z.read('Toolbox/GEM/'+menu_name).decode()
            for name in re.findall(r'/mqb/([^"/]+\.sh)',text):assert 'Toolbox/scripts/'+name in z.namelist(),name
        with zipfile.ZipFile(HERE/'build-D3/MU1427-route-guidance-D3-toolbox.zip') as old:
            for name in ('cpmap_install_791.sh','cpmap_install_790.sh','cpmap_tune.sh'):
                assert z.read('Toolbox/scripts/'+name)==old.read('Toolbox/scripts/'+name)
            # Existing AUTO MU entry blocks and shared installer remain exact.
            for cluster in ('791','790'):
                pattern=r'script\s+value[^\n]+/cpmap_install_'+cluster+r'\.sh"\s+label[^\n]+'
                assert re.search(pattern,menu).group()==re.search(pattern,old.read('Toolbox/GEM/carplay-maps-vc.esd').decode()).group()
            common='Custom/carplay_maps_vc/payload/common/install-carplay-maps.sh'
            assert z.read(common)==old.read(common)
            prefix='Custom/carplay_maps_vc/'
            for variant,x,y,w,h in [('default',200,96,400,364),('wide-card',160,96,480,364),('no-card',200,80,400,380)]:
                name=prefix+'tuning/MU1427/791/'+variant+'/core.so';b=z.read(name);before=old.read(name)
                assert len(b)==len(before)
                assert [immediate(b,k) for k in (0x2ba4,0x2b94,0x2b98,0x2b9c)]==[x,y,w,h]
                assert immediate(b,0x2a70)==30
                allowed=set(range(0x2b94,0x2b98))|set(range(0x2b9c,0x2ba0))
                assert all(i in allowed for i,(a0,b0) in enumerate(zip(before,b)) if a0!=b0)
                if variant=='no-card':assert b==before
            for name in old.namelist():
                if name.startswith(prefix+'payload/profiles/') and '/MU1427/' not in name and not name.endswith('/'):
                    assert z.read(name)==old.read(name)
        controller=z.read('Toolbox/scripts/cpmap_guidance.sh')
        manifest=json.loads(z.read('Custom/carplay_native_guidance/manifest.json'))
        assert sha(controller)==manifest['controller_sha256']
        assert manifest['default_enabled_after_boot'] and not manifest['manual_test_gate']
        case=c.ReleaseControls('test_factory_install_reinstall_and_no_sd_complete_removal');case.setUp()
        try:
            extracted=case.work/'extracted';z.extractall(extracted)
            shutil.rmtree(case.payload)
            shutil.copytree(extracted/'Custom/carplay_native_guidance',case.payload)
            case.script.write_bytes(controller)
            for script in (extracted/'Toolbox/scripts').glob('cpmap_guidance*.sh'):
                subprocess.run(['/bin/ksh','-n',str(script)],check=True,capture_output=True)
            subprocess.run(['/bin/ksh','-n',str(extracted/'Toolbox/scripts/cpmap_restore.sh')],check=True,capture_output=True)
            case.run_control('install');case.run_control('install')
            assert sha(case.jar.read_bytes())==manifest['jar_sha256']
            modified=case.lsd.read_text().replace('-Xbootclasspath/p:','-Xbootclasspath/p:$BASE_DIR/lsd/jars/Later.jar:')
            case.lsd.write_text(modified);shutil.rmtree(case.payload)
            case.run_control('disable',local=True);case.run_control('uninstall',local=True)
            case.assert_stock();assert not case.jar.exists()
            assert case.lsd.read_text()==case.original.replace('-Xbootclasspath/p:','-Xbootclasspath/p:$BASE_DIR/lsd/jars/Later.jar:')
            assert case.lsd.stat().st_mode&0o777==0o755
            # Execute the packaged factory-restore wrapper with a harmless
            # base restore sentinel, checking the native step runs first.
            shutil.copytree(extracted/'Custom/carplay_native_guidance',case.payload)
            case.run_control('install')
            scripts=case.root/'mnt/app/eso/hmi/engdefs/scripts/mqb';scripts.mkdir(parents=True)
            (scripts/'cpmap_restore_core.sh').write_text('#!/bin/ksh\necho BASE_RESTORE_REACHED\n')
            shutil.rmtree(case.payload)
            result=subprocess.run(['/bin/ksh',str(extracted/'Toolbox/scripts/cpmap_restore.sh')],env=case.env,capture_output=True,text=True,timeout=10)
            assert result.returncode==0 and 'BASE_RESTORE_REACHED' in result.stdout,result.stdout+result.stderr
            case.assert_stock();assert not case.jar.exists()
        finally:case.doCleanups()
    report={'passed':True,'archive_sha256':sha(a.archive.read_bytes()),
      'menus_clean_and_credits_verified':True,'auto_mu_installers_unchanged':True,
      'only_card_y_height_instructions_changed':True,'map_only_other_profiles_unchanged':True,
      'actual_zip_install_reinstall_no_sd_removal_passed':True,'actual_zip_factory_restore_wrapper_passed':True,
      'later_hmi_entries_and_modes_preserved':True,'test_sha256':sha(Path(__file__).read_bytes())}
    a.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))


if __name__=='__main__':main()
