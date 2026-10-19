#!/usr/bin/env python3
"""Real continuous worker + Java RAM reader, bounded storage and fault tests."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import struct
import subprocess
import tempfile
import time
import unittest

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('fixture',HERE/'test-observer.py')
f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f)


class Reader(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory(prefix='cpmap-live-reader-');cls.base=Path(cls.temp.name)
        cls.cc=['clang','-std=c99','-O2','-Wall','-Wextra','-Werror']
        sdk=Path('/Library/Developer/CommandLineTools/SDKs/MacOSX14.4.sdk')
        if sdk.exists():cls.cc+=['-isysroot',str(sdk)]
        cls.binary=cls.base/'reader'
        subprocess.run(cls.cc+[str(HERE/'release/reader.c'),'-o',str(cls.binary)],check=True)
        cls.cp=':'.join(str(p.resolve()) for p in (cls.base,ARGS.hmi/'CarPlayRouteGuidanceD1.jar',ARGS.stock))
        subprocess.run([str(ARGS.java/'bin/javac'),'-cp',cls.cp,'-d',str(cls.base),str(HERE/'release/TestMailbox.java')],check=True)

    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='cpmap-live-case-');self.addCleanup(self.temp.cleanup)
        self.work=Path(self.temp.name);self.source=self.work/'source';self.out=self.work/'ram'

    def write_source(self,seq=2):
        events=[(1,0x5201,f.fixtures.route()),(2,0x5202,f.fixtures.maneuver()+f.fixtures.tlv(9,b'\0')+f.fixtures.tlv(8,b'\0'))]
        for i in range(3,seq+1):
            payload=f.fixtures.route()+f.fixtures.tlv(10,(30).to_bytes(4,'big'))+f.fixtures.tlv(7,(1000).to_bytes(4,'big'))+f.fixtures.tlv(6,(120).to_bytes(8,'big'))
            events.append((i,0x5201,payload))
        tmp=self.work/'source.tmp';tmp.write_bytes(f.fixtures.snapshot(events[-16:],last=seq));tmp.replace(self.source)

    def wait(self,predicate,seconds=4):
        deadline=time.monotonic()+seconds
        while time.monotonic()<deadline:
            try:
                if predicate():return
            except FileNotFoundError:pass
            time.sleep(.02)
        self.fail('reader did not reach expected state')

    def mailbox(self):
        b=(self.out/'latest.bin').read_bytes()
        self.assertEqual(b[:4],b'RGM1');self.assertEqual(struct.unpack_from('<I',b,8)[0],len(b))
        return b

    def start(self):
        p=subprocess.Popen([str(self.binary),'serve',str(self.source),str(self.out)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        def stop():
            if p.poll() is None:p.terminate();p.wait(timeout=4)
        self.addCleanup(stop);self.wait(lambda:(self.out/'latest.bin').is_file());return p

    def java_reader(self,path=None):
        p=subprocess.Popen([str(ARGS.java/'bin/java'),'-Xverify:all','-cp',self.cp,'com.cpmap.rgi.TestMailbox',str(path or self.out/'latest.bin')],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        def stop():
            p.stdin.close();p.wait(timeout=4);p.stdout.close();p.stderr.close()
        self.addCleanup(stop)
        def next_frame(now):
            p.stdin.write(str(now)+'\n');p.stdin.flush();line=p.stdout.readline().strip()
            return line if line in ('same','invalid') else [int(x) for x in line.split(',')]
        return next_frame

    def test_native_to_java_baseline_fresh_progress_and_long_uptime(self):
        self.write_source();p=self.start();read=self.java_reader()
        self.assertEqual(read(1000)[0],0)
        self.write_source(3);self.wait(lambda:struct.unpack_from('<I',self.mailbox(),52)[0]==3)
        self.assertEqual(read(1200)[:6],[1,13,192,30,1000,120])
        # Java is no longer constrained by the diagnostic journal's 603s cap.
        self.write_source(4);self.wait(lambda:struct.unpack_from('<I',self.mailbox(),52)[0]==4)
        self.assertEqual(read(8*3600000)[:6],[1,13,192,30,1000,120]);self.assertIsNone(p.poll())

    def test_disconnect_same_old_window_cannot_revive_and_new_data_recovers(self):
        p=self.start();read=self.java_reader();self.assertEqual(read(1000)[0],0)
        self.write_source();self.wait(lambda:self.mailbox()[16]==1);self.assertEqual(read(1200)[0],0)
        self.write_source(3);self.wait(lambda:struct.unpack_from('<I',self.mailbox(),52)[0]==3);self.assertEqual(read(1400)[0],1)
        self.source.unlink();self.wait(lambda:self.mailbox()[16]==2);self.assertEqual(read(1600)[0],0)
        self.write_source(3);time.sleep(.3)
        self.assertEqual(self.mailbox()[16],2)
        self.write_source(4);self.wait(lambda:self.mailbox()[16]==1);self.assertEqual(read(1800)[0],1);self.assertIsNone(p.poll())

    def test_stale_and_manual_stop_publish_inactive_bounded_records(self):
        self.write_source();p=self.start()
        self.wait(lambda:self.mailbox()[16]==3,seconds=7)
        p.terminate();self.assertEqual(p.wait(timeout=3),0)
        self.assertEqual(self.mailbox()[16:24],struct.pack('<II',5,1))
        self.assertFalse((self.out/'events.rgj').exists())

    def test_largest_windows_use_constant_ram_storage(self):
        route=f.fixtures.route();payload=route+f.fixtures.tlv(0x7000,bytes(2048-len(route)-4))
        def update(last):
            tmp=self.work/'source.tmp'
            tmp.write_bytes(f.fixtures.snapshot([(i,0x5201,payload) for i in range(last-15,last+1)],last=last));tmp.replace(self.source)
        update(16);self.start()
        for last in range(17,30):
            update(last);self.wait(lambda:struct.unpack_from('<I',self.mailbox(),52)[0]==last)
            self.assertLessEqual(sum(p.stat().st_size for p in self.out.iterdir() if p.is_file()),70*1024)
        self.assertEqual(len(self.mailbox()),33120);self.assertFalse((self.out/'events.rgj').exists())

    def test_blocked_worker_deadline_exits_without_restart_loop(self):
        shim=self.work/'block.c';shim.write_text('''#define _POSIX_C_SOURCE 200809L
#include <sys/stat.h>
#include <unistd.h>
#include <time.h>
ssize_t blocked_read(int fd,void *b,size_t n){struct stat st;struct timespec t={5,0};if(!fstat(fd,&st)&&S_ISREG(st.st_mode))nanosleep(&t,0);return read(fd,b,n);}
''')
        obj=self.work/'reader.o';binary=self.work/'blocked'
        subprocess.run(self.cc+['-Dread=blocked_read','-c',str(HERE/'release/reader.c'),'-o',str(obj)],check=True)
        subprocess.run(self.cc+[str(obj),str(shim),'-o',str(binary)],check=True)
        self.write_source();start=time.monotonic()
        r=subprocess.run([str(binary),'serve',str(self.source),str(self.out)],capture_output=True,timeout=4)
        self.assertEqual(r.returncode,1);self.assertLess(time.monotonic()-start,3)
        self.assertEqual(self.mailbox()[16:24],struct.pack('<II',5,3))

    def test_mailbox_integrity_and_restarted_producer_baseline(self):
        path=self.work/'mail';read=self.java_reader(path)
        def put(counter,nonce,payload):
            path.write_bytes(struct.pack('<4s7I',b'RGM1',1,32+len(payload),counter,1,0,nonce,0)+payload)
        self.write_source(3);payload=f.compact(self.source.read_bytes())
        put(1,10,payload);self.assertEqual(read(1000)[0],0)
        self.assertEqual(read(1200),'same')
        self.write_source(4);payload=f.compact(self.source.read_bytes());put(2,10,payload);self.assertEqual(read(1400)[0],1)
        put(1,11,payload);self.assertEqual(read(1600)[0],0)
        self.write_source(5);payload=f.compact(self.source.read_bytes());put(2,11,payload);self.assertEqual(read(1800)[0],1)
        damaged=bytearray(path.read_bytes());damaged[-1]^=1;path.write_bytes(damaged)
        self.assertEqual(read(2000),'invalid')
        path.write_bytes(bytes(33121));self.assertEqual(read(2200),'invalid')
        path.write_bytes(b'RGM1');self.assertEqual(read(2400),'invalid')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('hmi',type=Path);p.add_argument('--java',type=Path,required=True)
    p.add_argument('--stock',type=Path,required=True);p.add_argument('--output',type=Path,required=True);ARGS=p.parse_args()
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Reader))
    report={'passed':result.wasSuccessful(),'tests':result.testsRun,
      'reader_source_sha256':hashlib.sha256((HERE/'release/reader.c').read_bytes()).hexdigest(),
      'mailbox_source_sha256':hashlib.sha256((HERE/'bridge/MailboxReader.java').read_bytes()).hexdigest(),
      'jar_sha256':hashlib.sha256((ARGS.hmi/'CarPlayRouteGuidanceD1.jar').read_bytes()).hexdigest(),
      'test_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    ARGS.output.write_text(json.dumps(report,indent=2)+'\n');raise SystemExit(not result.wasSuccessful())
