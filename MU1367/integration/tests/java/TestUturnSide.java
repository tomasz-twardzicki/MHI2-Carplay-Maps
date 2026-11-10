/* Host-only checks. SPDX-License-Identifier: GPL-3.0-or-later */
package com.cpmap.rgi;
import de.vw.mib.bap.mqbab2.generated.navsd.serializer.*;

/** A lane at exactly ±180° has no side: left-hand traffic turns it into the right U-turn. */
public final class TestUturnSide {
    static int checks;
    static final int LEFT=114, RIGHT=146, RHT=0, LHT=1;
    static void check(boolean ok,String why){checks++;if(!ok)throw new AssertionError(why);}
    /** A maneuver record carrying only the driving side. */
    static byte[] maneuver(int index,int type,int side,Integer angle){
        byte[] m=TestLanes.join(TestLanes.join(TestLanes.tlv(0,TestLanes.u16(16)),TestLanes.tlv(1,TestLanes.u16(index))),
            TestLanes.join(TestLanes.tlv(3,new byte[]{(byte)type}),TestLanes.tlv(9,new byte[]{0})));
        if(side>=0)m=TestLanes.join(m,TestLanes.tlv(8,new byte[]{(byte)side}));
        if(angle!=null)m=TestLanes.join(m,TestLanes.tlv(11,TestLanes.u16(angle.intValue())));
        return m;
    }
    static LiveModel.Frame lanes(int side,byte[]... lanes)throws Exception{
        TestLanes.Feed f=new TestLanes.Feed();f.state(1,7,true);
        if(side>=0)f.add(0x5202,maneuver(7,3,side,null));
        f.add(0x5204,TestLanes.instruction(7,lanes));return f.read();
    }
    static int main(int side,int highlight,int... angles)throws Exception{
        LiveModel.Frame f=lanes(side,TestLanes.lane(0,2,highlight,angles));
        check(f.lanes.length==1,"one lane");return f.lanes[0].direction;
    }
    static String sides(int side,int... angles)throws Exception{
        LiveModel.Frame f=lanes(side,TestLanes.lane(0,2,0,angles));check(f.lanes.length==1,"one lane");return f.lanes[0].sides;
    }
    public static void main(String[] args)throws Exception{
        TestLive.installMocks();
        // Main lane direction, by driving side.
        check(main(LHT,180,180)==RIGHT,"UK: 180 is the right U-turn");
        check(main(LHT,-180,-180)==RIGHT,"UK: -180 has no side either");
        check(main(LHT,65535,180)==RIGHT,"UK: unhighlighted single 180 lane");
        check(main(RHT,180,180)==LEFT,"right-hand traffic keeps the left U-turn");
        check(main(-1,180,180)==LEFT,"unknown side keeps the v1.4.2 behaviour");
        // A real sign always wins.
        check(main(LHT,-175,-175)==LEFT,"UK: a signed left U-turn stays left");
        check(main(RHT,175,175)==RIGHT,"right-hand traffic: a signed right U-turn stays right");
        check(main(LHT,180,180,-175)==LEFT,"a signed angle on the same byte settles the side");
        check(main(LHT,90,90)==192,"UK: ordinary turns are untouched");
        check(main(LHT,-90,-90)==64,"UK: ordinary left turn");
        // Side branches.
        check(sides(LHT,0,180).equals(String.valueOf((char)RIGHT)),"UK: side U-turn branch");
        check(sides(RHT,0,180).equals(String.valueOf((char)LEFT)),"right-hand side U-turn branch");
        check(sides(LHT,0,180,-175).equals(String.valueOf((char)LEFT)),"signed branch settles");
        check(sides(LHT,0,180,170).equals(String.valueOf((char)RIGHT)),"no duplicate after the swap");
        // The side may arrive after the lanes, and the current maneuver's own side wins.
        TestLanes.Feed f=new TestLanes.Feed();f.state(1,7,true);
        f.add(0x5204,TestLanes.instruction(7,TestLanes.lane(0,2,180,180)));
        check(f.read().lanes[0].direction==LEFT,"before any side: left");
        f.add(0x5202,maneuver(7,3,LHT,null));check(f.read().lanes[0].direction==RIGHT,"a later maneuver fixes the lanes already shown");
        // Through the factory lane builder and serializer.
        LiveModel.Frame frame=lanes(LHT,TestLanes.lane(0,2,180,180));TestLive.clock=frame.changed;
        LiveBridge bridge=TestLive.bridge();bridge.incoming=frame;bridge.journalAt=TestLive.clock;bridge.tick(TestLive.clock);
        LaneGuidance_ChangedArray out=TestLanes.factory();
        check(out.laneGuidanceOnOff==1&&out.getArrayData().size()==1,"factory lane");
        check(((LaneGuidance_LaneGuidance)out.getArrayData().get(0)).laneDirection==RIGHT,"factory receives the right U-turn");
        // Main arrow: a sideless 180 follows the driving side, a signed angle keeps its own.
        check(arrow(LHT,180)==192&&arrow(LHT,-180)==192,"UK main U-turn arrow");
        check(arrow(RHT,180)==64&&arrow(RHT,-180)==64,"right-hand main U-turn arrow");
        check(arrow(-1,180)==192&&arrow(-1,-180)==64,"unknown side keeps the sign");
        check(arrow(LHT,-170)==64&&arrow(RHT,170)==192,"signed U-turns unchanged");
        System.out.println("UTURN_SIDE_PASS checks="+checks+" left_hand_right_uturn=1 right_hand_unchanged=1 signed_unchanged=1 factory=1");
    }
    static int arrow(int side,int angle)throws Exception{
        LiveModel.Message m=LiveModel.decode(0x5202,maneuver(1,4,side,Integer.valueOf(angle)),0,maneuver(1,4,side,Integer.valueOf(angle)).length);
        int[] s=LiveModel.map(m);check(s[0]==25,"U-turn symbol");return s[1];
    }
}
