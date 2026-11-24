/* Host-only real-decoder/factory-handler regression. SPDX-License-Identifier: GPL-3.0-or-later */
package com.cpmap.rgi;
import java.io.*;
import java.lang.reflect.*;
import de.vw.mib.bap.datatypes.*;
import de.vw.mib.bap.mqbab2.generated.navsd.serializer.*;

public final class TestLaneCanonical {
 static int checks;
 static void check(boolean ok,String why){checks++;if(!ok)throw new AssertionError(why);}
 static LaneData lane(int status,int highlight,int... angles){byte[] b=TestLanes.lane(0,status,highlight,angles);return LaneData.decode(b,0,b.length);}
 static void mapping(){
  for(int status=0;status<=2;status++)for(int a=-180;a<=180;a+=15){
   LaneData l=lane(status,65535,a,a);check(l.direction==LaneData.direction(a)&&l.recommendation==status,"single supplied branch retains its real status");
   check(l.sides.length()==0,"primary never repeated as an extra, including neutral straight");
   check(l.sourceStatus==status&&l.sourceHighlight==1000&&l.sourceAngles.length()>0,"bounded source evidence retained");
   l=lane(status,a,-90,0,90);
   for(int j=0;j<l.sides.length();j++)check(l.sides.charAt(j)!=l.direction,"extras exclude primary regardless of recommendation");
   check(l.recommendation==status,"valid highlight preserves recommendation 0/1/2");
   check(l.getLaneType()==1&&l.getLaneDescription()==0&&l.getMarkingLeft()==0&&l.getMarkingRight()==0,"no fabricated lane type/availability/markings");
  }
  LaneData l=lane(2,65535,-90,0,90);check(l.direction==64&&l.recommendation==0&&l.sides.length()==2&&l.sides.charAt(0)==0&&l.sides.charAt(1)==192,"ambiguous real geometry remains neutral, no invented recommendation");
  l=lane(2,1000,-91,-90,0,1,90,92);check(l.sides.length()==2&&l.recommendation==0,"duplicates quantize/deduplicate without a repeated anchor");
  l=lane(2,65535,1000,-1000);check(l.direction==255&&l.sides.length()==0&&l.recommendation==0,"unknown source does not invent a straight lane");
  l=lane(99,0,0);check(l.sourceStatus==99&&l.recommendation==0,"unknown source status is recorded but never highlighted");
 }
 static void requests()throws Exception{
  TestLive.installMocks();TestLanes.Feed feed=new TestLanes.Feed();feed.state(1,7,true);
  feed.add(0x5204,TestLanes.instruction(7,TestLanes.lane(0,0,65535,-90,0,90),TestLanes.lane(1,0,65535,0),TestLanes.lane(2,1,65535,0),TestLanes.lane(3,2,90,0)));
  LiveModel.Frame frame=feed.read();TestLive.clock=frame.changed;LiveBridge b=TestLive.bridge();b.incoming=frame;b.journalAt=TestLive.clock;b.tick(TestLive.clock);
  check(LaneEvidence.decoded.indexOf("source_lane=0 status=0 highlight=1000 angles=-90,0,90 main=64 recommendation=0 extras=0,192")>=0,"production model records exact source and canonical output");
  Class stageClass=Class.forName("de.vw.mib.bap.mqbab2.navsd.functions.LaneGuidance");
  Class trackerClass=Class.forName("de.vw.mib.bap.mqbab2.common.arrays.FsgArrayMessageBlockingTracker");
  final LaneGuidance_StatusArray[] delivered=new LaneGuidance_StatusArray[1];
  Object tracker=Proxy.newProxyInstance(stageClass.getClassLoader(),new Class[]{trackerClass},new InvocationHandler(){public Object invoke(Object p,Method m,Object[] a){
   if(m.getName().equals("requestGetArray"))return Boolean.TRUE;
   if(m.getName().equals("reportStatusArray")){delivered[0]=(LaneGuidance_StatusArray)a[0];return null;}
   if(m.getReturnType()==Boolean.TYPE)return Boolean.FALSE;return null;
  }});
  for(int record=0;record<=3;record++){
   Object stage=stageClass.newInstance();Field full=stageClass.getDeclaredField("fullLaneGuidanceChangedArray");full.setAccessible(true);full.set(stage,TestLanes.factory());
   Field t=stageClass.getDeclaredField("_arrayRequestTracker");t.setAccessible(true);t.set(stage,tracker);
   LaneGuidance_GetArray q=new LaneGuidance_GetArray();q.asg_Id=record==1?2:record==3?9:1;
   q.getArrayHeader().setRecordAddress(record);q.getArrayHeader().start=0;q.getArrayHeader().elements=4;
   delivered[0]=null;Method get=stageClass.getMethod("getArray",new Class[]{BAPEntity.class,Class.forName("de.vw.mib.bap.functions.ArrayListener")});
   get.invoke(stage,new Object[]{q,null});
   check(delivered[0]!=null&&delivered[0].getArrayData().size()==4&&delivered[0].laneGuidanceOnOff==1,"real factory response keeps all four lanes");
   check(delivered[0].getArrayHeader().getRecordAddress()==record,"diagnostic observer never rewrites client request");
   check(LaneEvidence.request.indexOf("record="+record)>=0&&LaneEvidence.reply.indexOf("serialization_record="+record)>=0,"actual patched request/response hooks called");
   LaneGuidance_LaneGuidance neutral=(LaneGuidance_LaneGuidance)delivered[0].getArrayData().get(0),straight=(LaneGuidance_LaneGuidance)delivered[0].getArrayData().get(1),best=(LaneGuidance_LaneGuidance)delivered[0].getArrayData().get(3);
   check(neutral.guidanceInfo==0&&neutral.laneDirection==64&&neutral.laneSidestreets.toString().length()==2,"factory neutral branching geometry is canonical");
   check(straight.guidanceInfo==0&&straight.laneDirection==0&&straight.laneSidestreets.toString().length()==0,"factory neutral straight is one primary, no duplicate");
   check(best.guidanceInfo==2&&best.laneDirection==192,"recommended lane untouched");
   final int[] sideCalls=new int[1];
   de.vw.mib.bap.stream.BitStream bits=(de.vw.mib.bap.stream.BitStream)Proxy.newProxyInstance(stageClass.getClassLoader(),new Class[]{Class.forName("de.vw.mib.bap.stream.BitStream")},new InvocationHandler(){public Object invoke(Object p,Method m,Object[] a){if(m.getName().equals("pushBytes"))sideCalls[0]++;return null;}});
   delivered[0].getArrayData().serialize(bits);
   check(sideCalls[0]==(record<=1?4:0),"requested record controls whether branch strings are emitted");
  }
  check(LaneEvidence.clusterRecords==13&&LaneEvidence.hudRecords==2,"cluster/HUD request capabilities retained separately");
  String saved=LaneEvidence.decoded;feed.state(0,65535,false);check(saved.equals(LaneEvidence.decoded),"disconnect does not overwrite lane evidence");
 }
 static void bounds(File root)throws Exception{
  root.mkdirs();LaneData[] lanes=new LaneData[16];int[] angles=new int[16];for(int i=0;i<16;i++)angles[i]=-180+i*22;
  for(int i=0;i<16;i++)lanes[i]=lane(0,65535,angles);
  for(int i=0;i<2000;i++)LaneEvidence.received(lanes,i,false,i);
  LaneEvidence.selected(new LiveModel.Frame(true,0,0,-1,1000,60,1,1999,1,lanes,1999),1999);LaneEvidence.write(root.toString());File file=new File(root,"lane-evidence.txt");check(file.length()>0&&file.length()<=16384,"maximum source geometry stays within fixed evidence bound");
  String body=new String(TestRecovery.read(file),"US-ASCII");check(body.indexOf("instruction=1999")>=0&&body.indexOf("source_lane=")>=0,"latest numeric source evidence written atomically");
  check(root.list().length==1,"no append/archive accumulation");
  LaneEvidence.requested(null);LaneEvidence.assembled(null);check(body.length()<16384,"diagnostic invalid input cannot disrupt factory handler");
 }
 public static void main(String[] args)throws Exception{mapping();requests();bounds(new File(args[0]));System.out.println("CANONICAL_LANE_PASS checks="+checks+" real_factory_getArray=1 record_0_1_2_3=1 no_duplicate_primary=1 bounded_retained_evidence=1");}
}
