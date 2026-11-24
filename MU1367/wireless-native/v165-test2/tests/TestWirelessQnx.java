/* SPDX-License-Identifier: GPL-3.0-or-later */
package com.cpmap.rgi;
final class TestWirelessQnx {
    static int checks;
    static void check(boolean ok){checks++;if(!ok)throw new RuntimeException(new StringBuffer("wireless factory J9 contract ").append(checks).toString());}
    static byte[] join(byte[] a,byte[] b){byte[] c=new byte[a.length+b.length];System.arraycopy(a,0,c,0,a.length);System.arraycopy(b,0,c,a.length,b.length);return c;}
    static byte[] u16(int x){return new byte[]{(byte)(x>>8),(byte)x};}
    static byte[] tlv(int key,byte[] value){byte[] h=new byte[4];h[0]=(byte)((value.length+4)>>8);h[1]=(byte)(value.length+4);h[2]=(byte)(key>>8);h[3]=(byte)key;return join(h,value);}
    static void le(byte[] b,int at,int value){for(int i=0;i<4;i++)b[at+i]=(byte)(value>>(8*i));}
    static byte[] snapshot(byte[][] events){byte[] b=new byte[64];le(b,0,0x31494752);le(b,4,1);le(b,8,33088);le(b,16,1);le(b,20,events.length);le(b,24,events.length);le(b,36,1);le(b,40,42);
        for(int i=0;i<events.length;i++){byte[] e=new byte[16];le(e,0,i+1);int id=i==0?0x5201:0x5204;e[4]=(byte)id;e[5]=(byte)(id>>8);e[6]=(byte)events[i].length;e[7]=(byte)(events[i].length>>8);le(e,8,1);b=join(b,join(e,events[i]));}return b;}
    static void run()throws Exception {
        DriverSide coding=new DriverSide();
        new java.io.File("/ramdisk/driver-persist").mkdir();
        check(coding.write("/mnt/persist",2));
        java.io.FileInputStream saved=new java.io.FileInputStream("/mnt/persist/cpmap-driver-side.state");
        byte[] codingBytes=new byte[8];int codingCount=saved.read(codingBytes);saved.close();
        check(codingCount==8 && new String(codingBytes,"US-ASCII").equals("CPDS1\n2\n"));
        coding.poll(); // Factory context absent: unknown must preserve cache.
        check(new java.io.File("/mnt/persist/cpmap-driver-side.state").length()==8);
        WirelessSource lease=new WirelessSource();check(!lease.update("WCPRG1\n23\n456\n1\n1\n1\n",1000));check(lease.update("WCPRG1\n23\n456\n2\n1\n1\n",1100));check(!lease.update("WCPRG1\n23\n456\n2\n1\n1\n",2600));
        LiveModel wireless=new LiveModel(1),wired=new LiveModel();wireless.snapshot(snapshot(new byte[0][]),1000,true);wired.snapshot(snapshot(new byte[0][]),1000,true);
        byte[] route=join(join(tlv(0,u16(1)),tlv(1,new byte[]{1})),join(tlv(13,new byte[0]),join(tlv(16,u16(7)),tlv(18,new byte[]{1}))));
        byte[] lane=join(join(tlv(0,u16(0)),tlv(1,new byte[]{2})),join(tlv(2,u16(90)),tlv(3,u16(90))));
        byte[] lanes=join(tlv(1,u16(7)),tlv(2,lane));
        LiveModel.Frame frame=wireless.snapshot(snapshot(new byte[][]{route,lanes}),1100,false);
        check(frame.active && frame.progress>0 && frame.lanes.length==1);
        check(!wired.snapshot(snapshot(new byte[][]{route,lanes}),1100,false).active);
        check(new FeedRecovery(LiveBridge.WCP_ROOT).reader.component==1);
        check(new FeedRecovery(LiveBridge.ROOT).reader.component==16 && new FeedRecovery(LiveBridge.AA_ROOT).reader.component==16);
        System.out.println(new StringBuffer("WIRELESS_FACTORY_J9_PASS checks=").append(checks).append(" source_component=1 lane_default=1 wired_isolation=1").toString());
    }
}
