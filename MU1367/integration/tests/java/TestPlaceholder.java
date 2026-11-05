/* Host-only actual-output checks. SPDX-License-Identifier: GPL-3.0-or-later */
package com.cpmap.rgi;
import de.vw.mib.bap.mqbab2.generated.navsd.serializer.*;

public final class TestPlaceholder {
    static int checks;
    static void check(boolean ok,String why){checks++;if(!ok)throw new AssertionError(why);}
    public static void main(String[] args)throws Exception{
        TestLive.installMocks();TestLive.route=0;TestLive.connection=2;TestLive.clock=1000;
        LiveBridge b=TestLive.bridge();ManeuverDescriptor_Status out=new ManeuverDescriptor_Status();
        check(!LiveBridge.descriptor(out),"startup without owned frame retains OEM output");
        TestLanes.Feed feed=new TestLanes.Feed();feed.state(1,65535,false);
        LiveModel.Frame f=feed.read();TestLive.clock=f.changed;
        b.incoming=f;b.journalAt=TestLive.clock;b.lastTick=TestLive.clock;b.tick(TestLive.clock);
        check(b.owned&&f.main==0,"real active route without a maneuver can acquire guidance");
        check(LiveBridge.descriptor(out)&&out.maneuver_1.mainElement==2&&out.maneuver_1.direction==0,"straight DIRECTION_TO_DESTINATION placeholder for missing pictogram");
        DistanceToNextManeuver_Status distance=new DistanceToNextManeuver_Status();
        b.selected=new LiveModel.Frame(true,0,0,50,1000,60,1,TestLive.clock,1,LaneData.EMPTY,TestLive.clock);
        check(LiveBridge.distance(distance)&&!distance.validityInformation.distanceToNextManeuverValid&&distance.bargraphInfo.bargraphOnOff==0,"placeholder has no fabricated distance or countdown");
        int[] elements={3,11,12,13,21,22,25,27};
        for(int i=0;i<elements.length;i++){
            b.selected=new LiveModel.Frame(true,elements[i],192,50,1000,60,1,TestLive.clock,1);
            check(LiveBridge.descriptor(out)&&out.maneuver_1.mainElement==elements[i]&&out.maneuver_1.direction==192,"real symbols including destination unchanged");
        }
        b.selected=new LiveModel.Frame(false,0,0,-1,0,0,0);
        check(LiveBridge.descriptor(out)&&out.maneuver_1.mainElement==0,"cancellation clear stays blank");
        b.selected=f;TestLive.route=1;out.maneuver_1.mainElement=11;
        check(!LiveBridge.descriptor(out)&&out.maneuver_1.mainElement==11,"OEM navigation wins between timer ticks");
        TestLive.route=0;b.selected=f;TestLive.clock=f.changed+LiveModel.HOLD_MS;b.lastTick=TestLive.clock;b.journalAt=TestLive.clock;
        check(!LiveBridge.descriptor(out),"stale route never gains placeholder");
        b.selected=f;TestLive.clock=f.changed;b.lastTick=TestLive.clock;b.journalAt=TestLive.clock;TestLive.connection=0;
        check(!LiveBridge.descriptor(out),"disconnect never gains placeholder");
        System.out.println("PLACEHOLDER_PASS checks="+checks+" active_only=1 real_symbols=1 no_fake_distance=1 oem_stale_disconnect=1");
    }
}
