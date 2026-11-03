#!/usr/bin/env python3
"""Real worker faults and actual MU1367 bridge freshness across recovery."""
import argparse, hashlib, importlib.util, json, os, signal, struct, subprocess, sys, tempfile, time, unittest
from pathlib import Path
HERE=Path(__file__).resolve().parent
SRC=HERE.parent/'src/reader/reader.c'
RG=HERE.parents[2]/'MU1427/route-guidance'
sys.path.insert(0,str(RG))
spec=importlib.util.spec_from_file_location('original_reader_tests',RG/'test-release-reader.py')
original=importlib.util.module_from_spec(spec);spec.loader.exec_module(original)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

class Reader(original.Reader):
 @classmethod
 def setUpClass(cls):
  cls.temp=tempfile.TemporaryDirectory(prefix='mu1367-reader-');cls.base=Path(cls.temp.name)
  cls.cc=['clang','-std=c99','-O2','-Wall','-Wextra','-Werror']
  sdk=Path('/Library/Developer/CommandLineTools/SDKs/MacOSX14.4.sdk')
  if sdk.exists():cls.cc+=['-isysroot',str(sdk)]
  cls.binary=cls.base/'reader';cls.fault=cls.base/'fault-reader'
  subprocess.run(cls.cc+[str(SRC),'-o',str(cls.binary)],check=True)
  obj=cls.base/'reader.o'
  subprocess.run(cls.cc+['-Dread=fault_read','-Dwrite=fault_write','-Dwaitpid=fault_waitpid','-Drename=fault_rename','-Dfopen=fault_fopen','-c',str(SRC),'-o',str(obj)],check=True)
  subprocess.run(cls.cc+[str(obj),str(HERE/'reader-faults.c'),'-o',str(cls.fault)],check=True)
  cls.cp=':'.join(map(str,[cls.base,ARGS.guidance.resolve(),ARGS.stock.resolve()]))
  subprocess.run([str(ARGS.java/'bin/javac'),'-cp',cls.cp,'-d',str(cls.base),str(RG/'release/TestMailbox.java'),str(HERE/'java/TestLive.java'),str(HERE/'java/TestReaderRecovery.java')],check=True)
 def setUp(self):
  super().setUp();self.trigger=self.work/'trigger'
 def fault_start(self,mode):
  self.write_source()
  env=dict(os.environ,READER_TEST_MODE=mode,READER_TEST_TRIGGER=str(self.trigger))
  p=subprocess.Popen([str(self.fault),'serve',str(self.source),str(self.out)],env=env)
  def stop():
   if p.poll() is None:p.terminate();p.wait(timeout=4)
  self.addCleanup(stop);self.wait(lambda:(self.out/'latest.bin').is_file())
  return p
 def status(self):return dict(v.split('=',1) for v in (self.out/'status.txt').read_text().split() if '=' in v)
 def sequence(self):
  b=self.mailbox()
  return struct.unpack_from('<I',b,52)[0] if len(b)>=96 and b[16]==1 else -1
 def first(self):return self.out/'reader-failure-first.txt'
 def bridge(self):
  p=subprocess.Popen([str(ARGS.java/'bin/java'),'-Xverify:all','-cp',self.cp,'com.cpmap.rgi.TestReaderRecovery',str(self.out)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
  def stop():
   p.stdin.close();p.wait(timeout=4);err=p.stderr.read();p.stdout.close();p.stderr.close()
   self.assertEqual(p.returncode,0,err)
  self.addCleanup(stop)
  def poll(now):
   p.stdin.write(str(now)+'\n');p.stdin.flush();line=p.stdout.readline().strip()
   self.assertTrue(line, 'Java probe exited')
   return list(map(int,line.split(',')))
  return poll
 def await_restart(self):self.wait(lambda:int(self.status()['restarts'])==1 and self.mailbox()[16]==1,seconds=5)
 def test_blocked_worker_deadline_exits_without_restart_loop(self):
  # Replaces the old terminal-on-first-timeout test: budget remains bounded.
  p=self.fault_start('always-block');self.trigger.touch()
  self.assertEqual(p.wait(timeout=16),1)
  self.assertEqual(self.mailbox()[16:24],struct.pack('<II',5,3))
  self.assertEqual(self.status()['restarts'],'3')
  first=self.first().read_text();self.assertIn('cause=timeout',first)
  self.assertIn('child_reaped=1',first);self.assertIn('restarts=0',first)
  self.assertLess(len(first),1024)
 def recovery(self,mode,miss_invalidation=False):
  p=self.fault_start(mode);probe=self.bridge()
  self.assertEqual(probe(1000)[0],0)
  self.write_source(3);self.wait(lambda:self.sequence()==3)
  before=probe(1250);self.assertEqual(before[0],1)
  self.trigger.touch();self.wait(lambda:self.first().exists())
  first=self.first().read_bytes()
  if not miss_invalidation:self.assertEqual(probe(1500)[0],0)
  self.await_restart();new=probe(1750)
  self.assertEqual(new[0],0);self.assertEqual(new[1],0);self.assertNotEqual(new[2],before[2])
  time.sleep(1.1);self.assertEqual(probe(2000)[0],0)
  self.write_source(4);self.wait(lambda:self.sequence()==4)
  self.assertEqual(probe(2250)[0],1);self.assertIsNone(p.poll())
  self.assertEqual(self.first().read_bytes(),first)
  self.assertLess(sum(f.stat().st_size for f in self.out.iterdir() if f.is_file()),72*1024)
 def test_timeout_recovery_requires_fresh_input(self):self.recovery('block')
 def test_missed_invalidation_still_requires_new_baseline(self):self.recovery('block',True)
 def test_worker_eof_recovery_retains_exit_status(self):
  self.recovery('eof');s=self.first().read_text()
  self.assertIn('cause=eof',s);self.assertIn('child_status=10752',s)
 def test_partial_frame_discarded_on_restart(self):
  self.recovery('partial');s=self.first().read_text()
  self.assertIn('cause=eof',s);self.assertIn('partial_bytes=1024',s);self.assertIn('phase=4',s)
 def test_unconfirmed_reap_never_spawns_replacement(self):
  p=self.fault_start('unreaped');self.trigger.touch()
  # Fault shim hides reaping; separately kill the real child to cause EOF.
  self.wait(lambda:int(self.status()['worker_pid'])>0)
  os.kill(int(self.status()['worker_pid']),signal.SIGKILL)
  self.assertEqual(p.wait(timeout=4),1)
  self.assertEqual(self.status()['restarts'],'0')
  self.assertIn('child_reaped=0',self.first().read_text())
  self.assertIn('recovery_allowed=0',self.first().read_text())
 def test_manual_stop_during_backoff_is_prompt(self):
  p=self.fault_start('block');self.trigger.touch();self.wait(lambda:self.first().exists())
  t=time.monotonic();r=subprocess.run([str(self.binary),'stop',str(self.out)],capture_output=True,timeout=4)
  self.assertEqual(r.returncode,0);self.assertEqual(p.wait(timeout=3),0)
  self.assertLess(time.monotonic()-t,1)
  self.assertEqual(self.status()['reason'],'1');self.assertEqual(self.status()['restarts'],'0')
 def test_returned_enomem_does_not_restart_worker(self):
  p=self.fault_start('enomem');self.trigger.touch()
  self.wait(lambda:self.mailbox()[16]==2)
  self.assertEqual(struct.unpack_from('<I',self.mailbox(),32)[0],12)
  self.write_source(3);self.wait(lambda:self.mailbox()[16]==1)
  self.assertIsNone(p.poll());self.assertEqual(self.status()['restarts'],'0');self.assertFalse(self.first().exists())
 def test_output_failure_is_terminal(self):
  p=self.fault_start('output');self.trigger.touch()
  self.assertEqual(p.wait(timeout=4),1);self.assertEqual(self.status()['reason'],'4')
  self.assertEqual(self.status()['restarts'],'0')
 def test_first_failure_preserved_after_second_fault(self):
  p=self.fault_start('eof');self.trigger.touch();self.await_restart()
  first=self.first().read_bytes();self.trigger.touch()
  self.wait(lambda:int(self.status()['restarts'])==2,seconds=5)
  self.assertEqual(self.first().read_bytes(),first);self.assertIsNone(p.poll())
 def test_diagnostics_output_failure_prevents_recovery(self):
  p=self.fault_start('diagnostic-output')
  os.kill(int(self.status()['worker_pid']),signal.SIGKILL)
  self.assertEqual(p.wait(timeout=4),1);self.assertEqual(self.status()['reason'],'4')
  self.assertEqual(self.status()['restarts'],'0')
 def test_daemon_and_output_directory_gate(self):
  self.write_source()
  r=subprocess.run([str(self.binary),'start-live',str(self.source),str(self.out)],capture_output=True,timeout=4)
  self.assertEqual(r.returncode,0)
  try:
   again=subprocess.run([str(self.binary),'start-live',str(self.source),str(self.out)],capture_output=True,timeout=4)
   self.assertNotEqual(again.returncode,0)
  finally:
   r=subprocess.run([str(self.binary),'stop',str(self.out)],capture_output=True,timeout=4)
  self.assertEqual(r.returncode,0)

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__)
 for n in ('guidance','stock','java','output'):p.add_argument('--'+n,type=Path,required=True)
 ARGS=p.parse_args();original.ARGS=ARGS
 start=time.monotonic();result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Reader))
 report={'passed':result.wasSuccessful(),'tests':result.testsRun,'seconds':round(time.monotonic()-start,3),'reader_source_sha256':sha(SRC),'guidance_sha256':sha(ARGS.guidance),'test_sha256':sha(Path(__file__)),'fault_shim_sha256':sha(HERE/'reader-faults.c'),'on_unit_validated':False}
 ARGS.output.write_text(json.dumps(report,indent=2)+'\n');raise SystemExit(not result.wasSuccessful())
