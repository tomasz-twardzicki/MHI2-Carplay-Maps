/* SPDX-License-Identifier: GPL-3.0-or-later
 * Host-only v1.5.0-e Android Auto source tests on the guarded factory classes.
 * Connection type 3 is ASL's mapping of DSI CONNECTIONMETHOD_GAL (8) on K4525. */
package com.cpmap.rgi;
import de.vw.mib.bap.mqbab2.generated.navsd.serializer.*;

public final class TestAndroidAuto {
    static int checks;
    static void check(boolean ok,String m){checks++;if(!ok)throw new AssertionError(m);}
    static LiveModel.Frame frame(long at,int remaining,int seconds){
        return new LiveModel.Frame(true,13,64,150,remaining,seconds,5,at,1,LaneData.EMPTY,at,"Road",at,1);
    }
    public static void main(String[] a)throws Exception{
        TestLive.installMocks();
        // Directories and holds per connection; CarPlay and no phone stay on the CarPlay directory.
        check(LiveBridge.rootFor(3).equals("/ramdisk/pmcp-aa-rg"),"AA directory");
        check(LiveBridge.rootFor(2).equals(LiveBridge.ROOT) && LiveBridge.rootFor(0).equals(LiveBridge.ROOT)
            && LiveBridge.rootFor(-1).equals(LiveBridge.ROOT),"CarPlay and no phone read the CarPlay directory");
        check(LiveBridge.holdFor(LiveBridge.AA_ROOT)==10000 && LiveBridge.holdFor(LiveBridge.ROOT)==LiveModel.HOLD_MS,"hold per source");
        TestLive.connection=3;
        check(LiveBridge.factoryContext()==0 && LiveBridge.phone==3,"AA connection accepted as idle OEM context");
        check(LiveBridge.hold()==10000,"AA hold");
        // Frame of the previous source is never published after a switch.
        LiveBridge b=TestLive.bridge();b.root=LiveBridge.ROOT;
        b.incoming=frame(TestLive.clock,-1,-1);b.journalAt=TestLive.clock;
        TestLive.sent.clear();b.tick(TestLive.clock);
        check(!b.owned && b.current()==null && b.ownershipReason==10,"AA connection, CarPlay directory: nothing published");
        b.root=LiveBridge.AA_ROOT;TestLive.clock+=250;b.journalAt=TestLive.clock;
        b.incoming=frame(TestLive.clock,-1,-1);b.tick(TestLive.clock);
        check(b.owned,"AA frame published from the AA directory");
        ManeuverDescriptor_Status d=new ManeuverDescriptor_Status();
        check(LiveBridge.descriptor(d) && d.maneuver_1.mainElement==13 && d.maneuver_1.direction==64,"AA arrow");
        DistanceToNextManeuver_Status n=new DistanceToNextManeuver_Status();
        check(LiveBridge.distance(n) && n.validityInformation.distanceToNextManeuverValid
            && n.bargraphInfo.bargraphOnOff==1 && n.bargraphInfo.bargraph==75,"AA distance and bar");
        DistanceToDestination_Status total=new DistanceToDestination_Status();
        TimeToDestination_Status time=new TimeToDestination_Status();
        check(!LiveBridge.destinationDistance(total) && !LiveBridge.destinationValidity(total) && !LiveBridge.destinationTime(time),
            "AA without remaining distance/time keeps the factory path");
        // A switch back to CarPlay blocks the AA frame until the reader has switched.
        TestLive.connection=2;LiveBridge.factoryContext();
        check(b.current()==null,"CarPlay connection, AA directory: AA frame withheld");
        // CarPlay behaviour is unchanged, including invalid destination metrics.
        b=TestLive.bridge();b.root=LiveBridge.ROOT;TestLive.clock+=250;
        b.incoming=frame(TestLive.clock,-1,-1);b.journalAt=TestLive.clock;b.tick(TestLive.clock);
        check(b.owned && LiveBridge.destinationDistance(total) && !total.validityInformation.distanceToDestinationValid
            && LiveBridge.destinationTime(time) && !time.validityInformation.timeInfo_MinuteIsValid,"CarPlay destination unchanged");
        TestLive.connection=0;check(LiveBridge.factoryContext()==1,"no phone stays blocked");
        // Reader switch: new FeedRecovery, frame dropped, errors of the other source cleared.
        FeedRecovery cp=new FeedRecovery(LiveBridge.ROOT);cp.error=1;cp.fatal=true;cp.retryAt=99999;
        b.root=LiveBridge.ROOT;LiveBridge.phone=3;b.mode=2;b.journalAt=TestLive.clock;b.incoming=frame(TestLive.clock,-1,-1);
        FeedRecovery aa=b.switchRoot(cp);
        check(aa!=cp && aa.root.equals(LiveBridge.AA_ROOT) && aa.path.equals("/ramdisk/pmcp-aa-rg/latest.bin")
            && aa.error==0 && !aa.fatal && aa.retryAt<0 && b.incoming==null && b.mode==0 && b.journalAt==-1,"CarPlay to AA switch");
        check(b.switchRoot(aa)==aa,"same source keeps its feed");
        LiveBridge.phone=2;FeedRecovery back=b.switchRoot(aa);
        check(back!=aa && back.root.equals(LiveBridge.ROOT),"AA to CarPlay switch");
        int[] others={2,0,-1};
        for(int i=0;i<others.length;i++){
            LiveBridge.phone=others[i];FeedRecovery own=new FeedRecovery(LiveBridge.ROOT);b.root=LiveBridge.ROOT;
            for(int k=0;k<5;k++)check(b.switchRoot(own)==own,"connection "+others[i]+" never reads the AA directory");
        }
        // Quiet route: AA ends after 10 s, CarPlay keeps 180 s.
        int[] conns={3,2};long[] holds={10000,LiveModel.HOLD_MS};
        for(int i=0;i<conns.length;i++){
            TestLive.connection=conns[i];LiveBridge.factoryContext();TestLive.clock+=5000;
            long t0=TestLive.clock;LiveBridge q=TestLive.bridge();q.root=LiveBridge.rootFor(conns[i]);
            LiveModel.Frame g=frame(t0,1000,60);q.incoming=g;q.journalAt=t0;q.tick(t0);
            check(q.owned && TestArrow.output().bargraphInfo.bargraphOnOff==1,"connection "+conns[i]+": arrow and bar on");
            for(long t=t0+1000;t<t0+holds[i]-1;t+=1000){TestLive.clock=t;q.journalAt=t;q.tick(t);}
            long last=t0+holds[i]-1;TestLive.clock=last;q.journalAt=last;q.tick(last);
            check(q.owned && ArrowProgress.remaining(g,last)==75 && RoadName.current(g,last).equals("Road"),
                "connection "+conns[i]+": quiet route held until the hold ends");
            TestLive.clock=t0+holds[i];q.journalAt=TestLive.clock;q.tick(TestLive.clock);
            check(!q.owned && ArrowProgress.remaining(g,TestLive.clock)==-1 && RoadName.current(g,TestLive.clock).equals(""),
                "connection "+conns[i]+": arrow, bar and road end at the hold");
        }
        TestLive.connection=2;LiveBridge.factoryContext();
        System.out.println("{\"android_auto_assertions\":"+checks+"}");
    }
}
