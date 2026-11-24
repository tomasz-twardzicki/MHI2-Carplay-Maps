/* SPDX-License-Identifier: GPL-3.0-or-later */
package com.cpmap.audio;
import java.io.*;

/** Bounded full PPS snapshot. Missing/ambiguous identity means no picture. */
final class CoverMeta {
    final long uid;
    final int id,size;
    final String title,artist,album;
    CoverMeta(long u,int i,int s,String t,String a,String b){uid=u;id=i;size=s;title=t;artist=a;album=b;}
    static long unsigned(String s) throws IOException {
        long hi=0,lo=0;int base=10,start=0;
        if(s.startsWith("0x")){base=16;start=2;}
        if(s.length()<=start || s.length()-start>(base==16?16:20))throw new IOException("identity");
        for(int i=start;i<s.length();i++){
            char c=s.charAt(i);int n=c>='0'&&c<='9'?c-'0':c>='a'&&c<='f'?c-'a'+10:c>='A'&&c<='F'?c-'A'+10:-1;
            if(n<0 || n>=base)throw new IOException("identity");
            lo=lo*base+n;hi=hi*base+(lo>>>32);lo&=0xffffffffL;
            if(hi>0xffffffffL)throw new IOException("identity");
        }
        return hi<<32|lo;
    }
    static CoverMeta parse(byte[] data,int count)throws IOException{
        if(count<1 || count>16384)throw new IOException("PPS bound");
        String s=new String(data,0,count,"UTF8");
        String[] values=new String[7];int at=0,lines=0;
        while(at<s.length()){
            int end=s.indexOf('\n',at);if(end<0)end=s.length();
            if(end-at>4096 || ++lines>256)throw new IOException("PPS line bound");
            String line=s.substring(at,end);at=end+1;
            int colon=line.indexOf("::");if(colon<0)continue;
            String name=line.substring(0,colon),v=line.substring(colon+2).trim();int key=-1;
            if(name.equals("MediaItemPersistentIdentifier"))key=0;
            else if(name.equals("MediaItemArtworkFileTransferIdentifier"))key=1;
            else if(name.equals("MediaItemArtworkSize"))key=2;
            else if(name.equals("MediaItemTitle"))key=3;
            else if(name.equals("MediaItemArtist"))key=4;
            else if(name.equals("MediaItemAlbumTitle"))key=5;
            else if(name.equals("PlaybackStatus"))key=6;
            if(key>=0){if(values[key]!=null)throw new IOException("PPS duplicate");values[key]=v;}
        }
        if(values[0]==null||values[1]==null||values[2]==null||values[3]==null||
           values[6]==null||values[6].equals("Stopped"))return null;
        // Exact K4525 nowplay_update_recv: ulltoa(base 16), left padded to
        // sixteen digits, then PPS "%s::%s". Numeric-only IDs are hex too.
        if(values[0].length()!=16)return null;
        long uid=unsigned(new StringBuffer("0x").append(values[0]).toString()),id=unsigned(values[1]),size=unsigned(values[2]);
        if(! (uid!=0 && id>0 && id<=255 && size>=8 && size<=800000))return null;
        String title=TextModel.text(values[3]);if(title.length()==0)return null;
        return new CoverMeta(uid,(int)id,(int)size,title,TextModel.text(values[4]),TextModel.text(values[5]));
    }
    static CoverMeta read(String path)throws IOException{
        byte[] b=new byte[16385];FileInputStream in=new FileInputStream(path);int n;
        try{n=in.read(b);}finally{in.close();}return parse(b,n);
    }
    boolean matches(TextModel.Frame f){return f!=null && title.equals(f.title)&&artist.equals(f.artist)&&album.equals(f.album);}
    boolean same(CoverMeta m){return m!=null&&uid==m.uid&&id==m.id&&size==m.size&&title.equals(m.title)&&artist.equals(m.artist)&&album.equals(m.album);}
}
