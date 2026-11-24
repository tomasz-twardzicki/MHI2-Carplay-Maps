/* SPDX-License-Identifier: GPL-3.0-or-later */
package com.cpmap.audio;
import java.io.*;

/** One bounded numeric report from the already-reaped fetch process. */
final class FetchTiming {
    static long[] read(InputStream in)throws IOException{
        byte[] data=new byte[512];int size=0,n;
        while(size<data.length&&(n=in.read(data,size,data.length-size))>0)size+=n;
        if(size==data.length)throw new IOException("fetch report bound");
        String s=new String(data,0,size,"US-ASCII");
        int at=s.indexOf("ARTWORK_TIMING ");if(at<0)return null;
        int end=s.indexOf('\n',at);if(end<0)end=s.length();s=s.substring(at,end);
        String[] keys={"read_ms=","decode_write_ms=","recheck_ms=","png_bytes=","input_bytes=","width=","height="};
        long[] result=new long[keys.length];
        for(int i=0;i<keys.length;i++){
            int begin=s.indexOf(keys[i]);if(begin<0)return null;begin+=keys[i].length();
            int stop=s.indexOf(' ',begin);if(stop<0)stop=s.length();
            if(stop==begin||stop-begin>9)return null;
            long value=0;for(int j=begin;j<stop;j++){char c=s.charAt(j);if(c<'0'||c>'9')return null;value=value*10+c-'0';}
            result[i]=value;
        }
        return result;
    }
}
