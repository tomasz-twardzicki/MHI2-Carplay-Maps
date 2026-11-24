/* SPDX-License-Identifier: GPL-3.0-or-later */
package com.cpmap.audio;
import de.vw.mib.asl.internal.wcpcp.BorrowedScreen;
import de.vw.mib.asl.internal.wcpcp.MainScreenTrace;
import de.vw.mib.asl.framework.internal.framework.ServiceManager;
import de.vw.mib.event.dispatcher.SystemEventDispatcher;
import org.dsi.ifc.carplay.ResourceRequest;
import de.vw.mib.genericevents.EventGeneric;
import java.lang.reflect.*;
import java.io.*;
public final class TestBorrowedScreen {
    static int checks,events;
    static Class owner;
    static void check(boolean b,String why){checks++;if(!b)throw new RuntimeException(why);}
    static Object[] request(int id,int transfer) {
        ResourceRequest r=new ResourceRequest();r.resourceID=id;r.transferType=transfer;
        return new Object[]{new ResourceRequest[]{r}};
    }
    static void set(String name,Object value)throws Exception {Field f=owner.getDeclaredField(name);f.setAccessible(true);f.set(null,value);}
    static Object get(String name)throws Exception {Field f=owner.getDeclaredField(name);f.setAccessible(true);return f.get(null);}
    static void invoke(String name,Class[] types,Object[] args)throws Exception {Method m=owner.getDeclaredMethod(name,types);m.setAccessible(true);m.invoke(null,args);}
    static void track(int transfer,boolean foreground)throws Exception {
        set("fgCarplay",Boolean.valueOf(foreground));invoke("trackScreen",new Class[]{Class.forName("[Ljava.lang.Object;")},new Object[]{request(2,transfer)});
    }
    static void restore()throws Exception {invoke("cpmapRestoreBorrowedScreen",new Class[0],new Object[0]);}
    public static void main(String[] args)throws Exception {
        BorrowedScreen.cancel();BorrowedScreen.track(null,true);check(!BorrowedScreen.consume(),"null ignored");
        BorrowedScreen.track(request(1,3),true);BorrowedScreen.track(request(1,4),false);check(!BorrowedScreen.consume(),"audio requests excluded");
        BorrowedScreen.track(request(2,4),true);check(!BorrowedScreen.consume(),"unpaired unborrow ignored");
        BorrowedScreen.track(request(2,3),false);BorrowedScreen.track(request(2,4),false);check(!BorrowedScreen.consume(),"OEM foreground remains OEM");
        BorrowedScreen.track(request(2,3),true);BorrowedScreen.track(request(2,3),false);BorrowedScreen.track(request(2,4),false);
        check(BorrowedScreen.consume()&&!BorrowedScreen.consume(),"duplicate borrow preserves original owner, consumed once");
        BorrowedScreen.track(request(2,3),true);BorrowedScreen.track(request(2,1),false);BorrowedScreen.track(request(2,4),false);check(!BorrowedScreen.consume(),"explicit take cancels");
        String root=new StringBuffer(new File("/ramdisk").isDirectory()?"/ramdisk":System.getProperty("java.io.tmpdir")).append("/cpmap-screen-").append(System.currentTimeMillis()).toString();
        new File(new StringBuffer(root).append("/dev/shmem").toString()).mkdirs();new File(new StringBuffer(root).append("/ramdisk").toString()).mkdirs();
        System.setProperty("wcpcp.root",root);owner=Class.forName("de.vw.mib.asl.internal.wcpcp.WcpCp");owner.getDeclaredMethods();
        ServiceManager.eventDispatcher=(SystemEventDispatcher)Proxy.newProxyInstance(Class.forName("de.vw.mib.event.dispatcher.SystemEventDispatcher").getClassLoader(),new Class[]{Class.forName("de.vw.mib.event.dispatcher.SystemEventDispatcher")},new InvocationHandler(){
            public Object invoke(Object p,Method m,Object[] a){if(m.getName().equals("createAndSubmitHMIEvent")){check(((Integer)a[0]).intValue()==2910012,"actual CarPlay HMI event");events++;}return null;}
        });
        set("weRegistered",Boolean.TRUE);set("stage",new Integer(3));
        File session=new File(new StringBuffer(root).append("/dev/shmem/wcp_cp_session").toString());FileOutputStream f=new FileOutputStream(session);f.close();
        track(3,true);track(3,false);set("fgCarplay",Boolean.FALSE);track(4,false);restore();
        check(events==1&&((Boolean)get("confirmScreen")).booleanValue(),"hidden canvas restored via real event submission");restore();check(events==1,"no repeated enter");
        track(3,false);track(4,false);restore();check(events==1,"never steal OEM screen");
        track(3,true);set("mGetReceiverEventId",Class.forName("de.vw.mib.genericevents.EventGeneric").getMethod("getReceiverEventId",new Class[0]));
        EventGeneric leave=new EventGeneric();leave.setReceiverEventId(6100012);invoke("onObserverEvent",new Class[]{Class.forName("java.lang.Object")},new Object[]{leave});
        track(4,false);restore();check(events==1,"actual manual-leave event cancels restoration");
        track(3,true);track(4,false);session.delete();restore();check(events==1,"stale session excluded");
        f=new FileOutputStream(session);f.close();restore();check(events==1,"expired restoration never leaks into reconnect");
        track(3,true);track(4,false);set("weRegistered",Boolean.FALSE);restore();check(events==1,"unregistered service excluded");
        MainScreenTrace.resource(request(2,3));
        Class trace=Class.forName("de.vw.mib.asl.internal.wcpcp.MainScreenTrace");
        Method state=trace.getDeclaredMethod("state",new Class[]{Integer.TYPE,Boolean.TYPE,Boolean.TYPE,Integer.TYPE,Boolean.TYPE});state.setAccessible(true);
        String detail=(String)state.invoke(null,new Object[]{new Integer(3),Boolean.TRUE,Boolean.FALSE,new Integer(0),Boolean.TRUE});
        check(detail.indexOf("stage=3 session=1 foreground=0 canvas=0 confirm=1 transfer=3")>=0,"primary-screen trace observes without forcing foreground");
        MainScreenTrace.sample(3,true,false,0,true);
        if(new File("/ramdisk").isDirectory())check(new File("/ramdisk/cpmap-main-screen.log").length()>0,"worker trace exported with explicit clocks");
        session.delete();System.out.println(new StringBuffer("WIRELESS_SCREEN_RETURN_PASS checks=").append(checks).append(" factory_event=1 session_file=1 duplicate_borrow=1 manual_leave=1").toString());
    }
}
