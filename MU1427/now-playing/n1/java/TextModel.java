/* SPDX-License-Identifier: GPL-3.0-or-later */
package com.cpmap.audio;

import org.dsi.ifc.carplay.TrackData;

/** One bounded immutable track; explicit invalidation, no navigation-style TTL. */
public final class TextModel {
    public static final class Frame {
        public final String title, artist, album;
        public final long revision;
        Frame(String t, String a, String b, long r) { title=t; artist=a; album=b; revision=r; }
    }
    private Frame frame = new Frame("", "", "", 0);
    public synchronized Frame frame() { return frame; }
    public synchronized void clear() { frame = new Frame("", "", "", frame.revision+1); }
    public synchronized void track(TrackData input, int valid) {
        if (valid != 1 || input == null) { clear(); return; }
        frame = new Frame(text(input.title), text(input.artist), text(input.album), frame.revision+1);
    }
    static String text(String input) {
        if (input == null) return "";
        int size = input.length();
        // Bound all scanning as well as storage. Reject an oversized native value.
        if (size > 4096) return "";
        int limit = size > 256 ? 256 : size;
        if (limit < size && input.charAt(limit-1) >= 0xd800 && input.charAt(limit-1) <= 0xdbff) limit--;
        for (int i=0; i<limit; i++) {
            char c=input.charAt(i);
            if (c < 32 || c >= 127 && c <= 159) return "";
            if (c >= 0xd800 && c <= 0xdbff) {
                if (++i >= limit || input.charAt(i) < 0xdc00 || input.charAt(i) > 0xdfff) return "";
            } else if (c >= 0xdc00 && c <= 0xdfff) return "";
        }
        return input.substring(0, limit).trim();
    }
}
