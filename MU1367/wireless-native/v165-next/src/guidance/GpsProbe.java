/* SPDX-License-Identifier: GPL-3.0-or-later */
package com.cpmap.rgi;
import java.io.*;
import org.dsi.ifc.navigation.PosPosition;
import org.dsi.ifc.cartimeunitslanguage.ClockGPSSyncData;
/** Passive OEM notification probe. Does not send location to the phone, request
 * a new navigation mode, interpret units or manufacture a fix timestamp.
 * Callback work is bounded memory only; LiveBridge's reader performs RAM I/O.
 */
public final class GpsProbe {
    static final String ROOT="/mnt/app/carplay-mu1367-wireless-native-v165t1";
    static final String FLAG=ROOT+"/gps-probe.enabled";
    static final String PATH="/ramdisk/cpmap-gps-probe.txt";
    static final String[] events=new String[32];
    static volatile boolean enabled;
    static long positions,clocks,sources,demos,failures,written=-1,revision;
    static long bootClocks,bootSources,bootClockAt=-1,bootSourceAt=-1;
    static String bootClock="none",bootSource="none";
    static int cursor;
    static void event(String text){events[cursor]=text;cursor=(cursor+1)&31;revision++;}
    static long now(){return LiveBridge.now();}
    public static synchronized void position(PosPosition p,int validity,int instance){
        if(!enabled)return;
        try{
            positions++;
            StringBuffer b=new StringBuffer("position t=").append(now()).append(" instance=").append(instance).append(" validity=").append(validity);
            if(p==null)b.append(" null=1");else b.append(" state=").append(p.state)
                .append(" latitude_raw=").append(p.latitude).append(" longitude_raw=").append(p.longitude)
                .append(" direction_raw=").append(p.directionAngle).append(" speed_raw=").append(p.speed)
                .append(" map_matched=").append((p.reliability&1024)!=0?1:0).append(" raw_gnss_proven=0").append(" height_raw=").append(p.height).append(" reliability_raw=").append(p.reliability)
                .append(" used_satellites=").append(p.usedSatellites).append(" visible_satellites=").append(p.visibleSatellites)
                .append(" hdop_raw=").append(p.hdop).append(" vdop_raw=").append(p.vdop).append(" pdop_raw=").append(p.pdop);
            event(b.toString());
        }catch(Throwable ignored){failures++;}
    }
    public static synchronized void clock(ClockGPSSyncData p,int validity,int instance){
        // Initial OEM clock notifications may precede the guidance worker.
        // Keep only immutable bounded clock fields then; no early service lookup,
        // coordinate capture, file I/O or assumption that this is fresh UTC.
        try{
            bootClocks++;bootClockAt=enabled?now():-1;
            StringBuffer b=new StringBuffer("instance=").append(instance).append(" validity=").append(validity);
            if(p==null||p.time==null||p.date==null)b.append(" null=1");
            else b.append(" year=").append(p.date.year).append(" month=").append(p.date.month&255).append(" day=").append(p.date.day&255)
                .append(" hour=").append(p.time.hours&255).append(" minute=").append(p.time.minutes&255).append(" second=").append(p.time.seconds&255)
                .append(" timezone_raw=").append(p.time.timeZone).append(" summer_time=").append(p.time.summerTime?1:0);
            bootClock=b.toString();
            if(enabled){clocks++;event(new StringBuffer("gps_clock t=").append(bootClockAt).append(' ').append(bootClock).toString());}
        }catch(Throwable ignored){failures++;}
    }
    public static synchronized void source(int source,int validity,int instance){
        try{
            bootSources++;bootSourceAt=enabled?now():-1;
            bootSource=new StringBuffer("instance=").append(instance).append(" validity=").append(validity).append(" source_raw=").append(source).toString();
            if(enabled){sources++;event(new StringBuffer("clock_source t=").append(bootSourceAt).append(' ').append(bootSource).toString());}
        }catch(Throwable ignored){failures++;}
    }
    public static synchronized void demo(boolean active,int validity,int instance){
        if(!enabled)return;
        try{demos++;event(new StringBuffer("demo t=").append(now()).append(" instance=").append(instance).append(" validity=").append(validity).append(" active=").append(active?1:0).toString());}
        catch(Throwable ignored){failures++;}
    }
    static synchronized String snapshot(long time){
        StringBuffer b=new StringBuffer("CPGPSPROBE1 observe_only=1 forwarding=0 t=").append(time)
            .append(" revision=").append(revision).append(" positions=").append(positions).append(" clocks=").append(clocks)
            .append(" boot_clocks=").append(bootClocks).append(" boot_sources=").append(bootSources).append(" sources=").append(sources).append(" demos=").append(demos).append(" failures=").append(failures).append('\n');
        b.append("bootstrap_clock captured_at=").append(bootClockAt).append(" age_ms=").append(bootClockAt<0||time<bootClockAt?-1:time-bootClockAt).append(" utc_qualified=0 ").append(bootClock).append('\n');
        b.append("bootstrap_clock_source captured_at=").append(bootSourceAt).append(' ').append(bootSource).append('\n');
        for(int i=0;i<32;i++){String line=events[(cursor+i)&31];if(line!=null)b.append(line).append('\n');}
        return b.toString();
    }
    static void poll(long time){
        if(written>=0&&time>=written&&time-written<1000)return;written=time;
        boolean next=false;
        try{FileInputStream state=new FileInputStream(new File(ROOT,"STATE"));byte[] b=new byte[16];int n;
            try{n=state.read(b);}finally{state.close();}
            if(n==10&&"installed\n".equals(new String(b,0,n,"US-ASCII"))){
                FileInputStream flag=new FileInputStream(FLAG);try{next=flag.read()==49&&flag.read()==10&&flag.read()==-1;}finally{flag.close();}
            }
        }catch(Throwable ignored){}
        if(next!=enabled){
            synchronized(GpsProbe.classLock()){
                enabled=next;for(int i=0;i<32;i++)events[i]=null;cursor=0;revision++;
            }
            if(!next){new File(PATH).delete();return;}
        }
        if(!enabled)return;
        File stage=new File("/ramdisk/cpmap-gps-probe.new");
        try{
            FileOutputStream out=new FileOutputStream(stage);
            try{out.write(snapshot(time).getBytes("US-ASCII"));}finally{out.close();}
            if(!stage.renameTo(new File(PATH)))throw new IOException("GPS probe rename");
        }catch(Throwable ignored){synchronized(GpsProbe.classLock()){failures++;}stage.delete();}
    }
    /* Foundation/J9 has no Java-5 ldc Class constant support. */
    static Class classLock(){try{return Class.forName("com.cpmap.rgi.GpsProbe");}catch(ClassNotFoundException impossible){throw new RuntimeException();}}
}
