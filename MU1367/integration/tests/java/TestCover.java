/* SPDX-License-Identifier: GPL-3.0-or-later. Host/factory-J9 probe, never installed. */
package com.cpmap.audio;
import java.lang.reflect.*;
import java.util.*;
import org.dsi.ifc.carplay.TrackData;
import org.dsi.ifc.global.ResourceLocator;
import org.dsi.ifc.kombipictureserver.DSIKombiPictureServer;
import de.vw.mib.bap.mqbab2.common.api.APIFactory;
import de.vw.mib.bap.mqbab2.common.api.stages.BAPStageContext;
import de.vw.mib.bap.mqbab2.audiosd.functions.CurrentStationHandle;
import de.vw.mib.bap.mqbab2.generated.audiosd.serializer.CurrentStation_Handle_Status;
import de.vw.mib.asl.internal.kombipictureserver.usecaces.CoverArt;

public final class TestCover {
    static int checks,component=6,connection=2;static volatile long clock=1000;static boolean accept=true;
    static ArrayList sends=new ArrayList(),answers=new ArrayList();
    static void check(boolean ok,String why)throws Exception{checks++;if(!ok)throw new Exception(why);}
    static void set(Class c,String name,Object value)throws Exception{Field f=c.getDeclaredField(name);f.setAccessible(true);f.set(null,value);}
    static Object service(final Class type){
        return Proxy.newProxyInstance(type.getClassLoader(),new Class[]{type},new InvocationHandler(){
            public Object invoke(Object p,Method m,Object[] args)throws Exception{
                String n=m.getName();Class t=m.getReturnType();
                if(n.equals("getSystemTimeMillis"))return new Long(clock);
                if(n.equals("getSmarphoneIntegrationActiveConnectionType"))return new Integer(connection);
                if(n.equals("getCurrentAudioComponent"))return new Integer(component);
                if(n.equals("getUserInfo"))return new Integer(1);
                if(n.equals("dequeueBAPEntity"))return ((Class)args[1]).newInstance();
                if(n.equals("statusProperty")){sends.add(args[0]);return accept?Boolean.TRUE:Boolean.FALSE;}
                if(n.equals("responseCoverArt")){answers.add(args);return null;}
                if(t.isInterface())return service(t);
                if(t==Boolean.TYPE)return Boolean.FALSE;
                if(t==Integer.TYPE)return new Integer(0);
                if(t==Long.TYPE)return new Long(0);
                return null;
            }
        });
    }
    static CoverMeta meta(String uid,String id,String size)throws Exception{
        String s=new StringBuffer("@nowplaying\nMediaItemPersistentIdentifier::").append(uid).append("\nMediaItemArtworkFileTransferIdentifier::").append(id).append("\nMediaItemArtworkSize::").append(size).append("\nMediaItemTitle::Title\nMediaItemArtist::Artist\nMediaItemAlbumTitle::Album\nPlaybackStatus::Playing\n").toString();
        byte[] b=s.getBytes("UTF8");return CoverMeta.parse(b,b.length);
    }
    static Object[] lastAnswer(){return (Object[])answers.get(answers.size()-1);}
    static void answer(int handle,int status)throws Exception{
        CoverArt cover=new CoverArt();Field f=Class.forName("de.vw.mib.asl.internal.kombipictureserver.usecaces.CoverArt").getDeclaredField("_kombiPictureServer");f.setAccessible(true);f.set(cover,CoverBridge.server);
        int n=answers.size();cover.dsiKombiPictureServerIndicationCoverArt(handle,0,19);
        check(answers.size()==n+1,"actual patched CoverArt request hook");
        Object[] a=lastAnswer();check(((Integer)a[3]).intValue()==status,"request status");
        check(status==1?a[4]!=null:a[4]==null,"request locator/clear");
    }
    public static void main(String[] args)throws Exception{
        set(Class.forName("de.vw.mib.bap.mqbab2.common.api.APIFactory"),"INSTANCE",service(Class.forName("de.vw.mib.bap.mqbab2.common.api.APIFactoryInterface")));
        set(Class.forName("de.vw.mib.asl.framework.api.framework.ASLFrameworkFactory"),"frameworkApiInstance",service(Class.forName("de.vw.mib.asl.framework.api.framework.ASLFrameworkAPI")));
        set(Class.forName("de.vw.mib.format.internal.ServiceManager"),"configurationManager",service(Class.forName("de.vw.mib.configuration.ConfigurationManager")));
        CoverBridge.started=true;CoverBridge.enabled=true;TextBridge.INSTANCE.connected=true;TextBridge.epoch=7;
        CoverMeta m=meta("ffffffffffffffff","7","600");check(m.uid==-1L,"factory padded-hex unsigned 64-bit UID");
        check(meta("0000000000000010","7","600").uid==16L,"numeric-only factory UID is hexadecimal");
        check(CoverMeta.unsigned("0x123456789abcdef0")==0x123456789abcdef0L,"hex identity");
        check(meta("0000000000000000","7","600")==null&&meta("0000000000000001","0","600")==null&&meta("0000000000000001","256","600")==null,"invalid identities");
        check(meta("0000000000000001","7","800001")==null&&meta("0000000000000001","7","7")==null,"image bounds");
        String[] bad={"18446744073709551616","-1","1e3","0x10000000000000000",""};
        for(int i=0;i<bad.length;i++){boolean rejected=false;try{CoverMeta.unsigned(bad[i]);}catch(java.io.IOException expected){rejected=true;}check(rejected,"numeric ambiguity rejected");}
        String dup="MediaItemTitle::a\nMediaItemTitle::b\n";boolean rejected=false;
        try{CoverMeta.parse(dup.getBytes("UTF8"),dup.length());}catch(java.io.IOException expected){rejected=true;}check(rejected,"duplicate PPS keys rejected");
        TextBridge.MODEL.track(new TrackData("Title",1,"Album","Artist","",""),1);
        CurrentStationHandle handle=new CurrentStationHandle();handle.setDelegate((BAPStageContext)service(Class.forName("de.vw.mib.bap.mqbab2.common.api.stages.BAPStageContext")));handle.init(null);
        check(CoverBridge.stage==handle,"actual factory stage attach");
        CoverBridge.server((DSIKombiPictureServer)service(Class.forName("org.dsi.ifc.kombipictureserver.DSIKombiPictureServer")));
        CoverBridge.picture=new CoverBridge.Picture(m,17,"/var/app/icab/tmp/synthetic.png",7,CoverBridge.serial);CoverBridge.heartbeat=clock;
        CoverBridge.tick(clock);
        check(((CurrentStation_Handle_Status)sends.get(sends.size()-1)).fsgHandle==17,"factory BAP publishes our handle");
        check(CoverBridge.sent==17&&CoverBridge.pushed==17,"ack then proactive picture refresh");
        answer(17,1);answer(16,2);
        int count=sends.size(),replyCount=answers.size();clock+=200;CoverBridge.heartbeat=clock;CoverBridge.tick(clock);
        check(sends.size()==count&&answers.size()==replyCount,"unchanged cover does not flood transport");
        // Delayed second artwork on the same track gets a distinct handle and a new push.
        CoverBridge.picture=new CoverBridge.Picture(m,18,"/var/app/icab/tmp/synthetic-2.png",7,CoverBridge.serial);clock+=1000;CoverBridge.heartbeat=clock;accept=false;CoverBridge.tick(clock);
        check(CoverBridge.sent==17,"transport rejection does not claim acceptance");answer(18,2);
        accept=true;clock+=1000;CoverBridge.heartbeat=clock;CoverBridge.tick(clock);check(CoverBridge.sent==18,"rejected handle retried with backoff");answer(18,1);answer(17,2);
        clock+=3000;CoverBridge.tick(clock);check(CoverBridge.sent==-1,"hung worker lease clears handle");answer(18,2);
        CoverBridge.heartbeat=clock;clock+=1000;CoverBridge.tick(clock);check(CoverBridge.sent==18,"live worker can restore matching cover");
        component=1;CurrentStation_Handle_Status stock=new CurrentStation_Handle_Status();stock.fsgHandle=42;CoverBridge.fill(stock);
        check(stock.fsgHandle==42,"OEM source/handle preserved");check(!CoverBridge.answer(CoverBridge.server,18,0,19),"OEM picture service remains authoritative");
        component=6;TextBridge.MODEL.clear();check(CoverBridge.picture==null,"stop/disconnect/invalid metadata clears cover immediately");
        CoverBridge.picture=new CoverBridge.Picture(m,19,"/var/app/icab/tmp/synthetic-3.png",7,CoverBridge.serial);CoverBridge.heartbeat=clock;
        check(CoverBridge.current(clock)==null,"different text cannot acquire an old image");
        TextBridge.MODEL.track(new TrackData("Title",1,"Album","Artist","",""),1);TextBridge.epoch=8;check(CoverBridge.current(clock)==null,"prior session cannot acquire same-title image");
        handle.uninitialize();check(CoverBridge.stage==null,"actual factory detach");
        check(CoverBridge.failures==0,"no adapter/linkage failures");System.out.println(new StringBuffer("ARTWORK_JAVA_PASS checks=").append(checks).toString());
    }
}
