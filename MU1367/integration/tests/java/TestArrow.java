/* Host regression through production model and exact patched factory stage.
 * SPDX-License-Identifier: GPL-3.0-or-later */
package com.cpmap.rgi;
import de.vw.mib.bap.mqbab2.generated.navsd.serializer.DistanceToNextManeuver_Status;

public final class TestArrow {
    static int checks;
    static void check(boolean yes,String why){checks++;if(!yes)throw new AssertionError(why);}
    static LiveModel.Frame frame(int kind,int main,int meters,long routeAt){
        return new LiveModel.Frame(true,main,192,meters,1000,60,10,TestLive.clock,1,LaneData.EMPTY,routeAt,"",-1,kind);
    }
    static DistanceToNextManeuver_Status output(){
        for(int i=TestLive.sent.size()-1;i>=0;i--)if(TestLive.sent.get(i) instanceof DistanceToNextManeuver_Status)return (DistanceToNextManeuver_Status)TestLive.sent.get(i);
        throw new AssertionError("factory distance property absent");
    }
    static void values(){
        for(int kind=0;kind<=54;kind++){
            int limit=kind==8 || kind==22 || kind==23?2000:200;
            for(int d=0;d<=limit+1;d++){
                LiveModel.Frame f=frame(kind,13,d,TestLive.clock);
                int value=ArrowProgress.remaining(f,TestLive.clock);
                check(value==(d>limit?-1:d*100/limit),"percent is remaining real meters within the correct window");
            }
        }
        for(int main=0;main<=40;main++){
            boolean allowed=main>=3&&main<=5 || main>=13&&main<=27 || main>=32&&main<=35;
            check((ArrowProgress.remaining(frame(1,main,100,TestLive.clock),TestLive.clock)>=0)==allowed,"factory maneuver whitelist");
        }
        check(ArrowProgress.remaining(frame(1,13,-1,TestLive.clock),TestLive.clock)==-1,"unknown distance hidden");
        check(ArrowProgress.remaining(frame(1,13,Integer.MAX_VALUE,TestLive.clock),TestLive.clock)==-1,"large distance cannot overflow percentage");
        check(ArrowProgress.remaining(frame(1,13,20,1000),999)==-1,"clock reversal hides");
        check(ArrowProgress.remaining(frame(1,13,20,1000),6000)==-1,"stale route hides");
        check(ArrowProgress.remaining(frame(1,13,20,-1),1000)==-1,"no accepted route timestamp hides");
    }
    static byte[] route(int... order){
        byte[] list=new byte[0];for(int i=0;i<order.length;i++)list=TestLanes.join(list,TestLanes.u16(order[i]));
        return TestLanes.join(TestLanes.tlv(0,TestLanes.u16(16)),TestLanes.join(TestLanes.tlv(1,new byte[]{1}),TestLanes.tlv(13,list)));
    }
    static byte[] maneuver(int index,int type){
        return TestLanes.join(TestLanes.instruction(index),TestLanes.join(TestLanes.tlv(3,new byte[]{(byte)type}),TestLanes.join(TestLanes.tlv(9,new byte[]{0}),TestLanes.tlv(11,TestLanes.u16(-45)))));
    }
    static void model()throws Exception{
        TestLanes.Feed feed=new TestLanes.Feed();feed.add(0x5201,route(10,20));feed.read();
        feed.add(0x5202,maneuver(10,22));feed.add(0x5202,maneuver(20,1));feed.read();
        feed.add(0x5201,TestLanes.join(route(10,20),TestLanes.tlv(10,new byte[]{0,0,3,(byte)232})));LiveModel.Frame f=feed.read();
        check(f.maneuverType==22&&ArrowProgress.remaining(f,f.changed)==50,"decoded off-ramp uses 2km window");
        feed.add(0x5201,route(20));f=feed.read();check(!f.validDistance&&ArrowProgress.remaining(f,f.changed)==-1,"new head cannot inherit old countdown");
        feed.add(0x5201,TestLanes.join(route(20),TestLanes.tlv(10,new byte[]{0,0,0,100})));f=feed.read();
        check(f.maneuverType==1&&ArrowProgress.remaining(f,f.changed)==50,"next ordinary turn has its own 200m window");
        for(int phase:new int[]{5,0,2}){feed.state(phase,65535,false);f=feed.model.frame();check(!f.validDistance||!f.active,"stop/reroute cannot animate old turn");}
    }
    static void factory()throws Exception{
        TestLive.installMocks();TestLive.clock=1000;LiveBridge b=TestLive.bridge();TestLive.sent.clear();
        int[] distances={250,200,150,100,50,0};
        for(int i=0;i<distances.length;i++){
            TestLive.clock+=250;b.incoming=frame(1,13,distances[i],TestLive.clock);b.journalAt=TestLive.clock;b.tick(TestLive.clock);
            DistanceToNextManeuver_Status out=output();int expected=distances[i]>200?-1:distances[i]/2;
            check(out.bargraphInfo.bargraphOnOff==(expected<0?0:1)&&out.bargraphInfo.bargraph==(expected<0?0:expected),"actual factory output countdown");
        }
        TestLive.unit=1;TestLive.clock+=250;b.incoming=frame(22,13,1000,TestLive.clock);b.journalAt=TestLive.clock;b.tick(TestLive.clock);
        check(output().bargraphInfo.bargraph==50,"imperial formatting does not change metric progress calculation");TestLive.unit=0;
        TestLive.accept=false;TestLive.clock+=250;b.incoming=frame(22,13,500,TestLive.clock);b.journalAt=TestLive.clock;b.tick(TestLive.clock);
        check((b.refreshPending&2)!=0,"factory queue rejection retains distance retry");
        TestLive.accept=true;TestLive.clock+=250;b.journalAt=TestLive.clock;b.tick(TestLive.clock);check((b.refreshPending&2)==0&&output().bargraphInfo.bargraph==25,"retry publishes latest countdown");
        TestLive.clock=5999;b=TestLive.bridge();b.incoming=frame(1,13,100,1000);b.journalAt=TestLive.clock;b.tick(TestLive.clock);check(output().bargraphInfo.bargraphOnOff==1,"fresh at route deadline minus one");
        int sent=TestLive.sent.size();TestLive.clock=6000;b.journalAt=TestLive.clock;b.tick(TestLive.clock);
        check(b.owned&&TestLive.sent.size()==sent+1&&output().bargraphInfo.bargraphOnOff==0,"timer clears stale bar without new producer progress");
        TestLive.route=1;DistanceToNextManeuver_Status untouched=new DistanceToNextManeuver_Status();untouched.bargraphInfo.bargraph=71;
        check(!LiveBridge.distance(untouched)&&untouched.bargraphInfo.bargraph==71,"OEM takeover declines helper without touching stock output");TestLive.route=0;
        b.mode=0;TestLive.clock++;b.journalAt=TestLive.clock;b.tick(TestLive.clock);check(output().bargraphInfo.bargraphOnOff==0,"guidance stop clears bar");
    }
    public static void main(String[] args)throws Exception{values();model();factory();System.out.println("ARROW_PROGRESS_PASS checks="+checks+" actual_factory_stage=1 real_distance=1 route_freshness=1 oem_priority=1");}
}
