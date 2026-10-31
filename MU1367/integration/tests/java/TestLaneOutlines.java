/* Host-only regression through the production decoder and factory array.
 * SPDX-License-Identifier: GPL-3.0-or-later */
package com.cpmap.rgi;
import java.lang.reflect.*;
import de.vw.mib.bap.mqbab2.generated.navsd.serializer.*;

public final class TestLaneOutlines {
    static int checks;
    static void check(boolean yes,String why){checks++;if(!yes)throw new AssertionError(why);}
    static LaneData lane(int status,int highlight,int... angles){
        byte[] b=TestLanes.lane(0,status,highlight,angles);return LaneData.decode(b,0,b.length);
    }
    static void model(){
        for(int status=0;status<=2;status++){
            LaneData p=lane(status,65535,-90,0,90);
            check(p.direction==64&&p.recommendation==0,"ambiguous branch has drawable but unlit anchor");
            check(p.sides.length()==2&&p.sides.charAt(0)==0&&p.sides.charAt(1)==192,"all remaining branches preserved");
            p=lane(status,1000,-90,0);check(p.direction==64&&p.recommendation==0&&p.sides.charAt(0)==0,"invalid highlight does not light an arbitrary branch");
            p=lane(status,65535,0);check(p.direction==0&&p.recommendation==status,"single supplied direction retains phone status");
        }
        LaneData p=lane(2,90,-90,0);check(p.direction==192&&p.recommendation==2&&p.sides.length()==2,"real highlight outside plain set remains preferred");
        p=lane(2,0,-90,0,90);check(p.direction==0&&p.recommendation==2&&p.sides.charAt(0)==64&&p.sides.charAt(1)==192,"real highlighted straight retains both side branches");
        p=lane(2,65535,-91,-90,0,1,90,92);check(p.direction==64&&p.recommendation==0&&p.sides.length()==2,"duplicates and quantized duplicates collapse");
        p=lane(2,65535,1000,-90,0,-1000);check(p.direction==64&&p.sides.length()==1&&p.recommendation==0,"unknown sentinels are not invented as straight");
        p=lane(2,65535,1000,-1000);check(p.direction==255&&p.recommendation==0&&p.sides.length()==0,"all unknown remains unknown");
        p=lane(99,65535,-90,0);check(p.direction==64&&p.recommendation==0,"unknown status never creates a recommendation");
    }
    static void factory()throws Exception{
        TestLive.installMocks();TestLanes.Feed feed=new TestLanes.Feed();feed.state(1,7,true);
        feed.add(0x5204,TestLanes.instruction(7,TestLanes.lane(0,0,65535,-90,0,90),TestLanes.lane(1,0,65535,0),TestLanes.lane(2,1,65535,0),TestLanes.lane(3,2,90,0)));
        LiveModel.Frame f=feed.read();TestLive.clock=f.changed;LiveBridge b=TestLive.bridge();b.incoming=f;b.journalAt=TestLive.clock;b.tick(TestLive.clock);
        LaneGuidance_ChangedArray array=TestLanes.factory();check(array.laneGuidanceOnOff==1&&array.getArrayData().size()==4,"actual factory array retains all four lanes");
        LaneGuidance_LaneGuidance first=(LaneGuidance_LaneGuidance)array.getArrayData().get(0);
        LaneGuidance_LaneGuidance straight=(LaneGuidance_LaneGuidance)array.getArrayData().get(1);
        LaneGuidance_LaneGuidance allowed=(LaneGuidance_LaneGuidance)array.getArrayData().get(2);
        LaneGuidance_LaneGuidance best=(LaneGuidance_LaneGuidance)array.getArrayData().get(3);
        check(first.laneDirection==64&&first.guidanceInfo==0,"unselected multi-exit lane has an unlit real direction");
        check(straight.laneDirection==0&&straight.guidanceInfo==0,"unselected straight lane is drawable");
        check(allowed.laneDirection==0&&allowed.guidanceInfo==1,"allowed lane status unchanged");
        check(best.laneDirection==192&&best.guidanceInfo==2,"preferred lane status unchanged");
        check(first.laneType==1&&first.laneDescription==0&&first.laneMarking_left==0&&first.laneMarking_right==0,"no invented road type, borders or descriptions");
        final byte[][] raw=new byte[1][];
        de.vw.mib.bap.stream.BitStream bits=(de.vw.mib.bap.stream.BitStream)Proxy.newProxyInstance(TestLaneOutlines.class.getClassLoader(),new Class[]{Class.forName("de.vw.mib.bap.stream.BitStream")},new InvocationHandler(){public Object invoke(Object p,Method m,Object[] a){if(m.getName().equals("pushBytes"))raw[0]=(byte[])a[0];return null;}});
        first.laneSidestreets.serialize(bits);
        check(raw[0]!=null&&raw[0].length==2&&raw[0][0]==0&&(raw[0][1]&255)==192,"factory serializer retains straight zero and right byte without UTF8 encoding");
        best.laneSidestreets.serialize(bits);check(raw[0]!=null&&raw[0].length==1&&raw[0][0]==0,"preferred side branch retains raw straight byte");
    }
    public static void main(String[] args)throws Exception{model();factory();System.out.println("LANE_OUTLINES_PASS checks="+checks+" neutral_geometry=1 real_recommendations=1 factory_raw_bytes=1");}
}
