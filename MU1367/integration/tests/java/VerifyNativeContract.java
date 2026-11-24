/* SPDX-License-Identifier: GPL-3.0-or-later
 * Host-only verification against converted, unmodified MU1427 classes.
 * Nothing in this test is loaded onto the unit.
 */
import java.lang.reflect.*;
import java.util.*;

public final class VerifyNativeContract {
    private static final String BASE = "de.vw.mib.bap.mqbab2.generated.navsd.serializer.";
    private static void require(boolean ok, String message) {
        if (!ok) throw new AssertionError(message);
    }
    private static int constant(Class c, String name) throws Exception {
        return c.getField(name).getInt(null);
    }
    public static void main(String[] args) throws Exception {
        Class inner = Class.forName(BASE + "ManeuverDescriptor_Status$Maneuver_1");
        require(constant(inner, "MAIN_ELEMENT_TURN") == 13, "TURN constant");
        require(constant(inner, "MAIN_ELEMENT_ROUNDABOUT_TRS_RIGHT") == 21, "roundabout constant");
        require(constant(inner, "MAIN_ELEMENT_UTURN") == 25, "UTURN constant");
        Class status = Class.forName(BASE + "ManeuverDescriptor_Status");
        Object all = status.newInstance();
        for (int n = 1; n <= 3; n++) require(status.getField("maneuver_" + n).get(all) != null, "three slots");
        String[] properties = {"ManeuverDescriptor_Status", "DistanceToNextManeuver_Status",
                               "RG_Status_Status", "ManeuverState_Status"};
        int[] ids = {23, 18, 17, 55};
        for (int n = 0; n < ids.length; n++) {
            Class c = Class.forName(BASE + properties[n]);
            require(((Integer)c.getMethod("functionId", new Class[0]).invoke(null, new Object[0])).intValue() == ids[n], "FctID");
        }
        final ArrayList bytes = new ArrayList();
        Class stream = Class.forName("de.vw.mib.bap.stream.BitStream");
        Object output = Proxy.newProxyInstance(stream.getClassLoader(), new Class[]{stream},
            new InvocationHandler() {
                public Object invoke(Object p, Method m, Object[] a) {
                    if (m.getName().equals("pushByte")) bytes.add(Integer.valueOf(((Byte)a[0]).byteValue() & 255));
                    Class r = m.getReturnType();
                    if (r == Boolean.TYPE) return Boolean.FALSE;
                    if (r == Integer.TYPE) return Integer.valueOf(0);
                    return null;
                }
            });
        int vectors = 0;
        for (int main = 0; main <= 38; main++) {
            for (int direction = 0; direction < 256; direction += 16) {
                Object value = inner.newInstance();
                inner.getField("mainElement").setInt(value, main);
                inner.getField("direction").setInt(value, direction);
                inner.getField("zLevelGuidance").setInt(value, 0);
                bytes.clear();
                inner.getMethod("serialize", new Class[]{stream}).invoke(value, new Object[]{output});
                require(bytes.size() >= 3, "descriptor serialization");
                require(((Integer)bytes.get(0)).intValue() == main, "serialized main");
                require(((Integer)bytes.get(1)).intValue() == direction, "serialized direction");
                require(((Integer)bytes.get(2)).intValue() == 0, "serialized z level");
                vectors++;
            }
        }
        Class stage = Class.forName("de.vw.mib.bap.mqbab2.navsd.functions.ManeuverDescriptor");
        Object instance = stage.newInstance();
        Method map = stage.getDeclaredMethod("mapToBAPMainElement", new Class[]{Integer.TYPE});
        map.setAccessible(true);
        for (int value = 0; value <= 38; value++) {
            int expected = value == 32 ? 15 : value == 33 ? 16 : value;
            require(((Integer)map.invoke(instance, new Object[]{Integer.valueOf(value)})).intValue() == expected, "stock stage main remap");
        }
        System.out.println("{\"factory_descriptor_vectors\":" + vectors + ",\"factory_stage_cases\":39,\"slots\":3,\"fctids_verified\":true}");
    }
}
