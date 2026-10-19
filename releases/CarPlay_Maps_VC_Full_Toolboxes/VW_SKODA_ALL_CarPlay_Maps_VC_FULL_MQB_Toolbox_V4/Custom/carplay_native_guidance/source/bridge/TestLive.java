/* Host-only tests; reflection/proxies are never included in the unit JAR. */
package com.cpmap.rgi;
import java.io.*;
import java.lang.reflect.*;
import java.util.*;
import de.vw.mib.bap.mqbab2.common.api.APIFactory;
import de.vw.mib.bap.mqbab2.common.api.stages.Function;
import de.vw.mib.bap.mqbab2.common.api.stages.BAPStageContext;
import de.vw.mib.bap.mqbab2.generated.navsd.serializer.*;

public final class TestLive {
    static int checks, connection=2, route=0, status=0, unit=0;
    static long clock=1000;
    static boolean accept=true;
    static ArrayList<Object> sent=new ArrayList<Object>();
    static ArrayList<String> threads=new ArrayList<String>();
    static void check(boolean ok,String message) { checks++; if (!ok) throw new AssertionError(message); }
    static Object proxy(Class<?> type,InvocationHandler h) { return Proxy.newProxyInstance(type.getClassLoader(),new Class[]{type},h); }
    static Object zero(Class<?> t) {
        if (t==Integer.TYPE) return Integer.valueOf(0); if (t==Long.TYPE) return Long.valueOf(0);
        if (t==Boolean.TYPE) return Boolean.FALSE; return null;
    }
    static final class FactoryFormatter extends de.vw.mib.format.internal.FixFormatBaseImpl {
        protected void initServices() {} // host fixture: numeric factory methods are unchanged
    }
    static Object named(String type,final String kind) throws Exception {
        return proxy(Class.forName(type),new InvocationHandler() {
            public Object invoke(Object p,Method m,Object[] a) throws Throwable {
                String n=m.getName(); Class<?> t=m.getReturnType();
                if (n.equals("getFixFormatter")) return new FactoryFormatter();
                if (n.equals("getNavigationService")) return named(t.getName(),"nav");
                if (n.equals("getSmartphoneIntegrationService")) return named(t.getName(),"phone");
                if (n.equals("getServices") || n.equals("getTimerManager") || n.equals("getSystemService")) return named(t.getName(),n);
                if (n.equals("getSystemTimeMillis")) return Long.valueOf(clock);
                if (n.equals("getSmarphoneIntegrationActiveConnectionType")) return Integer.valueOf(connection);
                if (n.equals("getCurrentDistanceUnit")) return Integer.valueOf(unit);
                if (n.equals("getNavigationStatus")) return Integer.valueOf(status);
                if (n.equals("getRouteGuidanceState")) return Integer.valueOf(route);
                if (n.equals("getManeuverDescriptor") || n.equals("getLaneGuidance")) return Collections.EMPTY_LIST.iterator();
                if (n.equals("getDistanceToNextManeuver")) return named(t.getName(),"distance");
                if (n.equals("getDistanceToNextManeuverDistance")) return Integer.valueOf(88);
                if (n.startsWith("cnv")) { int[] out=(int[])a[1]; out[0]=88; out[1]=0; return null; }
                if (n.equals("dequeueBAPEntity")) return ((Class<?>)a[1]).newInstance();
                if (n.equals("getPropertyListener")) return named(t.getName(),"sink");
                if (n.equals("statusProperty")) { sent.add(a[0]); threads.add(Thread.currentThread().getName()); return Boolean.valueOf(accept); }
                return zero(t);
            }
        });
    }
    static void set(Class<?> c,String field,Object value) throws Exception { Field f=c.getDeclaredField(field); f.setAccessible(true); f.set(null,value); }
    static void installMocks() throws Exception {
        set(Class.forName("de.vw.mib.format.internal.ServiceManager"),"configurationManager",named("de.vw.mib.configuration.ConfigurationManager","config"));
        set(APIFactory.class,"INSTANCE",named("de.vw.mib.bap.mqbab2.common.api.APIFactoryInterface","api"));
        set(Class.forName("de.vw.mib.asl.framework.api.framework.ASLFrameworkFactory"),"frameworkApiInstance",named("de.vw.mib.asl.framework.api.framework.ASLFrameworkAPI","framework"));
    }
    static LiveBridge bridge() throws Exception {
        LiveBridge b=LiveBridge.INSTANCE;
        b.floor=-1; b.lastRun=0; b.runSerial=0; b.lastTick=clock; b.context=0; b.mode=2;
        b.owned=b.clearing=false; b.selected=null; b.refreshPending=0;
        b.incoming=new LiveModel.Frame(true,13,192,0,12340,3661,1,clock,1); b.journalAt=clock;
        String[] names={"ManeuverDescriptor","DistanceToNextManeuver","RGStatus","DistanceToDestination","TimeToDestination"};
        for (int i=0;i<names.length;i++) {
            Function f=(Function)Class.forName("de.vw.mib.bap.mqbab2.navsd.functions."+names[i]).newInstance();
            f.setDelegate((BAPStageContext)named(BAPStageContext.class.getName(),"context")); b.stages[i<3?i:i+1]=f;
        }
        return b;
    }
    static void integration() throws Exception {
        installMocks();
        check(LiveBridge.convertDistance(20,false)[0]==200,"factory tenfold distance scale");
        LiveBridge b=bridge();
        b.tick(clock); check(b.owned && sent.size()==5,"five factory properties published");
        check(((ManeuverDescriptor_Status)sent.get(0)).maneuver_1.direction==192,"factory descriptor output");
        check(((DistanceToNextManeuver_Status)sent.get(1)).validityInformation.distanceToNextManeuverValid,"zero distance valid");
        check(((DistanceToNextManeuver_Status)sent.get(1)).distanceToNextManeuver.distance==0,"zero retained");
        check(((RG_Status_Status)sent.get(2)).rg_Status==1,"RG active");
        DistanceToDestination_Status total=(DistanceToDestination_Status)sent.get(3);
        check(total.validityInformation.distanceToDestinationValid && total.distanceToDestination.distance==120 && total.distanceToDestination.unit==1,"factory route distance conversion");
        TimeToDestination_Status duration=(TimeToDestination_Status)sent.get(4);
        check(duration.timeInfo.timeInfoType==0 && duration.timeInfo.hour==1 && duration.timeInfo.minute==2,"remaining duration rounded up to minutes");
        check(duration.validityInformation.timeInfo_HourIsValid && duration.validityInformation.timeInfo_MinuteIsValid,"remaining duration valid");
        check(!duration.validityInformation.timeInfo_DayIsAvailableToBeDisplayed,"duration has no date");
        b.selected=new LiveModel.Frame(true,13,192,30,0,0,1,clock,1);
        DistanceToNextManeuver_Status scaled=new DistanceToNextManeuver_Status(); LiveBridge.distance(scaled);
        check(scaled.distanceToNextManeuver.distance==400 && scaled.distanceToNextManeuver.unit==0,"30 meters uses factory rounding and tenfold BAP scale");
        b.selected=new LiveModel.Frame(true,13,192,Integer.MAX_VALUE,0,0,1,clock,1);
        LiveBridge.distance(scaled); check(scaled.distanceToNextManeuver.distance==99990 && scaled.distanceToNextManeuver.unit==1,"factory distance saturation without multiplication overflow");
        int[] distances={0,1,9,10,19,20,30,89,90,99,100,949,950,1000,9949,9950,10000,Integer.MAX_VALUE};
        FactoryFormatter format=new FactoryFormatter();
        for (unit=0;unit<=1;unit++) for (int value:distances) {
            int[] expected=new int[2];
            if (unit==0) format.cnvDistance2KilometersExt(value,expected);
            else format.cnv2Distance2withMinDistanceMiles(value,expected);
            b.selected=new LiveModel.Frame(true,13,192,value,value,0,1,clock,1); LiveBridge.distance(scaled);
            check(scaled.distanceToNextManeuver.distance==expected[0] && scaled.distanceToNextManeuver.unit==expected[1],"maneuver uses actual factory conversion across boundaries/units");
            if (unit==0) format.cnv2Distance1Kilometers(value,expected);
            else format.cnv2Distance1Miles(value,expected);
            LiveBridge.destinationDistance(total);
            check(total.distanceToDestination.distance==expected[0] && total.distanceToDestination.unit==expected[1],"destination uses actual factory conversion across boundaries/units");
        }
        unit=0;
        b.selected=new LiveModel.Frame(true,13,192,-1,0,0,1,clock,1);
        LiveBridge.destinationTime(duration); LiveBridge.destinationDistance(total);
        check(total.validityInformation.distanceToDestinationValid && total.distanceToDestination.distance==0,"zero destination distance valid");
        check(duration.validityInformation.timeInfo_MinuteIsValid && duration.timeInfo.minute==0,"zero duration valid");
        b.selected=new LiveModel.Frame(true,13,192,-1,-1,-1,1,clock,1);
        LiveBridge.destinationTime(duration); LiveBridge.destinationDistance(total);
        check(!total.validityInformation.distanceToDestinationValid && !duration.validityInformation.timeInfo_MinuteIsValid,"missing metrics invalidate reused output");
        b.selected=b.incoming;
        for (String thread:threads) check(thread.equals(Thread.currentThread().getName()),"same event thread");
        ManeuverDescriptor_Status dirty=new ManeuverDescriptor_Status(); dirty.maneuver_2.mainElement=13; dirty.maneuver_3.direction=192;
        dirty.maneuver_1.sidestreets.setContent("old"); check(LiveBridge.descriptor(dirty),"fill override");
        check(dirty.maneuver_2.mainElement==0 && dirty.maneuver_3.direction==0 && dirty.maneuver_1.zLevelGuidance==0,"complete replacement");
        Object lane=Class.forName("de.vw.mib.bap.mqbab2.navsd.functions.LaneGuidance").newInstance();
        LaneGuidance_ChangedArray lanes=new LaneGuidance_ChangedArray(); lanes.laneGuidanceOnOff=1;
        Method fillLane=lane.getClass().getDeclaredMethod("computeFullLaneGuidanceList",new Class[]{LaneGuidance_ChangedArray.class}); fillLane.setAccessible(true);
        fillLane.invoke(lane,new Object[]{lanes});
        check(lanes.laneGuidanceOnOff==0 && lanes.getArrayData().size()==0,"factory lane array hidden");
        b.mode=1; clock+=250; sent.clear(); b.tick(clock);
        check(!b.owned && b.clearing && sent.size()==5,"shadow releases existing owner");
        check(((RG_Status_Status)sent.get(2)).rg_Status==0,"clear RG");
        check(!((DistanceToDestination_Status)sent.get(3)).validityInformation.distanceToDestinationValid,"clear route distance");
        check(!((TimeToDestination_Status)sent.get(4)).validityInformation.timeInfo_MinuteIsValid,"clear remaining duration");
        clock+=250; b.tick(clock); check(!b.clearing && b.selected==null,"stock refreshed after clear");
        check(!LiveBridge.descriptor(dirty),"pass-through helper declines");
        b=bridge(); sent.clear(); accept=false; b.tick(clock);
        check((b.refreshPending&LiveBridge.PROPERTIES)==LiveBridge.PROPERTIES,"queue rejection schedules retry");
        accept=true; clock+=250; b.tick(clock); check((b.refreshPending&LiveBridge.PROPERTIES)==0,"retry accepted");
        b.mode=0; accept=false; clock+=250; b.tick(clock); check(b.clearing,"rejected clear retained");
        clock+=250; b.tick(clock); check(b.clearing && b.selected!=null,"clear not lost at next tick");
        accept=true; clock+=250; b.tick(clock); check((b.refreshPending&LiveBridge.PROPERTIES)==0,"clear retry accepted");
        clock+=250; b.tick(clock); check(!b.clearing,"clear then stock handback");
        b=bridge(); b.tick(clock); route=1; clock+=250; sent.clear(); b.tick(clock);
        check(!b.owned && b.selected==null,"OEM route priority");
        check(((RG_Status_Status)sent.get(2)).rg_Status==1,"OEM status not blanked");
        route=0; clock+=250; b.tick(clock); check(!b.owned,"context alone cannot revive source");
        b.incoming=new LiveModel.Frame(true,13,64,20,2,clock,1); b.journalAt=clock; clock+=250; b.tick(clock); check(b.owned,"fresh progress takeover");
        route=2; check(!LiveBridge.descriptor(dirty),"calculating OEM blocks between ticks"); route=0;
        b=bridge(); b.tick(clock); connection=0; clock+=250; b.tick(clock); check(!b.owned,"disconnect releases"); connection=2;
        b=bridge(); b.tick(clock); clock+=1500; b.tick(clock); check(!b.owned,"missed HMI lease");
        b=bridge(); b.tick(clock); b.journalAt=clock-1500; clock+=250; b.tick(clock); check(!b.owned,"recorder heartbeat lease");
        b=bridge(); b.tick(clock); b.incoming=new LiveModel.Frame(true,13,64,20,2,clock-5000,1); clock+=250; b.tick(clock); check(!b.owned,"semantic stale deadline");
        b=bridge(); status=1; b.tick(clock); check(!b.owned,"native error cannot imply idle"); status=0;
        b=bridge(); b.mode=1; sent.clear(); b.tick(clock); check(!b.owned && sent.size()==0,"shadow writes nothing");
        b=bridge(); b.mode=0; b.tick(clock); check(!b.owned,"off by default");
        b.refreshPending=0; b.selected=null; LiveBridge.descriptor(dirty);
        check(b.refreshPending==0,"pass-through does not schedule endless stock refresh");
        b.refreshing=false; LiveBridge.accepted(false,b.stages[0]);
        check(b.refreshPending==0,"unrelated stock delivery keeps factory retry behavior");
        b=bridge(); b.tick(clock); Function original=b.stages[0]; b.stages[0]=null; clock+=250; b.tick(clock); check(!b.owned,"missing core stage blocks takeover");
        b.stages[0]=original; clock+=250; b.tick(clock); check(!b.owned,"stage reinitialization requires new source progress");
        System.out.println("{\"factory_integration_assertions\":"+checks+"}");
    }
    static void replay(String path,boolean bootstrap) throws Exception {
        JournalReader r=new JournalReader(path); if (!bootstrap) r.initialBytes=16;
        while (r.offset<r.file.length()) {
            r.file.seek(r.offset+4); byte[] t=new byte[4]; r.file.readFully(t); long at=LiveModel.u32(t,0);
            LiveModel.Frame f=r.next(at); if (f==null) throw new AssertionError("partial replay input");
            boolean active=f.active && at>=f.changed && at-f.changed<5000;
            System.out.println(at+","+(active?1:0)+","+f.main+","+f.direction+","+f.meters+","+f.remainingMeters+","+f.remainingSeconds);
        }
        r.close();
    }
    static void vectors() throws Exception {
        BufferedReader input=new BufferedReader(new InputStreamReader(System.in,"US-ASCII")); String line;
        while ((line=input.readLine())!=null) {
            String[] a=line.split(","); LiveModel.Message m=new LiveModel.Message(); int[] ids={3,9,8,11};
            for (int i=0;i<4;i++) if (!a[i].equals("x")) { m.has[ids[i]]=true; m.v[ids[i]]=Integer.parseInt(a[i]); }
            int[] result=LiveModel.map(m); System.out.println(result[0]+","+result[1]);
        }
    }
    static void fragment(String path,String temporary) throws Exception {
        RandomAccessFile input=new RandomAccessFile(path,"r"), output=new RandomAccessFile(temporary,"rw");
        output.setLength(0); byte[] header=new byte[16]; input.readFully(header); output.write(header);
        JournalReader reader=new JournalReader(temporary); int complete=0, partial=0;
        while (input.getFilePointer()<input.length()) {
            output.write(input.read()); long previous=reader.offset;
            LiveModel.Frame frame=reader.next(1000);
            if (frame==null) { check(reader.offset==previous,"partial record retained without mutation"); partial++; }
            else complete++;
        }
        check(reader.ended && reader.offset==output.length(),"fragmented end consumed");
        reader.close(); input.close(); output.close();
        System.out.println("{\"complete\":"+complete+",\"partial\":"+partial+"}");
    }
    public static void main(String[] args) throws Exception {
        if (args.length>0 && args[0].equals("replay")) replay(args[1],args.length>2);
        else if (args.length>0 && args[0].equals("vectors")) vectors();
        else if (args.length>0 && args[0].equals("fragment")) fragment(args[1],args[2]); else integration();
    }
}
