/* SPDX-License-Identifier: GPL-3.0-or-later */
package com.cpmap.rgi;
import java.io.*;
import java.util.Vector;
public final class TestRecovery {
 static int checks;
 static void check(boolean b,String why){checks++;if(!b)throw new AssertionError(why);}
 static final class Wire {
  final File root;final Vector<byte[]> events=new Vector<byte[]>();int seq,serial;long nonce=1;
  Wire(File r){root=r;r.mkdirs();}
  void add(int id,byte[] payload){byte[] b=new byte[payload.length+16];le(b,0,++seq);b[4]=(byte)id;b[5]=(byte)(id>>8);b[6]=(byte)payload.length;b[7]=(byte)(payload.length>>8);le(b,8,1);System.arraycopy(payload,0,b,16,payload.length);events.add(b);}
  void route(int phase){add(0x5201,TestLanes.route(phase,7,false));}
  void publish()throws Exception{int n=Math.min(16,events.size());byte[] b=new byte[64];le(b,0,0x31494752);le(b,4,1);le(b,8,33088);le(b,16,1);le(b,20,seq);le(b,24,n);le(b,36,1);le(b,40,1);
   for(int i=events.size()-n;i<events.size();i++)b=TestLanes.join(b,events.get(i));envelope(1,0,b);}
  void envelope(int kind,int detail,byte[] body)throws Exception{byte[] b=new byte[32];le(b,0,0x314d4752);le(b,4,1);le(b,8,32+body.length);le(b,12,++serial);le(b,16,kind);le(b,20,detail);le(b,24,(int)nonce);write(new File(root,"latest.bin"),TestLanes.join(b,body));}
 }
 static void le(byte[] b,int at,int n){TestLanes.le(b,at,n);}
 static void write(File f,byte[] b)throws Exception{FileOutputStream out=new FileOutputStream(f);out.write(b);out.close();}
 static byte[] read(File f)throws Exception{ByteArrayOutputStream out=new ByteArrayOutputStream();FileInputStream in=new FileInputStream(f);byte[] b=new byte[4096];int n;while((n=in.read(b))>=0)out.write(b,0,n);in.close();return out.toByteArray();}
 static void synthetic(File root)throws Exception{
  Wire w=new Wire(root);FeedRecovery f=new FeedRecovery(root.toString());w.route(0);w.publish();f.poll(1000);check(!f.live,"cold baseline never live");
  w.route(1);w.publish();f.poll(1100);check(f.live&&f.error==0,"fresh guide starts");f.poll(1200);check(f.live&&f.recordAt==1100,"unchanged poll retains lease");
  write(new File(root,"latest.bin"),new byte[]{1,2,3});f.poll(1300);check(!f.live&&f.error==1&&!f.fatal&&f.errors==1,"I/O validation error clears output");
  File first=new File(root,"failure-first.txt");byte[] saved=read(first);check(saved.length<768,"first failure bounded");
  check(new String(saved,"US-ASCII").indexOf("serial=-1 kind=-1 nonce=-1")>=0,"truncated input never inherits a good envelope identity");
  w.publish();f.poll(1400);check(!f.live&&f.reader.records==0,"retry backoff");f.poll(2300);check(!f.live&&f.error==1,"recovery baseline cannot resurrect");
  w.publish();f.poll(2400);check(!f.live,"heartbeat not fresh guidance");w.route(1);w.publish();f.poll(2500);check(f.live&&f.error==0&&f.recoveries==1,"fresh post-baseline recovery");
  f.poll(4000);check(!f.live,"heartbeat lease expires");
  w.envelope(2,4,new byte[0]);f.poll(4100);check(!f.live,"invalidation clears");w.publish();f.poll(4200);check(!f.live,"old route cannot revive after invalidation");
  w.route(1);w.publish();f.poll(4300);check(f.live,"new route update revives");
  byte[] bad=TestLanes.join(TestLanes.tlv(0,TestLanes.u16(16)),TestLanes.tlv(1,new byte[]{1,0}));w.add(0x5201,bad);w.publish();f.poll(4400);check(f.error==1&&!f.live,"semantic field width rejected");
  for(int i=0;i<500;i++){f.poll(4500+i*20);check(!f.live,"persistent bad input cannot revive");}
  check(f.errors<13,"bad input retry bounded to one per second");check(LiveModel.equal(saved,read(first)),"first failure never overwritten");
  Wire next=new Wire(root);next.nonce=2;next.route(0);next.publish();long time=f.retryAt;f.poll(time);check(!f.live,"new producer baseline");next.route(1);next.publish();f.poll(time+100);check(f.live&&f.recoveries==2,"new source recovers");
  check(new File(root,"latest.bin").delete(),"remove mailbox");f.poll(time+200);check(!f.live&&f.error==0,"normal disconnect clears without error latch");
  next.publish();f.poll(time+1200);check(!f.live,"reconnect baseline");next.route(1);next.publish();f.poll(time+1300);check(f.live,"cable after reconnect resumes");
  next.envelope(5,1,new byte[0]);f.poll(time+1400);check(!f.live,"terminal feed hides");
  Wire third=new Wire(root);third.nonce=3;third.route(0);third.publish();f.poll(time+1500);third.route(1);third.publish();f.poll(time+1600);check(f.live,"new producer after terminal resumes");
  f.pause();check(!f.live&&f.recordAt<0,"manual disable clears");third.publish();f.poll(time+1700);check(!f.live,"re-enable needs baseline and fresh input");
 }
 static void firstFault(File root)throws Exception{
  Wire w=new Wire(root);w.add(0x5201,TestLanes.join(TestLanes.tlv(0,TestLanes.u16(16)),TestLanes.tlv(1,new byte[]{1,0})));w.publish();FeedRecovery f=new FeedRecovery(root.toString());f.poll(1000);
  String s=new String(read(new File(root,"failure-first.txt")),"US-ASCII");check(s.indexOf("message=20993 field=1")>=0&&s.indexOf("sequence=1")>=0,"numeric offending message/field/sequence retained");
  check(s.indexOf("serial=1 kind=1 nonce=1")>=0,"offending envelope retained");
  File fatal=new File(root,"fatal");fatal.mkdirs();f=new FeedRecovery(fatal.toString());f.failed(new LinkageError("secret fixture must not appear"),1000);
  f.poll(5000);check(f.fatal&&!f.live&&f.error==1,"unexpected VM errors remain stopped");
  s=new String(read(new File(fatal,"failure-first.txt")),"US-ASCII");check(s.indexOf("fatal=1")>=0&&s.indexOf("secret")<0,"no exception messages in diagnostics");
 }
 static void bridge(File root)throws Exception{
  TestLive.installMocks();LiveBridge b=TestLive.bridge();FeedRecovery feed=new FeedRecovery(root.toString());Wire w=new Wire(root);
  w.route(0);w.publish();TestLive.clock=1000;b.pollProduction(feed,1000,false);b.tick(1000);
  w.route(1);w.publish();TestLive.clock=1250;b.pollProduction(feed,1250,false);b.tick(1250);check(b.owned,"production polling acquires actual bridge");
  write(new File(root,"latest.bin"),new byte[]{0});TestLive.clock=1500;b.pollProduction(feed,1500,false);b.tick(1500);check(!b.owned&&b.mode==0,"actual bridge releases on read error");
  w.publish();TestLive.clock=2500;b.pollProduction(feed,2500,false);b.tick(2500);check(!b.owned,"actual bridge refuses recovery baseline");
  w.route(1);w.publish();TestLive.clock=2750;b.pollProduction(feed,2750,false);b.tick(2750);check(b.owned&&b.mode==2,"actual bridge floor resets after recovery");
  TestLive.route=1;TestLive.clock=3000;b.pollProduction(feed,3000,false);b.tick(3000);check(!b.owned,"OEM takeover retained");TestLive.route=0;
  TestLive.clock=3250;b.pollProduction(feed,3250,true);b.tick(3250);check(b.mode==0&&!b.owned,"manual disable production path");
 }
 public static void main(String[] a)throws Exception{
  File root=new File(a[0]);synthetic(new File(root,"synthetic"));firstFault(new File(root,"fault"));bridge(new File(root,"bridge"));
  for(int i=1;i<a.length;i++){File dir=new File(root,"capture"+i);dir.mkdirs();write(new File(dir,"latest.bin"),read(new File(a[i])));FeedRecovery f=new FeedRecovery(dir.toString());f.poll(1000);check(f.errors==0&&!f.live,"private capture valid baseline; no replayed guidance");}
  System.out.println("RECOVERY_PASS checks="+checks+" strict_validation=1 fresh_after_baseline=1 actual_bridge=1 first_failure_bounded=1 private_captures="+(a.length-1));
 }
}
