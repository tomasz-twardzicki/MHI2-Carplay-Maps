/* SPDX-License-Identifier: GPL-3.0-or-later. Factory-J9 test, never installed. */
package com.cpmap.audio;

import java.io.*;
import org.dsi.ifc.carplay.*;
import org.dsi.ifc.global.ResourceLocator;

public final class LoadObserver {
    static int checks;
    static void check(boolean value) throws Exception {
        if (!value) throw new Exception("N0 check failed");
        checks++;
    }
    static String status(Object observer) throws Exception {
        java.lang.reflect.Method method = observer.getClass().getDeclaredMethod("status", new Class[0]);
        method.setAccessible(true);
        return (String) method.invoke(observer, new Object[0]);
    }
    public static void main(String[] args) throws Exception {
        Class target = Class.forName("de.vw.mib.asl.internal.carplay.target.HsmTarget");
        check(target.getDeclaredMethod("initializeDSI", new Class[0]) != null);
        check(target.getDeclaredMethod("deInitializeDSI", new Class[0]) != null);
        Class helper = Class.forName("com.cpmap.audio.NowPlayingObserver");
        java.lang.reflect.Constructor constructor = helper.getDeclaredConstructor(
            new Class[] {Class.forName("org.dsi.ifc.carplay.DSICarplay"), Long.TYPE});
        constructor.setAccessible(true);
        NowPlayingObserver o = (NowPlayingObserver) constructor.newInstance(new Object[] {null, new Long(1)});
        check(o instanceof DSICarplayListener);
        o.updateNowPlayingData(new TrackData("PRIVATE_TITLE", 0, "PRIVATE_ALBUM", "PRIVATE_ARTIST", "", ""), 1);
        PlaybackInfo info = new PlaybackInfo(); info.status = 1;
        o.updatePlaybackState(info, 1);
        o.updatePlayposition(0, 1);
        o.updateCoverArtUrl(new ResourceLocator("file:///PRIVATE_ART.png"), 1);
        check(status(o).indexOf("tracks=1 valid_tracks=1 titles=1 artists=1 albums=1") >= 0);
        check(status(o).indexOf("playback_state=1") >= 0);
        check(status(o).indexOf("positions=1 valid_positions=1") >= 0);
        check(status(o).indexOf("cover_urls=1") >= 0);
        check(status(o).indexOf("PRIVATE") < 0);
        check(status(o).length() < 4096);
        NowPlayingObserver.start(null);
        NowPlayingObserver.stop(null);
        // Exercise the real background writer and rename with the firmware libc/J9.
        java.lang.reflect.Field current = helper.getDeclaredField("current");
        current.setAccessible(true); current.set(null, o);
        Class type = Class.forName("com.cpmap.audio.NowPlayingObserver$StatusWriter");
        java.lang.reflect.Constructor ctor = type.getDeclaredConstructor(new Class[0]);
        ctor.setAccessible(true);
        Thread thread = new Thread((Runnable) ctor.newInstance(new Object[0]));
        thread.setDaemon(true);
        new File("/ramdisk/carplay-now-playing-n0.status").delete();
        thread.start();
        File status = new File("/ramdisk/carplay-now-playing-n0.status");
        try {
            for (int i = 0; i < 40 && !status.isFile(); i++) Thread.sleep(100);
            check(status.isFile() && status.length() > 0 && status.length() < 4096);
            BufferedReader reader = new BufferedReader(new InputStreamReader(new FileInputStream(status), "US-ASCII"));
            String line;
            try { line = reader.readLine(); } finally { reader.close(); }
            check(line.indexOf("observer_only=1") >= 0 && line.indexOf("PRIVATE") < 0);
        } finally { thread.interrupt(); thread.join(2000); }
        check(!thread.isAlive());
        System.out.print("N0_J9_PASS checks="); System.out.println(checks);
    }
}
