/* SPDX-License-Identifier: GPL-3.0-or-later */
package com.cpmap.audio;

import java.io.*;
import org.dsi.ifc.carplay.*;
import org.dsi.ifc.global.ResourceLocator;
import de.vw.mib.bap.array.timer.Timer;
import de.vw.mib.bap.array.timer.TimerNotifier;
import de.vw.mib.bap.mqbab2.common.api.APIFactory;
import de.vw.mib.bap.mqbab2.common.api.stages.Function;
import de.vw.mib.bap.mqbab2.common.api.smartphoneintegration.SmartphoneIntegrationService;
import de.vw.mib.bap.mqbab2.generated.audiosd.serializer.CurrentStationInfo_Status;
import de.vw.mib.asl.framework.api.framework.ASLFrameworkFactory;

/** N1 text only. DSI stores memory; only the factory ASL timer refreshes BAP. */
public final class TextBridge implements TimerNotifier, Runnable {
    static final TextBridge INSTANCE = new TextBridge();
    static final TextModel MODEL = new TextModel();
    static final int[] ATTRIBUTES = {3,4,5,6};
    static volatile Source source;
    static long epoch;
    static Thread writer;
    Function stage;
    Timer timer;
    volatile boolean connected;
    volatile int context = -1;
    volatile long ticks, fills, accepted, rejected, failures, attachFailures, tracks, covers, ioFailures;
    volatile long lastTick=-1, lastSent=-1;
    long filledRevision=-1;

