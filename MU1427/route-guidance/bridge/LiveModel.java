/* SPDX-License-Identifier: GPL-3.0-or-later
 * Bounded runtime decoder. Protocol/mapping adapted from rgi_decode.py and
 * rgi_maneuver.py; LuKa reference attribution is recorded in NATIVE-BRIDGE.md.
 * No HMI, device I/O, logging of payloads, or dependency on Java > 1.2 APIs.
 */
package com.cpmap.rgi;

import java.io.IOException;

public final class LiveModel {
    static final int SNAP = 33088;
    static final class Message {
        int id;
        long[] v = new long[21];
        byte[][] raw = new byte[21][];
        boolean[] has = new boolean[21];
        int[] components, order;
    }
    public static final class Frame {
        public final boolean active, validDistance;
        public final int main, direction, meters, remainingMeters, remainingSeconds;
        public final long progress, changed, epoch;
        Frame(boolean a, int m, int d, int distance, long p, long c, long e) {
            this(a,m,d,distance,-1,-1,p,c,e);
        }
        Frame(boolean a, int m, int d, int distance, int remaining, int seconds, long p, long c, long e) {
            remainingMeters=remaining; remainingSeconds=seconds;
            active=a; main=m; direction=d; meters=distance; validDistance=distance>=0;
            progress=p; changed=c; epoch=e;
        }
    }
    private long sec=-1, nsec=-1, wireSession=-1, high=0, seen=0;
    private long progress=0, changed=-1, epoch=0;
    private int state=-1, generation=0, distance=-1, distanceHead=-1, distanceGeneration=-1;
    private int remainingMeters=-1, remainingSeconds=-1;
    private int[] order=new int[0];
    private Message[] cache=new Message[32];
    private long[] ages=new long[32];
    private long age;
    private byte[] source, destination;
    private byte[][] retained=new byte[16][];

