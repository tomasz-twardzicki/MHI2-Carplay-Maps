/* Host and factory-J9 tests. Synthetic strings only in output/assertions.
 * SPDX-License-Identifier: GPL-3.0-or-later */
package com.cpmap.rgi;
import java.io.*;
import java.lang.reflect.Method;
import de.vw.mib.bap.mqbab2.generated.navsd.serializer.TurnToInfo_Status;
import de.vw.mib.bap.mqbab2.common.api.stages.Function;

public final class TestRoad {
    static int checks;
    static void check(boolean yes,String why){checks++;if(!yes)throw new RuntimeException(why);}
    static byte[] bytes(String s)throws Exception{return s.getBytes("UTF-8");}
    static String repeat(String s,int count){StringBuffer b=new StringBuffer();for(int i=0;i<count;i++)b.append(s);return b.toString();}
    static byte[] road(int state,String value)throws Exception{
        byte[] b=TestLanes.route(state,65535,false);
        return value==null?b:TestLanes.join(b,TestLanes.tlv(3,bytes(value)));
    }
    static LiveModel.Frame update(TestLanes.Feed feed,int state,String value)throws Exception{feed.add(0x5201,road(state,value));return feed.read();}
    static void text()throws Exception{
        check(RoadName.decode(bytes(" \tAleja \r\n Testowa \t\0")).equals("Aleja Testowa"),"single-line normalized road");
        check(RoadName.decode(bytes("Łódź Żółta")).equals("Łódź Żółta"),"UTF8 road preserved");
        check(RoadName.decode(bytes(" \r\n\t")).equals(""),"whitespace empty");
        check(RoadName.decode(bytes(repeat("A",256))).getBytes("UTF-8").length==75,"bounded ASCII");
        check(RoadName.decode(bytes(repeat("ł",128))).equals(repeat("ł",37)),"bounded multibyte");
        check(RoadName.decode(bytes(repeat("A",74)+"ł")).equals(repeat("A",74)),"never split UTF8");
        byte[] emoji={(byte)0xf0,(byte)0x9f,(byte)0x9a,(byte)0x97};
        String supplementary=RoadName.decode(emoji);check(supplementary.length()==2,"supplementary codepoint preserved");
        check(RoadName.decode(TestLanes.join(bytes(repeat("A",74)),emoji)).equals(repeat("A",74)),"never split supplementary UTF8");
        byte[][] invalid={new byte[]{(byte)0xc0,(byte)0x80},new byte[]{65,0,66},new byte[]{1},bytes(repeat("A",257))};
        for(int i=0;i<invalid.length;i++){boolean failed=false;try{RoadName.decode(invalid[i]);}catch(IOException expected){failed=true;}check(failed,"strict invalid text rejected");}
        TurnToInfo_Status out=new TurnToInfo_Status();out.turnToInfo.setContent(repeat("ł",37));check(out.turnToInfo.toString().equals(repeat("ł",37)),"factory BAP accepts bounded UTF8 without clipping");
    }
    static void model()throws Exception{
        TestLanes.Feed feed=new TestLanes.Feed();LiveModel.Frame f=update(feed,1,"Current Road");long at=f.roadAt;
        check(f.active&&f.currentRoad.equals("Current Road")&&at==f.changed,"fresh current road captured");
        check(RoadName.current(f,at+4999).equals("Current Road"),"road valid before deadline");
        check(RoadName.current(f,at+5000).equals(""),"road expires at deadline");
        check(RoadName.current(f,at-1).equals(""),"clock reversal clears");
        feed.now=at+4000;f=update(feed,1,null);check(f.roadAt==at&&RoadName.current(f,f.changed).equals("Current Road"),"absent delta retains within own lease");
        feed.now=at+5000;f=update(feed,1,null);check(f.active&&RoadName.current(f,f.changed).equals("Current Road")&&f.roadAt==at,"unchanged road survives fresh route deltas");
        f=update(feed,1,"Replacement Road");check(RoadName.current(f,f.changed).equals("Replacement Road"),"fresh field restores road");
        f=update(feed,1,"");check(f.currentRoad.equals("")&&RoadName.current(f,f.changed).equals(""),"explicit empty clears");
        byte[] maneuver=TestLanes.join(TestLanes.tlv(0,TestLanes.u16(16)),TestLanes.join(TestLanes.tlv(1,TestLanes.u16(1)),TestLanes.tlv(4,bytes("Upcoming Road"))));
        feed.add(0x5202,maneuver);f=feed.read();check(f.currentRoad.equals(""),"upcoming road is not current road");
        update(feed,1,"Before Reroute");f=update(feed,5,null);check(f.currentRoad.equals("")&&f.roadAt<0,"reroute clears");
        f=update(feed,1,null);check(f.currentRoad.equals(""),"reroute cannot resurrect");
        for(int phase=0;phase<=6;phase++)if(phase!=1&&phase!=6){update(feed,1,"Before phase");f=update(feed,phase,null);check(f.currentRoad.equals("")&&f.roadAt<0,"non-guiding phase clears");}
        update(feed,1,"Before session reset");feed.model.invalidate();check(feed.model.frame().currentRoad.equals(""),"session invalidation clears");
        feed=new TestLanes.Feed();feed.add(0x5201,TestLanes.join(road(1,"Old app road"),TestLanes.tlv(19,bytes("source-one"))));feed.read();
        feed.add(0x5201,TestLanes.join(road(1,null),TestLanes.tlv(19,bytes("source-two"))));f=feed.read();check(f.currentRoad.equals(""),"source switch clears");
        feed.add(0x5201,TestLanes.join(road(1,"Old destination road"),TestLanes.tlv(4,bytes("destination-one"))));feed.read();
        feed.add(0x5201,TestLanes.join(road(1,null),TestLanes.tlv(4,bytes("destination-two"))));f=feed.read();check(f.currentRoad.equals(""),"destination switch clears");
        // Cold retained content must never acquire a fresh road timestamp.
        TestLanes.Feed cold=new TestLanes.Feed();cold.add(0x5201,road(1,"Retained road"));cold.model.invalidate();cold.first=true;
        f=cold.read();check(f.currentRoad.equals("")&&f.roadAt<0,"bootstrap does not freshen retained text");
        feed=new TestLanes.Feed();
        byte[] active=TestLanes.join(TestLanes.tlv(0,TestLanes.u16(16)),TestLanes.tlv(1,new byte[]{1}));
        feed.add(0x5201,TestLanes.join(active,TestLanes.tlv(13,TestLanes.join(TestLanes.u16(10),TestLanes.u16(20)))));feed.read();
        feed.add(0x5202,TestLanes.join(TestLanes.tlv(0,TestLanes.u16(16)),TestLanes.join(TestLanes.tlv(1,TestLanes.u16(10)),TestLanes.tlv(4,bytes("Passed Road")))));feed.read();
        check(feed.model.frame().currentRoad.equals(""),"upcoming street still withheld");
        feed.add(0x5201,TestLanes.join(active,TestLanes.tlv(13,TestLanes.u16(20))));f=feed.read();
        check(f.currentRoad.equals("Passed Road"),"proven passed maneuver supplies absent current road");
        f=update(feed,5,null);check(f.currentRoad.equals(""),"reroute clears passed-road fallback");
    }
    static TurnToInfo_Status factory()throws Exception{
        Function stage=LiveBridge.INSTANCE.stages[6];
        Method m=stage.getClass().getDeclaredMethod("computeTurnToInfoStatus",new Class[0]);m.setAccessible(true);
        return (TurnToInfo_Status)m.invoke(stage,new Object[0]);
    }
    static void integration()throws Exception{
        TestLive.installMocks();TestLive.sent.clear();TestLanes.Feed feed=new TestLanes.Feed();LiveModel.Frame f=update(feed,1,"Factory Road");
        TestLive.clock=f.changed;LiveBridge b=TestLive.bridge();b.incoming=f;b.journalAt=TestLive.clock;b.tick(TestLive.clock);
        check(b.owned&&factory().turnToInfo.toString().equals("Factory Road"),"actual patched factory stage publishes road");
        check(TestLive.sent.get(TestLive.sent.size()-1) instanceof TurnToInfo_Status,"factory property uses existing output queue");
        int sent=TestLive.sent.size();TestLive.clock+=250;b.journalAt=TestLive.clock;b.tick(TestLive.clock);
        check(TestLive.sent.size()==sent,"unchanged name does not add timer traffic");
        // Maneuver-only activity cannot renew stale current-position context.
        long oldRoute=f.laneAt;TestLive.clock=oldRoute+5000;
        f=new LiveModel.Frame(true,13,192,30,1000,60,f.progress+1,TestLive.clock,f.epoch,LaneData.EMPTY,oldRoute,f.currentRoad,f.roadAt);
        b.lastTick=TestLive.clock;b.incoming=f;b.journalAt=TestLive.clock;b.tick(TestLive.clock);
        check(b.owned&&factory().turnToInfo.toString().equals(""),"road expires independently of active guidance");
        feed.now=TestLive.clock+1;f=update(feed,1,"New Road");TestLive.clock=f.changed;b.incoming=f;b.journalAt=TestLive.clock;b.tick(TestLive.clock);
        check(factory().turnToInfo.toString().equals("New Road"),"live name update");
        TestLive.accept=false;TestLive.clock+=250;b.refreshPending|=64;b.tick(TestLive.clock);check((b.refreshPending&64)!=0,"road queue rejection retries");
        TestLive.accept=true;TestLive.clock+=250;b.journalAt=TestLive.clock;b.tick(TestLive.clock);check((b.refreshPending&64)==0,"road retry accepted");
        TestLive.route=1;TestLive.clock+=250;b.tick(TestLive.clock);check(!b.owned&&factory().turnToInfo.toString().equals(TestLive.stockRoad),"OEM road wins on takeover");TestLive.route=0;
        b=TestLive.bridge();TestLive.clock=f.changed;b.lastTick=TestLive.clock;b.incoming=f;b.journalAt=TestLive.clock;b.tick(TestLive.clock);
        b.mode=0;TestLive.clock+=250;b.journalAt=TestLive.clock;b.tick(TestLive.clock);check(b.clearing&&factory().turnToInfo.toString().equals(""),"stop clears phone road");
        TestLive.clock+=250;b.tick(TestLive.clock);check(!b.clearing&&factory().turnToInfo.toString().equals(TestLive.stockRoad),"after clear the factory road output resumes");
        b=TestLive.bridge();b.stages[6]=null;b.tick(TestLive.clock);check(b.owned,"missing optional road stage leaves core guidance working");
        b.mode=0;TestLive.clock+=250;b.journalAt=TestLive.clock;b.tick(TestLive.clock);TestLive.clock+=250;b.tick(TestLive.clock);check(!b.clearing,"missing optional road stage does not block handback");
    }
    static void captures(String[] args)throws Exception{
        for(int i=0;i<args.length;i++){
            byte[] all=TestRecovery.read(new File(args[i]));if(all.length<32||LiveModel.u32(all,16)!=1)continue;
            int count=(int)LiveModel.u32(all,56),p=96,nonempty=0;
            for(int j=0;j<count;j++){
                int id=LiveModel.u16(all,p+4),n=LiveModel.u16(all,p+6);
                LiveModel.Message m=LiveModel.decode(id,all,p+16,n);if(id==0x5201&&m.has[3]&&RoadName.decode(m.raw[3]).length()>0)nonempty++;p+=16+n;
            }
            check(p==all.length,"capture envelope consumed");System.out.println("ROAD_PRIVATE_CAPTURE records="+count+" nonempty_current_roads="+nonempty);
        }
    }
    public static void main(String[] args)throws Exception{text();model();integration();captures(args);System.out.println("ROAD_NAME_PASS checks="+checks+" actual_factory_stage=1 own_freshness=1 oem_priority=1 bounded_utf8=1");}
}
