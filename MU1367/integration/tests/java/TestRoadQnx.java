/* Exact factory J9 probe, never installed. SPDX-License-Identifier: GPL-3.0-or-later */
package com.cpmap.rgi;
import java.lang.reflect.*;
import java.util.ArrayList;
import de.vw.mib.bap.mqbab2.navsd.functions.TurnToInfo;
import de.vw.mib.bap.mqbab2.generated.navsd.serializer.TurnToInfo_Status;
import de.vw.mib.bap.mqbab2.common.api.stages.BAPStageContext;

public final class TestRoadQnx {
    static long clock=1000;static int route;static boolean accept=true;static ArrayList sent=new ArrayList();static int checks;
    static void check(boolean yes,String why)throws Exception{checks++;if(!yes)throw new Exception(why);}
    static void set(Class c,String n,Object value)throws Exception{Field f=c.getDeclaredField(n);f.setAccessible(true);f.set(null,value);}
    static Object service(final Class type){
        return Proxy.newProxyInstance(type.getClassLoader(),new Class[]{type},new InvocationHandler(){
            public Object invoke(Object p,Method m,Object[] args)throws Exception{
                String n=m.getName();Class t=m.getReturnType();
                if(n.equals("getSystemTimeMillis"))return new Long(clock);
                if(n.equals("getSmarphoneIntegrationActiveConnectionType"))return new Integer(2);
                if(n.equals("getRouteGuidanceState"))return new Integer(route);
                if(n.equals("getTurnToInfoStreet"))return "OEM Road";
                if(n.equals("getTurnToInfoSignPost"))return "";
                if(n.equals("isSetupLaneGuidanceActive"))return Boolean.TRUE;
                if(n.equals("dequeueBAPEntity"))return ((Class)args[1]).newInstance();
                if(n.equals("statusProperty")){sent.add(args[0]);return accept?Boolean.TRUE:Boolean.FALSE;}
                if(t.isInterface())return service(t);
                if(t==Integer.TYPE)return new Integer(0);if(t==Long.TYPE)return new Long(0);if(t==Boolean.TYPE)return Boolean.FALSE;
                return null;
            }
        });
    }
    static LiveModel.Frame frame(String road,long at){return new LiveModel.Frame(true,13,192,30,1000,60,1,clock,1,LaneData.EMPTY,at,road,at);}
    static void prepare(LiveBridge b,LiveModel.Frame f){b.selected=f;b.context=0;b.mode=2;b.lastTick=clock;b.journalAt=clock;}
    public static void main(String[] args)throws Exception{
        set(Class.forName("de.vw.mib.bap.mqbab2.common.api.APIFactory"),"INSTANCE",service(Class.forName("de.vw.mib.bap.mqbab2.common.api.APIFactoryInterface")));
        set(Class.forName("de.vw.mib.asl.framework.api.framework.ASLFrameworkFactory"),"frameworkApiInstance",service(Class.forName("de.vw.mib.asl.framework.api.framework.ASLFrameworkAPI")));
        set(Class.forName("de.vw.mib.format.internal.ServiceManager"),"configurationManager",service(Class.forName("de.vw.mib.configuration.ConfigurationManager")));
        String road=RoadName.decode(" \tŁódź\r\nTestowa\0".getBytes("UTF-8"));check(road.equals("Łódź Testowa"),"factory UTF8 normalization");
        byte[] emoji={(byte)0xf0,(byte)0x9f,(byte)0x9a,(byte)0x97};check(RoadName.decode(emoji).length()==2,"factory supplementary UTF8");
        LiveBridge b=LiveBridge.INSTANCE;prepare(b,frame(road,clock));
        TurnToInfo stage=new TurnToInfo();stage.setDelegate((BAPStageContext)service(Class.forName("de.vw.mib.bap.mqbab2.common.api.stages.BAPStageContext")));stage.init(null);
        check(b.stages[6]==stage,"actual factory hook attach");stage.process(-1);
        check(((TurnToInfo_Status)sent.get(sent.size()-1)).turnToInfo.toString().equals(road),"actual patched factory output");
        accept=false;b.refreshPending=0;b.refreshing=true;stage.process(-1);check((b.refreshPending&64)!=0,"factory queue rejection tracked");accept=true;b.refreshing=false;
        clock+=LiveModel.HOLD_MS+1000;prepare(b,frame(road,1000));stage.process(-1);check(((TurnToInfo_Status)sent.get(sent.size()-1)).turnToInfo.toString().equals(""),"independent road expiry");
        prepare(b,frame(road,clock));route=1;stage.process(-1);check(((TurnToInfo_Status)sent.get(sent.size()-1)).turnToInfo.toString().equals("OEM Road"),"factory OEM priority");route=0;
        prepare(b,new LiveModel.Frame(false,0,0,-1,0,0,0));stage.process(-1);check(((TurnToInfo_Status)sent.get(sent.size()-1)).turnToInfo.toString().equals(""),"factory explicit clearing");
        StringBuffer longRoad=new StringBuffer();for(int i=0;i<128;i++)longRoad.append("ł");String limited=RoadName.decode(longRoad.toString().getBytes("UTF-8"));
        check(limited.getBytes("UTF-8").length==74,"factory byte bound");TurnToInfo_Status out=new TurnToInfo_Status();out.turnToInfo.setContent(limited);check(out.turnToInfo.toString().equals(limited),"factory BAP string bound");
        stage.uninitialize();check(b.stages[6]==null,"actual factory detach");
        System.out.println(new StringBuffer("ROAD_FACTORY_J9_PASS checks=").append(checks).append(" output=1 oem=1 clear=1 utf8=1").toString());
    }
}
