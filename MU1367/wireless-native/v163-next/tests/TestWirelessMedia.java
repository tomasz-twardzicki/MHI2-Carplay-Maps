/* SPDX-License-Identifier: GPL-3.0-or-later */
package com.cpmap.audio;
import java.io.*;
import java.lang.reflect.*;
import org.dsi.ifc.carplay.*;
import org.dsi.ifc.global.ResourceLocator;
import de.esolutions.fw.dsi.carplay.DSICarplayDispatcher;
import de.vw.mib.asl.framework.internal.framework.ServiceManager;
import de.vw.mib.asl.framework.internal.framework.reflection.ContainerReflectionFactory;
import de.vw.mib.asl.framework.internal.dsiproxy.lr.mma.LR2dbf5283b;
import de.vw.mib.genericevents.*;
import java.util.ArrayList;
public final class TestWirelessMedia {
    static int checks,trackCalls,stateCalls,posCalls,coverCalls;static ResourceLocator locator;
    static DSICarplayListener observer;
    static void check(boolean ok,String why){checks++;if(!ok)throw new RuntimeException(why);}
    static WirelessFrame sample(long position,long status,long uid,long counter)throws Exception {
        byte[] bytes=new byte[140+5+6+5];bytes[0]='W';bytes[1]='N';bytes[2]='P';bytes[3]='1';
        le(bytes,4,1);le(bytes,8,bytes.length);le(bytes,12,23);le(bytes,16,123);le(bytes,24,1);le(bytes,28,counter);le(bytes,32,1);
        le(bytes,36,uid);le(bytes,40,counter);le(bytes,44,13);le(bytes,48,uid);le(bytes,56,90000);le(bytes,60,position);le(bytes,64,status);le(bytes,76,0x84);le(bytes,80,1);le(bytes,84,873);
        String[] text={"Title","Artist","Album","","",""};int at=128;
        for(int i=0;i<6;i++){byte[] value=text[i].getBytes("UTF8");bytes[at++]=(byte)value.length;bytes[at++]=0;System.arraycopy(value,0,bytes,at,value.length);at+=value.length;}
        return new WirelessFrame(bytes);
    }
    static void le(byte[] bytes,int at,long value){for(int i=0;i<4;i++)bytes[at+i]=(byte)(value>>(8*i));}
    static void deliver(WirelessFrame f,long clock){WirelessMedia.frame=f;WirelessMedia.observed=System.currentTimeMillis();WirelessMedia.tick(clock);}
    static ArrayList listeners=new ArrayList();
    static ArrayList pending=new ArrayList();
    static boolean defer;
    static int events;
    static void dispatch(EventGeneric event)throws Exception {
        LR2dbf5283b invoker=new LR2dbf5283b();
        for(int i=0;i<listeners.size();i++)invoker.invoke(event.getInt(2),listeners.get(i),(Object[])event.getObject(3));
    }
    static void route(final TextBridge.Source source,final DSICarplayListener observer)throws Exception {
        listeners.clear();pending.clear();defer=false;listeners.add(source);if(observer!=null)listeners.add(observer);
        ServiceManager.reflectionFactory=new ContainerReflectionFactory(null) {
            public de.vw.mib.reflection.MultipleMethodAccessibleObject getListenersMmao(int type) {
                check(type==27,"exact CarPlay listener type");return new LR2dbf5283b();
            }
        };
        final EventFactory factory=(EventFactory)Proxy.newProxyInstance(Class.forName("de.vw.mib.genericevents.EventFactory").getClassLoader(),new Class[]{Class.forName("de.vw.mib.genericevents.EventFactory")},new InvocationHandler(){
            public Object invoke(Object p,Method m,Object[] a) {return m.getName().equals("newEvent")?new EventGeneric():null;}
        });
        final EventDispatcherHSM bus=(EventDispatcherHSM)Proxy.newProxyInstance(Class.forName("de.vw.mib.genericevents.EventDispatcherHSM").getClassLoader(),new Class[]{Class.forName("de.vw.mib.genericevents.EventDispatcherHSM")},new InvocationHandler(){
            public Object invoke(Object p,Method m,Object[] a)throws Throwable {
                if(m.getName().equals("sendSafe")) {
                    EventGeneric event=(EventGeneric)a[0];events++;
                    check(event.getReceiverTargetId()==1140001 && event.getReceiverEventId()==100003,"factory notification event destination");
                    check(event.getInt(0)==27 && event.getInt(1)==0,"CarPlay service instance zero");
                    /* Event-loop boundary is controlled; the real factory
                     * event maker, indices and listener invoker are executed. */
                    if(defer)pending.add(event);else dispatch(event);
                }
                return null;
            }
        });
        ServiceManager.mGenericEventFactory=factory;
        ServiceManager.eventMain=(GenericEvents)Proxy.newProxyInstance(Class.forName("de.vw.mib.genericevents.GenericEvents").getClassLoader(),new Class[]{Class.forName("de.vw.mib.genericevents.GenericEvents")},new InvocationHandler(){
            public Object invoke(Object p,Method m,Object[] a) {
                if(m.getName().equals("getEventDispatcher"))return bus;
                if(m.getName().equals("getEventFactory"))return factory;
                return null;
            }
        });
        WirelessMediaEvents.methods=null;
    }
    public static void main(String[] args)throws Exception {
        WirelessMedia.started=true;
        TestText.main(new String[0]); // actual factory BAP text + wired lifecycle regressions
        CoverBridge.started=true;WirelessMedia.started=true;TextBridge.INSTANCE.connected=true;
        TextBridge.Source source=new TextBridge.Source((DSICarplay)TestText.service(Class.forName("org.dsi.ifc.carplay.DSICarplay")),77);TextBridge.source=source;TextBridge.epoch=77;
        DSICarplayDispatcher dispatcher=new DSICarplayDispatcher(0);
        DSICarplayDispatcher unrelated=new DSICarplayDispatcher(0);
        new DSICarplayDispatcher(1);
        observer=(DSICarplayListener)Proxy.newProxyInstance(Class.forName("org.dsi.ifc.carplay.DSICarplayListener").getClassLoader(),new Class[]{Class.forName("org.dsi.ifc.carplay.DSICarplayListener")},new InvocationHandler(){
            public Object invoke(Object p,Method m,Object[] a){
                if(m.getName().equals("hashCode"))return new Integer(System.identityHashCode(p));
                if(m.getName().equals("equals"))return Boolean.valueOf(p==a[0]);
                check(Thread.currentThread().getName().equals("main"),"media delivery remains on ASL timer thread");
                if(m.getName().equals("updateNowPlayingData")){trackCalls++;check(((TrackData)a[0]).title.equals("Title")||((TrackData)a[0]).title.length()==0,"factory track mapping");}
                if(m.getName().equals("updatePlaybackState"))stateCalls++;
                if(m.getName().equals("updatePlayposition"))posCalls++;
                if(m.getName().equals("updateCoverArtUrl")){coverCalls++;locator=(ResourceLocator)a[0];}
                return null;
            }
        });
        route(source,observer);
        WirelessMediaEvents.resolve();
        WirelessFrame f=sample(1000,1,42,1);MediaLease lease=new MediaLease();
        check(!lease.update(f.leaseRecord(),1000),"initial stale snapshot not enough");check(lease.update(sample(1000,1,42,2).leaseRecord(),1100),"advancing accepted media lease");
        check(!lease.update(sample(1000,1,42,2).leaseRecord(),2700),"producer exit expires");
        long delivered=TextBridge.INSTANCE.tracks;
        dispatcher.updateNowPlayingData(new TrackData("lost",0,"","","",""),1);
        unrelated.updateNowPlayingData(new TrackData("also lost",0,"","","",""),1);
        check(TextBridge.INSTANCE.tracks==delivered,"reproduce separate-dispatcher delivery gap");
        TextBridge.MODEL.clear();defer=true;deliver(f,1000);
        check(pending.size()==4&&trackCalls==0&&TextBridge.MODEL.frame().title.length()==0,"queued events do not bypass ASL delivery");
        check(!CoverBridge.keep(WirelessMedia.coverMeta(),77),"cover waits for delivered track metadata");
        defer=false;for(int i=0;i<pending.size();i++)dispatch((EventGeneric)pending.get(i));pending.clear();
        check(trackCalls==1&&stateCalls==1&&posCalls==1&&coverCalls==1,"factory proxy notification events reach MU subscribers");
        check(CoverBridge.keep(WirelessMedia.coverMeta(),77),"delivered track opens matching cover gate");
        check(TextBridge.MODEL.frame().title.equals("Title")&&TextBridge.MODEL.frame().artist.equals("Artist"),"same event route reaches AID text bridge");
        CoverMeta meta=WirelessMedia.coverMeta();check(meta!=null&&meta.uid==42&&meta.id==0x84,"cover bound to accepted track");
        CoverBridge.enabled=true;CoverBridge.heartbeat=1000;CoverBridge.picture=new CoverBridge.Picture(meta,17,"/var/app/icab/tmp/wireless.png",77,CoverBridge.serial);
        deliver(f,1000);check(locator!=null&&locator.url.equals("/var/app/icab/tmp/wireless.png"),"normalized cover reaches MU locator");
        check(CoverBridge.current(1000)!=null,"same image serves AID picture path");
        deliver(sample(2000,1,42,2),1100);check(trackCalls==1&&posCalls==2,"position deltas do not replay tracks");
        deliver(sample(2000,2,42,3),1200);check(stateCalls==2&&TextBridge.MODEL.frame().title.equals("Title"),"pause retains track");
        WirelessMedia.usb=true;WirelessMedia.tick(1300);check(trackCalls==1,"wired takeover never sends wireless clear");
        WirelessMedia.usb=false;deliver(sample(3000,1,43,4),1400);check(CoverBridge.current(1400)==null&&locator==null,"new track rejects same-ID prior cover");
        deliver(sample(3000,0,43,5),1500);check(TextBridge.MODEL.frame().title.length()==0,"stopped clears AID model");
        deliver(sample(3000,1,43,6),1550);check(TextBridge.MODEL.frame().title.equals("Title"),"resume after stop restores retained track");
        WirelessMedia.observed=System.currentTimeMillis()-2000;WirelessMedia.tick(1600);check(WirelessMedia.current()==null&&locator==null,"expired producer clears media");
        check(CoverBridge.current(1600)==null,"expired session cannot serve prior picture");
        System.out.println(new StringBuffer("WIRELESS_MEDIA_JAVA_PASS checks=").append(checks).append(" factory_proxy_events=1 separate_dispatchers=1 event_loop_boundary_stubbed=1 wired_regression=1").toString());
    }
}
