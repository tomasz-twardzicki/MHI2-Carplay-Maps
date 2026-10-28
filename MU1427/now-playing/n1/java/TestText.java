/* SPDX-License-Identifier: GPL-3.0-or-later. Host-only integration harness. */
package com.cpmap.audio;
import java.lang.reflect.*;
import java.util.*;
import org.dsi.ifc.carplay.*;
import de.vw.mib.bap.mqbab2.common.api.APIFactory;
import de.vw.mib.bap.mqbab2.common.api.stages.BAPStageContext;
import de.vw.mib.bap.mqbab2.audiosd.functions.CurrentStationInfo;
import de.vw.mib.bap.mqbab2.generated.audiosd.serializer.CurrentStationInfo_Status;

public final class TestText {
    static int checks, connection=2, component=6;
    static long clock=1000;
    static boolean accept=true;
    static ArrayList<CurrentStationInfo_Status> sent=new ArrayList<CurrentStationInfo_Status>();
    static void check(boolean ok,String why) { checks++; if(!ok) throw new AssertionError(why); }
    static void set(Class c,String field,Object value) throws Exception {
        Field f=c.getDeclaredField(field); f.setAccessible(true); f.set(null,value);
    }
    static Object service(final Class type) {
        return Proxy.newProxyInstance(type.getClassLoader(),new Class[]{type},new InvocationHandler() {
            public Object invoke(Object p,Method m,Object[] args) throws Exception {
                String n=m.getName(); Class t=m.getReturnType();
                if(n.equals("getSystemTimeMillis")) return Long.valueOf(clock);
                if(n.equals("getSmarphoneIntegrationActiveConnectionType")) return Integer.valueOf(connection);
                if(n.equals("getCurrentAudioComponent")) return Integer.valueOf(component);
                if(n.equals("getUserInfo")) return Integer.valueOf(1);
                if(n.equals("dequeueBAPEntity")) return ((Class)args[1]).newInstance();
                if(n.equals("statusProperty")) {
                    check(Thread.currentThread().getName().equals("main"),"output on event thread");
                    sent.add((CurrentStationInfo_Status)args[0]); return Boolean.valueOf(accept);
                }
                if(t.isInterface()) return service(t);
                if(t==Boolean.TYPE) return Boolean.FALSE;
                if(t==Integer.TYPE) return Integer.valueOf(0);
                if(t==Long.TYPE) return Long.valueOf(0);
                return null;
            }
        });
    }
    static String content(Object value) throws Exception {
        return value.toString();
    }
    static CurrentStationInfo_Status last() { return sent.get(sent.size()-1); }
    static void tick() { clock+=250; TextBridge.INSTANCE.tick(clock); }
    static TrackData track(String title,String artist,String album) { return new TrackData(title,12,album,artist,"",""); }
    public static void main(String[] args) throws Exception {
        set(APIFactory.class,"INSTANCE",service(Class.forName("de.vw.mib.bap.mqbab2.common.api.APIFactoryInterface")));
        set(Class.forName("de.vw.mib.asl.framework.api.framework.ASLFrameworkFactory"),"frameworkApiInstance",
            service(Class.forName("de.vw.mib.asl.framework.api.framework.ASLFrameworkAPI")));
        set(Class.forName("de.vw.mib.format.internal.ServiceManager"),"configurationManager",service(Class.forName("de.vw.mib.configuration.ConfigurationManager")));
        TextModel model=new TextModel();
        model.track(track("Title","Artist","Album"),1);
        check(model.frame().title.equals("Title") && model.frame().artist.equals("Artist"),"native field order");
        model.track(track("bad\ntext",null,"album"),1);
        check(model.frame().title.equals("") && model.frame().artist.equals(""),"control/null clear");
        model.track(track("bad\ud800","bad\udc00",""),1);
        check(model.frame().title.equals("") && model.frame().artist.equals(""),"malformed UTF16 rejected");
        char[] many=new char[257]; Arrays.fill(many,'x'); many[255]='\ud83d'; many[256]='\ude00';
        model.track(track(new String(many),"Beyonc\u00e9",null),1);
        check(model.frame().title.length()==255 && model.frame().artist.equals("Beyonc\u00e9"),"bounded Unicode, no split pair");
        for(int valid=0;valid<=2;valid+=2) {
            model.track(track("old","old","old"),1); model.track(null,valid);
            check(model.frame().title.length()==0,"invalid clears");
        }
        CurrentStationInfo stage=new CurrentStationInfo();
        stage.setDelegate((BAPStageContext)service(BAPStageContext.class));
        stage.init(null);
        TextBridge.Source input=new TextBridge.Source((DSICarplay)service(DSICarplay.class),1);
        TextBridge.source=input;
        input.updateNowPlayingData(track("PRIVATE_TITLE","PRIVATE_ARTIST","PRIVATE_ALBUM"),1);
        tick();
        check(content(last().primaryInformation).equals("PRIVATE_TITLE"),"actual factory text send");
        check(content(last().secondaryInformation).equals("PRIVATE_ARTIST") && last().si_Type==73,"artist mapping");
        check(content(last().tertiaryInformation).equals("PRIVATE_ALBUM") && last().ti_Type==74 && last().pi_Type==72,"album/title types");
        int count=sent.size(); tick(); check(sent.size()==count,"no duplicate timer sends");
        clock+=60000; tick(); check(TextBridge.MODEL.frame().title.equals("PRIVATE_TITLE"),"long track has no TTL");
        PlaybackInfo info=new PlaybackInfo(); info.status=2; input.updatePlaybackState(info,1);
        check(TextBridge.MODEL.frame().title.equals("PRIVATE_TITLE"),"pause retains text");
        info.status=0; input.updatePlaybackState(info,1); tick();
        check(content(last().primaryInformation).equals("Apple CarPlay") && content(last().secondaryInformation).equals("") && last().si_Type==0,"stop clears to factory label");
        input.updateNowPlayingData(track("next",null,null),1); accept=false; tick();
        long rejected=TextBridge.INSTANCE.rejected; accept=true; tick();
        check(rejected>0 && content(last().primaryInformation).equals("next"),"queue rejection retried");
        connection=0; TextBridge.connection(APIFactory.getAPIFactory().getSmartphoneIntegrationService());
        input.updateNowPlayingData(track("stale","stale","stale"),1);
        check(TextBridge.MODEL.frame().title.equals(""),"disconnected callbacks cannot revive cache");
        connection=2; TextBridge.connection(APIFactory.getAPIFactory().getSmartphoneIntegrationService()); tick();
        check(content(last().primaryInformation).equals("Apple CarPlay"),"reconnect requires new text");
        input.updateNowPlayingData(track("fresh","a","b"),1); tick();
        component=2;
        CurrentStationInfo_Status stock=new CurrentStationInfo_Status();
        check(!TextBridge.fill(stock),"other audio component owns output");
        tick(); int stockCount=sent.size();
        input.updateNowPlayingData(track("fresh","a","b"),1); tick();
        check(sent.size()==stockCount,"phone changes do not refresh another audio source");
        component=6; tick();
        check(!content(last().primaryInformation).equals("fresh"),"stock source-switch suppression is retained");
        stage.timerFired((de.vw.mib.bap.array.timer.Timer)service(de.vw.mib.bap.array.timer.Timer.class));
        check(content(last().primaryInformation).equals("fresh"),"stock deferred timer returns to phone source");
        clock+=2000;
        CurrentStationInfo_Status expired=new CurrentStationInfo_Status();
        check(TextBridge.fill(expired) && content(expired.primaryInformation).equals("Apple CarPlay"),"expired ASL lease clears all text");
        TextBridge.accepted(true,stage); tick();
        check(content(last().primaryInformation).equals("fresh"),"timer renews valid same-session track after fallback");
        input.updateNowPlayingData(track("bad",null,null),2); tick();
        check(content(last().primaryInformation).equals("Apple CarPlay") && last().ti_Type==0,"invalid native track clears old tails");
        input.updateNowPlayingData(track("Beyonc\u00e9","artist","album"),1); tick();
        check(content(last().primaryInformation).equals("Beyonc\u00e9"),"factory BAP Unicode path");
        connection=3;
        check(!TextBridge.fill(stock),"other phone protocol remains stock");
        connection=2;
        input.updateNowPlayingData(track("fresh","a","b"),1);
        input.live=false; input.updateNowPlayingData(track("late","late","late"),1);
        check(TextBridge.MODEL.frame().title.equals("fresh"),"late listener ignored");
        input.asyncException(1,"private ignored",0);
        check(TextBridge.INSTANCE.failures==0,"late exception ignored");
        stage.uninitialize(); check(!TextBridge.fill(stock),"actual factory stage detach cannot override");
        check(TextBridge.INSTANCE.failures==0,"no bridge failures");
        System.out.println("{\"text_assertions\":"+checks+"}");
    }
}