    static long now() {
        return ASLFrameworkFactory.getASLFrameworkAPI().getServices().getTimerManager().getSystemTimeMillis();
    }
    public static synchronized void start(DSICarplay service) {
        if (service == null || source != null && source.service == service && source.live) return;
        if (source != null) source.close();
        MODEL.clear();
        source = new Source(service, ++epoch);
        try {
            if (writer == null) {
                Thread t=new Thread(INSTANCE,"CPMapAudioN1"); t.setDaemon(true); t.start(); writer=t;
            }
            service.setNotification(ATTRIBUTES,source);
        } catch (Throwable t) { INSTANCE.attachFailures++; source.close(); }
    }
    public static synchronized void stop(DSICarplay service) {
        if (source != null && source.service == service) source.close();
    }
    public static void attach(Function f) {
        try {
            INSTANCE.stage=f; INSTANCE.lastSent=-1;
            INSTANCE.observeConnection(APIFactory.getAPIFactory().getSmartphoneIntegrationService());
            if (INSTANCE.timer == null) INSTANCE.timer=APIFactory.getAPIFactory().getTimerService().createTimer(INSTANCE,200);
            INSTANCE.timer.retrigger(null);
        } catch (Throwable t) { INSTANCE.failures++; }
    }
    public static void detach(Function f) {
        try {
            if (INSTANCE.stage == f) {
                INSTANCE.stage=null; MODEL.clear(); INSTANCE.lastSent=-1;
                if (INSTANCE.timer != null) INSTANCE.timer.stop();
            }
        } catch (Throwable t) { INSTANCE.failures++; }
    }
    public static void connection(SmartphoneIntegrationService service) {
        try { INSTANCE.observeConnection(service); }
        catch (Throwable t) { INSTANCE.connected=false; MODEL.clear(); INSTANCE.failures++; }
    }
    static synchronized void observeConnection(SmartphoneIntegrationService service) {
        boolean active=service.getSmarphoneIntegrationActiveConnectionType()==2;
        if (INSTANCE.connected != active) { MODEL.clear(); INSTANCE.lastSent=-1; }
        INSTANCE.connected=active;
    }
    static boolean eligible() {
        return APIFactory.getAPIFactory().getSmartphoneIntegrationService().getSmarphoneIntegrationActiveConnectionType()==2
            && APIFactory.getAPIFactory().getSoundService().getCurrentAudioComponent()==6;
    }
    public void timerFired(Timer ignored) {
        try { tick(now()); }
        catch (Throwable t) { connected=false; MODEL.clear(); failures++; lastSent=-1; }
        finally { try { if (stage != null) timer.retrigger(null); } catch (Throwable t) { failures++; } }
    }
    void tick(long time) {
        ticks++;
        if (lastTick>=0 && time<lastTick) { MODEL.clear(); lastSent=-1; }
        lastTick=time;
        observeConnection(APIFactory.getAPIFactory().getSmartphoneIntegrationService());
        int next=eligible()?1:0;
        if (next != context) { context=next; lastSent=-1; }
        if (stage != null && (lastSent<0 || next==1 && MODEL.frame().revision != lastSent)) {
            filledRevision=MODEL.frame().revision;
            stage.process(-1); // Stock throttling/deferred send and transport remain authoritative.
        }
    }
    public static boolean accepted(boolean ok, Function f) {
        if (INSTANCE.stage == f) {
            if (ok) { INSTANCE.lastSent=INSTANCE.filledRevision; INSTANCE.accepted++; }
            else INSTANCE.rejected++;
        }
        return ok;
    }
    public static boolean fill(CurrentStationInfo_Status out) {
        try {
            if (INSTANCE.stage == null || !eligible()) return false;
            long time=now();
            boolean lease=INSTANCE.connected && INSTANCE.lastTick>=0 && time>=INSTANCE.lastTick && time-INSTANCE.lastTick<1500;
            TextModel.Frame frame=MODEL.frame();
            render(out,lease?frame:null);
            INSTANCE.filledRevision=lease?frame.revision:-1; INSTANCE.fills++;
            return true;
        } catch (Throwable t) { INSTANCE.failures++; return false; }
    }
    public static void render(CurrentStationInfo_Status out, TextModel.Frame frame) {
        String title=frame==null?"":frame.title, artist=frame==null?"":frame.artist, album=frame==null?"":frame.album;
        out.primaryInformation.setContent(title.length()==0?"Apple CarPlay":title);
        out.pi_Type=72;
        out.secondaryInformation.setContent(artist); out.si_Type=artist.length()==0?0:73;
        out.tertiaryInformation.setContent(album); out.ti_Type=album.length()==0?0:74;
    }
    public void run() {
        long writes=0;
        for (;;) {
            try {
                StringBuffer s=new StringBuffer(1024);
                s.append("format=1 build=").append(BuildInfo.ID).append(" text_output=1 epoch=").append(epoch);
                s.append(" connected=").append(connected?1:0).append(" context=").append(context);
                s.append(" ticks=").append(ticks).append(" fills=").append(fills).append(" accepted=").append(accepted);
                s.append(" rejected=").append(rejected).append(" failures=").append(failures);
                s.append(" attach_failures=").append(attachFailures).append(" tracks=").append(tracks).append(" covers=").append(covers);
                s.append(" io_failures=").append(ioFailures).append(" writes=").append(++writes).append('\n');
                byte[] data=s.toString().getBytes("US-ASCII");
                if (data.length>4096) throw new IOException("status bound");
                File temp=new File("/ramdisk/carplay-now-playing-n1.status.new");
                FileOutputStream stream=new FileOutputStream(temp);
                try { stream.write(data); } finally { stream.close(); }
                if (!temp.renameTo(new File("/ramdisk/carplay-now-playing-n1.status"))) throw new IOException("status rename");
            } catch (Throwable t) { ioFailures++; }
            try { Thread.sleep(1000); } catch (InterruptedException stop) { return; }
        }
    }
    static synchronized void track(Source from,TrackData data,int valid) {
        if (!from.active()) return;
        INSTANCE.tracks++;
        if (INSTANCE.connected) MODEL.track(data,valid);
    }
    static synchronized void playback(Source from,PlaybackInfo info,int valid) {
        if (from.active() && (valid!=1 || info==null || info.status==0 || info.status<0 || info.status>4)) MODEL.clear();
    }
    static synchronized void error(Source from) {
        if (from.active()) { MODEL.clear(); INSTANCE.failures++; }
    }
    static final class Source implements DSICarplayListener {
        final DSICarplay service;
        final long generation;
        volatile boolean live=true;
        Source(DSICarplay s,long g) { service=s; generation=g; }
        void close() {
            live=false; MODEL.clear();
            try { service.clearNotification(ATTRIBUTES,this); } catch (Throwable t) { INSTANCE.failures++; }
        }
        boolean active() { return live && source==this; }
        public void updateNowPlayingData(TrackData data,int valid) {
            track(this,data,valid);
        }
        public void updatePlaybackState(PlaybackInfo info,int valid) {
            playback(this,info,valid);
        }
        public void updateCoverArtUrl(ResourceLocator art,int valid) { if (active()) INSTANCE.covers++; }
        public void asyncException(int error,String message,int request) { error(this); }
        public void updatePlayposition(int value,int valid) { }
        public void updateMode(Resource[] r,AppState[] a,int valid) { }
        public void responseModeChange(Resource[] r,AppState[] a,int result) { }
        public void requestBTDeactivation(String address,int reason) { }
        public void updateDeviceInfo(DeviceInfo info,int valid) { }
        public void updateCallState(CallState[] state,int valid) { }
        public void updateTelephonyState(TelephonyState state,int valid) { }
        public void updateTextInputState(int state,int valid) { }
        public void duckAudio(int input,double level) { }
        public void unduckAudio(int input) { }
        public void oemAppSelected() { }
        public void updateMainAudioType(int type,int valid) { }
    }
}
