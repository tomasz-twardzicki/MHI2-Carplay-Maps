/* SPDX-License-Identifier: GPL-3.0-or-later */
package com.cpmap.audio;

/** Native milliseconds only; never advance a paused or silent input by guessing. */
final class ProgressModel {
    static int position=-1;
    static synchronized void clear(){position=-1;}
    static synchronized void position(int value,int valid){position=valid==1&&value>=0?value:-1;}
    static synchronized int seconds(TextModel.Frame track){
        if(position<0||track.duration<=0||track.title.length()==0)return 0;
        return Math.min(Math.min(position,track.duration)/1000,65534);
    }
    static int total(TextModel.Frame track){
        return track.title.length()==0?0:Math.min(track.duration/1000,65534);
    }
}
