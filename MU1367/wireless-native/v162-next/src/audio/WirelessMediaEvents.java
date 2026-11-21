/* SPDX-License-Identifier: GPL-3.0-or-later */
package com.cpmap.audio;
import de.vw.mib.asl.framework.internal.framework.ServiceManager;
import de.vw.mib.asl.framework.internal.framework.dsi.proxy.DSIProxyTarget;
import de.vw.mib.asl.framework.internal.framework.dsi.util.RuntimeGeneratedConstants;
import de.vw.mib.asl.framework.internal.framework.dsi.util.Cfg;
import de.vw.mib.reflection.MultipleMethodAccessibleObject;
import org.dsi.ifc.carplay.*;
import org.dsi.ifc.global.ResourceLocator;
/** Use the same ASL/DSI proxy event route as the registered wireless service.
 * A freshly constructed DSICarplayDispatcher has unrelated listener lists. */
final class WirelessMediaEvents {
    static final int TYPE=27;
    static int[] methods;
    static boolean ready() {
        return ServiceManager.eventMain!=null && ServiceManager.mGenericEventFactory!=null && ServiceManager.reflectionFactory!=null;
    }
    static synchronized void resolve()throws Exception {
        if(methods!=null)return;
        if(!RuntimeGeneratedConstants.SERVICE_TS_NS[TYPE].equals("org.dsi.ifc.carplay.DSICarplay") ||
           !RuntimeGeneratedConstants.LISTENER_TS_NS[TYPE].equals("org.dsi.ifc.carplay.DSICarplayListener"))throw new IllegalStateException("MU1367 CarPlay type");
        MultipleMethodAccessibleObject table=ServiceManager.reflectionFactory.getListenersMmao(TYPE);
        String[] names={"updateNowPlayingData","updatePlaybackState","updatePlayposition","updateCoverArtUrl"};
        Class[] types={Class.forName("org.dsi.ifc.carplay.TrackData"),Class.forName("org.dsi.ifc.carplay.PlaybackInfo"),Integer.TYPE,Class.forName("org.dsi.ifc.global.ResourceLocator")};
        int[] next=new int[4];
        for(int i=0;i<4;i++) {
            next[i]=table.getIndex("org.dsi.ifc.carplay.DSICarplayListener",names[i],new Class[]{types[i],Integer.TYPE});
            // DSI attribute IDs are 3..6; Cfg's mask indices are zero based.
            if(next[i]<0 || Cfg.PT.getNotificationIndex(TYPE,next[i])!=i+2)throw new IllegalStateException("MU1367 media notification");
        }
        methods=next;
    }
    static void send(int attribute,Object value)throws Exception {
        resolve();
        ServiceManager.eventMain.getEventDispatcher().sendSafe(
            DSIProxyTarget.createNotificationInvocationEvent(TYPE,0,methods[attribute-3],new Object[]{value,new Integer(1)}));
    }
}
