/* SPDX-License-Identifier: GPL-3.0-or-later */
package com.cpmap.rgi;
import java.io.*;
import de.vw.mib.bap.mqbab2.generated.navsd.serializer.*;
public final class TestWirelessEndToEnd {
    static int checks;
    static void check(boolean ok,String why){checks++;if(!ok)throw new AssertionError(why);}
    static byte[] wireless(byte[] b){check(b[0]==0 && b[1]==6 && b[2]==0 && b[3]==0,"component TLV fixture");b[4]=0;b[5]=1;return b;}
    static void event(DataOutputStream out,int id,byte[] payload)throws Exception{out.writeShort(id);out.writeShort(payload.length);out.write(payload);}
    public static void main(String[] args)throws Exception {
        File root=new File(args[0]);root.mkdirs();File input=new File(root,"events.bin");
        DataOutputStream out=new DataOutputStream(new FileOutputStream(input));
        event(out,0,new byte[0]);
        byte[] route=TestLanes.join(TestLanes.join(TestLanes.tlv(0,TestLanes.u16(1)),TestLanes.tlv(1,new byte[]{1})),TestLanes.join(TestLanes.tlv(13,TestLanes.u16(7)),TestLanes.join(TestLanes.tlv(16,TestLanes.u16(7)),TestLanes.tlv(18,new byte[]{1}))));
        event(out,0x5201,route);
        byte[] maneuver=TestLanes.join(TestLanes.tlv(0,TestLanes.u16(1)),TestLanes.join(TestLanes.tlv(1,TestLanes.u16(7)),TestLanes.tlv(3,new byte[]{1})));
        event(out,0x5202,maneuver);
        event(out,0x5204,wireless(TestLanes.instruction(7,TestLanes.sample())));
        event(out,0x5201,route);event(out,0xffff,new byte[0]);out.close();
        Process process=new ProcessBuilder(new String[]{args[1],input.toString(),root.toString()}).inheritIO().start();check(process.waitFor()==0,"native publisher exit");
        File latest=new File(root,"latest.bin");MailboxReader reader=new MailboxReader(latest.toString(),1),wired=new MailboxReader(latest.toString());LiveModel.Frame frame=null;
        for(int i=0;i<5;i++) {
            TestRecovery.write(latest,TestRecovery.read(new File(root,i+".bin")));
            frame=reader.next(1000+i*100);LiveModel.Frame wrong=wired.next(1000+i*100);
            check(wrong==null || !wrong.active,"wireless component cannot activate wired reader");
        }
        check(frame!=null && frame.active && frame.progress>0 && frame.lanes.length==3,"native publisher -> component 1 model incl lanes");
        TestLive.installMocks();TestLive.connection=2;LiveBridge.phone=2;LiveBridge.wirelessActive=true;
        LiveBridge bridge=TestLive.bridge();bridge.root=LiveBridge.WCP_ROOT;bridge.incoming=frame;bridge.journalAt=TestLive.clock=frame.changed;bridge.tick(TestLive.clock);
        check(bridge.owned,"wireless frame acquires existing BAP publisher");
        LaneGuidance_ChangedArray lanes=TestLanes.factory();check(lanes.laneGuidanceOnOff==1 && lanes.getArrayData().size()==3,"factory lane array output");
        TestRecovery.write(latest,TestRecovery.read(new File(root,"5.bin")));frame=reader.next(1600);check(!frame.active,"native session-loss envelope clears output");
        bridge.incoming=frame;bridge.journalAt=TestLive.clock=1600;bridge.tick(TestLive.clock);check(!bridge.owned,"wireless disconnect releases BAP ownership");
        LiveBridge.wirelessActive=false;
        check(new FeedRecovery(LiveBridge.WCP_ROOT).reader.component==1,"production wireless reader component");
        check(new FeedRecovery(LiveBridge.ROOT).reader.component==16 && new FeedRecovery(LiveBridge.AA_ROOT).reader.component==16,"wired/AA components retained");
        System.out.println("WIRELESS_NATIVE_E2E_PASS checks="+checks+" c_publisher=1 factory_lanes=1 component_isolation=1 disconnect_clear=1");
    }
}
