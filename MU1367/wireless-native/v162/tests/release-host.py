#!/usr/bin/env python3
"""Real release migrations, including stable 1.6.1, and OEM/media diagnostics."""
import argparse,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
p=argparse.ArgumentParser(add_help=False);p.add_argument('--stable-zip',type=Path,required=True)
a,remaining=p.parse_known_args();sys.argv=[sys.argv[0],*remaining]
source=HERE.parents[1]/'stable/test-host.py';code=source.read_text().replace('carplay-mu1367-wireless-native-v161t2','carplay-mu1367-wireless-native-v162').replace('release-v161','release-v162').replace('1_6_1','1_6_2_E_TEST1')
code=code.replace("('original-v161',a.v161_zip)]","('original-v161',a.v161_zip),('stable-v161',Path("+repr(str(a.stable_zip.resolve()))+"))]")
code=code.replace("(rg/'latest.bin').write_bytes", "(rg/'nowplaying.bin').write_bytes(b'media-snapshot');(rg/'cover.bin').write_bytes(b'complete-cover');(self.root/'ramdisk/wcp-now-playing.status').write_bytes(b'media-status')\n  (rg/'latest.bin').write_bytes")
code=code.replace("  for f in d.rglob('*'):","  self.assertEqual((d/'wireless/state/wcp-rg-nowplaying.bin').read_bytes(),b'media-snapshot')\n  self.assertEqual((d/'wireless/state/wcp-rg-cover.bin').read_bytes(),b'complete-cover')\n  self.assertEqual((d/'wireless/state/wcp-now-playing.status').read_bytes(),b'media-status')\n  for f in d.rglob('*'):")
exec(compile(code,str(source),'exec'),dict(__file__=str(source),__name__='candidate_release_tests'))
