/* SPDX-License-Identifier: GPL-3.0-or-later */
package com.cpmap.rgi;
import java.lang.reflect.*;
import de.esolutions.fw.dsi.navigation.DSINavigationDispatcher;
import de.esolutions.fw.dsi.cartimeunitslanguage.DSICarTimeUnitsLanguageDispatcher;
import org.dsi.ifc.navigation.*;
import org.dsi.ifc.cartimeunitslanguage.*;
public final class TestGpsProbe {
    static int delivered;
    static void check(boolean ok,String why){if(!ok)throw new RuntimeException(why);}
    static Object observer(String name)throws Exception{
        Class type=Class.forName(name);
        return Proxy.newProxyInstance(type.getClassLoader(),new Class[]{type},new InvocationHandler(){
            public Object invoke(Object proxy,Method method,Object[] args){
                if(method.getName().equals("hashCode"))return new Integer(System.identityHashCode(proxy));
                if(method.getName().equals("equals"))return Boolean.valueOf(proxy==args[0]);
                if(method.getName().startsWith("update"))delivered++;
                return null;
            }
        });
    }
    public static void main(String[] args)throws Exception{
        TestRoadLabel.run();
        DSINavigationDispatcher nav=new DSINavigationDispatcher(0);
        DSICarTimeUnitsLanguageDispatcher clock=new DSICarTimeUnitsLanguageDispatcher(0);
        nav.addNotificationListener(28,(org.dsi.ifc.base.DSIListener)observer("org.dsi.ifc.navigation.DSINavigationListener"));
        clock.addNotificationListener(9,(org.dsi.ifc.base.DSIListener)observer("org.dsi.ifc.cartimeunitslanguage.DSICarTimeUnitsLanguageListener"));
        GpsProbe.enabled=false;
        clock.updateClockGPSSyncData(new ClockGPSSyncData(new ClockTime(),new ClockDate()),1);
        clock.updateClockSource(3,1);
        check(GpsProbe.bootClocks==1&&GpsProbe.bootSources==1&&GpsProbe.clocks==0,"initial clock kept without enabling probe or service lookup");
        check(GpsProbe.snapshot(1234).indexOf("bootstrap_clock captured_at=-1 age_ms=-1 utc_qualified=0")>=0,"unknown bootstrap timestamp never becomes fresh UTC");
        PosPosition p=new PosPosition();p.state=2;p.latitude=123;p.longitude=-456;p.speed=78;
        GpsProbe.enabled=false;nav.updateSoPosPosition(p,1);check(GpsProbe.positions==0,"probe disabled");
        int before=delivered;GpsProbe.enabled=true;nav.updateSoPosPosition(p,1);
        check(GpsProbe.positions==1,"actual factory dispatcher calls probe");
        check(delivered==before+1,"original OEM listener still receives position");
        ClockGPSSyncData data=new ClockGPSSyncData(new ClockTime(),new ClockDate());
        data.date.year=2026;data.date.month=11;data.date.day=20;data.time.hours=12;data.time.minutes=34;data.time.seconds=56;
        clock.updateClockGPSSyncData(data,1);clock.updateClockSource(3,1);nav.updateEtcDemoModeState(true,1);
        String text=GpsProbe.snapshot(1234);
        check(text.indexOf("forwarding=0")>=0&&text.indexOf("latitude_raw=123 longitude_raw=-456")>=0,"raw coordinates only");
        check(text.indexOf("year=2026 month=11 day=20 hour=12 minute=34 second=56")>=0,"raw clock retained");
        check(text.indexOf("source_raw=3")>=0&&text.indexOf("active=1")>=0,"source and demo state visible");
        new DSINavigationDispatcher(1).updateSoPosPosition(p,1);
        check(GpsProbe.snapshot(1234).indexOf("instance=1")>=0,"dispatcher instances remain distinguishable");
        nav.updateSoPosPosition(null,3);clock.updateClockGPSSyncData(null,3);
        check(GpsProbe.snapshot(1234).indexOf("null=1")>=0,"null validity updates retained");
        for(int i=0;i<200;i++)nav.updateSoPosPosition(p,1);
        text=GpsProbe.snapshot(1234);int lines=0;for(int i=0;i<text.length();i++)if(text.charAt(i)=='\n')lines++;
        check(lines==35&&text.length()<16384,"bounded rolling RAM snapshot");
        GpsProbe.enabled=false;long count=GpsProbe.positions;nav.updateSoPosPosition(p,1);check(GpsProbe.positions==count,"disable stops observation");
        if(new java.io.File("/ramdisk").isDirectory()){
            new java.io.File("/ramdisk/app").mkdir();new java.io.File(GpsProbe.ROOT).mkdirs();
            java.io.FileOutputStream state=new java.io.FileOutputStream(new java.io.File(GpsProbe.ROOT,"STATE"));state.write("installed\n".getBytes("US-ASCII"));state.close();
            java.io.File flag=new java.io.File(GpsProbe.FLAG);java.io.FileOutputStream option=new java.io.FileOutputStream(flag);option.write("1\n".getBytes("US-ASCII"));option.close();
            GpsProbe.poll(5000);check(GpsProbe.enabled,"explicit probe opt-in");
            nav.updateSoPosPosition(p,1);GpsProbe.poll(6000);
            check(new java.io.File(GpsProbe.PATH).length()>0,"atomic RAM export");
            check(flag.delete(),"probe off flag");GpsProbe.poll(7000);
            check(!GpsProbe.enabled&&!new java.io.File(GpsProbe.PATH).exists(),"disable removes RAM export");
            java.io.File mode=new java.io.File(RoadName.ROOT,"road-label.mode");option=new java.io.FileOutputStream(mode);option.write("next\n".getBytes("US-ASCII"));option.close();
            RoadName.poll(8000);check(RoadName.mode==RoadName.NEXT,"GEM next mode read by worker");
            option=new java.io.FileOutputStream(mode);option.write("off\n".getBytes("US-ASCII"));option.close();RoadName.poll(9000);check(RoadName.mode==RoadName.OFF,"GEM off mode");
            check(mode.delete(),"remove mode preference");RoadName.poll(10000);check(RoadName.mode==RoadName.CURRENT,"missing mode keeps existing current-road default");
            System.out.println("GPS_PROBE_RAM_PASS opt_in=1 atomic_export=1 disable_clears=1");
        }
        System.out.println("GPS_PROBE_PASS actual_factory_dispatchers=1 original_listener_preserved=1 bounded=1 forwarding=0");
    }
}
