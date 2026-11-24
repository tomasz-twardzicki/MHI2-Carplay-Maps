/* Host-only real decoder/factory regression. SPDX-License-Identifier: GPL-3.0-or-later */
package com.cpmap.rgi;
import de.vw.mib.bap.mqbab2.generated.navsd.serializer.*;
import java.lang.reflect.*;
import java.util.Vector;
public final class TestNormalLanes {
    static int checks;
    static void check(boolean ok,String why){checks++;if(!ok)throw new AssertionError(why);}
    static LaneData lane(int status,int highlight,int... angles){
        byte[] raw=TestLanes.lane(0,status,highlight,angles);
        return LaneData.decode(raw,0,raw.length);
    }
    public static void main(String[] args)throws Exception{
        check(LaneGuidance_LaneGuidance.LANE_TYPE_NORMAL_LANE==1 &&
            LaneGuidance_LaneGuidance.LANE_TYPE_UNSPECIFIC_LANE_TYPE==0,"exact factory constants");
        for(int status=0;status<=2;status++)for(int angle=-180;angle<=180;angle+=15){
            LaneData l=lane(status,1000,angle);
            check(l.getLaneType()==1&&l.getLaneDescription()==0,"supplied geometry classified normal/available");
            check(l.direction==LaneData.direction(angle)&&l.recommendation==status,"direction and actual recommendation preserved");
            check(l.sides.length()==0&&l.getMarkingLeft()==0&&l.getMarkingRight()==0,"no duplicate branches or invented borders");
        }
        LaneData l=lane(2,1000,1000,-1000);
        check(l.direction==255&&l.getLaneType()==0&&l.getLaneDescription()==15&&l.recommendation==0,"unknown lane remains unspecified/unlit");
        l=lane(2,1000,-90,0,90);
        check(l.getLaneType()==1&&l.recommendation==0&&l.sides.length()==2,"ambiguous directions stay neutral");
        TestLive.installMocks();TestLanes.Feed feed=new TestLanes.Feed();feed.state(1,7,true);
        feed.add(0x5204,TestLanes.instruction(7,TestLanes.lane(0,0,1000,-90),
            TestLanes.lane(1,2,0),TestLanes.lane(2,2,0)));
        LiveModel.Frame f=feed.read();TestLive.clock=f.changed;LiveBridge b=TestLive.bridge();
        b.incoming=f;b.journalAt=TestLive.clock;b.tick(TestLive.clock);
        LaneGuidance_ChangedArray out=TestLanes.factory();
        check(out.laneGuidanceOnOff==1&&out.getArrayData().size()==3,"captured three-lane layout");
        for(int i=0;i<3;i++){
            LaneGuidance_LaneGuidance e=(LaneGuidance_LaneGuidance)out.getArrayData().get(i);
            check(e.laneType==1&&e.laneDescription==0,"real factory array has normal lanes");
            check(e.laneDirection==(i==0?64:0)&&e.guidanceInfo==(i==0?0:2),"captured left/straight recommendations intact");
            for(int record=0;record<=1;record++){
                de.vw.mib.bap.datatypes.ArrayHeader h=new de.vw.mib.bap.datatypes.ArrayHeader();
                h.setRecordAddress(record);e.setArrayHeader(h);
                final Vector bytes=new Vector(),nibbles=new Vector();
                de.vw.mib.bap.stream.BitStream bits=(de.vw.mib.bap.stream.BitStream)Proxy.newProxyInstance(
                    TestNormalLanes.class.getClassLoader(),new Class[]{de.vw.mib.bap.stream.BitStream.class},
                    new InvocationHandler(){public Object invoke(Object proxy,Method method,Object[] values){
                        if(method.getName().equals("pushByte"))bytes.addElement(values[0]);
                        if(method.getName().equals("pushBits")&&((Integer)values[0]).intValue()==4)nibbles.addElement(values[1]);
                        return null;
                    }});
                e.serialize(bits);
                check(((Byte)bytes.lastElement()).intValue()==1,"actual full-format serializer emits normal type byte");
                check(((Integer)nibbles.lastElement()).intValue()==(i==0?0:2),"actual serialized guidance nibble unchanged");
            }
        }
        System.out.println("NORMAL_LANE_PASS checks="+checks+" captured_layout=1 factory_type=1 unknown_unspecified=1 real_recommendations=1");
    }
}
