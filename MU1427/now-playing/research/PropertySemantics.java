/* SPDX-License-Identifier: GPL-3.0-or-later. Host-only exact-factory probe. */
package com.cpmap.audio.research;

import java.lang.reflect.*;
import de.vw.mib.bap.datatypes.BAPEntity;
import de.vw.mib.bap.mqbab2.common.api.adapter.BAPDataPoolValueAdapter;
import de.vw.mib.bap.mqbab2.common.api.adapter.AbstractBAPDataPool;
import de.vw.mib.bap.mqbab2.common.marshalling.FunctionRegistryListenerAdapter;
import de.vw.mib.bap.mqbab2.generated.audiosd.serializer.CurrentStationInfo_Status;
import de.vw.mib.asl.api.bap.dispatcher.BAPDispatcher;

public final class PropertySemantics {
    static int checks, dispatched;
    static void check(boolean value, String why) {
        checks++; if (!value) throw new AssertionError(why);
    }
    static CurrentStationInfo_Status frame(String title) {
        CurrentStationInfo_Status value = new CurrentStationInfo_Status();
        value.primaryInformation.setContent(title); value.pi_Type = 72;
        return value;
    }
    static boolean update(Method method, Object adapter, BAPEntity value, boolean force) throws Exception {
        return ((Boolean) method.invoke(null, adapter, value, Boolean.valueOf(force))).booleanValue();
    }
    public static void main(String[] args) throws Exception {
        Constructor ctor = BAPDataPoolValueAdapter.class.getDeclaredConstructor(
            Integer.TYPE, Integer.TYPE, Integer.TYPE, String.class);
        ctor.setAccessible(true);
        Object adapter = ctor.newInstance(Integer.valueOf(21), Integer.valueOf(3),
            Integer.valueOf(1), "synthetic");
        Method method = AbstractBAPDataPool.class.getDeclaredMethod("updateValueAdapterWithNewValue",
            BAPDataPoolValueAdapter.class, BAPEntity.class, Boolean.TYPE);
        method.setAccessible(true);
        check(update(method, adapter, frame("alpha"), false), "first value changes cache");
        check(!update(method, adapter, frame("alpha"), false), "equal content returns false");
        check(update(method, adapter, frame("beta"), false), "different content returns true");
        check(update(method, adapter, frame("beta"), true), "uncached update forces true");
        BAPDispatcher dispatcher = (BAPDispatcher) Proxy.newProxyInstance(
            BAPDispatcher.class.getClassLoader(), new Class[]{BAPDispatcher.class}, new InvocationHandler() {
                public Object invoke(Object proxy, Method m, Object[] a) {
                    if (m.getName().equals("transmitData")) dispatched++;
                    return null;
                }
            });
        FunctionRegistryListenerAdapter listener = new FunctionRegistryListenerAdapter(17, dispatcher);
        listener.getFunctionRegistryListenerAdapter(21);
        boolean returned = listener.statusProperty(frame("gamma"), null);
        check(dispatched == 1, "base listener dispatches property");
        check(!returned, "false return can accompany dispatch");
        System.out.println("{\"checks\":" + checks + ",\"duplicate_returns_false\":true,"
            + "\"false_does_not_imply_transport_failure\":true}");
    }
}
