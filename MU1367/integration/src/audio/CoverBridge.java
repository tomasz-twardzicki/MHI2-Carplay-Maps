/* SPDX-License-Identifier: GPL-3.0-or-later
 * VW picture-service approach credited to brisoleg/e-golf-mib2 (GPL-3.0),
 * commit a5a15515191105143727871ae61931307713abb1. Our capture remains passive.
 */
package com.cpmap.audio;
import java.io.*;
import java.util.*;
import de.vw.mib.asl.framework.internal.framework.ServiceManager;
import de.vw.mib.asl.internal.kombipictureserver.common.controller.Controller;
import de.vw.mib.bap.mqbab2.audiosd.functions.CurrentStationHandle;
import de.vw.mib.bap.mqbab2.generated.audiosd.serializer.CurrentStation_Handle_Status;
import org.dsi.ifc.kombipictureserver.DSIKombiPictureServer;
import org.dsi.ifc.global.ResourceLocator;

/** Worker does file/device/decoder work. Factory ASL timer alone sends HMI/BAP. */
public final class CoverBridge implements Runnable {
    static final String ROOT="/mnt/app/carplay-mu1367-artwork", DIR="/var/app/icab/tmp/", PREFIX="cpmap-art-";
    static final CoverBridge INSTANCE=new CoverBridge();
    static volatile CurrentStationHandle stage;
    static volatile DSIKombiPictureServer server;
    static volatile Picture picture;
    static volatile long heartbeat=-1,workerEpoch=-1;
    static volatile boolean enabled;
    static volatile long serial;
    static boolean started;
    static int sent=-2,filled=-1,pushed=-2;
    static long lastAttempt=-1,lastStart=-1,failures,fetches,misses,responses,clears;
    static int lastWanted=-2;
    static volatile long lastFetchMs=-1,maxFetchMs,fastMisses,slowMisses,missingPolls,mismatchPolls,pushes,serviceStarts;
    static final class Picture {
        final CoverMeta meta;final int handle;final String path;final long epoch,generation;
        Picture(CoverMeta m,int h,String p,long e,long g){meta=m;handle=h;path=p;epoch=e;generation=g;}
    }
    static synchronized void invalidate(){picture=null;serial++;}
    public static void attach(CurrentStationHandle f){stage=f;sent=pushed=-2;lastWanted=-2;}
    public static void detach(CurrentStationHandle f){if(stage==f){stage=null;sent=pushed=-2;}}
    public static void server(DSIKombiPictureServer s){server=s;}
    static boolean eligible(){return TextBridge.INSTANCE.connected&&TextBridge.eligible();}
    static Picture current(long now){
        Picture p=picture;
        if(!enabled || p==null || heartbeat<0 || now<heartbeat || now-heartbeat>2500 ||
           p.epoch!=TextBridge.epoch || p.generation!=serial || !p.meta.matches(TextBridge.MODEL.frame()))return null;
        return p;
    }
    public static void fill(CurrentStation_Handle_Status s){
        try{
            if(!eligible() || s.fsgHandle!=-1)return;
            Picture p=current(TextBridge.now());s.fsgHandle=p==null?-1:p.handle;
            s.fsgHandle_absolutePosition=0;
            filled=s.fsgHandle;
        }catch(Throwable t){failures++;}
    }
    public static boolean accepted(boolean ok,CurrentStation_Handle_Status s,CurrentStationHandle f){
        try{if(ok&&stage==f){if(eligible()){sent=s.fsgHandle;CoverTiming.accepted(sent,TextBridge.now());}else sent=pushed=-2;}}
        catch(Throwable t){failures++;}return ok;
    }
    public static boolean answer(DSIKombiPictureServer s,long h,int variant,int source){
        try{
            if(s==null || source!=19 || variant!=0 || !eligible())return false;
            Picture p=current(TextBridge.now());boolean valid=p!=null&&p.handle==h&&sent==p.handle;
            s.responseCoverArt(h,variant,source,valid?1:2,valid?new ResourceLocator(p.path):null);
            responses++;return true;
        }catch(Throwable t){failures++;return true;}
    }
    public static void tick(long time){
        try{
            if(!started){Thread t=new Thread(INSTANCE,"CPMapArtwork");t.setDaemon(true);t.start();started=true;}
            if(stage==null)return;
            boolean active=eligible();Picture p=active?current(time):null;int wanted=p==null?-1:p.handle;
            if(!active && sent==-2)return;
            if(wanted!=sent && (wanted!=lastWanted||lastAttempt<0||time<lastAttempt||time-lastAttempt>=1000)){
                filled=-1;lastAttempt=time;lastWanted=wanted;stage.process(-1);
                // When OEM owns the source, leave all factory handle values alone.
                if(!active){sent=-2;pushed=-2;return;}
            }
            if(!active)return;
            if(p!=null && server==null && (lastStart<0||time<lastStart||time-lastStart>=10000)){
                lastStart=time;startPictureService();
            }
            if(server!=null && sent==wanted && pushed!=wanted){
                server.responseCoverArt(wanted,0,19,p==null?2:1,p==null?null:new ResourceLocator(p.path));
                pushed=wanted;if(p==null)clears++;else{pushes++;CoverTiming.pushed(wanted,time);}
            }
        }catch(Throwable t){failures++;}
    }
    static void startPictureService(){
        HashMap targets=ServiceManager.eventMain.getEventDispatcher().getTargets();Iterator it=targets.keySet().iterator();
        while(it.hasNext()){
            Object t=ServiceManager.eventMain.getEventDispatcher().getTarget(((Integer)it.next()).intValue());
            if(t!=null&&t.getClass().getName().equals("de.vw.mib.asl.internal.kombipictureserver.controller.PictureServerController")){
                // Exact K4525 factory CoverArt.getIdentifier(), not the other train's sequence ID.
                serviceStarts++;((Controller)t).getSequence(1480001).executeSequence();return;
            }
        }
    }
    static boolean sourceLive(long e){TextBridge.Source s=TextBridge.source;return s!=null&&s.live&&s.generation==e&&TextBridge.INSTANCE.connected;}
    static boolean keep(CoverMeta a,long e){return sourceLive(e)&&a!=null&&a.matches(TextBridge.MODEL.frame());}
    static boolean remove(String p){if(p==null)return true;File f=new File(p);return !f.exists()||f.delete();}
    static void status(int handle,long attempts,long errors){
        try{
            StringBuffer s=new StringBuffer(256);s.append("format=1 artwork=1 enabled=").append(enabled?1:0);
            s.append(" handle=").append(handle).append(" attempts=").append(attempts).append(" errors=").append(errors);
            s.append(" fetches=").append(fetches).append(" misses=").append(misses).append(" hmi_errors=").append(failures);
            s.append(" responses=").append(responses).append(" clears=").append(clears).append('\n');
            s.append(" fetch_process_last_ms=").append(lastFetchMs).append(" fetch_process_max_ms=").append(maxFetchMs);
            s.append(" fetch_miss_under_500ms=").append(fastMisses).append(" fetch_miss_over_500ms=").append(slowMisses);
            s.append(" metadata_missing_polls=").append(missingPolls).append(" metadata_mismatch_polls=").append(mismatchPolls);
            s.append(" proactive_pushes=").append(pushes).append(" picture_service_starts=").append(serviceStarts).append('\n');
            File tmp=new File("/ramdisk/cpmap-artwork.status.new");FileOutputStream out=new FileOutputStream(tmp);
            try{out.write(s.toString().getBytes("US-ASCII"));}finally{out.close();}
            if(!tmp.renameTo(new File("/ramdisk/cpmap-artwork.status")))throw new IOException("rename");
            tmp=new File("/ramdisk/cpmap-artwork-timing.status.new");out=new FileOutputStream(tmp);
            try{out.write(CoverTiming.status().getBytes("US-ASCII"));}finally{out.close();}
            if(!tmp.renameTo(new File("/ramdisk/cpmap-artwork-timing.status")))throw new IOException("timing rename");
        }catch(Throwable t){/* diagnostic output is optional */}
    }
    public void run(){
        String[] cache=new String[8];int cacheAt=0,handle=0;long attempts=0,errors=0;
        // Unique paths and monotonically increasing handles; no handle/path reuse this HMI boot.
        StringBuffer nonce=new StringBuffer();nonce.append(Long.toHexString(System.currentTimeMillis())).append('-');
        String boot=nonce.toString();CoverMeta done=null,trying=null;long doneEpoch=-1,doneSerial=-1,tryingEpoch=-1,tryingSerial=-1,retryAt=-1;int tries=0;
        boolean cacheSafe=true;long statusAt=-1;
        CoverMeta observed=null;long observedEpoch=-1,observedSerial=-1,seenAt=-1,matchedAt=-1;
        try{
            String[] names=new File(DIR).list();
            if(names==null)throw new IOException("cache absent");
            for(int i=0;i<names.length;i++)if(names[i].startsWith(PREFIX)&&!remove(new StringBuffer(DIR).append(names[i]).toString()))throw new IOException("cache cleanup");
        }catch(Throwable t){errors++;cacheSafe=false;}
        for(;;){
            String pending=null;
            try{
                enabled=cacheSafe&&!new File(ROOT+"/disabled").exists();long e=TextBridge.epoch,g=serial;
                CoverMeta before=enabled&&sourceLive(e)?CoverMeta.read("/ramdisk/pps/iap2/nowplaying"):null;
                heartbeat=TextBridge.now();workerEpoch=e;
                if(before!=null&&(observedEpoch!=e||observedSerial!=g||!before.same(observed))){observed=before;observedEpoch=e;observedSerial=g;seenAt=heartbeat;matchedAt=-1;}
                if(!keep(before,e)){if(before==null)missingPolls++;else mismatchPolls++;picture=null;done=null;}
                else if(doneEpoch!=e || doneSerial!=g || !before.same(done)){
                    if(matchedAt<0)matchedAt=heartbeat;
                    picture=null;
                    if(tryingEpoch!=e||tryingSerial!=g||!before.same(trying)){trying=before;tryingEpoch=e;tryingSerial=g;tries=0;retryAt=-1;}
                    if(handle<60000&&(retryAt<0||heartbeat<retryAt-30000||heartbeat>=retryAt)){
                        int next=handle+1;attempts++;tries++;retryAt=heartbeat+(tries<8?200:tries<30?1000:30000);
                        String path=new StringBuffer(DIR).append(PREFIX).append(boot).append(attempts).append(".png").toString();
                        pending=path;
                        Process child=null;int rc=-1;long[] fetchReport=null;
                        long fetchAt=TextBridge.now();
                        try{
                            child=Runtime.getRuntime().exec(new String[]{ROOT+"/artwork-fetch","/dev/ipod0/rgi-events","/ramdisk/.cpmap-artwork-fetch",path,Long.toHexString(before.uid),Integer.toString(before.id),Integer.toString(before.size)});
                            child.getOutputStream().close();
                            // Native supervisor bounds the worker to 5s; stdout is bounded numeric text.
                            rc=child.waitFor();
                            try{fetchReport=FetchTiming.read(child.getInputStream());}catch(IOException optionalReport){}
                        }finally{if(child!=null){try{child.getInputStream().close();child.getErrorStream().close();}catch(IOException ignored){}}}
                        lastFetchMs=CoverTiming.delay(fetchAt,TextBridge.now());if(lastFetchMs>maxFetchMs)maxFetchMs=lastFetchMs;
                        CoverMeta after=CoverMeta.read("/ramdisk/pps/iap2/nowplaying");
                        if(rc==0&&enabled&&serial==g&&before.same(after)&&keep(after,e)){
                            if(!remove(cache[cacheAt]))throw new IOException("cache eviction");
                            cache[cacheAt]=path;cacheAt=(cacheAt+1)%cache.length;pending=null;
                            handle=next;
                            CoverTiming.ready(next,seenAt,matchedAt,TextBridge.now(),lastFetchMs,tries,TextBridge.trackChangedAt);
                            CoverTiming.fetched(next,fetchReport);
                            picture=new Picture(after,next,path,e,g);done=after;doneEpoch=e;doneSerial=g;fetches++;
                        }else{misses++;if(lastFetchMs>=500)slowMisses++;else fastMisses++;}
                    }
                }
                heartbeat=TextBridge.now();
            }catch(Throwable t){picture=null;done=null;errors++;heartbeat=-1;}
            finally{if(!remove(pending)){cacheSafe=false;enabled=false;picture=null;errors++;}}
            long time=System.currentTimeMillis();
            if(statusAt<0||time<statusAt||time-statusAt>=1000){status(picture==null?-1:picture.handle,attempts,errors);statusAt=time;}
            try{Thread.sleep(200);}catch(InterruptedException stop){picture=null;heartbeat=-1;return;}
        }
    }
}
