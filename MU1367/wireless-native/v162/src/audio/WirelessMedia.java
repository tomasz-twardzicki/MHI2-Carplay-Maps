/* SPDX-License-Identifier: GPL-3.0-or-later */
package com.cpmap.audio;
import java.io.*;
import java.util.Iterator;
import de.esolutions.fw.dsi.carplay.DSICarplayDispatcher;
import org.dsi.ifc.carplay.*;
import org.dsi.ifc.global.ResourceLocator;
/** Worker reads snapshots; the existing factory ASL timer alone notifies DSI. */
public final class WirelessMedia implements Runnable {
    static volatile DSICarplayDispatcher dispatcher;
    static volatile WirelessFrame frame;
    static volatile long observed=-1;
    static volatile boolean usb;
    static boolean started,owned;
    static DSICarplayDispatcher lastDispatcher;
    static long lastEpoch=-1;
    static WirelessFrame sent;
    static String sentCover="";
    static long tracks,playbacks,positions,covers,errors,polls;
    public static synchronized void register(DSICarplayDispatcher d,int instance) {
        if(instance!=0)return;dispatcher=d;
        if(!started){Thread worker=new Thread(new WirelessMedia(),"CPMapWirelessMedia");worker.setDaemon(true);worker.start();started=true;}
    }
    static WirelessFrame current() {
        long now=System.currentTimeMillis();WirelessFrame f=frame;
        return !usb&&f!=null&&observed>=0&&now>=observed&&now-observed<1500?f:null;
    }
    static boolean active(){return current()!=null;}
    static CoverMeta coverMeta() {
        WirelessFrame f=current();
        if(f==null||f.uid==0||f.art==0||f.cover==0||f.size<8||f.text[0].length()==0||(f.known&4)!=0&&f.status==0)return null;
        return new CoverMeta(f);
    }
    static boolean confirm(DSICarplayDispatcher d,int attribute) {
        /* Factory 0x80 notifications confirm a pending subscription before
         * delivery. Wireless has no native DSI producer to do that step. */
        Iterator pending=d.getUnconfirmedNotificationListenerIterator(attribute);
        boolean changed=false;
        while(pending.hasNext()){d.confirmNotificationListener(attribute,(org.dsi.ifc.base.DSIListener)pending.next());changed=true;}
        return changed;
    }
    static void tick(long now) {
        try {
            DSICarplayDispatcher d=dispatcher;WirelessFrame f=current();
            if(d==null)return;
            if(!TextBridge.INSTANCE.connected || f==null) {
                if(owned&&!usb&&TextBridge.INSTANCE.connected) {
                    d.updateNowPlayingData(new TrackData("",0,"","","",""),1);
                    d.updatePlaybackState(new PlaybackInfo(0,0,0,""),1);d.updatePlayposition(0,1);d.updateCoverArtUrl(null,1);
                }
                owned=false;sent=null;sentCover="";return;
            }
            if(d!=lastDispatcher||lastEpoch!=TextBridge.epoch){sent=null;sentCover="";lastDispatcher=d;lastEpoch=TextBridge.epoch;}
            boolean subscribers=confirm(d,3)|confirm(d,4)|confirm(d,5)|confirm(d,6);
            boolean trackChanged=subscribers||!f.sameTrack(sent)||sent!=null&&(sent.known&4)!=0&&sent.status==0&&(f.known&4)!=0&&f.status>0;
            if(trackChanged) {
                d.updateNowPlayingData(new TrackData(f.text[0],f.duration,f.text[2],f.text[1],f.text[3],f.text[4]),1);tracks++;
            }
            if((f.known&4)!=0 && (subscribers||!f.sameSession(sent)||sent.status!=f.status||sent.shuffle!=f.shuffle||sent.repeat!=f.repeat||!sent.text[5].equals(f.text[5]))) {
                d.updatePlaybackState(new PlaybackInfo(f.status,f.shuffle,f.repeat,f.text[5]),1);playbacks++;
            }
            if((f.known&8)!=0 && (trackChanged||sent.position!=f.position)) {d.updatePlayposition(f.position,1);positions++;}
            CoverBridge.Picture picture=CoverBridge.current(now);
            String path=picture!=null&&picture.meta.wireless!=null&&f.sameCover(picture.meta.wireless)?picture.path:"";
            if(subscribers||!f.sameCover(sent)||!path.equals(sentCover)) {d.updateCoverArtUrl(path.length()==0?null:new ResourceLocator(path),1);covers++;sentCover=path;}
            sent=f;owned=true;
        }catch(Throwable t){errors++;sent=null;}
    }
    public void run() {
        MediaLease lease=new MediaLease();long lastStatus=0;
        for(;;) {
            long now=System.currentTimeMillis();
            try {
                usb=new File("/dev/ipod0").exists();WirelessFrame next=WirelessFrame.read("/ramdisk/wcp-rg/nowplaying.bin");polls++;
                if(!usb&&lease.update(next.leaseRecord(),now)){frame=next;observed=now;}else{frame=null;observed=-1;}
            }catch(Throwable t){lease.update("",now);frame=null;observed=-1;}
            if(now<lastStatus || now-lastStatus>=1000) {
                lastStatus=now;
                try {
                    String s=new StringBuffer("WCPMEDIA1 dispatcher=").append(dispatcher==null?0:1).append(" active=").append(active()?1:0).append(" usb=").append(usb?1:0).append(" polls=").append(polls).append(" tracks=").append(tracks).append(" playback=").append(playbacks).append(" positions=").append(positions).append(" covers=").append(covers).append(" errors=").append(errors).append('\n').toString();
                    File temp=new File("/ramdisk/wcp-now-playing.status.new");FileOutputStream out=new FileOutputStream(temp);try{out.write(s.getBytes("US-ASCII"));}finally{out.close();}
                    if(!temp.renameTo(new File("/ramdisk/wcp-now-playing.status")))throw new IOException("status rename");
                }catch(Throwable t){/* optional diagnostics */}
            }
            try{Thread.sleep(200);}catch(InterruptedException stop){frame=null;observed=-1;return;}
        }
    }
}
