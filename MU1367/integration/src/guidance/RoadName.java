/* SPDX-License-Identifier: GPL-3.0-or-later */
package com.cpmap.rgi;

/** Current-road text only. No maneuver-description or upcoming-road fallback. */
public final class RoadName {
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
            && f.laneAt>=0 && time>=f.laneAt && time-f.laneAt<MAX_AGE
            && f.currentRoad!=null?f.currentRoad:"";
    }
}
