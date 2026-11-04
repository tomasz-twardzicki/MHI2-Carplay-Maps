/* SPDX-License-Identifier: GPL-3.0-or-later */
package com.cpmap.rgi;

import de.vw.mib.bap.mqbab2.generated.navsd.serializer.DistanceToNextManeuver_Status;

/** Native remaining-distance bar; the cluster renders its own animation.
 * Scale/window reference: MacsInSpace/mib2-android-auto-vc d563d147.
 * Independent implementation using this adapter's validated CarPlay frames.
 */
public final class ArrowProgress {
    static final long ROUTE_AGE=LiveModel.HOLD_MS;
    static int window(LiveModel.Frame f){
        // iAP2 maneuver types, not Android Auto's enum (whose 8 means exit).
        int t=f==null?-1:f.maneuverType;
        return t==8 || t==22 || t==23?2000:200;
    }
    static boolean supported(int main){
        // Exact MU1367 verifiedBapBargraphSetting whitelist.
        return main>=3 && main<=5 || main>=13 && main<=27 || main>=32 && main<=35;
    }
    static int remaining(LiveModel.Frame f,long now){
        if(f==null || !f.active || !f.validDistance || !supported(f.main)
            || f.laneAt<0 || now<f.laneAt || now-f.laneAt>=ROUTE_AGE)return -1;
        int limit=window(f);
        return f.meters>limit?-1:(int)((long)f.meters*100/limit);
    }
    static void fill(DistanceToNextManeuver_Status out,LiveModel.Frame f,long now){
        int value=remaining(f,now);
        out.bargraphInfo.bargraphOnOff=value<0?0:1;
        out.bargraphInfo.bargraph=value<0?0:value;
    }
}
