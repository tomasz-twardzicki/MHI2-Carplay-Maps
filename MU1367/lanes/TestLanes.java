/* Host-only regression against production decoder and factory lane stage.
 * SPDX-License-Identifier: GPL-3.0-or-later */
package com.cpmap.rgi;
import java.io.*;
import java.lang.reflect.Method;
import java.util.Vector;
import de.vw.mib.bap.mqbab2.generated.navsd.serializer.*;

public final class TestLanes {
 static int checks;
 static void check(boolean condition,String name){checks++;if(!condition)throw new AssertionError(name);}
 static byte[] join(byte[] a,byte[] b){byte[] c=new byte[a.length+b.length];System.arraycopy(a,0,c,0,a.length);System.arraycopy(b,0,c,a.length,b.length);return c;}
 static byte[] tlv(int id,byte[] b){byte[] out=new byte[b.length+4];out[0]=(byte)(out.length>>8);out[1]=(byte)out.length;out[2]=(byte)(id>>8);out[3]=(byte)id;System.arraycopy(b,0,out,4,b.length);return out;}
 static byte[] u16(int n){return new byte[]{(byte)(n>>8),(byte)n};}
 static byte[] lane(int position,int status,int highlight,int... angles){
  byte[] out=join(tlv(0,u16(position)),tlv(1,new byte[]{(byte)status}));
  if(highlight!=65535)out=join(out,tlv(3,u16(highlight)));
  for(int a:angles)out=join(out,tlv(2,u16(a)));return out;
 }
 static byte[] instruction(int index,byte[]... lanes){
  byte[] out=join(tlv(0,u16(16)),tlv(1,u16(index)));for(byte[] b:lanes)out=join(out,tlv(2,b));return out;
 }
 static byte[] route(int phase,int index,boolean show){
  return join(join(tlv(0,u16(16)),tlv(1,new byte[]{(byte)phase})),join(tlv(13,new byte[0]),join(tlv(16,u16(index)),tlv(18,new byte[]{(byte)(show?1:0)}))));
 }
 static void le(byte[] b,int at,int n){for(int i=0;i<4;i++)b[at+i]=(byte)(n>>(8*i));}
 static final class Feed {
  final LiveModel model=new LiveModel();final Vector<byte[]> events=new Vector<byte[]>();int sequence;long now=1000;boolean first=true;
  Feed()throws Exception{add(0x5201,route(0,65535,false));read();}
  void add(int id,byte[] payload){
   byte[] e=new byte[16+payload.length];le(e,0,++sequence);e[4]=(byte)id;e[5]=(byte)(id>>8);e[6]=(byte)payload.length;e[7]=(byte)(payload.length>>8);le(e,8,1);System.arraycopy(payload,0,e,16,payload.length);events.add(e);
  }
  LiveModel.Frame read()throws Exception{
   int count=Math.min(16,events.size());byte[] b=new byte[64];le(b,0,0x31494752);le(b,4,1);le(b,8,33088);le(b,16,1);le(b,20,sequence);le(b,24,count);le(b,36,1);le(b,40,1);
   for(int i=events.size()-count;i<events.size();i++)b=join(b,events.get(i));
   LiveModel.Frame f=model.snapshot(b,now++,first);first=false;return f;
  }
  LiveModel.Frame state(int phase,int index,boolean show)throws Exception{add(0x5201,route(phase,index,show));return read();}
 }
 static byte[][] sample(){return new byte[][]{lane(2,2,90,0),lane(0,0,65535,-90),lane(1,1,65535,0)};}
 static LiveModel.Frame active(Feed f)throws Exception{f.state(1,7,true);f.add(0x5204,instruction(7,sample()));return f.read();}
 static LaneGuidance_ChangedArray factory()throws Exception{
  Object f=Class.forName("de.vw.mib.bap.mqbab2.navsd.functions.LaneGuidance").newInstance();
  LaneGuidance_ChangedArray out=new LaneGuidance_ChangedArray();
  Method method=f.getClass().getDeclaredMethod("computeFullLaneGuidanceList",new Class[]{Class.forName("de.vw.mib.bap.mqbab2.generated.navsd.serializer.LaneGuidance_ChangedArray")});method.setAccessible(true);method.invoke(f,out);return out;
 }
 static void model()throws Exception{
  for(int a=-180;a<=180;a++){int d=LaneData.direction(a);check(d>=0&&d<=240&&d%16==0,"direction sector");check((d+LaneData.direction(-a))%256==0,"mirrored direction");}
  check(LaneData.direction(-90)==64&&LaneData.direction(90)==192&&LaneData.direction(180)==128,"factory geometry");
  check(LaneData.direction(1000)==255&&LaneData.direction(-1000)==255&&LaneData.direction(181)==255,"unknown angles");
  LaneData p=LaneData.decode(lane(0,2,90,-90,0),0,lane(0,2,90,-90,0).length);
  check(p.direction==192&&p.recommendation==2&&p.sides.length()==2&&p.sides.charAt(0)==64&&p.sides.charAt(1)==0,"separate highlighted angle and raw side exits");
  byte[] bytes=lane(0,2,65535,-90,0);p=LaneData.decode(bytes,0,bytes.length);
  check(p.direction==255&&p.recommendation==0&&p.sides.length()==2,"ambiguous branch never recommended");
  bytes=lane(0,1,1000,0,0);p=LaneData.decode(bytes,0,bytes.length);check(p.direction==0&&p.recommendation==1,"duplicate directions collapse");
  Feed f=new Feed();LiveModel.Frame frame=active(f);
  check(frame.active&&frame.main==0&&frame.lanes.length==3,"lanes independent of an empty maneuver list");
  check(frame.lanes[0].position==0&&frame.lanes[2].position==2&&frame.lanes[2].recommendation==2,"left-to-right order and recommendations");
  check(f.state(1,8,true).lanes.length==0,"unknown selected instruction clears");
  check(f.state(1,7,true).lanes.length==3,"explicit known instruction reselects");
  check(f.state(1,7,false).lanes.length==0,"phone hide");
  check(f.state(1,7,true).lanes.length==3,"phone show");
  f.add(0x5204,instruction(7,lane(0,2,0),lane(0,1,90)));frame=f.read();check(frame.active&&frame.lanes.length==0,"duplicate positions hide whole instruction only");
  f.add(0x5204,instruction(7,lane(65535,2,0)));check(f.read().lanes.length==0,"unknown lane position");
  byte[][] many=new byte[17][];for(int i=0;i<17;i++)many[i]=lane(i,0,0);
  f.add(0x5204,instruction(7,many));check(f.read().lanes.length==0,"oversized layout never silently truncated");
  int[] angles=new int[17];f.add(0x5204,instruction(7,lane(0,2,0,angles)));check(f.read().lanes.length==0,"too many angles");
  f.add(0x5204,instruction(7,lane(0,2,1000,1000)));check(f.read().lanes.length==0,"unrecognisable layout");
  f.add(0x5204,instruction(7,join(lane(0,2,0),tlv(0,u16(1)))));check(f.read().lanes.length==0,"duplicate mandatory field");
  f.add(0x5204,instruction(7,new byte[]{0,8,0,0}));check(f.read().lanes.length==0,"malformed nested TLV clears only lanes");
  byte[] omitted=instruction(7,sample());omitted=LiveModel.copy(omitted,6,omitted.length-6);f.add(0x5204,omitted);check(f.read().lanes.length==3,"missing component broadcasts");
  f.add(0x5204,join(tlv(0,u16(99)),instruction(7,sample())));check(f.read().lanes.length==3,"component set includes ours");
  f.add(0x5204,join(tlv(0,u16(99)),tlv(1,u16(7))));check(f.read().lanes.length==3,"other component cannot clear our lanes");
  check(f.state(2,7,true).lanes.length==0,"arrival clears");
  check(f.state(1,7,true).lanes.length==0,"new route cannot revive old lanes");
  f.add(0x5204,instruction(7,sample()));check(f.read().lanes.length==3,"fresh lane content");
  check(f.state(3,7,true).lanes.length==0,"reroute clears");
  check(f.state(1,7,true).lanes.length==0,"reroute requires fresh lane content");
  f.model.invalidate();check(f.model.frame().lanes.length==0,"disconnect/gap reset");
  LaneData.Cache cache=new LaneData.Cache();cache.put(7,frame.lanes);cache.selected=7;cache.showing=true;
  for(int i=10;i<40;i++)cache.put(i,LaneData.EMPTY);
  int saved=0;for(int i=0;i<6;i++)if(cache.values[i]!=null&&cache.keys[i]==7)saved++;
  check(saved==1,"lookahead cache protects selected instruction");
 }
 static void integration()throws Exception{
  TestLive.installMocks();Feed f=new Feed();LiveModel.Frame frame=active(f);TestLive.clock=frame.changed;
  LiveBridge b=TestLive.bridge();b.incoming=frame;b.journalAt=TestLive.clock;b.tick(TestLive.clock);
  LaneGuidance_ChangedArray out=factory();check(out.laneGuidanceOnOff==1&&out.getArrayData().size()==3,"factory lane stage enabled");
  LaneGuidance_LaneGuidance right=(LaneGuidance_LaneGuidance)out.getArrayData().get(2);
  check(right.laneDirection==192&&right.guidanceInfo==2&&right.laneSidestreets.toString().length()==1&&right.laneSidestreets.toString().charAt(0)==0,"factory BAP best lane and straight side exit");
  check(right.laneType==0&&right.laneDescription==15&&right.laneMarking_left==0&&right.laneMarking_right==0,"no invented lane geometry/markings");
  TestLive.setupLane=false;out=factory();check(out.laneGuidanceOnOff==0,"OEM lane setting honored");TestLive.setupLane=true;
  f.state(1,8,true);frame=f.state(1,7,false);TestLive.clock=frame.changed;b.incoming=frame;b.journalAt=TestLive.clock;b.tick(TestLive.clock);out=factory();
  check(out.laneGuidanceOnOff==0&&out.getArrayData().size()==0,"live hide clears actual factory array");
  frame=f.state(1,7,true);TestLive.clock=frame.changed;b.incoming=frame;b.journalAt=TestLive.clock;b.tick(TestLive.clock);check(factory().laneGuidanceOnOff==1,"lane restoration");
  // Use the unmodified factory six-lane window and omitted-edge markers.
  byte[][] road=new byte[10][];for(int i=0;i<10;i++)road[i]=lane(i,i==6?2:0,i==6?90:0);
  f.add(0x5204,instruction(7,road));frame=f.read();TestLive.clock=frame.changed;b.incoming=frame;b.journalAt=TestLive.clock;b.tick(TestLive.clock);out=factory();
  check(out.getArrayData().size()==6,"factory six-lane capacity");
  check(((LaneGuidance_LaneGuidance)out.getArrayData().getFirst()).laneType==23,"factory hidden-left marker");
  boolean recommended=false;for(int i=0;i<6;i++)if(((LaneGuidance_LaneGuidance)out.getArrayData().get(i)).guidanceInfo==2)recommended=true;
  check(recommended,"factory window retains preferred lane");
  TestLive.clock+=5001;b.lastTick=TestLive.clock;b.journalAt=TestLive.clock;
  b.incoming=new LiveModel.Frame(true,13,192,30,1000,60,frame.progress+1,TestLive.clock,frame.epoch,frame.lanes,frame.laneAt);b.tick(TestLive.clock);out=factory();
  check(out.laneGuidanceOnOff==0&&out.getArrayData().size()==0&&b.owned,"lane deadline independent of fresh arrow feed");
  TestLive.route=1;TestLive.clock+=250;b.tick(TestLive.clock);check(!b.owned&&b.selected==null&&factory().getArrayData().size()==0,"OEM priority");TestLive.route=0;
 }
 public static void main(String[] a)throws Exception{model();integration();System.out.println("LANES_PASS checks="+checks+" actual_factory_builder=1 no_maneuver_dependency=1 independent_freshness=1");}
}
