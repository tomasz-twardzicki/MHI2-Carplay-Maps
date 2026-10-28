#!/usr/bin/env python3
"""Build lane-enabled guidance and map-only-default settings from exact MU1367.
SPDX-License-Identifier: GPL-3.0-or-later
"""
import argparse
import importlib.util
import json
from pathlib import Path
import sys
import stage
HERE=Path(__file__).resolve().parent
REPO=HERE.parents[1]
sys.path.insert(0,str(HERE.parent/'port'))
from firmware import sha


def main():
 p=argparse.ArgumentParser(description=__doc__)
 for n in ('java-home','stock-jar','jxe','asm-dir','toolchain','output'):p.add_argument('--'+n,type=Path,required=True)
 a=p.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
 src=stage.guidance(out)
 path=HERE.parent/'port/build-hmi.py';text=path.read_text()
 text=stage.replace(text,"src = RG / 'bridge' if feature == 'guidance' else AUDIO / 'n1/java'","src = LANE_SOURCE if feature == 'guidance' else AUDIO / 'n1/java'")
 text=stage.replace(text,"runtime = baseline.RUNTIME if feature == 'guidance'","runtime = baseline.RUNTIME+('LaneData.java',) if feature == 'guidance'")
 env={'__file__':str(path),'__name__':'lane_hmi_builder','LANE_SOURCE':src}
 exec(compile(text,str(path),'exec'),env)
 old=sys.argv;sys.argv=['lane-hmi','--java-home',str(a.java_home),'--stock-jar',str(a.stock_jar),'--jxe',str(a.jxe),'--asm-dir',str(a.asm_dir),'--output',str(out/'hmi')]
 try:env['main']()
 finally:sys.argv=old
 path=HERE.parent/'settings-v2/build.py';spec=importlib.util.spec_from_file_location('lane_settings_builder',path);settings=importlib.util.module_from_spec(spec);spec.loader.exec_module(settings)
 original=settings.stage_sources
 def defaults(directory):
  source=original(directory);stage.cards(source);return source
 settings.stage_sources=defaults
 sys.argv=['lane-settings','--java-home',str(a.java_home),'--stock-jar',str(a.stock_jar),'--asm-dir',str(a.asm_dir),'--toolchain',str(a.toolchain),'--output',str(out/'runtime')]
 try:settings.main()
 finally:sys.argv=old
 hmi=json.loads((out/'hmi/manifest.json').read_text());runtime=json.loads((out/'runtime/manifest.json').read_text())
 files={n:sha((out/relative).read_bytes()) for n,relative in [('CarPlayMU1367Guidance.jar','hmi/CarPlayMU1367Guidance.jar'),('VCMenu.jar','runtime/VCMenu.jar'),('core.so','runtime/core.so')]}
 manifest={'firmware':'MU1367','cluster':'791','files':files,'hmi':hmi,'runtime':runtime,'card_default':'off','existing_card_toggle':True,'native_driver_and_reader_changed':False,'lane_source_sha256':{p.name:sha(p.read_bytes()) for p in HERE.iterdir() if p.is_file()},'on_unit_validated':False}
 (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');print(json.dumps({'files':files,'card_default':'off'}))


if __name__=='__main__':main()
