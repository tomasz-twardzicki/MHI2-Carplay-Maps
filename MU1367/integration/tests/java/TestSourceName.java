/* Host-only checks. SPDX-License-Identifier: GPL-3.0-or-later */
package com.cpmap.rgi;

/** Apple Maps alternates "Apple Maps" and a localized name such as "Mapy Apple" within one route. */
public final class TestSourceName {
    static int checks;
    static void check(boolean ok,String why){checks++;if(!ok)throw new AssertionError(why);}
    static LiveModel model;static long now;
    static void fresh(){model=new LiveModel();now=1000;TestQuietQnx.sequence=0;TestQuietQnx.events=new byte[16][];}
    static LiveModel.Frame send(int id,byte[] payload)throws Exception{
        now+=100;TestQuietQnx.add(id,payload);return model.snapshot(TestQuietQnx.window(),now,false);
    }
    static byte[] name(String source)throws Exception{return TestQuietQnx.tlv(19,(source+"\0").getBytes("UTF-8"));}
    static byte[] order(int[] indexes){
        byte[] list=new byte[indexes.length*2];
        for(int i=0;i<indexes.length;i++)list[i*2+1]=(byte)indexes[i];
        return TestQuietQnx.tlv(13,list);
    }
    static byte[] route(int[] indexes,int meters){
        return TestQuietQnx.join(TestQuietQnx.join(TestQuietQnx.tlv(0,TestQuietQnx.u16(16)),TestQuietQnx.tlv(1,new byte[]{1})),
            TestQuietQnx.join(order(indexes),TestQuietQnx.tlv(10,new byte[]{0,0,(byte)(meters>>8),(byte)meters})));
    }
    /** Delta carrying only a state, a distance and the name, as a sparse phone update does. */
    static byte[] delta(String source,int phase,int meters)throws Exception{
        return TestQuietQnx.join(TestQuietQnx.join(TestQuietQnx.tlv(0,TestQuietQnx.u16(16)),TestQuietQnx.tlv(1,new byte[]{(byte)phase})),
            TestQuietQnx.join(TestQuietQnx.tlv(10,new byte[]{0,0,(byte)(meters>>8),(byte)meters}),name(source)));
    }
    /** Every maneuver record is sent once up front; the phone does not repeat it later. */
    static void start(String source)throws Exception{
        send(0x5201,TestQuietQnx.join(route(new int[]{1,2,3},300),name(source)));
        send(0x5202,TestQuietQnx.maneuver(1,2));
        send(0x5202,TestQuietQnx.maneuver(2,1));
        send(0x5202,TestQuietQnx.maneuver(3,3));
        send(0x5201,route(new int[]{1,2,3},300));
    }
    static void alias(String first,String second)throws Exception{
        fresh();start(first);
        LiveModel.Frame f=send(0x5201,delta(second,1,280));
        check(f.active&&f.main==13&&f.direction==192&&f.meters==280,first+" -> "+second+" keeps the current arrow and distance");
        f=send(0x5201,route(new int[]{2,3},500));
        check(f.main==13&&f.direction==64&&f.meters==500,first+" -> "+second+" keeps the maneuvers already sent");
        f=send(0x5201,delta(first,1,450));
        check(f.main==13&&f.direction==64&&f.meters==450,"flipping back keeps them too");
        f=send(0x5201,route(new int[]{3},200));
        check(f.main==13&&f.direction==0&&f.meters==200,"the last maneuver is still known");
    }
    static void different(String first,String second)throws Exception{
        fresh();start(first);
        LiveModel.Frame f=send(0x5201,delta(second,1,280));
        check(f.main==0&&f.meters==-1,first+" -> "+second+" is another app and clears its maneuvers");
    }
    public static void main(String[] args)throws Exception{
        alias("Apple Maps","Mapy Apple");
        alias("Mapy Apple","Apple Maps");
        alias("Apple Maps","Apple Karten");
        alias("Apple Maps","Apple マップ");
        alias("apple maps","Plans APPLE");

        different("Apple Maps","Google Maps");
        different("Google Maps","Mapy Apple");
        different("Mapy Apple","Waze");
        different("Google Maps","Waze");
        different("Google Maps","Mapy Google");
        different("Pineapple Nav","Apple Maps");

        // Same app, new destination: still a new route.
        fresh();
        send(0x5201,TestQuietQnx.join(TestQuietQnx.join(route(new int[]{1},300),name("Apple Maps")),TestQuietQnx.tlv(4,"Home".getBytes("UTF-8"))));
        send(0x5202,TestQuietQnx.maneuver(1,2));
        LiveModel.Frame f=send(0x5201,route(new int[]{1},300));check(f.main==13,"guiding");
        f=send(0x5201,TestQuietQnx.join(delta("Mapy Apple",1,280),TestQuietQnx.tlv(4,"Work".getBytes("UTF-8"))));
        check(f.main==0&&f.meters==-1,"a new destination clears whatever the name says");

        // Same app, real end of route: still ends.
        fresh();start("Apple Maps");
        f=send(0x5201,delta("Mapy Apple",0,0));
        check(!f.active,"a stop under the other name still stops");

        // A flip inside a reroute must not end the episode.
        fresh();start("Apple Maps");
        f=send(0x5201,delta("Mapy Apple",5,0));
        check(f.active&&f.main==LiveModel.MAIN_RECALCULATING&&f.meters==300,"a reroute under the other name keeps its counters");

        check(LiveModel.sameSource("Mapy Apple".getBytes("UTF-8"),"Apple Maps".getBytes("UTF-8")),"both Apple Maps names");
        check(!LiveModel.sameSource("Mapy Apple".getBytes("UTF-8"),"Waze".getBytes("UTF-8")),"another app");
        check(LiveModel.sameSource("Waze".getBytes("UTF-8"),"Waze".getBytes("UTF-8")),"identical name");
        check(!LiveModel.sameSource(null,"Waze".getBytes("UTF-8")),"no name is not a match");

        // Diagnostics still record both names, and count only the real clears.
        fresh();long source=GuidanceEvidence.sourceClears,destination=GuidanceEvidence.destinationClears;
        start("Apple Maps");send(0x5201,delta("Mapy Apple",1,280));
        check(GuidanceEvidence.sourceClears==source,"an alias flip is not a clear");
        send(0x5201,delta("Waze",1,280));
        check(GuidanceEvidence.sourceClears==source+1,"another app is");
        send(0x5201,TestQuietQnx.tlv(0,TestQuietQnx.u16(16)));
        check(GuidanceEvidence.destinationClears==destination,"no destination change");
        String text=GuidanceEvidence.snapshot();
        check(text.indexOf("Mapy_Apple")>=0&&text.indexOf("Apple_Maps")>=0,"both names stay visible");
        check(text.indexOf("route_clears source=")>=0,"clear causes are reported");
        // The flip log says when a flip happened and what came with it, within its bound.
        long flipsBefore=GuidanceEvidence.flipCount;
        fresh();now=50000;start("Apple Maps");now=70000;send(0x5201,TestQuietQnx.join(delta("Mapy Apple",1,280),order(new int[]{2,3})));
        check(GuidanceEvidence.flipCount==flipsBefore+1,"one flip logged");
        check(GuidanceEvidence.snapshot().indexOf(":1:1:10110")>=0,"state and contents are logged: "+GuidanceEvidence.snapshot());
        send(0x5201,delta("Apple Maps",1,270));
        check(GuidanceEvidence.flipCount==flipsBefore+2,"same name again is not a flip, the other way is");
        for(int i=0;i<500;i++)send(0x5201,delta(i%2==0?"Mapy Apple":"Apple Maps",1,260));
        byte[] body=GuidanceEvidence.snapshot().getBytes("US-ASCII");
        check(body.length<=4096,"evidence stays inside its bound");
        String logged=GuidanceEvidence.snapshot();logged=logged.substring(logged.indexOf("source_flips"));logged=logged.substring(0,logged.indexOf('\n'));
        int separators=0;for(int i=0;i<logged.length();i++)if(logged.charAt(i)==';')separators++;
        check(separators==GuidanceEvidence.FLIPS-1,"first and latest flips only: "+logged);
        System.out.println("SOURCE_NAME_PASS checks="+checks+" apple_aliases_keep_route=1 other_apps_clear=1 destination_clears=1 stop_stops=1 reroute_kept=1");
    }
}
