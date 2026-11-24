/* SPDX-License-Identifier: GPL-3.0-or-later */
package com.cpmap.rgi;
import java.io.*;
/** Background-only accepted-session lease. Producer and HMI clocks need not agree. */
final class WirelessSource {
    static final long LEASE_MS=1500;
    String identity="";
    long counter=-1, changed=-1;
    boolean update(String record,long now) {
        try {
            String[] lines=new String[6]; int start=0;
            for(int i=0;i<6;i++) {
                int end=record.indexOf('\n',start);
                if(end<start)throw new IOException();
                lines[i]=record.substring(start,end);start=end+1;
            }
            if(start!=record.length() || !"WCPRG1".equals(lines[0]))throw new IOException();
            long pid=number(lines[1]),nonce=number(lines[2]),next=number(lines[3]),session=number(lines[4]),accepted=number(lines[5]);
            if(pid<=1 || pid>2147483647L || nonce>4294967295L || session>4294967295L || accepted>1 || next==0)throw new IOException();
            String key=new StringBuffer().append(pid).append(':').append(nonce).append(':').append(session).toString();
            if(!identity.equals(key) || next<counter) {identity=key;counter=next;changed=-1;return false;}
            if(next>counter) {counter=next;changed=now;}
            return accepted==1 && session>0 && changed>=0 && now>=changed && now-changed<LEASE_MS;
        } catch(Throwable t) {identity="";counter=changed=-1;return false;}
    }
    boolean poll(String path,long now) {
        try {
            FileInputStream f=new FileInputStream(path);byte[] b=new byte[160];int size=0;
            try {int n;while((n=f.read(b,size,b.length-size))>0) {size+=n;if(size==b.length)throw new IOException();}}
            finally {f.close();}
            return update(new String(b,0,size,"US-ASCII"),now);
        }catch(Throwable t){return update("",now);}
    }
    static long number(String s)throws IOException {
        if(s.length()==0 || s.length()>19 || s.length()>1 && s.charAt(0)=='0')throw new IOException();
        long value=0;
        for(int i=0;i<s.length();i++) {int c=s.charAt(i)-'0';if(c<0 || c>9 || value>(Long.MAX_VALUE-c)/10)throw new IOException();value=value*10+c;}
        return value;
    }
}
