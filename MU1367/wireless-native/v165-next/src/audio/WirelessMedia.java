/* SPDX-License-Identifier: GPL-3.0-or-later */
package com.cpmap.audio;
import java.io.*;
import org.dsi.ifc.carplay.*;
import org.dsi.ifc.global.ResourceLocator;
/** Worker reads snapshots; the existing factory ASL timer alone notifies DSI. */
public final class WirelessMedia implements Runnable {
    static volatile WirelessFrame frame;
    static volatile long observed=-1;
    static volatile boolean usb;
    static boolean started,owned;
    static long lastEpoch=-1;
    static WirelessFrame sent;
    static String sentCover="";
    static long tracks,playbacks,positions,covers,errors,polls,coversWithPath,coverClears;
    public static synchronized void start() {
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
    static void tick(long now) {
        try {
            WirelessFrame f=current();
            if(!WirelessMediaEvents.ready())return;
            if(!TextBridge.INSTANCE.connected || f==null) {
                if(owned&&!usb&&TextBridge.INSTANCE.connected) {
                    WirelessMediaEvents.send(3,new TrackData("",0,"","","",""));
                    WirelessMediaEvents.send(4,new PlaybackInfo(0,0,0,""));WirelessMediaEvents.send(5,new Integer(0));WirelessMediaEvents.send(6,null);
                }
                owned=false;sent=null;sentCover="";return;
            }
            boolean subscribers=lastEpoch!=TextBridge.epoch;
            if(subscribers){sent=null;sentCover="";lastEpoch=TextBridge.epoch;}
            boolean trackChanged=subscribers||!f.sameTrack(sent)||sent!=null&&(sent.known&4)!=0&&sent.status==0&&(f.known&4)!=0&&f.status>0;
            if(trackChanged) {
                WirelessMediaEvents.send(3,new TrackData(f.text[0],f.duration,f.text[2],f.text[1],f.text[3],f.text[4]));tracks++;
            }
            if((f.known&4)!=0 && (subscribers||!f.sameSession(sent)||sent.status!=f.status||sent.shuffle!=f.shuffle||sent.repeat!=f.repeat||!sent.text[5].equals(f.text[5]))) {
                WirelessMediaEvents.send(4,new PlaybackInfo(f.status,f.shuffle,f.repeat,f.text[5]));playbacks++;
            }
            if((f.known&8)!=0 && (trackChanged||sent.position!=f.position)) {WirelessMediaEvents.send(5,new Integer(f.position));positions++;}
            CoverBridge.Picture picture=CoverBridge.current(now);
            String path=picture!=null&&picture.meta.wireless!=null&&f.sameCover(picture.meta.wireless)?picture.path:"";
            if(subscribers||!f.sameCover(sent)||!path.equals(sentCover)) {WirelessMediaEvents.send(6,path.length()==0?null:new ResourceLocator(path));covers++;if(path.length()>0)coversWithPath++;else coverClears++;sentCover=path;}
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
                    String s=new StringBuffer("WCPMEDIA2 route=asl-dsi-proxy ready=").append(WirelessMediaEvents.ready()?1:0).append(" active=").append(active()?1:0).append(" usb=").append(usb?1:0).append(" polls=").append(polls).append(" queued_tracks=").append(tracks).append(" queued_playback=").append(playbacks).append(" queued_positions=").append(positions).append(" queued_covers=").append(covers).append(" queued_cover_paths=").append(coversWithPath).append(" queued_cover_clears=").append(coverClears).append(" delivered_tracks=").append(TextBridge.INSTANCE.tracks).append(" delivered_covers=").append(TextBridge.INSTANCE.covers).append(" errors=").append(errors).append('\n').toString();
                    File temp=new File("/ramdisk/wcp-now-playing.status.new");FileOutputStream out=new FileOutputStream(temp);try{out.write(s.getBytes("US-ASCII"));}finally{out.close();}
                    if(!temp.renameTo(new File("/ramdisk/wcp-now-playing.status")))throw new IOException("status rename");
                }catch(Throwable t){/* optional diagnostics */}
            }
            try{Thread.sleep(200);}catch(InterruptedException stop){frame=null;observed=-1;return;}
        }
    }
}
