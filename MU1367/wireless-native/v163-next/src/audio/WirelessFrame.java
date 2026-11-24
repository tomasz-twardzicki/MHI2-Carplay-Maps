/* SPDX-License-Identifier: GPL-3.0-or-later */
package com.cpmap.audio;
import java.io.*;
/** One bounded, immutable accepted-session snapshot. All I/O is worker-only. */
final class WirelessFrame {
    final long pid,nonce,session,counter,generation,revision,uid,cover;
    final int known,duration,position,status,shuffle,repeat,art,size;
    final boolean accepted;
    final String[] text;
    static long u32(byte[] b,int at){return (b[at]&255L)|(b[at+1]&255L)<<8|(b[at+2]&255L)<<16|(b[at+3]&255L)<<24;}
    static long u64(byte[] b,int at){return u32(b,at)|u32(b,at+4)<<32;}
    WirelessFrame(byte[] b)throws IOException {
        if(b.length<140 || b.length>8192 || b[0]!='W'||b[1]!='N'||b[2]!='P'||b[3]!='1'||u32(b,4)!=1||u32(b,8)!=b.length)throw new IOException("media header");
        pid=u32(b,12);nonce=u64(b,16);session=u32(b,24);counter=u32(b,28);accepted=u32(b,32)==1;
        generation=u32(b,36);revision=u32(b,40);known=(int)u32(b,44);uid=u64(b,48);
        duration=(int)u32(b,56);position=(int)u32(b,60);status=(int)u32(b,64);shuffle=(int)u32(b,68);repeat=(int)u32(b,72);
        art=(int)u32(b,76);cover=u32(b,80);size=(int)u32(b,84);
        if(pid<=1||pid>2147483647L||counter==0||u32(b,32)>1||known<0||known>15||duration<0||position<0||status<0||status>4||shuffle<0||shuffle>2||repeat<0||repeat>2||art<0||art>255||size<0||size>800000)throw new IOException("media fields");
        if(accepted && session==0 || cover!=0 && (size<8||art==0||uid==0||generation==0) || cover==0 && size!=0)throw new IOException("media identity");
        for(int i=88;i<128;i++)if(b[i]!=0)throw new IOException("media reserved");
        text=new String[6];int at=128;
        for(int i=0;i<6;i++) {
            if(at+2>b.length)throw new IOException("media text");int n=(b[at]&255)|(b[at+1]&255)<<8;at+=2;
            if(n>1024||n>b.length-at)throw new IOException("media text bound");
            String s=new String(b,at,n,"UTF8");byte[] check=s.getBytes("UTF8");if(check.length!=n)throw new IOException("media UTF8");
            for(int j=0;j<n;j++)if(check[j]!=b[at+j])throw new IOException("media UTF8");
            text[i]=TextModel.text(s);at+=n;
        }
        if(at!=b.length)throw new IOException("media trailing bytes");
    }
    static WirelessFrame read(String path)throws IOException {
        File file=new File(path);long size=file.length();if(size<140||size>8192)throw new IOException("media bound");
        byte[] bytes=new byte[(int)size];DataInputStream in=new DataInputStream(new FileInputStream(file));
        try{in.readFully(bytes);if(in.read()!=-1)throw new IOException("media growth");}finally{in.close();}
        return new WirelessFrame(bytes);
    }
    String leaseRecord(){return new StringBuffer("WCPRG1\n").append(pid).append('\n').append(nonce&0xffffffffL).append('\n').append(counter).append('\n').append(session).append('\n').append(accepted?1:0).append('\n').toString();}
    boolean sameSession(WirelessFrame f){return f!=null&&pid==f.pid&&nonce==f.nonce&&session==f.session;}
    boolean sameTrack(WirelessFrame f){if(!sameSession(f)||generation!=f.generation||uid!=f.uid||duration!=f.duration)return false;for(int i=0;i<5;i++)if(!text[i].equals(f.text[i]))return false;return true;}
    boolean sameCover(WirelessFrame f){return sameTrack(f)&&art==f.art&&cover==f.cover&&size==f.size;}
    String[] decodeCommand(String output){return new String[]{"/mnt/app/carplay-mu1367-wireless-media/wireless-artwork-fetch","/ramdisk/wcp-rg/cover.bin","/ramdisk/.cpmap-wireless-artwork-fetch",output,Long.toString(pid),Long.toHexString(nonce),Long.toString(session),Long.toString(generation),Long.toHexString(uid),Integer.toString(art),Long.toString(cover),Integer.toString(size)};}
}
