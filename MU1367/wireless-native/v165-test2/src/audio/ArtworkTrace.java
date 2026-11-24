/* SPDX-License-Identifier: GPL-3.0-or-later */
package com.cpmap.audio;
import java.io.*;
/** Bounded worker-only diagnostics; never copy track text or image bytes here. */
final class ArtworkTrace {
    static final String PATH="/ramdisk/cpmap-artwork.log";
    static volatile long errorSequence,lastErrorAt,hmiErrors;
    static long hmiWritten;static volatile String hmiDetail="";
    static String previous="",lastClass="none",lastPhase="none",lastMessage="";
    static String gate="source_live=0 keep=0";
    static String safe(String text) {
        if(text==null)return "";StringBuffer out=new StringBuffer();int n=Math.min(text.length(),160);
        for(int i=0;i<n;i++){char c=text.charAt(i);out.append(c<=32||c==127?'_':c);}
        return out.toString();
    }
    static String state(CoverMeta meta,long epoch,boolean enabled) {
        TextBridge.Source source=TextBridge.source;WirelessFrame frame=WirelessMedia.current();
        TextModel.Frame model=TextBridge.MODEL.frame();
        return new StringBuffer("enabled=").append(enabled?1:0).append(" epoch=").append(epoch)
            .append(" source=").append(source==null?0:1).append(" source_flag=").append(source!=null&&source.live?1:0)
            .append(" source_epoch=").append(source==null?-1:source.generation).append(" connected=").append(TextBridge.INSTANCE.connected?1:0)
            .append(" source_live=").append(CoverBridge.sourceLive(epoch)?1:0).append(" keep=").append(CoverBridge.keep(meta,epoch)?1:0)
            .append(" usb=").append(WirelessMedia.usb?1:0).append(" wireless=").append(frame==null?0:1)
            .append(" session=").append(frame==null?0:frame.session).append(" generation=").append(frame==null?0:frame.generation)
            .append(" uid_known=").append(frame!=null&&(frame.known&1)!=0?1:0).append(" uid_nonzero=").append(frame!=null&&frame.uid!=0?1:0)
            .append(" art=").append(frame==null?0:frame.art).append(" cover=").append(frame==null?0:frame.cover)
            .append(" cover_bytes=").append(frame==null?0:frame.size).append(" metadata=").append(meta==null?0:1)
            .append(" text_match=").append(meta!=null&&meta.matches(model)?1:0).append(" model_revision=").append(model.revision).toString();
    }
    static void hmiError(String phase,Throwable problem){
        try{hmiDetail=new StringBuffer("phase=").append(safe(phase)).append(" class=").append(safe(problem.getClass().getName())).append(" message=").append(safe(problem.getMessage())).toString();hmiErrors++;}catch(Throwable ignored){}
    }
    static void observe(CoverMeta meta,long epoch,boolean enabled) {
        try{if(hmiWritten!=hmiErrors){hmiWritten=hmiErrors;write("hmi-error",hmiDetail);}
        gate=state(meta,epoch,enabled);if(!gate.equals(previous)){previous=gate;write("gate",gate);}}
        catch(Throwable ignored){/* Keep diagnostics outside rendering failure handling. */}
    }
    static long clock(){try{return TextBridge.now();}catch(Throwable unavailable){return System.currentTimeMillis();}}
    static void error(String phase,Throwable problem) {
        try{errorSequence++;lastErrorAt=clock();lastPhase=safe(phase);lastClass=safe(problem.getClass().getName());lastMessage=safe(problem.getMessage());
        write("error",new StringBuffer("phase=").append(lastPhase).append(" class=").append(lastClass).append(" message=").append(lastMessage).append(' ').append(gate).toString());}catch(Throwable ignored){}
    }
    static void write(String event,String detail) {
        try {
            String line=new StringBuffer("ARTWORK t_ms=").append(clock()).append(" event=").append(event).append(' ').append(detail).append('\n').toString();
            byte[] bytes=line.getBytes("UTF8");if(bytes.length>65536)return;
            File file=new File(PATH);
            if(file.exists()&&file.length()+bytes.length>65536) {
                File old=new File(new StringBuffer(PATH).append(".1").toString());
                if(old.exists()&&!old.delete())return;if(!file.renameTo(old))return;
            }
            FileOutputStream out=new FileOutputStream(file,true);try{out.write(bytes);}finally{out.close();}
        }catch(Throwable ignored){/* Diagnostic failure never changes rendering. */}
    }
}
