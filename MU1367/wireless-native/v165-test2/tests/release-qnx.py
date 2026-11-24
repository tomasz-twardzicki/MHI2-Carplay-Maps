#!/usr/bin/env python3
"""Run the production candidate orchestrator and combined collectors with factory tools."""
from pathlib import Path
source=Path(__file__).resolve().parents[2]/'stable/test-flow-qnx.py'
code=source.read_text().replace('carplay-mu1367-wireless-native-v161t2','carplay-mu1367-wireless-native-v165t2').replace('release-v161','release-v165t2').replace('1_6_1','1_6_5_E_TEST2')
code=code.replace("production_release_controller_sha256=sha((HERE/'control.sh').read_bytes())","production_release_controller_sha256=sha((release/'control.sh').read_bytes())")
exec(compile(code,str(source),'exec'),dict(__file__=str(source),__name__='candidate_release_qnx'))
