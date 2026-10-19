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
    final Function[] stages=new Function[6];
    Timer timer;
    boolean started, owned, clearing, refreshing;
    LiveModel.Frame selected;
    long floor=-1, lastRun=-1, lastTick=-1, publishedProgress=-1, publishedEpoch=-1;
    int publishedMain=-1, publishedDirection=-1, publishedMeters=-2;
    int refreshPending;
    static int slot(int id) { return id==23?0:id==18?1:id==17?2:id==24?3:id==21?4:id==22?5:-1; }
    static final int PROPERTIES=55; // all stages except the lane array
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
            for (int i=0;i<6;i++) if (INSTANCE.stages[i]==stage) INSTANCE.stages[i]=null;
            INSTANCE.selected=null; INSTANCE.owned=false; INSTANCE.refreshPending=63;
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
            if (!allowed(time) || factoryContext()!=0 || selected.active && (mode!=2 || time<selected.changed || time-selected.changed>=5000
                    || journalAt<0 || time<journalAt || time-journalAt>=1500)) {
                selected=null; refreshPending=63; return null;
            }
            return selected;
        } catch (Throwable t) { selected=null; refreshPending=63; failures++; return null; }
    }
    public void timerFired(Timer ignored) {
        try { tick(now()); }
        catch (Throwable t) { selected=null; owned=false; refreshPending=63; failures++; }
        finally { try { timer.retrigger(null); } catch (Throwable t) { failures++; } }
    }
    void refresh() {
        // Retry any failed stage on subsequent timer ticks. HMI transport
        // acceptance is checked by a narrow patch at statusProperty's return.
        for (int i=0;i<6;i++) if ((refreshPending&(1<<i))!=0 && stages[i]!=null) {
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
        boolean fresh=frame!=null && frame.active && frame.progress>floor && frame.changed>=0 && time>=frame.changed && time-frame.changed<5000
            && journalAt>=0 && time>=journalAt && time-journalAt<1500;
        if (mode==1 && c==0 && fresh) proposals++;
        boolean take=mode==2 && c==0 && lease && fresh && core;
        if (!take) {
            if (owned) {
                // Clear under still-known CarPlay/OEM-idle context; next tick
                // explicitly refreshes the latest stock state. OEM takeover
                // skips blank output and goes straight to stock.
                if (c==0 && lease) {
                    selected=new LiveModel.Frame(false,0,0,-1,0,0,0); clearing=true;
                } else selected=null;
                owned=false; releases++; refreshPending=63;
            } else if (clearing && (refreshPending&PROPERTIES)==0) { selected=null; clearing=false; refreshPending=63; }
            else if (clearing && c==0 && lease) { /* retain clear until queue acceptance */ }
            else selected=null;
        } else {
            boolean changed=!owned || frame.progress!=publishedProgress || frame.epoch!=publishedEpoch || frame.main!=publishedMain || frame.direction!=publishedDirection || frame.meters!=publishedMeters;
            owned=true; clearing=false; selected=frame;
            if (changed) {
                publishedProgress=frame.progress; publishedEpoch=frame.epoch; publishedMain=frame.main; publishedDirection=frame.direction; publishedMeters=frame.meters;
                refreshPending=63; proposals++;
            }
        }
        refresh();
    }
    public static boolean descriptor(ManeuverDescriptor_Status out) {
        LiveModel.Frame f=INSTANCE.current(); if (f==null) return false;
        out.reset(); // Includes all three directions/z-level/side-street strings.
        out.maneuver_1.mainElement=f.main; out.maneuver_1.direction=f.direction;
        INSTANCE.writes++; return true;
    }
    public static int descriptorRouteState(NavigationService stock) {
        return INSTANCE.current()!=null?1:stock.getRouteGuidanceState();
    }
    public static boolean distance(DistanceToNextManeuver_Status out) {
        LiveModel.Frame f=INSTANCE.current(); if (f==null) return false;
        out.reset();
        int[] converted=convertDistance(f.validDistance?f.meters:0,false);
        out.distanceToNextManeuver.distance=converted[0];
        out.distanceToNextManeuver.unit=converted[1]; out.validityInformation.distanceToNextManeuverValid=f.validDistance;
        out.bargraphInfo.bargraphOnOff=0; out.bargraphInfo.bargraph=0;
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
    public static boolean lanes(LaneGuidance_ChangedArray out) {
        if (INSTANCE.current()==null) return false;
        out.reset(); out.laneGuidanceOnOff=0; return true;
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
                .append(" failures=").append(failures).append(" records=").append(records).append(" error=").append(error).append('\n');
            try { out.write(s.toString().getBytes("US-ASCII")); } finally { out.close(); }
            if (!temp.renameTo(target)) failures++;
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
    void runProduction() {
        MailboxReader reader=new MailboxReader(ROOT+"/latest.bin");
        long written=-1, recordAt=-1; int error=0;
        runId="1"; runSerial++;
        for (;;) {
            try {
                long time=now();
                if (new File(ROOT+"/disabled").exists() || error!=0) { incoming=null; mode=0; }
                else {
                    try {
                        LiveModel.Frame frame=reader.next(time);
                        if (frame!=null) { incoming=frame; journalAt=recordAt=time; }
                        if (reader.ended || recordAt<0 || time<recordAt || time-recordAt>=1500) { incoming=null; mode=0; }
                        else mode=2;
                    } catch (FileNotFoundException e) { incoming=null; mode=0; }
                }
                if (written<0 || time<written || time-written>=1000) {
                    if (new File(ROOT).isDirectory()) status(reader.records,error);
                    written=time;
                }
            } catch (Throwable t) { incoming=null; mode=0; error=1; }
            try { Thread.sleep(100); } catch (InterruptedException e) { incoming=null; mode=0; return; }
        }
    }
}
