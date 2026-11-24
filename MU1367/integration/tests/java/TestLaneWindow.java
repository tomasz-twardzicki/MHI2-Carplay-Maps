/* Host regression: actual production model and full-window handoff. GPL-3.0-or-later. */
package com.cpmap.rgi;
public final class TestLaneWindow {
    static int checks;
    static void check(boolean ok,String why){checks++;if(!ok)throw new AssertionError(why);}
    static void add(TestLanes.Feed feed,int index,int direction)throws Exception{
        feed.add(0x5204,TestLanes.instruction(index,TestLanes.lane(0,0,65535,direction)));feed.read();
    }
    public static void main(String[] args)throws Exception{
        TestLanes.Feed feed=new TestLanes.Feed();feed.state(1,100,true);
        for(int i=100;i<106;i++)add(feed,i,-90);
        for(int i=200;i<206;i++){
            add(feed,i,0);
            check(feed.model.frame().lanes.length==1&&feed.model.frame().lanes[0].direction==64,"prefetch never selects a future lane event");
        }
        LiveModel.Frame f=feed.state(1,200,true);
        if(args.length>0&&args[0].equals("old")){
            check(f.active&&f.lanes.length==0,"old build reproduces lost first event");
            System.out.println("LANE_WINDOW_OLD_DEFECT_REPRODUCED active=1 lanes=0");return;
        }
        check(f.active&&f.lanes.length==1&&f.lanes[0].direction==0,"first event survives complete window before route selector");
        for(int i=200;i<206;i++)check(feed.state(1,i,true).lanes.length==1,"all six prefetched events remain selectable without a resend");
        feed.state(1,200,true);
        for(int i=300;i<340;i++)add(feed,i,90);
        check(feed.model.frame().lanes.length==1&&feed.model.frame().lanes[0].direction==0,"overflow preserves selected event");
        check(feed.state(1,339,true).lanes[0].direction==192,"latest future event retained");
        check(feed.state(1,999,true).lanes.length==0,"unknown selector does not borrow a neighboring event");
        feed.state(1,339,true);feed.add(0x5204,TestLanes.instruction(339));check(feed.read().lanes.length==0,"explicit empty event remains empty");
        check(feed.state(0,65535,false).lanes.length==0,"cancel clears");
        check(feed.state(1,200,true).lanes.length==0,"cancelled events cannot revive");
        LaneData.Cache cache=new LaneData.Cache();LaneData[] lanes={new LaneData(0,0,0,"")};
        cache.put(1,lanes);cache.selected=1;cache.showing=true;
        for(int i=2;i<100;i++)cache.put(i,lanes);
        int stored=0;for(int i=0;i<cache.values.length;i++)if(cache.values[i]!=null)stored++;
        check(stored==32&&cache.current()==lanes,"storage bound and active protection");
        cache.clear();for(int i=0;i<cache.values.length;i++)check(cache.values[i]==null,"clear releases every retained event");
        System.out.println("LANE_WINDOW_PASS checks="+checks+" full_prefetch=1 active_protected=1 explicit_empty=1 bounded_32=1 cancel_clear=1");
    }
}
