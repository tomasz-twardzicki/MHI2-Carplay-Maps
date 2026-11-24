/* SPDX-License-Identifier: GPL-3.0-or-later */
package com.cpmap.audio;
import java.io.*;
public final class TestArtworkTrace {
    static void check(boolean ok,String why){if(!ok)throw new RuntimeException(why);}
    public static void main(String[] args)throws Exception {
        WirelessFrame old=WirelessMedia.frame;long observed=WirelessMedia.observed;boolean usb=WirelessMedia.usb;
        try {
            WirelessMedia.frame=null;WirelessMedia.usb=false;
            check(CoverBridge.metadata()==null,"inactive wireless must not open wired PPS");
            WirelessMedia.usb=true;
            // A wired source retains the original PPS read, including its I/O failure.
            try{CoverBridge.metadata();}catch(IOException expected){}
            String state=ArtworkTrace.state(null,TextBridge.epoch,true);
            check(state.indexOf("keep=0")>=0&&state.indexOf("metadata=0")>=0,"missing metadata gate visible");
            ArtworkTrace.error("test-phase",new IOException("test\nmessage\tbounded"));
            check(ArtworkTrace.lastClass.equals("java.io.IOException")&&ArtworkTrace.lastPhase.equals("test-phase"),"exception identity retained");
            check(ArtworkTrace.lastMessage.equals("test_message_bounded"),"diagnostic line escaping");
            StringBuffer longMessage=new StringBuffer();for(int i=0;i<500;i++)longMessage.append('x');
            check(ArtworkTrace.safe(longMessage.toString()).length()==160,"exception message bounded");
        }finally{WirelessMedia.frame=old;WirelessMedia.observed=observed;WirelessMedia.usb=usb;}
        if(new File("/ramdisk").isDirectory()) {
            StringBuffer burst=new StringBuffer();for(int i=0;i<600;i++)burst.append('x');
            for(int i=0;i<250;i++)ArtworkTrace.write("rotation-test",burst.toString());
            check(new File(ArtworkTrace.PATH).length()<=65536,"current trace bound");
            File previous=new File(new StringBuffer(ArtworkTrace.PATH).append(".1").toString());
            check(previous.length()>0&&previous.length()<=65536,"prior trace rotated and bounded");
        }
        System.out.println("ARTWORK_TRACE_PASS exception_class_message=1 bounded=1 inactive_wireless_no_pps=1 gate=1");
    }
}
