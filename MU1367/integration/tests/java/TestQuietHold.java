/* SPDX-License-Identifier: GPL-3.0-or-later */
package com.cpmap.rgi;
import java.io.*;
import de.vw.mib.bap.mqbab2.generated.navsd.serializer.*;
/** Apple-style sparse deltas and Waze-style malformed first messages. */
public final class TestQuietHold {
 static int checks;
 static void check(boolean b,String why){checks++;if(!b)throw new AssertionError(why);}
 static byte[] j(byte[] a,byte[] b){return TestLanes.join(a,b);}
 static byte[] t(int id,byte[] b){return TestLanes.tlv(id,b);}
 static byte[] routeTo(int phase,int index,int meters){
  return j(j(t(0,TestLanes.u16(16)),t(1,new byte[]{(byte)phase})),j(t(13,TestLanes.u16(index)),t(10,new byte[]{0,0,(byte)(meters>>8),(byte)meters})));
 }
 static byte[] maneuver(int index,int type){return j(j(t(0,TestLanes.u16(16)),t(1,TestLanes.u16(index))),j(t(3,new byte[]{(byte)type}),t(9,new byte[]{0})));}
 static void quiet(File root)throws Exception{
  TestRecovery.Wire w=new TestRecovery.Wire(root);FeedRecovery f=new FeedRecovery(root.toString());
  w.route(0);w.publish();f.poll(1000);check(!f.live,"cold baseline");
  w.add(0x5201,routeTo(1,5,300));w.add(0x5202,maneuver(5,2));w.add(0x5201,routeTo(1,5,250));w.publish();f.poll(1100);
  check(f.live&&f.last.main==13&&f.last.direction==192&&f.last.meters==250,"route, maneuver and distance active");
  long generation=f.generation;
  w.envelope(3,5000,new byte[0]);f.poll(6100);
  check(f.live&&f.last.main==13&&f.last.meters==250&&f.generation==generation,"reader STALE keeps the model");
  for(long now=7100;now<=60100;now+=1000){w.envelope(3,5000,new byte[0]);f.poll(now);check(f.live,"heartbeat-backed quiet route held");}
  w.add(0x5201,routeTo(1,5,120));w.publish();f.poll(61000);
  check(f.live&&f.last.main==13&&f.last.direction==192&&f.last.meters==120,"distance-only delta reuses cached maneuver");
  w.envelope(3,5000,new byte[0]);f.poll(61000+LiveModel.HOLD_MS-1);check(f.live,"held until the bound");
  w.envelope(3,5000,new byte[0]);f.poll(61000+LiveModel.HOLD_MS);check(!f.live,"silence bound releases");
  w.add(0x5201,routeTo(1,5,100));w.publish();f.poll(62000+LiveModel.HOLD_MS);check(f.live&&f.last.main==13,"fresh delta after the bound resumes");
  w.add(0x5201,TestLanes.route(0,65535,false));w.publish();f.poll(62100+LiveModel.HOLD_MS);check(!f.live&&!f.last.active,"explicit route end clears immediately");
  w.envelope(2,4,new byte[0]);f.poll(62200+LiveModel.HOLD_MS);check(!f.live,"invalidation still clears");
 }
 static void wazeFirst(File root)throws Exception{
  GuidanceEvidence.session=-1;long before=GuidanceEvidence.rejected;
  TestRecovery.Wire w=new TestRecovery.Wire(root);FeedRecovery f=new FeedRecovery(root.toString());
  // Captured on-unit fault: RouteGuidanceUpdate sequence 1 fails at field 1.
  w.add(0x5201,t(1,new byte[]{0}));w.publish();f.poll(1000);
  check(!f.live&&f.error==0&&f.errors==0,"malformed first message is not a feed failure");
  check(GuidanceEvidence.rejected==before+1&&GuidanceEvidence.lastRejected.indexOf("seq=1 id=5201 field=1")>=0
   &&GuidanceEvidence.lastRejected.indexOf("shape=1:1=00")>=0,"rejection shape recorded");
  w.add(0x5201,routeTo(1,7,400));w.add(0x5202,maneuver(7,1));w.add(0x5201,routeTo(1,7,350));w.publish();f.poll(1100);
  check(f.live&&f.last.main==13&&f.last.direction==64&&f.last.meters==350,"valid messages display while the bad one is still in the window");
  f.rebase();f.poll(2000);check(GuidanceEvidence.rejected==before+1,"window replay is not double counted");
  check(GuidanceEvidence.route>=2&&GuidanceEvidence.maneuver>=1,"message counts recorded");
  File out=new File(root,"evidence");out.mkdirs();GuidanceEvidence.write(out.toString());
  String text=new String(TestRecovery.read(new File(out,"guidance-evidence.txt")),"US-ASCII");
  check(text.length()<4096&&text.indexOf("hold_ms=180000")>=0&&text.indexOf("maneuver_types=")>=0,"bounded evidence file");
 }
 static void sources(File root)throws Exception{
  GuidanceEvidence.session=-1;
  TestRecovery.Wire w=new TestRecovery.Wire(root);FeedRecovery f=new FeedRecovery(root.toString());
  byte[] named=j(routeTo(1,3,200),t(19,"Waze\0".getBytes("US-ASCII")));
  w.add(0x5201,named);w.publish();f.poll(1000);
  check(GuidanceEvidence.snapshot().indexOf("current=Waze")>=0,"source app name recorded");
  byte[] odd=j(routeTo(1,3,200),t(19,"Bad=Name;\0".getBytes("US-ASCII")));w.add(0x5201,odd);w.publish();f.poll(1100);
  String s=GuidanceEvidence.snapshot();check(s.indexOf("Bad?Name?")>=0&&s.indexOf("changes=")>=0,"source names sanitized");
 }
 static void bridge(File root)throws Exception{
  TestLive.installMocks();LiveBridge b=TestLive.bridge();FeedRecovery feed=new FeedRecovery(root.toString());TestRecovery.Wire w=new TestRecovery.Wire(root);
  w.route(0);w.publish();TestLive.clock=1000;b.pollProduction(feed,1000,false);b.tick(1000);
  w.add(0x5201,routeTo(1,5,300));w.add(0x5202,maneuver(5,2));w.publish();TestLive.clock=1250;b.pollProduction(feed,1250,false);b.tick(1250);
  check(b.owned,"bridge owns active route");
  ManeuverDescriptor_Status out=new ManeuverDescriptor_Status();
  long now=2250;
  for(;now<1250+LiveModel.HOLD_MS;now+=1000){
   w.envelope(3,5000,new byte[0]);TestLive.clock=now;b.pollProduction(feed,now,false);b.tick(now);
   if(!b.owned)break;
   if(now==61250)check(LiveBridge.descriptor(out)&&out.maneuver_1.mainElement==13&&out.maneuver_1.direction==192,"held maneuver output after a minute of silence");
  }
  check(now>=1250+LiveModel.HOLD_MS,"bridge held the quiet route for the whole bound");
  w.envelope(3,5000,new byte[0]);TestLive.clock=now;b.pollProduction(feed,now,false);b.tick(now);
  check(!b.owned&&b.lastReleaseReason!=3,"bridge releases at the silence bound");
  w.add(0x5201,routeTo(1,5,200));w.publish();now+=250;TestLive.clock=now;b.pollProduction(feed,now,false);b.tick(now);
  check(b.owned,"fresh delta reacquires");
  out=new ManeuverDescriptor_Status();check(LiveBridge.descriptor(out)&&out.maneuver_1.mainElement==13&&out.maneuver_1.direction==192,"held maneuver output after reacquire");
 }
 public static void main(String[] a)throws Exception{
  File root=new File(a[0]);quiet(new File(root,"quiet"));wazeFirst(new File(root,"waze"));sources(new File(root,"sources"));bridge(new File(root,"bridge"));
  System.out.println("QUIET_HOLD_PASS checks="+checks+" hold_ms="+LiveModel.HOLD_MS+" stale_keeps_model=1 message_scoped_rejection=1 actual_bridge=1");
 }
}
