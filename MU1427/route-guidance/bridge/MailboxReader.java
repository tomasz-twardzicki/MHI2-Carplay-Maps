/* SPDX-License-Identifier: GPL-3.0-or-later */
package com.cpmap.rgi;

import java.io.*;

/** Bounded atomic RAM mailbox. Only the background thread reads it. */
public final class MailboxReader {
    final String path;
    LiveModel model=new LiveModel();
    long instance=-1, serial;
    boolean baseline, ended;
    byte[] previous;
    long records;
    public MailboxReader(String p) { path=p; }
    public LiveModel.Frame next(long now) throws IOException {
        FileInputStream in=new FileInputStream(path);
        byte[] bytes=new byte[LiveModel.SNAP+33]; int size=0;
        try {
            for (;;) {
                int n=in.read(bytes,size,bytes.length-size);
                if (n<0) break;
                LiveModel.require(n>0); size+=n;
                LiveModel.require(size<bytes.length);
            }
        } finally { in.close(); }
        LiveModel.require(size>=32 && LiveModel.u32(bytes,0)==0x314d4752L && LiveModel.u32(bytes,4)==1
            && LiveModel.u32(bytes,8)==size);
        long number=LiveModel.u32(bytes,12), kind=LiveModel.u32(bytes,16), detail=LiveModel.u32(bytes,20);
        long nonce=LiveModel.u32(bytes,24) | LiveModel.u32(bytes,28)<<32;
        LiveModel.require(number>0);
        byte[] complete=LiveModel.copy(bytes,0,size);
        if (nonce!=instance) {
            model=new LiveModel(); baseline=false; ended=false; serial=0; previous=null; instance=nonce;
        }
        LiveModel.require(number>=serial);
        if (number==serial) { LiveModel.require(LiveModel.equal(previous,complete)); return null; }
        LiveModel.Frame frame;
        if (kind==1) {
            LiveModel.require(!ended && detail==0);
            frame=model.snapshot(LiveModel.copy(bytes,32,size-32),now,!baseline);
            baseline=true;
        } else {
            LiveModel.require(!ended || kind==5);
            if (kind==2) LiveModel.require(detail>=1 && detail<=6 && (size==32 || size==36));
            else if (kind==3) LiveModel.require(size==32 && detail==5000);
            else if (kind==5) { LiveModel.require(size==32 && detail<=4); ended=true; }
            else LiveModel.require(false);
            model.invalidate(); frame=model.frame();
        }
        serial=number; previous=complete; records++; return frame;
    }
}
