/* Factory ARM/J9 probe. SPDX-License-Identifier: GPL-3.0-or-later */
package com.cpmap.rgi;
import java.lang.reflect.*;
import de.vw.mib.bap.mqbab2.navsd.functions.DistanceToNextManeuver;
import de.vw.mib.bap.mqbab2.generated.navsd.serializer.DistanceToNextManeuver_Status;
import de.vw.mib.bap.mqbab2.common.api.stages.BAPStageContext;

public final class TestArrowQnx {
    static int checks;
    static void check(boolean yes,String message)throws Exception{checks++;if(!yes)throw new Exception(message);}
    static LiveModel.Frame frame(int kind,int meters){
        return new LiveModel.Frame(true,13,192,meters,1000,60,1,TestRoadQnx.clock,1,LaneData.EMPTY,TestRoadQnx.clock,"",-1,kind);
    }
    static DistanceToNextManeuver_Status latest(){return (DistanceToNextManeuver_Status)TestRoadQnx.sent.get(TestRoadQnx.sent.size()-1);}
    public static void main(String[] args)throws Exception{
        Class api=Class.forName("de.vw.mib.bap.mqbab2.common.api.APIFactoryInterface");
        TestRoadQnx.set(Class.forName("de.vw.mib.bap.mqbab2.common.api.APIFactory"),"INSTANCE",TestRoadQnx.service(api));
        TestRoadQnx.set(Class.forName("de.vw.mib.asl.framework.api.framework.ASLFrameworkFactory"),"frameworkApiInstance",TestRoadQnx.service(Class.forName("de.vw.mib.asl.framework.api.framework.ASLFrameworkAPI")));
        TestRoadQnx.clock=2000;TestRoadQnx.route=0;TestRoadQnx.accept=true;
        LiveBridge b=LiveBridge.INSTANCE;DistanceToNextManeuver stage=new DistanceToNextManeuver();
        stage.setDelegate((BAPStageContext)TestRoadQnx.service(Class.forName("de.vw.mib.bap.mqbab2.common.api.stages.BAPStageContext")));stage.init(null);
        check(b.stages[1]==stage,"factory attach");
        int[] distances={201,200,150,100,50,0};
        for(int i=0;i<distances.length;i++){
            TestRoadQnx.prepare(b,frame(1,distances[i]));stage.process(-1);
            check(latest().bargraphInfo.bargraphOnOff==(i==0?0:1)&&latest().bargraphInfo.bargraph==(i==0?0:distances[i]/2),"factory countdown output");
        }
        TestRoadQnx.prepare(b,frame(22,1000));stage.process(-1);check(latest().bargraphInfo.bargraph==50,"factory off-ramp window");
        final byte[] raw=new byte[2];final int[] count={0};
        Class bits=Class.forName("de.vw.mib.bap.stream.BitStream");
        Object sink=Proxy.newProxyInstance(bits.getClassLoader(),new Class[]{bits},new InvocationHandler(){public Object invoke(Object p,Method m,Object[] a){if(m.getName().equals("pushByte"))raw[count[0]++]=((Byte)a[0]).byteValue();return null;}});
        latest().bargraphInfo.serialize((de.vw.mib.bap.stream.BitStream)sink);
        check(count[0]==2&&raw[0]==1&&raw[1]==50,"factory serialized enable and remaining percent bytes");
        TestRoadQnx.clock+=5000;b.lastTick=TestRoadQnx.clock;b.journalAt=TestRoadQnx.clock;stage.process(-1);check(latest().bargraphInfo.bargraphOnOff==0,"stale helper output cannot animate");
        TestRoadQnx.prepare(b,frame(1,100));TestRoadQnx.route=1;DistanceToNextManeuver_Status original=new DistanceToNextManeuver_Status();original.bargraphInfo.bargraph=73;
        check(!LiveBridge.distance(original)&&original.bargraphInfo.bargraph==73,"OEM handback declines override");TestRoadQnx.route=0;
        TestRoadQnx.prepare(b,new LiveModel.Frame(false,0,0,-1,0,0,0));stage.process(-1);check(latest().bargraphInfo.bargraphOnOff==0,"explicit clearing");
        stage.uninitialize();check(b.stages[1]==null,"factory detach");
        System.out.println(new StringBuffer("ARROW_FACTORY_J9_PASS checks=").append(checks).append(" factory_serialization=1 countdown=1 oem=1 clear=1").toString());
    }
}
