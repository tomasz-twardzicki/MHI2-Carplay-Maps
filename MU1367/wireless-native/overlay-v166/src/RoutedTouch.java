/* SPDX-License-Identifier: GPL-3.0-or-later */
package de.vw.mib.asl.internal.wcpcp;

import java.io.File;
import java.io.FileOutputStream;
import java.net.DatagramPacket;
import java.net.DatagramSocket;
import java.net.InetAddress;
import org.dsi.ifc.carplay.TouchEvent;

/** Forward only touch events which passed the OEM widget hit-testing path. */
public final class RoutedTouch {
    private static DatagramSocket socket;
    private static InetAddress loopback;
    private static int sequence;
    private static long routed, rejected, failures, published;

    private RoutedTouch() {}

    public static synchronized boolean forward(Object[] args, boolean active) {
        if (!active || args == null || args.length != 3 ||
            !(args[0] instanceof Integer) || !(args[1] instanceof Integer) ||
            !(args[2] instanceof TouchEvent[])) return reject();
        int source = ((Integer)args[0]).intValue();
        int type = ((Integer)args[1]).intValue();
        TouchEvent[] contacts = (TouchEvent[])args[2];
        // This receiver protocol is a single-contact touchscreen interface.
        // Never reinterpret touchpad coordinates or invent a second contact.
        if (source != 1 || (type != 0 && type != 1) || contacts.length != 1 ||
            contacts[0] == null || contacts[0].x < 0 || contacts[0].x > 32767 ||
            contacts[0].y < 0 || contacts[0].y > 32767) return reject();
        try {
            if (socket == null) {
                socket = new DatagramSocket();
                loopback = InetAddress.getByName("127.0.0.1");
            }
            byte[] packet = new byte[12];
            packet[0] = 87; packet[1] = 84; packet[2] = 1;
            packet[3] = (byte)(type == 0 ? 3 : 4);
            put(packet, 4, contacts[0].x); put(packet, 6, contacts[0].y);
            put(packet, 8, 0); sequence = (sequence + 1) & 65535;
            put(packet, 10, sequence);
            socket.send(new DatagramPacket(packet, packet.length, loopback, 7102));
            routed++; publish(); return true;
        } catch (Exception error) {
            failures++; publish(); return false;
        }
    }

    private static boolean reject() { rejected++; publish(); return false; }
    private static void put(byte[] packet, int at, int value) {
        packet[at] = (byte)(value >> 8); packet[at + 1] = (byte)value;
    }
    public static synchronized String status() {
        return new StringBuffer("ROUTED_TOUCH1 path=oem-dsi raw_intercept=0 routed=")
            .append(routed).append(" rejected=").append(rejected)
            .append(" failures=").append(failures).append('\n').toString();
    }
    private static void publish() {
        long now = System.currentTimeMillis();
        if (now >= published && now - published < 1000) return;
        published = now;
        String root = System.getProperty("wcpcp.root", "");
        File target = new File(new StringBuffer(root).append("/ramdisk/cpmap-touch.status").toString());
        File pending = new File(new StringBuffer(target.getPath()).append(".new").toString());
        FileOutputStream output = null;
        try {
            output = new FileOutputStream(pending);
            output.write(status().getBytes("US-ASCII")); output.close(); output = null;
            if (!pending.renameTo(target)) pending.delete();
        } catch (Exception error) {
            if (output != null) try { output.close(); } catch (Exception ignored) {}
            pending.delete();
        }
    }
}
