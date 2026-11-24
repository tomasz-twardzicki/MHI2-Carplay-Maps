import java.io.*;
import java.lang.reflect.*;
import java.util.ArrayList;
import de.vw.mib.asl.framework.internal.framework.ServiceManager;
import de.vw.mib.genericevents.EventFactory;
import de.vw.mib.genericevents.EventGeneric;

/** Real adapter bytecode with only three file-path constants relocated by the
 * fixture. The dispatcher is observed; no profile-disconnect ACK is simulated.
 */
public final class TestCallRelease {
    static int checks;
    static Class owner;
    static String root="/ramdisk/cpmap-call-contract";
    static final Sink sink=new Sink();
    public static final class Sink {
        int count;EventGeneric event;
        public void sendSafe(EventGeneric e){count++;event=e;}
    }
    static void check(boolean b,String why){checks++;if(!b)throw new RuntimeException(why);}
    static void set(String name,Object value)throws Exception{Field f=owner.getDeclaredField(name);f.setAccessible(true);f.set(null,value);}
    static String path(String tail){return new StringBuffer(root).append(tail).toString();}
    static void put(String tail,String text)throws Exception{File f=new File(path(tail));f.getParentFile().mkdirs();FileOutputStream out=new FileOutputStream(f);try{out.write(text.getBytes("US-ASCII"));}finally{out.close();}}
    static void request()throws Exception{
        set("entered",Boolean.TRUE);set("btDisableDone",Boolean.FALSE);
        Method m=owner.getDeclaredMethod("maybeBtDisable",new Class[0]);m.setAccessible(true);m.invoke(null,new Object[0]);
    }
    static void fixtureService(String name)throws Exception{
        Field field=Class.forName("de.vw.mib.asl.framework.internal.framework.ServiceManager").getField(name);Class type=field.getType();
        field.set(null,Proxy.newProxyInstance(type.getClassLoader(),new Class[]{type},new InvocationHandler(){
            public Object invoke(Object p,Method m,Object[] a){
                String result=m.getReturnType().getName();
                if("boolean".equals(result))return Boolean.FALSE;
                if("int".equals(result))return new Integer(0);
                if("long".equals(result))return new Long(0);
                return null;
            }
        }));
    }
    public static void main(String[] args)throws Exception{
        if(args.length>0)root=args[0];
        Class.forName("de.vw.mib.asl.internal.wcpcp.RoutedTouch").getDeclaredMethods();
        owner=Class.forName("de.vw.mib.asl.internal.wcpcp.WcpCp");
        Class factoryType=Class.forName("de.vw.mib.genericevents.EventFactory");
        ServiceManager.mGenericEventFactory=(EventFactory)Proxy.newProxyInstance(factoryType.getClassLoader(),new Class[]{factoryType},new InvocationHandler(){
            public Object invoke(Object p,Method m,Object[] a){
                if(m.getName().equals("newEvent")){EventGeneric e=new EventGeneric();e.setReceiverEventId(((Integer)a[0]).intValue());return e;}return null;
            }
        });
        set("dispatcher",sink);set("mSendSafe",sink.getClass().getMethod("sendSafe",new Class[]{Class.forName("de.vw.mib.genericevents.EventGeneric")}));
        File flag=new File(path("/mnt/persist/wcp_btaudio_release")),released=new File(path("/dev/shmem/wcp_bt_released"));flag.delete();released.delete();
        put("/dev/shmem/wcp_bt_disable","001122334455\n");request();
        check(sink.count==0&&!released.exists(),"default keeps Bluetooth profiles");
        put("/mnt/persist/wcp_btaudio_release","1\n");put("/dev/shmem/wcp_bt_disable","bad\n");request();
        check(sink.count==0&&!released.exists(),"invalid phone identity cannot release profiles");
        fixtureService("configManagerDiag");fixtureService("persistence");fixtureService("logger");
        Class data=Class.forName("de.vw.mib.asl.internal.phone.ASLPhoneData");Object phone=data.getMethod("getInstance",new Class[0]).invoke(null,new Object[0]);
        ArrayList devices=new ArrayList();devices.add("00:11:22:33:44:55");data.getField("trustedBTDevicesAddresses").set(phone,devices);
        put("/dev/shmem/wcp_bt_disable","AABBCCDDEEFF\n");request();
        check(sink.count==0&&!released.exists(),"untrusted address cannot become a broad disconnect");
        put("/dev/shmem/wcp_bt_disable","001122334455\n");request();
        check(sink.count==1,"one addressed request emitted");
        check(sink.event.getReceiverEventId()==3600032,"actual OEM disconnect service");
        check("00:11:22:33:44:55".equals(sink.event.getString(0)),"exact trusted device, no null address");
        check(sink.event.getBoolean(1)&&sink.event.getBoolean(2),"actual OEM media and phone fields selected");
        check(released.exists(),"legacy marker records request; no ACK claimed");
        set("weRegistered",Boolean.FALSE);set("connDriven",Boolean.FALSE);
        Method down=owner.getDeclaredMethod("onSessionDown",new Class[0]);down.setAccessible(true);down.invoke(null,new Object[0]);
        check(!released.exists(),"disconnect retires release marker");
        flag.delete();new File(path("/dev/shmem/wcp_bt_disable")).delete();
        System.out.println(new StringBuffer("CALL_RELEASE_CONTRACT_PASS checks=").append(checks).append(" addressed_phone=1 default_off=1 malformed_refused=1 untrusted_refused=1 oem_fields=1 request_only_no_ack=1").toString());
    }
}
