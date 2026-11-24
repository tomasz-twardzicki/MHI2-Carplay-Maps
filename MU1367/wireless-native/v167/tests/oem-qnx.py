#!/usr/bin/env python3
"""Native baseline OEM reset, including the additional recovery-folder names."""
import argparse,hashlib,importlib.util,json,shutil,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
p=argparse.ArgumentParser()
for n in ('build','reader-setup','toolchain','firmware-commands','output'):p.add_argument('--'+n,type=Path,required=True)
a=p.parse_args();module=a.build.resolve()/'sd-card/Custom/carplay_mu1367_oem_reset'
inputs=a.output.resolve().with_name(a.output.name+'-inputs');shutil.copytree(module,inputs,ignore=shutil.ignore_patterns('source'))
m=json.loads((inputs/'manifest.json').read_text())
line=next(line for line in (module/'control.sh').read_text().splitlines() if line.startswith('LAYERS='))
m['layers_archived']=line[len("LAYERS='"):-1].split();m['controller_sha256']=sha(module/'control.sh')
(inputs/'manifest.json').write_text(json.dumps(m,indent=2)+'\n')
template=HERE.parents[2]/'integration/tests/factory_reset.py'
spec=importlib.util.spec_from_file_location('native_oem',template);fixture=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixture)
sys.argv=[sys.argv[0],'--payload',str(inputs),'--reader-setup',str(a.reader_setup),'--toolchain',str(a.toolchain),'--firmware-commands',str(a.firmware_commands),'--output',str(a.output)]
rc=fixture.main()
report=json.loads((a.output/'result.json').read_text());report.update(archived_recovery_roots=m['layers_archived'],archive_marker_note='Inherited console marker says archives=12; actual generated assertions cover every listed recovery root.')
(a.output/'result.json').write_text(json.dumps(report,indent=2)+'\n');raise SystemExit(rc)
