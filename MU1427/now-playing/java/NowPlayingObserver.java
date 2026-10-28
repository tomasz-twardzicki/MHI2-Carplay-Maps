/* SPDX-License-Identifier: GPL-3.0-or-later */
package com.cpmap.audio;

import java.io.File;
import java.io.FileOutputStream;
import org.dsi.ifc.carplay.*;
import org.dsi.ifc.global.ResourceLocator;

/** N0 observation only. No BAP calls, image reads, playback commands or text logs. */
public final class NowPlayingObserver implements DSICarplayListener {
    static final int[] ATTRIBUTES = {3, 4, 5, 6};
    private static NowPlayingObserver current;
    private static Thread writer;
    private static long generation;
    private static long attachFailures;
    private final DSICarplay source;
    private final long epoch;
    private boolean attached = true;
    private long tracks, validTracks, titles, artists, albums;
    private long playback, validPlayback, positions, validPositions;
    private long covers, validCovers, coverUrls, coverIds, exceptions;
    private long clearFailures, ioFailures;
    private int playbackState = -1;

    NowPlayingObserver(DSICarplay service, long session) {
        source = service;
        epoch = session;
    }

    public static synchronized void start(DSICarplay source) {
        if (source == null) return;
        if (current != null && current.source == source && current.isAttached()) return;
        if (current != null) current.close();
        NowPlayingObserver next = new NowPlayingObserver(source, ++generation);
        current = next;
        try {
            if (writer == null) {
                Thread thread = new Thread(new StatusWriter(), "CPMapAudioN0");
                thread.setDaemon(true);
                thread.start();
                writer = thread;
            }
            // Start diagnostics before subscribing, so failed registration is observable.
            // Separate listener: the factory listener and its attributes stay intact.
            source.setNotification(ATTRIBUTES, next);
        } catch (Throwable failure) {
            attachFailures++;
            next.close();
        }
    }

    public static synchronized void stop(DSICarplay source) {
        if (current != null && current.source == source) current.close();
    }

    private static synchronized NowPlayingObserver observation() { return current; }
    private static synchronized long failures() { return attachFailures; }

    private synchronized boolean isAttached() { return attached; }

    private void close() {
        synchronized (this) {
            if (!attached) return;
            attached = false;
            playbackState = -1;
        }
        try { source.clearNotification(ATTRIBUTES, this); }
        catch (Throwable failure) { synchronized (this) { clearFailures++; } }
    }

    public synchronized void updateNowPlayingData(TrackData data, int valid) {
        if (!attached) return;
        tracks++;
        if (valid != 1 || data == null) return;
        validTracks++;
        if (present(data.title)) titles++;
        if (present(data.artist)) artists++;
        if (present(data.album)) albums++;
    }

    public synchronized void updatePlaybackState(PlaybackInfo info, int valid) {
        if (!attached) return;
        playback++;
        playbackState = -1;
        if (valid != 1 || info == null || info.status < 0 || info.status > 4) return;
        validPlayback++;
        playbackState = info.status;
    }

    public synchronized void updatePlayposition(int position, int valid) {
        if (!attached) return;
        positions++;
        if (valid == 1 && position >= 0) validPositions++;
    }

    public synchronized void updateCoverArtUrl(ResourceLocator art, int valid) {
        if (!attached) return;
        covers++;
        if (valid != 1 || art == null) return;
        validCovers++;
        if (present(art.url)) coverUrls++;
        else if (art.id >= 0) coverIds++;
    }

    public synchronized void asyncException(int error, String message, int request) {
        if (attached) exceptions++;
    }

    private static boolean present(String value) { return value != null && value.length() != 0; }

    synchronized String status() {
        StringBuffer s = new StringBuffer(1024);
        s.append("format=1 build=").append(BuildInfo.ID).append(" observer_only=1 epoch=").append(epoch);
        s.append(" attached=").append(attached ? 1 : 0);
        s.append(" tracks=").append(tracks).append(" valid_tracks=").append(validTracks);
        s.append(" titles=").append(titles).append(" artists=").append(artists).append(" albums=").append(albums);
        s.append(" playback=").append(playback).append(" valid_playback=").append(validPlayback);
        s.append(" playback_state=").append(playbackState);
        s.append(" positions=").append(positions).append(" valid_positions=").append(validPositions);
        s.append(" covers=").append(covers).append(" valid_covers=").append(validCovers);
        s.append(" cover_urls=").append(coverUrls).append(" cover_ids=").append(coverIds);
        s.append(" exceptions=").append(exceptions).append(" clear_failures=").append(clearFailures);
        s.append(" io_failures=").append(ioFailures).append('\n');
        return s.toString();
    }

    private static final class StatusWriter implements Runnable {
        public void run() {
            long writes = 0;
            for (;;) {
                NowPlayingObserver observation = observation();
                long failures = failures();
                if (observation != null) {
                    try {
                        StringBuffer value = new StringBuffer(observation.status());
                        value.append("writes=").append(++writes).append(" attach_failures=").append(failures).append('\n');
                        byte[] bytes = value.toString().getBytes("US-ASCII");
                        if (bytes.length > 4096) throw new java.io.IOException("status bound");
                        File target = new File("/ramdisk/carplay-now-playing-n0.status");
                        File temp = new File("/ramdisk/carplay-now-playing-n0.status.new");
                        FileOutputStream stream = new FileOutputStream(temp);
                        try { stream.write(bytes); } finally { stream.close(); }
                        if (!temp.renameTo(target)) throw new java.io.IOException("status rename");
                    } catch (Throwable failure) {
                        synchronized (observation) { observation.ioFailures++; }
                    }
                }
                try { Thread.sleep(1000); } catch (InterruptedException stop) { return; }
            }
        }
    }

    public void updateMode(Resource[] r, AppState[] a, int valid) { }
    public void responseModeChange(Resource[] r, AppState[] a, int result) { }
    public void requestBTDeactivation(String address, int reason) { }
    public void updateDeviceInfo(DeviceInfo info, int valid) { }
    public void updateCallState(CallState[] state, int valid) { }
    public void updateTelephonyState(TelephonyState state, int valid) { }
    public void updateTextInputState(int state, int valid) { }
    public void duckAudio(int source, double level) { }
    public void unduckAudio(int source) { }
    public void oemAppSelected() { }
    public void updateMainAudioType(int type, int valid) { }
}
