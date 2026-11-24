/* SPDX-License-Identifier: GPL-3.0-or-later */
package com.cpmap.rgi;

/** Current/upcoming/off dial text; route freshness and exact head remain authoritative. */
public final class RoadName {
    static final int OFF=0,CURRENT=1,NEXT=2;
    static volatile int mode=CURRENT;
    static long polled=-1;
    static final String ROOT="/mnt/app/carplay-mu1367-wireless-native-v165t2";
    static String modeName(){return mode==NEXT?"next":mode==OFF?"off":"current";}
    // Worker-only preference I/O. HMI/BAP render paths read one volatile mode.
    static void poll(long time){
        if(polled>=0&&time>=polled&&time-polled<1000)return;polled=time;int next=CURRENT;
        try{
            java.io.FileInputStream in=new java.io.FileInputStream(ROOT+"/STATE");byte[] b=new byte[16];int n;
            try{n=in.read(b);}finally{in.close();}
            if(n==10&&"installed\n".equals(new String(b,0,n,"US-ASCII"))){
                in=new java.io.FileInputStream(ROOT+"/road-label.mode");try{n=in.read(b);}finally{in.close();}
                String value=n>0?new String(b,0,n,"US-ASCII"):"";
                if(value.equals("next\n"))next=NEXT;else if(value.equals("off\n"))next=OFF;
            }
        }catch(Throwable ignored){}mode=next;
    }
    static String display(LiveModel.Frame f,long time){
        if(mode==OFF)return "";
        if(mode==CURRENT)return current(f,time);
        return f!=null&&f.active&&f.maneuverIndex>=0&&f.laneAt>=0&&time>=f.laneAt&&time-f.laneAt<LiveBridge.hold()
            && f.nextRoad!=null?f.nextRoad:"";
    }
    static final long MAX_AGE=LiveModel.HOLD_MS;
    // Factory turnToInfo has a 76-byte BAP string including its length byte.
    static final int MAX_BYTES=75;
    static String decode(byte[] raw) throws java.io.IOException {
        if(raw==null)return "";
        LiveModel.text(raw,0,raw.length,256);
        int end=raw.length;
        if(end>0 && raw[end-1]==0)end--;
        byte[] out=new byte[MAX_BYTES];int n=0,p=0;boolean space=false;
        while(p<end){
            int c=raw[p]&255;
            if(c==9 || c==10 || c==13 || c==32){space=n>0;p++;continue;}
            int width=c<128?1:c<224?2:c<240?3:4;
            int gap=space?1:0;
            if(n+gap+width>MAX_BYTES)break;
            if(space)out[n++]=32;
            System.arraycopy(raw,p,out,n,width);n+=width;p+=width;space=false;
        }
        return new String(out,0,n,"UTF-8");
    }
    static String current(LiveModel.Frame f,long time){
        // The protocol sends deltas: an omitted road field is unchanged state.
        // laneAt is the existing timestamp of the last accepted route update.
        // Maneuver/lane-only activity cannot keep that route context fresh.
        return f!=null && f.active && f.roadAt>=0 && time>=f.roadAt
            && f.laneAt>=0 && time>=f.laneAt && time-f.laneAt<LiveBridge.hold()
            && f.currentRoad!=null?f.currentRoad:"";
    }
}
