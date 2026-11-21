#!/usr/bin/env python3
"""Execute preference behavior against the actual four packaged menu JARs."""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
p = argparse.ArgumentParser()
for name in ('build', 'java', 'output'):
    p.add_argument('--' + name, type=Path, required=True)
a = p.parse_args()
out = a.output.resolve()
out.mkdir(parents=True, exist_ok=False)
results = {}
for variant in ('6', '7', '6-road', '7-road'):
    jar = a.build.resolve() / ('sd-card/Custom/carplay_mu1367_guidance_v3/' + variant + '/VCMenu.jar')
    classes = out / variant
    classes.mkdir()
    subprocess.run([str(a.java / 'javac'), '-cp', str(jar), '-d', str(classes), str(HERE / 'TestCardDefault.java')], check=True)
    result = subprocess.check_output([str(a.java / 'java'), '-cp', str(classes) + ':' + str(jar), 'TestCardDefault', str(classes / 'prefs')], text=True)
    assert 'CARD_OFF_DEFAULT_PASS' in result
    results[variant] = dict(result=result.strip(), menu_sha256=hashlib.sha256(jar.read_bytes()).hexdigest())
report = dict(passed=True, variants=results, default='Off', saved_choices_preserved=True, runtime_modified=False)
(out / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report))
