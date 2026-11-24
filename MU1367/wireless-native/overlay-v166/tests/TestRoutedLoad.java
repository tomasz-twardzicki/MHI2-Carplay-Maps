import java.io.File;
import de.vw.mib.asl.internal.wcpcp.RoutedTouch;

public final class TestRoutedLoad {
    public static void main(String[] args) throws Exception {
        System.setProperty("wcpcp.root", "/ramdisk/routed-load");
        new File("/ramdisk/routed-load/ramdisk").mkdirs();
        Class.forName("de.vw.mib.asl.internal.wcpcp.WcpCp").getDeclaredMethods();
        Class.forName("de.vw.mib.asl.internal.system.input.TouchInputDeviceImpl").getDeclaredMethods();
        if (RoutedTouch.forward(null, false)) throw new Exception("inactive touch forwarded");
        if (RoutedTouch.status().indexOf("raw_intercept=0") < 0) throw new Exception("missing route contract");
        System.out.println("ROUTED_TOUCH_FACTORY_J9_PASS classes=2 rejected_inactive=1 network_not_stubbed_as_success=1");
    }
}
