/* SPDX-License-Identifier: GPL-3.0-or-later
 * D1 experimental MQBAB2 adapter. HMI timer owns all output; the background
 * reader only publishes immutable memory and sanitized status on local RAM.
 */
package com.cpmap.rgi;

import java.io.*;
import de.vw.mib.bap.array.timer.Timer;
import de.vw.mib.bap.array.timer.TimerNotifier;
import de.vw.mib.bap.mqbab2.common.api.APIFactory;
import de.vw.mib.bap.mqbab2.common.api.APIFactoryInterface;
import de.vw.mib.bap.mqbab2.common.api.navigation.NavigationService;
import de.vw.mib.bap.mqbab2.common.api.stages.Function;
import de.vw.mib.bap.mqbab2.generated.navsd.serializer.*;
import de.vw.mib.asl.framework.api.framework.ASLFrameworkFactory;

public final class LiveBridge implements TimerNotifier, Runnable {
    static final String ROOT=BuildInfo.RELEASE?"/ramdisk/carplay-route-guidance":"/ramdisk/cpmap-rgi-D1";
    static final LiveBridge INSTANCE=new LiveBridge();
    final Function[] stages=new Function[7];
    Timer timer;
    boolean started, owned, clearing, refreshing;
    LiveModel.Frame selected;
    long floor=-1, lastRun=-1, lastTick=-1, publishedProgress=-1, publishedEpoch=-1;
    int publishedMain=-1, publishedDirection=-1, publishedMeters=-2;
    int refreshPending;
    String publishedRoad="";
    int publishedBar=-1;
    volatile long lastOwnedAt=-1,lastReleaseAt=-1,lastReleaseProgress=-1,lastReleaseFloor=-1;
    volatile long lastReleaseFrameAge=-1,lastReleaseJournalAge=-1;
    volatile int lastReleaseReason,lastReleaseContext=-1,lastReleaseMode;
    volatile int ownershipReason;
    volatile String firstUnexpectedRelease="none",ownershipHistory="none";
    final String[] ownershipEvents=new String[16];
    int ownershipEventAt;
    void noteOwnership(long time,int reason,LiveModel.Frame frame){
        ownershipEvents[ownershipEventAt]=new StringBuffer().append(time).append(':').append(reason)
            .append(':').append(context).append(':').append(mode)
            .append(':').append(frame==null?-1:frame.progress).append(':').append(floor)
            .append(':').append(frame==null?-1:age(time,frame.changed)).append(':').append(age(time,journalAt))
            .append(':').append(productionFeed==null?-1:productionFeed.reader.observedKind).toString();
        ownershipEventAt=(ownershipEventAt+1)&15;
        StringBuffer history=new StringBuffer();
        for(int i=0;i<16;i++){String event=ownershipEvents[(ownershipEventAt+i)&15];
            if(event!=null){if(history.length()>0)history.append(';');history.append(event);}}
        ownershipHistory=history.toString();
    }
    static long age(long time,long stamp){return stamp<0 || time<stamp?-1:time-stamp;}
    static int slot(int id) { return id==23?0:id==18?1:id==17?2:id==24?3:id==21?4:id==22?5:id==20?6:-1; }
    static final int PROPERTIES=119; // all stages except the lane array
    volatile LiveModel.Frame incoming;
    volatile long journalAt=-1, runSerial, ticks, proposals, writes, releases, failures;
    volatile int mode, context=-1;
    volatile String runId="0", hmiRun="0";
    static long now() {
        return ASLFrameworkFactory.getASLFrameworkAPI().getServices().getTimerManager().getSystemTimeMillis();
    }
    public static void attach(Function stage) {
        try { INSTANCE.register(stage); } catch (Throwable t) { INSTANCE.failures++; }
    }
    public static void detach(Function stage) {
        try {
            for (int i=0;i<7;i++) if (INSTANCE.stages[i]==stage) INSTANCE.stages[i]=null;
            INSTANCE.selected=null; INSTANCE.owned=false; INSTANCE.refreshPending=127;
            LiveModel.Frame frame=INSTANCE.incoming;
            if (frame!=null) INSTANCE.floor=frame.progress;
        } catch (Throwable t) { INSTANCE.failures++; }
    }
    void register(Function f) {
        int at=slot(f.getFunctionId());
        if (at<0) return;
        stages[at]=f;
        if (!started && stages[0]!=null && stages[1]!=null && stages[2]!=null) {
            timer=APIFactory.getAPIFactory().getTimerService().createTimer(this,250);
            Thread reader=new Thread(this,"CPMAP-RGI-D1"); reader.setDaemon(true); reader.start();
            started=true; timer.retrigger(null);
        }
    }
    static int factoryContext() {
        APIFactoryInterface api=APIFactory.getAPIFactory();
        NavigationService nav=api.getNavigationService();
        int connection=api.getSmartphoneIntegrationService().getSmarphoneIntegrationActiveConnectionType();
        int status=nav.getNavigationStatus(), route=nav.getRouteGuidanceState();
        if (connection!=2) return 1;
        if (status!=0 || route<0 || route>2) return 2;
        return route==0?0:3;
    }
    boolean allowed(long time) {
        return context==0 && lastTick>=0 && time>=lastTick && time-lastTick<1500;
    }
    // Also re-read actual OEM context at each stock callback: an OEM route may
    // start between timer ticks. No wrapper/cached override is the authority.
    LiveModel.Frame current() {
        if (selected==null) return null;
        try {
            long time=now();
            if (!allowed(time) || factoryContext()!=0 || selected.active && (mode!=2 || time<selected.changed || time-selected.changed>=LiveModel.HOLD_MS
                    || journalAt<0 || time<journalAt || time-journalAt>=1500)) {
                selected=null; refreshPending=127; return null;
            }
            return selected;
        } catch (Throwable t) { selected=null; refreshPending=127; failures++; return null; }
    }
    public void timerFired(Timer ignored) {
        try { tick(now()); }
        catch (Throwable t) { selected=null; owned=false; refreshPending=127; failures++; }
        finally { try { timer.retrigger(null); } catch (Throwable t) { failures++; } }
    }
    void refresh() {
        // Retry any failed stage on subsequent timer ticks. HMI transport
        // acceptance is checked by a narrow patch at statusProperty's return.
        for (int i=0;i<7;i++) if ((refreshPending&(1<<i))!=0 && stages[i]!=null) {
            try { refreshing=true; refreshPending&=~(1<<i); stages[i].process(-1); }
            catch (Throwable t) { refreshPending|=1<<i; failures++; }
            finally { refreshing=false; }
        }
    }
    public static boolean accepted(boolean ok, Function stage) {
        if (!ok && INSTANCE.refreshing) {
            int at=slot(stage.getFunctionId());
            if (at>=0) INSTANCE.refreshPending|=1<<at;
        }
        return ok;
    }
    void tick(long time) {
        ticks++; int c=factoryContext(); context=c;
        LiveModel.Frame frame=incoming;
        if (lastRun!=runSerial) {
            floor=0; lastRun=runSerial; proposals=writes=releases=0; hmiRun=runId;
        }
        boolean lease=lastTick>=0 && time>=lastTick && time-lastTick<1500;
        lastTick=time;
        boolean core=stages[0]!=null && stages[1]!=null && stages[2]!=null && stages[4]!=null && stages[5]!=null;
        if (frame==null || c!=0 || !lease || mode==0 || !core) {
            if (frame!=null) floor=frame.progress;
        }
        boolean fresh=frame!=null && frame.active && frame.progress>floor && frame.changed>=0 && time>=frame.changed && time-frame.changed<LiveModel.HOLD_MS
            && journalAt>=0 && time>=journalAt && time-journalAt<1500;
        if (mode==1 && c==0 && fresh) proposals++;
        boolean take=mode==2 && c==0 && lease && fresh && core;
        ownershipReason=take?0:c!=0?1:!core?2:!lease?3:mode!=2?4:frame==null?5:
            journalAt<0 || time<journalAt || time-journalAt>=1500?6:
            !frame.active?7:frame.changed<0 || time<frame.changed || time-frame.changed>=LiveModel.HOLD_MS?8:9;
        if(take)lastOwnedAt=time;
        if (!take) {
            if (owned) {
                // Clear under still-known CarPlay/OEM-idle context; next tick
                // explicitly refreshes the latest stock state. OEM takeover
                // skips blank output and goes straight to stock.
                if (c==0 && lease) {
                    selected=new LiveModel.Frame(false,0,0,-1,0,0,0); clearing=true;
                } else selected=null;
                noteOwnership(time,ownershipReason,frame);
                lastReleaseAt=time;lastReleaseReason=ownershipReason;
                lastReleaseContext=c;lastReleaseMode=mode;
                lastReleaseProgress=frame==null?-1:frame.progress;lastReleaseFloor=floor;
                lastReleaseFrameAge=frame==null?-1:age(time,frame.changed);
                lastReleaseJournalAge=age(time,journalAt);
                if(c==0 && mode==2 && firstUnexpectedRelease.equals("none"))
                    firstUnexpectedRelease=new StringBuffer().append(time).append(':').append(ownershipReason)
                        .append(':').append(lastReleaseFrameAge).append(':').append(lastReleaseJournalAge)
                        .append(':').append(lastReleaseProgress).append(':').append(floor).toString();
                owned=false; releases++; refreshPending=127;
            } else if (clearing && (refreshPending&(stages[6]==null?55:PROPERTIES))==0) { selected=null; clearing=false; refreshPending=127; }
            else if (clearing && c==0 && lease) { /* retain clear until queue acceptance */ }
            else selected=null;
        } else {
            boolean changed=!owned || frame.progress!=publishedProgress || frame.epoch!=publishedEpoch || frame.main!=publishedMain || frame.direction!=publishedDirection || frame.meters!=publishedMeters;
            if(!owned)noteOwnership(time,0,frame);
            owned=true; clearing=false; selected=frame;
            if (changed) {
                publishedProgress=frame.progress; publishedEpoch=frame.epoch; publishedMain=frame.main; publishedDirection=frame.direction; publishedMeters=frame.meters;
                refreshPending=127; proposals++;
            }
        }
        if(owned && stages[3]!=null)refreshPending|=8;
        if(owned){
            LaneEvidence.selected(frame,time);
            int bar=ArrowProgress.remaining(frame,time);
            if(bar!=publishedBar){publishedBar=bar;refreshPending|=2;}
            String road=RoadName.current(frame,time);
            if(!road.equals(publishedRoad)){publishedRoad=road;refreshPending|=64;}
        }
        refresh();
    }
    public static boolean descriptor(ManeuverDescriptor_Status out) {
        LiveModel.Frame f=INSTANCE.current(); if (f==null) return false;
        out.reset(); // Includes all three directions/z-level/side-street strings.
        // Only an owned, fresh active route may use the placeholder. Clearing,
        // cancellation, OEM ownership and missing/stale route data stay blank.
        boolean placeholder=f.active && f.main==0;
        out.maneuver_1.mainElement=placeholder?13:f.main;
        out.maneuver_1.direction=placeholder?0:f.direction;
        INSTANCE.writes++; return true;
    }
    public static int descriptorRouteState(NavigationService stock) {
        return INSTANCE.current()!=null?1:stock.getRouteGuidanceState();
    }
    public static boolean distance(DistanceToNextManeuver_Status out) {
        LiveModel.Frame f=INSTANCE.current(); if (f==null) return false;
        out.reset();
        boolean realDistance=f.validDistance && f.main!=0;
        int[] converted=convertDistance(realDistance?f.meters:0,false);
        out.distanceToNextManeuver.distance=converted[0];
        out.distanceToNextManeuver.unit=converted[1]; out.validityInformation.distanceToNextManeuverValid=realDistance;
        ArrowProgress.fill(out,f,now());
        INSTANCE.writes++; return true;
    }
    static int[] convertDistance(int meters, boolean destination) {
        int[] out=new int[2];
        de.vw.mib.bap.mqbab2.common.api.system.SystemService system=APIFactory.getAPIFactory().getSystemService();
        de.vw.mib.format.FixFormat format=APIFactory.getAPIFactory().getFixFormatter();
        boolean miles=system.getCurrentDistanceUnit()==1;
        if (destination) {
            if (miles) format.cnv2Distance1Miles(meters,out);
            else format.cnv2Distance1Kilometers(meters,out);
        } else {
            if (miles) format.cnv2Distance2withMinDistanceMiles(meters,out);
            else format.cnvDistance2KilometersExt(meters,out);
        }
        return out;
    }
    public static boolean turnTo(TurnToInfo_Status out) {
        LiveModel.Frame f=INSTANCE.current();if(f==null)return false;
        out.reset();out.turnToInfo.setContent(RoadName.current(f,now()));
        INSTANCE.writes++;return true;
    }
    public static boolean destinationDistance(DistanceToDestination_Status out) {
        LiveModel.Frame f=INSTANCE.current(); if (f==null) return false;
        out.reset();
        boolean valid=f.active && f.remainingMeters>=0;
        int[] converted=convertDistance(valid?f.remainingMeters:0,true);
        out.distanceToDestination.distance=converted[0]; out.distanceToDestination.unit=converted[1];
        out.validityInformation.distanceToDestinationValid=valid;
        INSTANCE.writes++; return true;
    }
    public static boolean destinationValidity(DistanceToDestination_Status out) {
        // Stock computes validity separately after setDistanceAndUnit.
        if (INSTANCE.current()==null) return false;
        return true;
    }
    public static boolean destinationTime(TimeToDestination_Status out) {
        LiveModel.Frame f=INSTANCE.current(); if (f==null) return false;
        out.reset();
        boolean valid=f.active && f.remainingSeconds>=0;
        int minutes=valid?(f.remainingSeconds+59)/60:0;
        // Remaining duration, not an assumed epoch/timezone for phone ETA.
        out.timeInfo.timeInfoType=0; out.timeInfo.navigationTimeFormat=0;
        out.timeInfo.hour=minutes/60; out.timeInfo.minute=minutes%60;
        out.validityInformation.timeInfo_HourIsValid=valid;
        out.validityInformation.timeInfo_MinuteIsValid=valid;
        INSTANCE.writes++; return true;
    }
    public static boolean route(RG_Status_Status out) {
        LiveModel.Frame f=INSTANCE.current(); if (f==null) return false;
        out.rg_Status=f.active?1:0; INSTANCE.writes++; return true;
    }
    private static LiveModel.Frame laneFrame() {
        LiveModel.Frame f=INSTANCE.current();
        if(f==null || !f.active || f.laneAt<0)return null;
        long time=now();return time>=f.laneAt && time-f.laneAt<LiveModel.HOLD_MS?f:null;
    }
    public static java.util.Iterator laneIterator(NavigationService stock) {
        if(INSTANCE.current()==null)return stock.getLaneGuidance();
        LiveModel.Frame f=laneFrame();return LaneData.iterator(f==null?LaneData.EMPTY:f.lanes);
    }
    public static boolean lanesVisible(NavigationService stock) {
        if(INSTANCE.current()==null)return stock.isSetupLaneGuidanceActive();
        LiveModel.Frame f=laneFrame();return f!=null && f.lanes.length>0 && stock.isSetupLaneGuidanceActive();
    }
    // Factory/QNX load probes retain this signature. Actual transmission uses
    // the stock lane builder, array diff, six-lane window and request tracker.
    public static boolean lanes(LaneGuidance_ChangedArray out) {
        if(INSTANCE.current()==null)return false;
        out.reset();out.laneGuidanceOnOff=0;return true;
    }
    static String request() throws IOException {
        File f=new File(ROOT+"/request"); if (!f.isFile()) return "";
        LiveModel.require(f.length()>0 && f.length()<=64);
        FileInputStream in=new FileInputStream(f); byte[] b=new byte[65]; int n;
        try { n=in.read(b); } finally { in.close(); }
        LiveModel.require(n>0 && n<=64); String s=new String(b,0,n,"US-ASCII").trim();
        LiveModel.require(s.startsWith("shadow ") || s.startsWith("live "));
        int split=s.indexOf(' '); LiveModel.require(split+1<s.length());
        for (int i=split+1;i<s.length();i++) LiveModel.require(s.charAt(i)>='0' && s.charAt(i)<='9');
        return s;
    }
    void status(long records, int error) {
        try {
            File target=new File(ROOT+"/adapter-status.txt"), temp=new File(ROOT+"/adapter-status.tmp");
            FileOutputStream out=new FileOutputStream(temp);
            StringBuffer s=new StringBuffer(BuildInfo.RELEASE?"RG build=":"D1 build="); s.append(BuildInfo.ID).append(" run=").append(hmiRun).append(" mode=").append(mode).append(" context=").append(context).append(" ticks=").append(ticks)
                .append(" proposals=").append(proposals).append(" writes=").append(writes).append(" releases=").append(releases)
                .append(" failures=").append(failures).append(" records=").append(records).append(" arrow_remaining_percent=").append(ArrowProgress.remaining(incoming,now())).append(" arrow_window_m=").append(ArrowProgress.window(incoming)).append(" road_fields_seen=").append(productionFeed==null?0:productionFeed.roadFields).append(" nonempty_roads_seen=").append(productionFeed==null?0:productionFeed.roadNonempty).append(" lane_messages_seen=").append(productionFeed==null?0:productionFeed.laneMessages).append(" neutral_lanes_seen=").append(productionFeed==null?0:productionFeed.neutralLanes).append(" neutral_branches_seen=").append(productionFeed==null?0:productionFeed.neutralBranches).append(" road_present=").append(RoadName.current(incoming,now()).length()>0?1:0).append(" road_at=").append(incoming==null?-1:incoming.roadAt).append(" lane_count=").append(incoming==null?0:incoming.lanes.length).append(" lane_at=").append(incoming==null?-1:incoming.laneAt).append(" ownership_history=").append(ownershipHistory).append(" first_unexpected_release=").append(firstUnexpectedRelease).append(" owned=").append(owned?1:0).append(" ownership_reason=").append(ownershipReason)
                .append(" last_owned_at=").append(lastOwnedAt).append(" last_release_at=").append(lastReleaseAt)
                .append(" last_release_reason=").append(lastReleaseReason).append(" last_release_context=").append(lastReleaseContext)
                .append(" last_release_mode=").append(lastReleaseMode).append(" last_release_progress=").append(lastReleaseProgress)
                .append(" last_release_floor=").append(lastReleaseFloor).append(" last_release_frame_age=").append(lastReleaseFrameAge)
                .append(" last_release_journal_age=").append(lastReleaseJournalAge)
                .append(" mailbox_serial=").append(productionFeed==null?-1:productionFeed.reader.observedSerial)
                .append(" mailbox_kind=").append(productionFeed==null?-1:productionFeed.reader.observedKind)
                .append(" feed_errors=").append(productionFeed==null?0:productionFeed.errors).append(" feed_recoveries=").append(productionFeed==null?0:productionFeed.recoveries).append(" feed_fatal=").append(productionFeed!=null && productionFeed.fatal?1:0).append(" error=").append(error).append('\n');
            try { out.write(s.toString().getBytes("US-ASCII")); } finally { out.close(); }
            if (!temp.renameTo(target)) failures++;
            LaneEvidence.write(ROOT);
            GuidanceEvidence.write(ROOT);
        } catch (IOException e) { failures++; }
    }
    public void run() {
        if (BuildInfo.RELEASE) { runProduction(); return; }
        JournalReader reader=null; String token=""; long startedAt=0, written=-1, recordAt=-1; int error=0;
        for (;;) {
            try {
                long time=now(); String requested=request();
                if (!requested.equals(token)) {
                    incoming=null; mode=0; journalAt=-1;
                    if (reader!=null) { reader.close(); reader=null; }
                    token=requested; error=0; startedAt=time; recordAt=-1;
                    runId=token.length()==0?"0":token.substring(token.indexOf(' ')+1); runSerial++;
                    if (token.length()>0) {
                        reader=new JournalReader(ROOT+"/capture/events.rgj");
                        mode=token.startsWith("live ")?2:1;
                    }
                }
                if (reader!=null && error==0) {
                    LiveModel.require(time>=startedAt && time-startedAt<=303000);
                    LiveModel.Frame f; int batch=0;
                    while (batch++<64 && (f=reader.next(time))!=null) {
                        incoming=f; journalAt=recordAt=time;
                    }
                    // No heartbeat is a failed producer even when the last
                    // selected head remains in the regular RAM journal.
                    if (reader.ended || recordAt>=0 && time-recordAt>=1500) { incoming=null; mode=0; }
                }
                if (written<0 || time-written>=1000) { if (new File(ROOT).isDirectory()) status(reader==null?0:reader.records,error); written=time; }
            } catch (Throwable t) { incoming=null; mode=0; error=1; }
            try { Thread.sleep(100); } catch (InterruptedException e) { incoming=null; mode=0; return; }
        }
    }
    FeedRecovery productionFeed;
    void runProduction() {
        FeedRecovery feed=new FeedRecovery(ROOT);productionFeed=feed;
        long written=-1;
        runId="1";runSerial++;
        for (;;) {
            try {
                long time=now();
                pollProduction(feed,time,new File(ROOT+"/disabled").exists());
                if(written<0 || time<written || time-written>=1000){
                    if(new File(ROOT).isDirectory())status(feed.reader.records,feed.error);
                    written=time;
                }
            }catch(Throwable t){incoming=null;mode=0;journalAt=-1;feed.failed(t,0);}
            try{Thread.sleep(100);}catch(InterruptedException e){incoming=null;mode=0;return;}
        }
    }
    long feedGeneration=-1;
    void pollProduction(FeedRecovery feed,long time,boolean disabled){
        if(productionFeed!=feed){productionFeed=feed;feedGeneration=-1;}
        if(disabled){feed.pause();incoming=null;mode=0;journalAt=-1;}
        else {
            LiveModel.Frame frame=feed.poll(time);
            if(!feed.live){incoming=null;mode=0;journalAt=-1;}
            if(feed.generation!=feedGeneration){feedGeneration=feed.generation;runSerial++;runId=Long.toString(feedGeneration+1);}
            if(frame!=null)incoming=frame;
            journalAt=feed.recordAt;mode=feed.live?2:0;
            if(mode==0)incoming=null;
        }
    }
}
