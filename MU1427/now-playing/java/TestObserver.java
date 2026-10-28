/* SPDX-License-Identifier: GPL-3.0-or-later. Host test, never installed. */
package com.cpmap.audio;

import java.lang.reflect.*;
import java.util.Arrays;
import org.dsi.ifc.carplay.*;
import org.dsi.ifc.global.ResourceLocator;

public final class TestObserver {
    private static int assertions;
    static void check(boolean ok) {
        assertions++;
        if (!ok) throw new AssertionError("assertion " + assertions);
    }
    static void has(NowPlayingObserver o, String value) { check(o.status().contains(value)); }

    static final class Service implements InvocationHandler {
        final DSICarplay proxy = (DSICarplay) Proxy.newProxyInstance(
            TestObserver.class.getClassLoader(), new Class[] {DSICarplay.class}, this);
        NowPlayingObserver observer;
        int registrations, clears;
        boolean failRegister, failClear;
        public Object invoke(Object p, Method m, Object[] a) {
            if (m.getName().equals("setNotification")) {
                check(Arrays.equals((int[]) a[0], new int[] {3, 4, 5, 6}));
                registrations++;
                observer = (NowPlayingObserver) a[1];
                if (failRegister) throw new IllegalStateException("registration");
            } else if (m.getName().equals("clearNotification")) {
                check(a[1] == observer);
                clears++;
                if (failClear) throw new IllegalStateException("clear");
            } else throw new AssertionError("Unexpected service operation: " + m.getName());
            return null;
        }
    }

    public static void main(String[] args) throws Exception {
        // Host tests exercise callbacks without starting the on-unit RAM writer.
        Field writer = NowPlayingObserver.class.getDeclaredField("writer");
        writer.setAccessible(true);
        writer.set(null, new Thread());
        NowPlayingObserver.start(null);
        Service first = new Service();
        NowPlayingObserver.start(first.proxy);
        check(first.registrations == 1);
        NowPlayingObserver o = first.observer;
        has(o, "attached=1");
        NowPlayingObserver.start(first.proxy);
        check(first.registrations == 1 && first.clears == 0);

        TrackData track = new TrackData("PRIVATE_TITLE", 42, "PRIVATE_ALBUM", "PRIVATE_ARTIST", "", "");
        o.updateNowPlayingData(track, 0);
        o.updateNowPlayingData(track, 2);
        o.updateNowPlayingData(null, 1);
        o.updateNowPlayingData(track, 1);
        o.updateNowPlayingData(new TrackData(), 1);
        has(o, "tracks=5 valid_tracks=2 titles=1 artists=1 albums=1");
        PlaybackInfo playback = new PlaybackInfo();
        playback.status = 1;
        o.updatePlaybackState(playback, 1);
        has(o, "playback_state=1");
        playback.status = 2;
        o.updatePlaybackState(playback, 1);
        has(o, "playback_state=2");
        o.updatePlaybackState(playback, 2);
        has(o, "playback_state=-1");
        playback.status = 99;
        o.updatePlaybackState(playback, 1);
        o.updatePlaybackState(null, 1);
        has(o, "playback=5 valid_playback=2");
        o.updatePlayposition(0, 1);
        o.updatePlayposition(-1, 1);
        o.updatePlayposition(12, 2);
        has(o, "positions=3 valid_positions=1");
        ResourceLocator art = new ResourceLocator("file:///PRIVATE_ART.png");
        o.updateCoverArtUrl(art, 1);
        o.updateCoverArtUrl(new ResourceLocator(5), 1);
        o.updateCoverArtUrl(new ResourceLocator(), 1);
        o.updateCoverArtUrl(art, 2);
        o.updateCoverArtUrl(null, 1);
        has(o, "covers=5 valid_covers=3 cover_urls=1 cover_ids=1");
        o.asyncException(9, "PRIVATE_ERROR", 7);
        has(o, "exceptions=1");
        check(!o.status().contains("PRIVATE"));
        check(o.status().length() < 4096);

        Service second = new Service();
        NowPlayingObserver.start(second.proxy);
        check(first.clears == 1 && second.registrations == 1);
        has(o, "attached=0");
        String old = o.status();
        o.updateNowPlayingData(track, 1);
        o.updateCoverArtUrl(art, 1);
        o.updatePlaybackState(playback, 1);
        o.updatePlayposition(0, 1);
        o.asyncException(0, "ignored", 0);
        check(old.equals(o.status()));
        has(second.observer, "tracks=0");
        check(!second.observer.status().equals(o.status()));
        NowPlayingObserver.stop(first.proxy);
        check(second.clears == 0);
        second.failClear = true;
        NowPlayingObserver.stop(second.proxy);
        has(second.observer, "attached=0");
        has(second.observer, "clear_failures=1");
        NowPlayingObserver.stop(second.proxy);
        check(second.clears == 1);

        Service bad = new Service();
        bad.failRegister = true;
        NowPlayingObserver.start(bad.proxy);
        check(bad.registrations == 1 && bad.clears == 1);
        has(bad.observer, "attached=0");
        // Loading the actual patched class triggers host bytecode verification.
        Class.forName("de.vw.mib.asl.internal.carplay.target.HsmTarget", false,
                      TestObserver.class.getClassLoader()).getDeclaredMethods();
        System.out.println("{\"observer_assertions\":" + assertions + "}");
    }
}
