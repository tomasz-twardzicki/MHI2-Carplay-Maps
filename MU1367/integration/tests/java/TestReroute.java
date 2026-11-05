/* Host-only checks. SPDX-License-Identifier: GPL-3.0-or-later */
package com.cpmap.rgi;
import de.vw.mib.bap.mqbab2.generated.navsd.serializer.*;

/** The reroute shape from captured journals: 1,5,0,3,1 then a start maneuver at 0 m. */
public final class TestReroute {
    static int checks;
    static void check(boolean ok,String why){checks++;if(!ok)throw new AssertionError(why);}
    static byte[] state(int phase){return TestQuietQnx.join(TestQuietQnx.tlv(0,TestQuietQnx.u16(16)),TestQuietQnx.tlv(1,new byte[]{(byte)phase}));}
    static byte[] full(int phase,int index,int meters,int left,int seconds){
        byte[] m=TestQuietQnx.route(phase,index,meters);
        m=TestQuietQnx.join(m,TestQuietQnx.tlv(7,new byte[]{0,0,(byte)(left>>8),(byte)left}));
        return TestQuietQnx.join(m,TestQuietQnx.tlv(6,new byte[]{0,0,0,0,0,0,(byte)(seconds>>8),(byte)seconds}));
    }
    static LiveModel model;static long now;
    static LiveModel.Frame send(int id,byte[] payload,long gap)throws Exception{
        now+=gap;TestQuietQnx.add(id,payload);return model.snapshot(TestQuietQnx.window(),now,false);
    }
    static LiveModel.Frame guide(int index,int type,int meters)throws Exception{
        send(0x5201,full(1,index,meters,5000,600),100);
        send(0x5202,TestQuietQnx.maneuver(index,type),10);
        return send(0x5201,full(1,index,meters,5000,600),10);
    }
    static LiveModel.Frame reroute()throws Exception{
        LiveModel.Frame f=send(0x5201,state(5),1000);
        check(f.active&&f.main==9&&f.direction==0,"state 5 shows CALC_ROUTE");
        check(f.meters==300&&f.remainingMeters==5000&&f.remainingSeconds==600,"state 5 keeps every counter");
        check(f.lanes.length==0,"old lanes do not survive");
        f=send(0x5201,state(0),300);
        check(f.active&&f.main==9&&f.meters==300&&f.remainingMeters==5000,"stop inside a reroute is provisional");
        f=send(0x5201,state(0),5);check(f.active&&f.main==9,"repeated stop");
        f=send(0x5201,state(3),5);check(f.active&&f.main==9&&f.meters==300,"loading continues the episode");
        f=send(0x5202,TestQuietQnx.maneuver(0,11),5);check(f.active&&f.main==9&&f.meters==300,"new start maneuver");
        f=send(0x5202,TestQuietQnx.maneuver(1,2),5);check(f.active&&f.main==9,"new lookahead");
        return f;
    }
    public static void main(String[] args)throws Exception{
        LiveModel.Frame f;
        // Whole captured sequence.
        model=new LiveModel();now=1000;TestQuietQnx.sequence=0;TestQuietQnx.events=new byte[16][];
        f=guide(1,2,300);check(f.active&&f.main==13&&f.direction==192&&f.meters==300,"guiding");
        long floor=f.progress,epoch=f.epoch;
        f=reroute();
        check(f.epoch==epoch&&f.progress>floor,"no invalidation; progress stays above the ownership floor");
        f=send(0x5201,full(1,0,0,5100,620),5);
        check(f.active&&f.main==9&&f.meters==300,"start maneuver at 0 m does not restart the counter");
        check(f.remainingMeters==5100&&f.remainingSeconds==620,"new route totals are taken at once");
        f=send(0x5201,full(1,1,0,5100,620),15000);
        check(f.main==9&&f.meters==300,"0 m on the next head is still not a real distance");
        f=send(0x5201,full(1,1,280,5100,620),100);
        check(f.active&&f.main==13&&f.direction==192&&f.meters==280,"the first real distance resumes guidance");
        f=send(0x5201,full(1,1,0,5100,620),100);
        check(f.main==13&&f.meters==0,"0 m is honoured again after recovery");
        // A real cancel inside a reroute still clears, on the next message.
        model=new LiveModel();now=1000;TestQuietQnx.sequence=0;TestQuietQnx.events=new byte[16][];
        guide(1,2,300);send(0x5201,state(5),1000);send(0x5201,state(0),300);
        f=send(0x5201,state(0),LiveModel.STOP_GRACE_MS);
        check(!f.active&&f.main==0&&f.meters==-1&&f.remainingMeters==-1,"grace ends in a full stop");
        // ...or when the phone goes quiet.
        model=new LiveModel();now=1000;TestQuietQnx.sequence=0;TestQuietQnx.events=new byte[16][];
        guide(1,2,300);send(0x5201,state(5),1000);send(0x5201,state(0),300);
        model.quiet();f=model.frame();check(!f.active&&f.meters==-1,"quiet ends a provisional stop");
        // A plain stop while guiding stays immediate.
        model=new LiveModel();now=1000;TestQuietQnx.sequence=0;TestQuietQnx.events=new byte[16][];
        guide(1,2,300);f=send(0x5201,state(0),100);
        check(!f.active&&f.meters==-1&&f.remainingMeters==-1,"explicit end clears at once");
        // A new destination is a new route, not a reroute.
        model=new LiveModel();now=1000;TestQuietQnx.sequence=0;TestQuietQnx.events=new byte[16][];
        send(0x5201,TestQuietQnx.join(full(1,1,300,5000,600),TestQuietQnx.tlv(4,"Home".getBytes("UTF-8"))),100);
        send(0x5202,TestQuietQnx.maneuver(1,2),10);
        f=send(0x5201,TestQuietQnx.join(state(5),TestQuietQnx.tlv(4,"Work".getBytes("UTF-8"))),100);
        check(!f.active&&f.meters==-1,"destination change clears");
        // Loading before any guidance is not a recalculation.
        model=new LiveModel();now=1000;TestQuietQnx.sequence=0;TestQuietQnx.events=new byte[16][];
        send(0x5201,state(0),100);f=send(0x5201,state(3),100);
        check(!f.active,"route start stays inactive");
        // Waiting ends by time...
        model=new LiveModel();now=1000;TestQuietQnx.sequence=0;TestQuietQnx.events=new byte[16][];
        guide(1,2,300);reroute();send(0x5201,full(1,0,0,5100,620),5);
        f=send(0x5201,full(1,0,0,5100,620),LiveModel.RECOVER_MS);
        check(f.main==0&&f.meters==300,"after the bound the phone's own maneuver shows (no angle: placeholder)");
        f=send(0x5201,full(1,0,0,5100,620),100);check(f.meters==0,"and its distance");
        // ...or when a sparse phone goes quiet.
        model=new LiveModel();now=1000;TestQuietQnx.sequence=0;TestQuietQnx.events=new byte[16][];
        guide(1,2,300);reroute();send(0x5201,full(1,0,0,5100,620),5);
        model.quiet();f=model.frame();check(f.active&&f.main==0,"quiet ends the wait");
        // The bridge never releases output, and the bar holds its value.
        TestLive.installMocks();TestLive.route=0;TestLive.connection=2;TestLive.status=0;TestLive.clock=1000;
        LiveBridge b=TestLive.bridge();
        model=new LiveModel();now=1000;TestQuietQnx.sequence=0;TestQuietQnx.events=new byte[16][];
        f=guide(1,2,100);
        LiveModel.Frame[] seq={f,send(0x5201,state(5),300),send(0x5201,state(0),300),send(0x5201,state(3),5),send(0x5202,TestQuietQnx.maneuver(0,11),5),send(0x5201,full(1,0,0,5100,620),5),send(0x5202,TestQuietQnx.maneuver(1,2),5),send(0x5201,full(1,1,90,5100,620),300)};
        long releases=b.releases;int[] bars={50,50,50,50,50,50,50,45};
        for(int i=0;i<seq.length;i++){
            TestLive.clock=seq[i].changed;b.incoming=seq[i];b.journalAt=TestLive.clock;b.lastTick=TestLive.clock-100;b.floor=0;b.mode=2;b.tick(TestLive.clock);
            check(b.owned&&b.selected==seq[i],"guidance stays owned");
            ManeuverDescriptor_Status d=new ManeuverDescriptor_Status();DistanceToNextManeuver_Status n=new DistanceToNextManeuver_Status();
            check(LiveBridge.descriptor(d)&&LiveBridge.distance(n),"output is produced");
            check(d.maneuver_1.mainElement==(i==0||i==7?13:9),"maneuver or CALC_ROUTE");
            check(n.validityInformation.distanceToNextManeuverValid&&n.bargraphInfo.bargraphOnOff==1&&n.bargraphInfo.bargraph==bars[i],"distance and bar carry on");
        }
        check(b.releases==releases,"a reroute releases nothing");
        System.out.println("REROUTE_PASS checks="+checks+" sequence=1,5,0,3,1 counters_held=1 real_stop_clears=1 new_destination_clears=1");
    }
}
