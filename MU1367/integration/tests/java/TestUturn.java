package com.cpmap.rgi;
import java.lang.reflect.*;
import java.util.*;
import de.vw.mib.bap.mqbab2.generated.navsd.serializer.*;
import de.vw.mib.bap.stream.BitStream;
public class TestUturn {
 public static void main(String[] args)throws Exception{
  TestLive.installMocks();
  int checks=0;
  int[] angles={-180,-170,170,179,180};int[] directions={114,114,146,146,114};
  for(int i=0;i<angles.length;i++)if(LaneData.direction(angles[i])!=directions[i])throw new AssertionError("U-turn mapping");
  if(LaneData.direction(-169)!=128||LaneData.direction(169)!=128)throw new AssertionError("reviewed unchanged boundary");
  for(int angle=-180;angle<=180;angle++){
   TestLanes.Feed feed=new TestLanes.Feed();
   feed.state(1,7,true);
   feed.add(0x5204,TestLanes.instruction(7,TestLanes.lane(0,2,angle,angle,0)));
   LiveModel.Frame frame=feed.read();TestLive.clock=frame.changed;
   LiveBridge bridge=TestLive.bridge();bridge.incoming=frame;bridge.journalAt=TestLive.clock;bridge.tick(TestLive.clock);
   LaneGuidance_ChangedArray out=TestLanes.factory();
   if(out.laneGuidanceOnOff!=1||out.getArrayData().size()!=1)throw new AssertionError("missing lane "+angle);
   LaneGuidance_LaneGuidance lane=(LaneGuidance_LaneGuidance)out.getArrayData().get(0);
   int expected=LaneData.direction(angle);
   if(lane.laneDirection!=expected||lane.guidanceInfo!=2)throw new AssertionError("factory changed lane "+angle);
   if(expected!=0&&(lane.laneSidestreets.toString().length()!=1||lane.laneSidestreets.toString().charAt(0)!=0))throw new AssertionError("side exit lost "+angle);
   out.getArrayHeader().setRecordAddress(2);
   final List<Integer> bytes=new ArrayList<Integer>();
   BitStream bits=(BitStream)Proxy.newProxyInstance(TestUturn.class.getClassLoader(),new Class[]{BitStream.class},new InvocationHandler(){public Object invoke(Object p,Method m,Object[] a){if(m.getName().equals("pushByte"))bytes.add(((Number)a[0]).intValue()&255);return null;}});
   lane.serialize(bits);
   if(!bytes.contains(expected))throw new AssertionError("wire direction missing "+angle+" "+bytes);
   checks++;
  }
  // Side-branch U-turns go through the same decoder and factory builder.
  for(int angle:new int[]{-180,-170,170,179,180}){
   TestLanes.Feed feed=new TestLanes.Feed();feed.state(1,7,true);
   feed.add(0x5204,TestLanes.instruction(7,TestLanes.lane(0,2,0,0,angle)));
   LiveModel.Frame frame=feed.read();TestLive.clock=frame.changed;
   LiveBridge bridge=TestLive.bridge();bridge.incoming=frame;bridge.journalAt=TestLive.clock;bridge.tick(TestLive.clock);
   LaneGuidance_ChangedArray out=TestLanes.factory();LaneGuidance_LaneGuidance lane=(LaneGuidance_LaneGuidance)out.getArrayData().get(0);
   if(lane.laneDirection!=0||lane.laneSidestreets.toString().length()!=1||lane.laneSidestreets.toString().charAt(0)!=LaneData.direction(angle))throw new AssertionError("side U-turn lost "+angle);
   checks++;
  }
  System.out.println("UTURN_FACTORY_TRANSPORT_PASS angle_sweep=361 side_branch_cases=5 checks="+checks);
  for(int angle:new int[]{-180,-170,-169,-90,0,90,169,170,179,180})System.out.println(angle+" -> "+LaneData.direction(angle));
 }
}
