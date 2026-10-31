#!/usr/bin/env python3
"""Real-controller fresh/update/tuning/recovery tests in isolated filesystems."""
import argparse,hashlib,importlib.util,json,os,re,shlex,shutil,subprocess,tempfile,unittest,zipfile
from pathlib import Path
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('previous_suite_tests',HERE/'fixture.py');base=importlib.util.module_from_spec(spec);spec.loader.exec_module(base)
sha=base.sha

class Suite(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  base.Suite.setUpClass.__func__(cls)
  # These are isolated host filesystems, not a power-loss/durability emulator.
  # QNX tests separately run the real firmware sync and mount is mocked there.
  f=cls.tools/'sync';f.write_text('#!/bin/ksh\nexit 0\n');f.chmod(0o755)
 tearDownClass=classmethod(base.Suite.tearDownClass.__func__)
 base6=base.Suite.base6
 prepare=base.Suite.prepare
 run_script=base.Suite.run_script
 def setUp(self):
  base.Suite.setUp(self)
  self.oldp=self.p;self.p=self.sd/'Custom/carplay_mu1367_map_only'
  # Replace every verifier digest in both complete payload checkers. Runtime
  # files/controllers are the actual payload; only hashing/mounts use host tools.
  native=sha((ARGS.package/'sd-card/Custom/carplay_mu1367_map_only/verify').read_bytes());host=sha(ARGS.verifier.read_bytes())
  for f in self.sd.glob('Custom/*/payload-check.sh'):f.write_text(f.read_text().replace(native,host))
 @staticmethod
 def runtime(root):
  values=base.Suite.runtime(root)
  for name in ('refinements','map-only'):
   p=root/'mnt/app'/('carplay-mu1367-'+name)/'control.sh'
   values[str(p.relative_to(root/'mnt/app'))]=(sha(p.read_bytes()),p.stat().st_mode&0o777) if p.is_file() else None
  return values
 def action(self,action,success=True):return self.run_script(self.p/'actions.sh',[action,self.p],success)
 def old_install(self):return self.run_script(self.oldp/'actions.sh',['install',self.oldp])
 def saved(self,action,success=True,name='map-only'):
  return self.run_script(self.app/('carplay-mu1367-'+name)/'control.sh',[action],success)
 def expected(self,variant='6'):
  m=json.loads((self.p/variant/'manifest.json').read_text())
  for key,path in [('core','carplaymaps/core.so'),('guidance','eso/hmi/lsd/jars/CarPlayMU1367Guidance.jar'),('menu','eso/hmi/lsd/jars/VCMenu.jar')]:self.assertEqual(sha((self.app/path).read_bytes()),m['files'][key])
