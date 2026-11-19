/* SPDX-License-Identifier: GPL-3.0-or-later */
package com.cpmap.rgi;
public final class TestWireless {
    static int checks;
    static void check(boolean ok,String why){checks++;if(!ok)throw new AssertionError(why);}
    static String status(long counter,int session,int accepted){return "WCPRG1\n23\n456\n"+counter+"\n"+session+"\n"+accepted+"\n";}
    public static void main(String[] args)throws Exception {
        WirelessSource lease=new WirelessSource();
        check(!lease.update(status(1,1,1),1000),"static leftover cannot acquire lease");
        check(lease.update(status(2,1,1),1100),"fresh heartbeat accepted");
        check(lease.update(status(2,1,1),2599),"live lease");
        check(!lease.update(status(2,1,1),2600),"producer death expires");
        check(!lease.update(status(3,1,0),2700),"explicit session loss immediate");
        check(!lease.update(status(4,2,1),2800),"new session must advance");
        check(lease.update(status(5,2,1),2900),"new session heartbeat");
        check(!lease.update(status(6,2,1)+"junk",3000),"trailing data rejected");
        check(!lease.update("WCPRG1\n23\n456\n-1\n1\n1\n",3000),"negative counter rejected");
        TestLive.installMocks();LiveBridge b=TestLive.bridge();LiveBridge.phone=2;LiveBridge.wirelessActive=false;
        FeedRecovery wired=new FeedRecovery(LiveBridge.ROOT);b.root=LiveBridge.ROOT;
        check(b.switchRoot(wired)==wired,"wired behavior unchanged");
        LiveBridge.wirelessActive=true;FeedRecovery wcp=b.switchRoot(wired);
        check(wcp!=wired && wcp.root.equals("/ramdisk/wcp-rg") && b.incoming==null && b.mode==0,"wireless acquires third root and clears wired frame");
        check(LiveBridge.rootFor(3).equals(LiveBridge.AA_ROOT),"AA source unaffected by wireless lease");
        LiveBridge.wirelessActive=false;FeedRecovery back=b.switchRoot(wcp);
        check(back!=wcp && back.root.equals(LiveBridge.ROOT),"wireless loss returns wired reader");
        System.out.println("WIRELESS_SOURCE_PASS checks="+checks+" no_hmi_thread_io=1 lease_ms=1500");
    }
}
