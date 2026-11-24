/* SPDX-License-Identifier: GPL-3.0-or-later
 * v1.5.4: the OEM navigation's "time to destination / arrival time" choice for the cluster.
 * The stock TimeToDestination reads the choice from NavigationService.getTimeToDestinationTimeInfo()
 * (datapool 1110059, 1 = arrival time) and takes the arrival clock from the OEM route, which CarPlay
 * does not have. Here the arrival time is the unit's own clock (the HMI clock datapool, already local
 * time with the car's time zone and summer time) plus the phone's remaining time. No epoch, time zone or
 * date is assumed: without a valid HMI clock the remaining time is sent, as before.
 */
package com.cpmap.rgi;

import de.vw.mib.bap.mqbab2.common.api.APIFactory;
import de.vw.mib.asl.framework.api.framework.ASLFrameworkFactory;
import de.vw.mib.datapool.ASLDatapool;
import org.osgi.framework.BundleContext;
import org.osgi.framework.ServiceReference;

final class ArrivalClock {
    static final int TIME_INFO_ARRIVAL=1;     // TimeInfo.TIME_INFO_TYPE_ARRIVAL_TIME
    static final int DP_TIME_HOUR=1640;       // ASLSystemListenerConstants.TIME__HOUR (0..23)
    static final int DP_TIME_MINUTE=1641;     // ASLSystemListenerConstants.TIME__MINUTE
    static final int DP_TIME_VALID=3572;      // ASLSystemListenerConstants.TIME_VALID
    private static ASLDatapool pool;
    static volatile int lastSetting=-1, lastClock=-1, arrivals, fallbacks;

    private ArrivalClock() {}

    /** The OEM choice: true when the navigation setup asks for the arrival time. */
    static boolean wanted() {
        int v=APIFactory.getAPIFactory().getNavigationService().getTimeToDestinationTimeInfo();
        lastSetting=v; return v==TIME_INFO_ARRIVAL;
    }

    /** The same OSGi lookup as the stock APIFactory.getService(ASLDatapool.class); cached once found. */
    private static ASLDatapool pool() {
        if (pool==null) {
            BundleContext ctx=ASLFrameworkFactory.getASLFrameworkAPI().getServices().getBundleContext();
            ServiceReference ref=ctx==null?null:ctx.getServiceReference("de.vw.mib.datapool.ASLDatapool");
            Object p=ref==null?null:ctx.getService(ref);
            if (p instanceof ASLDatapool) pool=(ASLDatapool)p;
        }
        return pool;
    }

    /** The HMI clock as minutes of the day 0..1439, or -1 when it is not valid or not readable. */
    static int clockMinutes() {
        try {
            ASLDatapool p=pool(); if (p==null) return -1;
            if (!p.getBoolean(DP_TIME_VALID,false)) return -1;
            int h=p.getInteger(DP_TIME_HOUR,-1), m=p.getInteger(DP_TIME_MINUTE,-1);
            if (h<0 || h>23 || m<0 || m>59) return -1;
            return h*60+m;
        } catch (Throwable t) { return -1; }
    }

    /** Arrival minutes of the day for the remaining seconds; the clock minute is on average half gone. */
    static int arrival(int clock, int remainingSeconds) {
        return (int)((clock+((long)remainingSeconds+30)/60)%(24*60));
    }

    /** Arrival minute of the day, or -1 to send the remaining time instead. */
    static int resolve(int remainingSeconds) {
        boolean arrival;
        try { arrival=wanted(); } catch (Throwable t) { arrival=false; }
        if (!arrival) return -1;
        int clock=clockMinutes(); lastClock=clock;
        if (clock<0) { fallbacks++; return -1; }
        arrivals++;
        return arrival(clock,remainingSeconds<0?0:remainingSeconds);
    }

    /** 12/24 h exactly as stock setTimeInfo: system format 0 -> BAP 1, anything else -> 0. */
    static int timeFormat() {
        try { return APIFactory.getAPIFactory().getSystemService().getSystemTimeFormat()==0?1:0; }
        catch (Throwable t) { return 0; }
    }
}