    static void require(boolean condition) throws IOException {
        if (!condition) throw new IOException("RGI structural validation failed");
    }
    public static long u32(byte[] b, int p) {
        return (b[p]&255L) | (b[p+1]&255L)<<8 | (b[p+2]&255L)<<16 | (b[p+3]&255L)<<24;
    }
    static int be16(byte[] b, int p) { return (b[p]&255)<<8 | b[p+1]&255; }
    static int u16(byte[] b, int p) { return (b[p]&255) | (b[p+1]&255)<<8; }
    static byte[] copy(byte[] b, int p, int n) {
        byte[] result=new byte[n]; System.arraycopy(b,p,result,0,n); return result;
    }
    static boolean equal(byte[] a, byte[] b) {
        if (a==null || b==null) return a==b;
        if (a.length!=b.length) return false;
        for (int i=0;i<a.length;i++) if (a[i]!=b[i]) return false;
        return true;
    }
    // Strict UTF-8, optional one trailing NUL, no embedded/control characters.
    static void text(byte[] b, int p, int n, int max) throws IOException {
        require(n<=max); int end=p+n;
        if (n>0 && b[end-1]==0) end--;
        while (p<end) {
            int c=b[p++]&255, count=0, value=c, min=0;
            if (c>=0xc2 && c<=0xdf) { count=1; value=c&31; min=128; }
            else if (c>=0xe0 && c<=0xef) { count=2; value=c&15; min=2048; }
            else if (c>=0xf0 && c<=0xf4) { count=3; value=c&7; min=65536; }
            else require(c<128);
            require(p+count<=end);
            for (int i=0;i<count;i++) { c=b[p++]&255; require((c&192)==128); value=(value<<6)|(c&63); }
            require(value>=min && value<=0x10ffff && !(value>=0xd800 && value<=0xdfff));
            require(!(value<32 && value!=9 && value!=10 && value!=13) && !(value>=127 && value<160));
        }
    }
    // Encoding: positive=scalar width, -1=text256, -2=text64, -3=u16 list,
    // -4=signed angle list, -5=nested TLVs. Unknown IDs stay opaque.
    static final int[] ROUTE={-3,1,1,-1,-1,8,8,4,-2,1,4,-2,1,-3,2,1,2,2,1,-2,1};
    static final int[] MANEUVER={-3,2,-1,1,-1,4,-2,1,1,1,-4,2,2,-1};
    static final int[] LANE={-3,2,-5,-1};
    static void nested(byte[] b, int p, int end) throws IOException {
        int count=0;
        while (p<end) { require(end-p>=4 && ++count<=256); int n=be16(b,p); require(n>=4 && p+n<=end); p+=n; }
    }
    static Message decode(int id, byte[] b, int p, int length) throws IOException {
        require(id==0x5201 || id==0x5202 || id==0x5204);
        Message m=new Message(); m.id=id; int end=p+length, count=0, angles=0, nestedCount=0;
        int[] schema=id==0x5201?ROUTE:id==0x5202?MANEUVER:LANE;
        while (p<end) {
            require(end-p>=4 && ++count<=256); int n=be16(b,p), key=be16(b,p+2);
            require(n>=4 && p+n<=end); int at=p+4, size=n-4; p+=n;
            if (key>=schema.length) continue;
            int kind=schema[key]; boolean repeat=kind==-4 || kind==-5;
            require(!m.has[key] || repeat); m.has[key]=true;
            if (kind>0) {
                require(size==kind); long value=0;
                for (int i=0;i<size;i++) value=(value<<8)|(b[at+i]&255L);
                if (id==0x5202 && key==11) value=(short)value;
                m.v[key]=value;
            } else if (kind==-1 || kind==-2) {
                text(b,at,size,kind==-1?256:64);
                if (id==0x5201 && (key==4 || key==19)) {
                    if (size>0 && b[at+size-1]==0) size--;
                    m.raw[key]=copy(b,at,size);
                }
            } else if (kind==-3 || kind==-4) {
                require(size%2==0 && size/2<=(key==0?8:16));
                if (kind==-4) { angles+=size/2; require(angles<=16); }
                else {
                    int[] list=new int[size/2];
                    for (int i=0;i<list.length;i++) list[i]=be16(b,at+2*i);
                    if (key==0) m.components=list; else m.order=list;
                }
            } else {
                nested(b,at,at+size);
                for (int q=at;q<at+size;q+=be16(b,q)) require(++nestedCount<=256);
            }
        }
        require(m.components!=null && m.components.length>0);
        for (int i=0;i<m.components.length;i++) for (int j=0;j<i;j++) require(m.components[i]!=m.components[j]);
        require(id==0x5201 || m.has[1]); return m;
    }
    private void clearCache() {
        cache=new Message[32]; ages=new long[32]; order=new int[0];
        distance=-1; distanceHead=-1; distanceGeneration=-1; generation++;
        remainingMeters=remainingSeconds=-1;
    }
    public void invalidate() { clearCache(); state=-1; source=destination=null; seen=0; changed=-1; epoch++; }
    private int head() { return order.length>0?order[0]:-1; }
    private Message current() {
        if (state!=1 && state!=6) return null;
        for (int i=0;i<cache.length;i++) if (cache[i]!=null && cache[i].v[1]==head()) return cache[i];
        return null;
    }
    private boolean apply(Message m) {
        boolean component=false;
        for (int i=0;i<m.components.length;i++) if (m.components[i]==0x10) component=true;
        if (!component) return false;
        if (m.id!=0x5201) {
            if (state!=1 && state!=3 && state!=4 && state!=5 && state!=6) return false;
            if (m.id==0x5204) return true; // validated; no lane geometry is projected
            int slot=-1;
            for (int i=0;i<cache.length;i++) {
                if (cache[i]==null) { if (slot<0) slot=i; }
                else if (cache[i].v[1]==m.v[1]) { slot=i; break; }
            }
            if (slot<0) {
                // Same bounded eviction order as the host: outside order first,
                // then furthest lookahead. Never evict the current head.
                long oldest=Long.MAX_VALUE; int furthest=-1;
                for (int i=0;i<cache.length;i++) {
                    int index=(int)cache[i].v[1], rank=-1;
                    if (index==head()) continue;
                    for (int j=0;j<order.length;j++) if (order[j]==index) rank=j;
                    if (rank<0 && ages[i]<oldest) { slot=i; oldest=ages[i]; }
                    if (slot<0 && rank>furthest) furthest=rank;
                }
                if (slot<0) for (int i=0;i<cache.length;i++) if (cache[i].v[1]==order[furthest]) slot=i;
            }
            if (slot<0) return false;
            cache[slot]=m; ages[slot]=++age; return true;
        }
        int next=m.has[1]?(int)m.v[1]:state;
        boolean sourceChange=m.has[19] && source!=null && !equal(source,m.raw[19]);
        boolean destChange=m.has[4] && destination!=null && destination.length>0 && m.raw[4].length>0 && !equal(destination,m.raw[4]);
        if (next==0 && state!=0 || next>0 && state<=0 || (next==3 || next==5) && state>0 && state!=next || sourceChange || destChange || next>6) {
            clearCache(); destination=null; if (sourceChange) source=null;
        }
        state=next;
        if (m.has[19]) source=m.raw[19];
        if (next>=1 && next<=6) {
            if (m.has[4]) destination=m.raw[4];
            if (m.has[13]) order=m.order;
        }
        if (next!=1 && next!=6) remainingMeters=remainingSeconds=-1;
        if (next==2) { cache=new Message[32]; distance=-1; }
        return true;
    }
    public Frame snapshot(byte[] b, long now, boolean bootstrap) throws IOException {
        require(b.length>=64 && b.length<=SNAP);
        long sequence=u32(b,20), count=u32(b,24), session=u32(b,16), s=u32(b,40), ns=u32(b,44);
        require(u32(b,0)==0x31494752L && u32(b,4)==1 && u32(b,8)==SNAP && (u32(b,12)&1)==0);
        require(u32(b,28)<=1 && u32(b,32)==0 && u32(b,36)<=1 && ns<1000000000L);
        require(count==Math.min(sequence,16) && (u32(b,36)!=0 || sequence==0) && (u32(b,36)==0 || session!=0));
        for (int i=48;i<64;i+=4) require(u32(b,i)==0);
        Message[] messages=new Message[(int)count]; byte[][] bytes=new byte[(int)count][];
        int pos=64;
        boolean same=sec==s && nsec==ns && wireSession==session;
        if (same) require(sequence>=high);
        // Validate every event and immutable overlap before mutating cache.
        for (int i=0;i<count;i++) {
            require(pos+16<=b.length); long seq=sequence-count+1+i;
            int id=u16(b,pos+4), length=u16(b,pos+6);
            require(u32(b,pos)==seq && u32(b,pos+8)==session && u32(b,pos+12)==0 && length<=2048 && pos+16+length<=b.length);
            messages[i]=decode(id,b,pos+16,length); bytes[i]=copy(b,pos,16+length);
            byte[] previous=retained[(int)((seq-1)&15)];
            if (same && seq<=high && previous!=null && u32(previous,0)==seq) require(equal(previous,bytes[i]));
            pos+=16+length;
        }
        require(pos==b.length);
        long oldHigh=same?high:sequence;
        if (!same) { invalidate(); sec=s; nsec=ns; wireSession=session; high=0; retained=new byte[16][]; }
        if (count>0 && sequence-count+1>seen+1) invalidate();
        if (u32(b,28)!=0 || u32(b,36)==0) { invalidate(); }
        else for (int i=0;i<count;i++) {
            long seq=sequence-count+1+i;
            if (seq>seen) {
                boolean accepted=apply(messages[i]);
                if (head()!=distanceHead || generation!=distanceGeneration || current()==null) distance=-1;
                distanceHead=current()==null?-1:head(); distanceGeneration=generation;
                if (accepted && seq>oldHigh && !bootstrap) {
                    progress++; changed=now;
                    Message m=messages[i];
                    if (m.id==0x5201 && (state==1 || state==6)) {
                        if (m.has[7]) remainingMeters=m.v[7]>=0 && m.v[7]<=Integer.MAX_VALUE?(int)m.v[7]:-1;
                        // Unsigned u64 input, bounded to factory RTT's 99h59m.
                        if (m.has[6]) remainingSeconds=m.v[6]>=0 && m.v[6]<=359940?(int)m.v[6]:-1;
                    }
                    if (m.id==0x5201 && m.has[10] && current()!=null) distance=m.v[10]<=Integer.MAX_VALUE?(int)m.v[10]:-1;
                }
            }
        }
        for (int i=0;i<count;i++) retained[(int)((sequence-count+i)&15)]=bytes[i];
        high=sequence; seen=sequence;
        return frame();
    }
    public Frame frame() {
        int[] symbol=map(current());
        return new Frame((state==1 || state==6) && changed>=0,symbol[0],symbol[1],distance,remainingMeters,remainingSeconds,progress,changed,epoch);
    }
    static int turn(int a) { int n=Math.abs(a); return n<=22?0:n<=67?(a<0?32:224):n<=112?(a<0?64:192):(a<0?96:160); }
    static int[] symbol(int main,int direction) { return new int[]{main,direction}; }
    static int[] map(Message m) {
        if (m==null || !m.has[3]) return symbol(0,0);
        int t=(int)m.v[3], a=(int)m.v[11], j=m.has[9]?(int)m.v[9]:-1, side=m.has[8]?(int)m.v[8]:-1;
        boolean angle=m.has[11] && a>=-180 && a<=180, sideKnown=side==0 || side==1;
        if (t<0 || t>53) return symbol(0,0);
        if (t==0 || t==5 || t==15 || t==17) return symbol(11,0);
        if (t==10 || t==12 || t==27) return symbol(3,0);
        if (t==52 || t==53) return symbol(12,t==52?64:192);
        if (t==11 || t==16 || t==51) return angle?symbol(13,turn(a)):symbol(0,0);
        if (j!=0 && j!=1) return symbol(0,0);
        if (t==6) return sideKnown?symbol(13,side==1?64:192):symbol(0,0);
        if (t==7 || t==19 || t>=28 && t<=46) {
            if (j!=1 || !sideKnown) return symbol(0,0);
            if (t==7) return symbol(side==1?27:26,side==1?64:192);
            if (t==19) return symbol(side==1?22:21,128);
            int[] bins={128,112,96,80,64,48,32,16,0,240,224,208,192,176,160,144,128};
            return angle?symbol(side==1?22:21,bins[((a+180)*4+45)/90]):symbol(0,0);
        }
        if (j!=0) return symbol(0,0);
        if (t==24 || t==25) return symbol(3,t==24?64:192);
        int d=-1;
        if (t==1 || t==20) d=64; else if (t==2 || t==21) d=192; else if (t==3) d=0;
        else if (t==13 || t==22 || t==49) d=32; else if (t==14 || t==23 || t==50) d=224;
        else if (t==47) d=96; else if (t==48) d=160;
        if (d>=0) {
            if (angle && (t==20 && a<0 || t==21 && a>0)) d=Math.abs(a)<=67?(t==20?32:224):Math.abs(a)>112?(t==20?96:160):d;
            return symbol(13,d);
        }
        if (t==4 || t==18 || t==26) {
            if (angle && a!=0) return symbol(25,a<0?64:192);
            return sideKnown?symbol(25,side==1?192:64):symbol(0,0);
        }
        if ((t==8 || t==9) && angle && a!=0) return symbol(13,a<0?32:224);
        return symbol(0,0);
    }
}
