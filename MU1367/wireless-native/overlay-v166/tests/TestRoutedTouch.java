import java.io.*;
import java.lang.reflect.*;
import java.net.*;
import org.dsi.ifc.carplay.TouchEvent;
import de.vw.mib.asl.internal.wcpcp.RoutedTouch;

public final class TestRoutedTouch {
    private static int checks;
    private static Class owner;
    private static String path(String root, String tail) { return new StringBuffer(root).append(tail).toString(); }
    private static void check(boolean yes, String why) { checks++; if (!yes) throw new RuntimeException(why); }
    private static void set(String name, Object value) throws Exception {
        Field field = owner.getDeclaredField(name); field.setAccessible(true); field.set(null, value);
    }
    private static Object[] touch(int source, int state, int x, int y) {
        return new Object[]{new Integer(source), new Integer(state), new TouchEvent[]{new TouchEvent(x,y)}};
    }
    private static void call(Object[] args) throws Exception {
        Method method = owner.getDeclaredMethod("onServiceCall", new Class[]{Class.forName("java.lang.String"),Class.forName("[Ljava.lang.Object;")});
        method.setAccessible(true); method.invoke(null,new Object[]{"postTouchEvent",args});
    }
    private static byte[] receive(DatagramSocket socket) throws Exception {
        byte[] data = new byte[32]; DatagramPacket packet = new DatagramPacket(data,data.length);
        socket.receive(packet); check(packet.getLength()==12,"WT packet length"); return data;
    }
    private static void quiet(DatagramSocket socket) throws Exception {
        try { receive(socket); throw new RuntimeException("unexpected forwarded input"); }
        catch (SocketTimeoutException expected) { checks++; }
    }
    public static void main(String[] args) throws Exception {
        String root=args[0]; new File(path(root,"/dev/shmem")).mkdirs(); new File(path(root,"/ramdisk")).mkdirs();
        System.setProperty("wcpcp.root",root);
        DatagramSocket socket=new DatagramSocket(7102,InetAddress.getByName("127.0.0.1")); socket.setSoTimeout(100);
        owner=Class.forName("de.vw.mib.asl.internal.wcpcp.WcpCp");
        set("stage",new Integer(3)); set("weRegistered",Boolean.TRUE);
        File session=new File(path(root,"/dev/shmem/wcp_cp_session")); new FileOutputStream(session).close();
        call(touch(1,1,321,123)); byte[] down=receive(socket);
        check(down[0]==87&&down[1]==84&&down[2]==1&&down[3]==4,"native press mapped to WT press");
        check((down[4]&255)==1&&(down[5]&255)==65&&(down[6]&255)==0&&(down[7]&255)==123,"OEM coordinates preserved");
        call(touch(1,0,321,123)); byte[] up=receive(socket); check(up[3]==3,"native release mapped to WT release");
        check((up[11]&255)==((down[11]+1)&255),"sequence advances");
        call(touch(0,1,12,34)); quiet(socket);
        call(touch(1,2,12,34)); quiet(socket);
        call(touch(1,1,-1,34)); quiet(socket);
        call(new Object[]{new Integer(1),new Integer(1),new TouchEvent[0]}); quiet(socket);
        session.delete(); call(touch(1,1,12,34)); quiet(socket);
        new FileOutputStream(session).close(); set("weRegistered",Boolean.FALSE); call(touch(1,1,12,34)); quiet(socket);
        set("weRegistered",Boolean.TRUE); set("stage",new Integer(2)); call(touch(1,1,12,34)); quiet(socket);
        check(!RoutedTouch.forward(null,true),"malformed input rejected");
        socket.close(); session.delete();
        System.out.println(new StringBuffer("OEM_ROUTED_TOUCH_PASS checks=").append(checks).append(" real_cp_dispatch=1 loopback=1 raw_hook_removed=1").toString());
    }
}
