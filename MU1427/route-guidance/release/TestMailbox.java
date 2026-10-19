/* SPDX-License-Identifier: GPL-3.0-or-later. Host harness, never installed. */
package com.cpmap.rgi;
import java.io.*;
public final class TestMailbox {
    public static void main(String[] args) throws Exception {
        MailboxReader reader=new MailboxReader(args[0]);
        BufferedReader commands=new BufferedReader(new InputStreamReader(System.in));
        String command;
        while ((command=commands.readLine())!=null) {
            try {
                LiveModel.Frame f=reader.next(Long.parseLong(command));
                if (f==null) System.out.println("same");
                else System.out.println((f.active?1:0)+","+f.main+","+f.direction+","+f.meters+","+f.remainingMeters+","+f.remainingSeconds+","+f.changed);
            } catch (IOException e) { System.out.println("invalid"); }
        }
    }
}
