/* SPDX-License-Identifier: GPL-3.0-or-later */
package org.omonob.cpmap.ui;
import java.io.*;
import java.util.zip.CRC32;

/** Bounded atomic settings shared with the MU1367 native core. */
public final class DisplaySettings {
    public static final int STREAM=6, LAYOUT=7;
    private static final Object LOCK=new Object();
    private final File root;
    public static final class State {
        public final int stream,layout; public final long generation; public final String source;
        State(int s,int l,long g,String origin){stream=s;layout=l;generation=g;source=origin;}
        public int choice(int field){if(field==STREAM)return stream;if(field==LAYOUT)return layout;throw new IllegalArgumentException("Unknown display setting");}
    }
    public DisplaySettings(File directory)throws IOException {
        if(directory==null)throw new IOException("Missing settings directory");
        root=directory.getCanonicalFile();
    }
    public static DisplaySettings systemStore()throws IOException {
        String path=System.getProperty("cpmap.ui.stateDir");
        return new DisplaySettings(new File(path==null||path.length()==0?"/mnt/icab/persistent/cpmap-ui":path));
    }
    public static int count(int field){if(field!=STREAM&&field!=LAYOUT)throw new IllegalArgumentException("Unknown display setting");return 4;}
    public static String name(int field){count(field);return field==STREAM?"Map stream (reconnect)":"Turn-card layout (reconnect)";}
    public static String label(int field,int choice){
        if(choice<0||choice>=count(field))throw new IllegalArgumentException("Invalid display choice");
        String[] stream={"30 fps / IDR 20","40 fps / IDR 5","30 fps / IDR 5","40 fps / IDR 20"};
        String[] layout={"Existing narrow","Existing wide","Compact, below route bar","Upstream compact"};
        return field==STREAM?stream[choice]:layout[choice];
    }
    private File file(String name)throws IOException {
        File f=new File(root,name);
        if(!f.getAbsoluteFile().equals(f.getCanonicalFile()))throw new IOException("Settings symlink refused");
        return f;
    }
    public State read()throws IOException{synchronized(LOCK){return readLocked();}}
    private State readLocked()throws IOException {
        File main=file("display.state"),previous=file("display.previous");
        State state=decode(main,"saved");if(state!=null)return state;
        state=decode(previous,"recovered");if(state!=null)return state;
        if(main.exists()||previous.exists())throw new IOException("Damaged display preferences");
        return new State(0,0,0,"default");
    }
    public State select(int field,int choice)throws IOException {
        label(field,choice);
        synchronized(LOCK){
            State old=readLocked();
            if(old.generation==Long.MAX_VALUE)throw new IOException("Generation overflow");
            if(!root.isDirectory()&&!root.mkdirs())throw new IOException("Settings directory unavailable");
            State next=new State(field==STREAM?choice:old.stream,field==LAYOUT?choice:old.layout,old.generation+1,"saved");
            File pending=file("display.pending"),main=file("display.state"),previous=file("display.previous");
            FileOutputStream out=new FileOutputStream(pending);
            try{out.write(encode(next));out.flush();out.getFD().sync();}finally{out.close();}
            if(!same(next,decode(pending,"pending")))throw new IOException("Display readback failed");
            if(decode(main,"saved")!=null){
                if(previous.exists()&&!previous.delete())throw new IOException("Backup rotation failed");
                if(!main.renameTo(previous))throw new IOException("Backup rename failed");
            }else if(main.exists()&&!main.delete())throw new IOException("Damaged primary cannot be replaced");
            if(!pending.renameTo(main))throw new IOException("Commit failed; previous retained");
            if(!same(next,readLocked()))throw new IOException("Display commit readback failed");
            return next;
        }
    }
    private static boolean same(State a,State b){return b!=null&&a.stream==b.stream&&a.layout==b.layout&&a.generation==b.generation;}
    private static byte[] encode(State s)throws IOException {
        String body=new StringBuffer("format=1\nstream=").append(s.stream).append("\nlayout=").append(s.layout).append("\ngeneration=").append(s.generation).append('\n').toString();
        byte[] bytes=body.getBytes("US-ASCII");CRC32 crc=new CRC32();crc.update(bytes,0,bytes.length);
        return new StringBuffer(body).append("crc32=").append(Long.toHexString(crc.getValue())).append('\n').toString().getBytes("US-ASCII");
    }
    private static State decode(File file,String source)throws IOException {
        if(!file.isFile()||file.length()<1||file.length()>192)return null;
        byte[] bytes=new byte[(int)file.length()];FileInputStream in=new FileInputStream(file);int off=0;
        try{while(off<bytes.length){int n=in.read(bytes,off,bytes.length-off);if(n<=0)return null;off+=n;}if(in.read()!=-1)return null;}finally{in.close();}
        String text=new String(bytes,"US-ASCII");String[] lines=new String[5];int pos=0;
        for(int i=0;i<5;i++){int end=text.indexOf('\n',pos);if(end<0)return null;lines[i]=text.substring(pos,end);pos=end+1;}
        if(pos!=text.length()||!lines[0].equals("format=1")||lines[1].length()!=8||!lines[1].startsWith("stream=")||lines[2].length()!=8||!lines[2].startsWith("layout=")||!lines[3].startsWith("generation="))return null;
        int stream=lines[1].charAt(7)-'0',layout=lines[2].charAt(7)-'0';long gen;
        try{gen=Long.parseLong(lines[3].substring(11));}catch(NumberFormatException bad){return null;}
        if(stream<0||stream>3||layout<0||layout>3||gen<1)return null;
        State state=new State(stream,layout,gen,source);
        return text.equals(new String(encode(state),"US-ASCII"))?state:null;
    }
}
