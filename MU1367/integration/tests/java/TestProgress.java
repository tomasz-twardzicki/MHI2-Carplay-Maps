/* SPDX-License-Identifier: GPL-3.0-or-later. Host and factory ARM J9 regression. */
package com.cpmap.audio;
import java.lang.reflect.*;
import org.dsi.ifc.carplay.*;
import de.vw.mib.bap.datatypes.BAPEntity;
import de.vw.mib.bap.functions.PropertyListener;
import de.vw.mib.bap.mqbab2.common.api.stages.*;
import de.vw.mib.bap.mqbab2.generated.audiosd.*;
import de.vw.mib.bap.mqbab2.generated.audiosd.serializer.*;
import de.vw.mib.bap.mqbab2.audiosd.functions.FunctionList;
import de.vw.mib.bap.stream.BitStreamTransformer;
import de.vw.mib.bap.marshalling.BAPService;

public final class TestProgress {
    static int checks;static byte[] bytes;
    static int dsiCalls,forwardedEvents;
    static void check(boolean ok,String why)throws Exception{checks++;if(!ok)throw new Exception(why);}
    static PlayPosition_Status last(){return (PlayPosition_Status)TestCover.sends.get(TestCover.sends.size()-1);}
    static TrackData track(String title,int duration){return new TrackData(title,duration,"Album","Artist","","");}
    static void tick(){TestCover.clock+=200;TextBridge.INSTANCE.lastTick=TestCover.clock;TrackProgress.tick(TestCover.clock);}
    public static void main(String[] args)throws Exception{
        TestCover.set(Class.forName("de.vw.mib.bap.mqbab2.common.api.APIFactory"),"INSTANCE",TestCover.service(Class.forName("de.vw.mib.bap.mqbab2.common.api.APIFactoryInterface")));
        TestCover.set(Class.forName("de.vw.mib.asl.framework.api.framework.ASLFrameworkFactory"),"frameworkApiInstance",TestCover.service(Class.forName("de.vw.mib.asl.framework.api.framework.ASLFrameworkAPI")));
        TestCover.connection=2;TestCover.component=6;TestCover.clock=1000;TextBridge.INSTANCE.connected=true;
        TextBridge.INSTANCE.lastTick=TestCover.clock;TextBridge.MODEL.clear();
        // Exercise the actual patched pool registration (all stock factories null).
        BAPAudioSDDataPool pool=new BAPAudioSDDataPool(null);
        Method init=pool.getClass().getDeclaredMethod("initializeInternal",new Class[]{Class.forName("de.vw.mib.bap.mqbab2.generated.audiosd.AudioSDBindingFactory")});init.setAccessible(true);
        init.invoke(pool,new Object[]{TestCover.service(Class.forName("de.vw.mib.bap.mqbab2.generated.audiosd.AudioSDBindingFactory"))});
        check(pool.getStage(52) instanceof TrackProgress&&pool.getProperty(52)!=null,"actual BAP pool owns progress function");
        FunctionList list=new FunctionList();list.setDelegate((BAPStageContext)TestCover.service(Class.forName("de.vw.mib.bap.mqbab2.common.api.stages.BAPStageContext")));
        check(((FunctionList_FctList)list.init(null)).fctPlayPositionAvailable,"actual advertised capability");
        TrackProgress stage=(TrackProgress)pool.getStage(52);
        stage.setDelegate((BAPStageContext)TestCover.service(Class.forName("de.vw.mib.bap.mqbab2.common.api.stages.BAPStageContext")));stage.init(null);
        TextBridge.Source input=new TextBridge.Source(null,1);TextBridge.source=input;
        input.updateNowPlayingData(track("Title",240000),1);input.updatePlayposition(65000,1);tick();
        check(last().timePosition==65&&last().totalPlayTime==240,"milliseconds to seconds");
        int count=TestCover.sends.size();tick();check(TestCover.sends.size()==count,"unchanged values suppressed");
        input.updatePlayposition(65999,1);tick();check(TestCover.sends.size()==count,"sub-second input suppressed");
        input.updatePlayposition(66000,1);tick();check(last().timePosition==66,"next second delivered");
        PlaybackInfo info=new PlaybackInfo();info.status=2;input.updatePlaybackState(info,1);
        TestCover.clock+=60000;tick();check(last().timePosition==66,"pause never extrapolates");
        info.status=1;input.updatePlaybackState(info,1);input.updatePlayposition(10000,1);tick();
        check(last().timePosition==10,"backward seek");input.updatePlayposition(200000,1);tick();check(last().timePosition==200,"forward seek");
        input.updateNowPlayingData(track("Title",240000),1);tick();check(last().timePosition==200,"duplicate metadata retains position");
        input.updateNowPlayingData(track("Next",180000),1);tick();check(last().timePosition==0&&last().totalPlayTime==180,"new track drops previous position");
        input.updatePlayposition(200000,1);tick();check(last().timePosition==180,"position bounded by duration");
        input.updatePlayposition(-1,1);tick();check(last().timePosition==0,"negative position invalidated");
        input.updatePlayposition(45000,1);tick();input.updatePlayposition(50000,2);tick();check(last().timePosition==0,"invalid DSI flag clears position");
        input.updateNowPlayingData(track("Live",0),1);input.updatePlayposition(80000,1);tick();check(last().timePosition==0&&last().totalPlayTime==0,"unknown duration hides progress");
        input.updateNowPlayingData(track("Long",Integer.MAX_VALUE),1);input.updatePlayposition(Integer.MAX_VALUE,1);tick();
        check(last().timePosition==65534&&last().totalPlayTime==65534,"wire width cannot wrap");
        TestCover.clock+=2000;PlayPosition_Status expired=stage.value();check(expired.totalPlayTime==0,"expired ASL lease clears progress");
        tick();TestCover.component=1;tick();check(last().timePosition==0&&last().totalPlayTime==0,"radio handback clears progress");
        count=TestCover.sends.size();input.updatePlayposition(70000,1);tick();check(TestCover.sends.size()==count,"phone updates cannot flood radio");
        TestCover.component=6;tick();check(last().timePosition==70,"return to current phone track");
        info.status=0;input.updatePlaybackState(info,1);tick();check(last().totalPlayTime==0,"stop clears progress");
        TextBridge.INSTANCE.connected=false;input.updateNowPlayingData(track("Late",200000),1);input.updatePlayposition(99000,1);
        TextBridge.INSTANCE.connected=true;tick();check(last().totalPlayTime==0,"disconnected callbacks ignored");
        input.updateNowPlayingData(track("Fresh",200000),1);input.updatePlayposition(30000,1);tick();input.live=false;
        input.updatePlayposition(90000,1);tick();check(last().timePosition==30,"old listener position ignored");
        // Actual factory serializer -> actual marshaller -> byte-sequence service.
        BAPService transport=(BAPService)Proxy.newProxyInstance(Class.forName("de.vw.mib.bap.marshalling.BAPService").getClassLoader(),new Class[]{Class.forName("de.vw.mib.bap.marshalling.BAPService")},new InvocationHandler(){
            public Object invoke(Object p,Method m,Object[] a)throws Exception{
                check(m.getName().equals("requestByteSequence")&&((Integer)a[0]).intValue()==52&&((Integer)a[1]).intValue()==7,"native BAP function/opcode");
                bytes=(byte[])a[2];return null;
            }});
        PlayPosition_Status out=stage.value();new AudioSDMarshaller(transport,new BitStreamTransformer()).statusEntity(52,out);
        check(bytes.length==6,"exact wire payload length");
        PlayPosition_Status decoded=new PlayPosition_Status(BitStreamTransformer.newBitStreamForValue(bytes));
        check(decoded.timePosition==30&&decoded.totalPlayTime==200&&!decoded.attributes.variableBitRateActive&&decoded.bufferLevel==0,"factory wire roundtrip");
        // Exercise the real service proxy rather than ending at a mock marshaller.
        final Object listener=Proxy.newProxyInstance(Class.forName("org.dsi.ifc.bap.DSIBAPListener").getClassLoader(),new Class[]{Class.forName("org.dsi.ifc.bap.DSIBAPListener")},new InvocationHandler(){
            public Object invoke(Object p,Method m,Object[] a){forwardedEvents++;return null;}});
        final Object dsi=Proxy.newProxyInstance(Class.forName("org.dsi.ifc.bap.DSIBAP").getClassLoader(),new Class[]{Class.forName("org.dsi.ifc.bap.DSIBAP")},new InvocationHandler(){
            public Object invoke(Object p,Method m,Object[] a)throws Exception{
                check(m.getName().equals("requestByteSequence")&&((Integer)a[0]).intValue()==49&&((Integer)a[1]).intValue()==52&&((Integer)a[2]).intValue()==7,"exact native service handoff");dsiCalls++;return null;}});
        Object lcu=Proxy.newProxyInstance(Class.forName("de.vw.mib.asl.api.bap.lcu.BAPLogicalControlUnit").getClassLoader(),new Class[]{Class.forName("de.vw.mib.asl.api.bap.lcu.BAPLogicalControlUnit")},new InvocationHandler(){
            public Object invoke(Object p,Method m,Object[] a){
                if(m.getName().equals("getLogicalControlUnitID"))return new Integer(49);
                if(m.getName().equals("getService"))return dsi;
                if(m.getName().equals("getServiceListener"))return listener;return null;}});
        de.vw.mib.bap.mqbab2.common.marshalling.BAPServiceProxy proxy=new de.vw.mib.bap.mqbab2.common.marshalling.BAPServiceProxy((de.vw.mib.asl.api.bap.lcu.BAPLogicalControlUnit)lcu);
        long calls=AudioDiagnostics.nativeCalls,returns=AudioDiagnostics.nativeReturns;
        new AudioSDMarshaller(proxy,new BitStreamTransformer()).statusEntity(52,out);
        check(dsiCalls==1&&AudioDiagnostics.nativeCalls==calls+1&&AudioDiagnostics.nativeReturns==returns+1,"native diagnostics bracket actual call");
        check(AudioDiagnostics.nativePosition==30&&AudioDiagnostics.nativeTotal==200,"numeric payload retained independently of attempt counter");
        de.vw.mib.bap.internal.dispatcher.BAPDispatcherTarget dispatcher=new de.vw.mib.bap.internal.dispatcher.BAPDispatcherTarget();
        Field registered=dispatcher.getClass().getDeclaredField("registeredBAPControlUnits");registered.setAccessible(true);
        ((de.vw.mib.collections.ints.IntObjectOptHashMap)registered.get(dispatcher)).put(49,lcu);
        long acks=AudioDiagnostics.acks,errors=AudioDiagnostics.errors,indications=AudioDiagnostics.indications;
        dispatcher.acknowledge(49,52,0);dispatcher.indicationError(49,52,66);dispatcher.indicationVoid(49,52,2);
        check(AudioDiagnostics.acks==acks+1&&AudioDiagnostics.lastAck==0&&AudioDiagnostics.errors==errors+1&&AudioDiagnostics.lastError==66&&AudioDiagnostics.indications==indications+1&&forwardedEvents==3,"real dispatcher observes and preserves native callback forwarding");
        dispatcher.indicationError(49,51,66);check(AudioDiagnostics.errors==errors+1&&forwardedEvents==4,"other functions never attributed to progress");
        count=TestCover.sends.size();stage.indicationError(66,null);input.live=true;input.updatePlayposition(31000,1);tick();
        check(TestCover.sends.size()==count&&TrackProgress.lastIndicationError==66,"function rejection rate limits retries and records error");
        stage.initialize(false);tick();check(TestCover.sends.size()==count+1,"new initialization allows negotiation again");
        stage.indicationError(35,null);input.updatePlayposition(32000,1);tick();count=TestCover.sends.size();tick();
        check(TestCover.sends.size()==count,"transient error retry is rate limited");
        TestCover.clock+=1000;tick();check(TestCover.sends.size()==count+1&&last().timePosition==32,"transient error recovers after bounded delay");
        stage.uninitialize();check(TrackProgress.stage==null&&TrackProgress.failures==0,"detach, no bridge failures");
        System.out.println(new StringBuffer("AUDIO_PROGRESS_PASS checks=").append(checks).toString());
    }
}
