/* Factory ARM/J9 U-turn probe; never installed. SPDX-License-Identifier: GPL-3.0-or-later */
package com.cpmap.rgi;
import java.lang.reflect.*;
import de.vw.mib.bap.mqbab2.generated.navsd.serializer.*;
import de.vw.mib.bap.stream.BitStream;
public final class TestUturnQnx {
 public static void main(String[] args)throws Exception {
  TestRoadQnx.main(args);TestArrowQnx.main(args);TestQuietQnx.main(args);
  int[] angles={-180,-170,170,179,180};int[] expected={114,114,146,146,114};
  int checks=0;TestRoadQnx.clock=2000;TestRoadQnx.route=0;
  for(int i=0;i<angles.length;i++) {
   int angle=angles[i];
   byte[] raw={0,6,0,0,0,0,0,5,0,1,2,0,6,0,2,0,0,0,6,0,3,(byte)(angle>>8),(byte)angle};
   LaneData data=LaneData.decode(raw,0,raw.length);
   if(data==null||data.getDirection()!=expected[i])throw new Exception("U-turn decode");
   LiveModel.Frame frame=new LiveModel.Frame(true,13,192,30,1000,60,1,TestRoadQnx.clock,1,new LaneData[]{data},TestRoadQnx.clock,"",-1);
   TestRoadQnx.prepare(LiveBridge.INSTANCE,frame);
   Object factory=Class.forName("de.vw.mib.bap.mqbab2.navsd.functions.LaneGuidance").newInstance();
   LaneGuidance_ChangedArray array=new LaneGuidance_ChangedArray();
   Method fill=factory.getClass().getDeclaredMethod("computeFullLaneGuidanceList",new Class[]{Class.forName("de.vw.mib.bap.mqbab2.generated.navsd.serializer.LaneGuidance_ChangedArray")});fill.setAccessible(true);fill.invoke(factory,new Object[]{array});
   if(array.laneGuidanceOnOff!=1||array.getArrayData().size()!=1)throw new Exception("U-turn factory lane");
   LaneGuidance_LaneGuidance lane=(LaneGuidance_LaneGuidance)array.getArrayData().get(0);
   if(lane.laneDirection!=expected[i]||lane.guidanceInfo!=2||lane.laneSidestreets.toString().length()!=1||lane.laneSidestreets.toString().charAt(0)!=0)throw new Exception("U-turn factory fields");
   final int[] written={-1};
   Class bits=Class.forName("de.vw.mib.bap.stream.BitStream");
   BitStream sink=(BitStream)Proxy.newProxyInstance(bits.getClassLoader(),new Class[]{bits},new InvocationHandler(){public Object invoke(Object p,Method m,Object[] a){if(m.getName().equals("pushByte"))written[0]=((Byte)a[0]).byteValue()&255;return null;}});
   array.getArrayHeader().setRecordAddress(2);lane.serialize(sink);
   if(written[0]!=expected[i])throw new Exception("U-turn wire byte");checks++;
  }
  if(LaneData.direction(-169)!=128||LaneData.direction(169)!=128)throw new Exception("unchanged edge");
  System.out.println(new StringBuffer("UTURN_FACTORY_J9_PASS cases=").append(checks).append(" decoder=1 actual_factory_builder=1 serializer=1 boundary=1 build=").append(BuildInfo.ID).toString());
 }
}
