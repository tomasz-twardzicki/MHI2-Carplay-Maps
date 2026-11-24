#!/usr/bin/env python3
"""Reader-specific integrity gates in the full experimental release transaction."""
import argparse,importlib.util,json,shutil,unittest
from pathlib import Path
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('release',HERE/'test-package.py');release=importlib.util.module_from_spec(spec);spec.loader.exec_module(release)
class Suite(release.Suite):
 def test_unknown_reader_refused_before_snapshot(self):
  self.v2();reader=self.app/'carplay-mu1367/rgi-observer';original=reader.read_bytes();reader.write_bytes(b'unknown reader')
  before=self.runtime(self.root)
  self.assertIn('UNEXPECTED_BASE_reader',self.action('install',False));self.assertEqual(before,self.runtime(self.root))
  self.assertFalse((self.app/'carplay-mu1367-guidance-v3').exists())
  reader.write_bytes(original);self.action('install');self.expected()
 def test_missing_reader_snapshot_cannot_be_archived(self):
  for names in [('reader.sha256',),('reader','reader.sha256')]:
   with self.subTest(missing=names):
    shutil.rmtree(self.root);shutil.copytree(self.seed,self.root);self.v2();self.action('install');self.action('uninstall')
    saved=self.app/'carplay-mu1367-guidance-v3'
    for name in names:(saved/'backup'/name).unlink()
    before=self.runtime(self.root)
    self.assertIn('SNAPSHOT_HASH_MISSING',self.action('install',False));self.assertEqual(before,self.runtime(self.root))
    self.assertFalse(list(self.app.glob('carplay-mu1367-guidance-v3.removed-*')))
 def test_old_standalone_test_must_be_restored_first(self):
  self.v2();self.revision('release-v1.4.3')
  old=self.app/'carplay-mu1367-reader-recovery';old.mkdir();(old/'STATE').write_text('installed\n')
  before=self.runtime(self.root)
  self.assertIn('RESTORE_STANDALONE_READER_TEST_FIRST',self.action('install',False));self.assertEqual(before,self.runtime(self.root))
def main():
 global ARGS
 p=argparse.ArgumentParser(description=__doc__)
 for n in ('package','inputs','verifier','output'):p.add_argument('--'+n,type=Path,required=True)
 ARGS=p.parse_args();release.ARGS=ARGS;release.parent.ARGS=ARGS;release.parent.base.ARGS=ARGS
 names=[n for n in Suite.__dict__ if n.startswith('test_')]
 result=unittest.TextTestRunner(verbosity=2).run(unittest.TestSuite(Suite(n) for n in names))
 m=json.loads((ARGS.package/'manifest.json').read_text())
 ARGS.output.write_text(json.dumps({'passed':result.wasSuccessful(),'tests':result.testsRun,'archive_sha256':m['archive_sha256'],'reader_sha256':m['reader_sha256'],'mounts_and_sync_mocked_on_host':True,'on_unit_validated':False},indent=2)+'\n')
 raise SystemExit(not result.wasSuccessful())
if __name__=='__main__':main()
