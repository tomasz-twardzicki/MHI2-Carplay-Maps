/* SPDX-License-Identifier: GPL-3.0-or-later */
package com.cpmap.audio;
import java.io.*;
import java.lang.reflect.*;
import de.vw.mib.bap.mqbab2.generated.audiosd.BAPAudioSDDataPool;
import de.vw.mib.bap.mqbab2.audiosd.functions.FunctionList;
import de.vw.mib.bap.mqbab2.generated.audiosd.serializer.FunctionList_FctList;
import de.vw.mib.bap.mqbab2.common.api.stages.BAPStageContext;
public final class TestArtworkR3 {
    static int checks;
    static void check(boolean ok,String why)throws Exception{checks++;if(!ok)throw new Exception(why);}
    static long[] parse(String s)throws Exception{return FetchTiming.read(new ByteArrayInputStream(s.getBytes("US-ASCII")));}
    public static void main(String[] args)throws Exception{
        check(TextBridge.ATTRIBUTES.length==2&&TextBridge.ATTRIBUTES[0]==3&&TextBridge.ATTRIBUTES[1]==4,"only metadata and playback-state notifications");
        BAPAudioSDDataPool pool=new BAPAudioSDDataPool(null);
        Method init=pool.getClass().getDeclaredMethod("initializeInternal",new Class[]{Class.forName("de.vw.mib.bap.mqbab2.generated.audiosd.AudioSDBindingFactory")});init.setAccessible(true);
        init.invoke(pool,new Object[]{TestCover.service(Class.forName("de.vw.mib.bap.mqbab2.generated.audiosd.AudioSDBindingFactory"))});
        check(pool.getStage(52)==null,"factory progress stage stays absent");
        FunctionList list=new FunctionList();list.setDelegate((BAPStageContext)TestCover.service(Class.forName("de.vw.mib.bap.mqbab2.common.api.stages.BAPStageContext")));
        check(!((FunctionList_FctList)list.init(null)).fctPlayPositionAvailable,"factory progress capability stays unchanged");
        check(parse("ARTWORK_FETCH_OK\n")==null,"old helper report remains compatible");
        long[] report=parse("ARTWORK_TIMING read_ms=3 decode_write_ms=12 recheck_ms=4 png_bytes=4096 input_bytes=35000 width=600 height=600\nARTWORK_FETCH_OK\n");
        check(report!=null&&report[0]==3&&report[1]==12&&report[3]==4096&&report[6]==600,"numeric fetch stages parsed");
        check(parse("ARTWORK_TIMING read_ms=-1\n")==null,"malformed report ignored");
        boolean bounded=false;try{FetchTiming.read(new ByteArrayInputStream(new byte[513]));}catch(IOException expected){bounded=true;}check(bounded,"report size bound");
        CoverTiming.ready(99,100,100,200,100,1,50);CoverTiming.fetched(99,report);String status=CoverTiming.status();
        check(status.indexOf("decode_write_ms=12")>=0&&status.indexOf("png_bytes=4096")>=0,"native stages retained in bounded image history");
        System.out.println(new StringBuffer("ARTWORK_R3_PASS checks=").append(checks).toString());
    }
}
