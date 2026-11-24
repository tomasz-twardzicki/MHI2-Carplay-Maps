/* SPDX-License-Identifier: GPL-3.0-or-later */
package de.vw.mib.asl.internal.wcpcp;
import org.dsi.ifc.carplay.ResourceRequest;
/** Transient screen ownership across a popup/reverse borrow. Duplicate borrow
 * requests are idempotent; an explicit take or user leave cancels restoration. */
public final class BorrowedScreen {
    private static boolean borrowed,wasCarPlay,pending;
    public static synchronized void track(Object[] arguments,boolean foreground) {
        if(arguments==null||arguments.length==0||!(arguments[0] instanceof ResourceRequest[]))return;
        ResourceRequest[] requests=(ResourceRequest[])arguments[0];
        for(int i=0;i<requests.length;i++) {
            ResourceRequest r=requests[i];if(r==null||r.resourceID!=2)continue;
            if(r.transferType==3) {
                if(!borrowed){borrowed=true;wasCarPlay=foreground;pending=false;}
            } else if(r.transferType==4) {
                if(borrowed){pending=wasCarPlay;borrowed=false;wasCarPlay=false;}
            } else if(r.transferType==1)cancel();
        }
    }
    public static synchronized boolean consume() {boolean value=pending;pending=false;return value;}
    public static synchronized void cancel() {borrowed=wasCarPlay=pending=false;}
}
