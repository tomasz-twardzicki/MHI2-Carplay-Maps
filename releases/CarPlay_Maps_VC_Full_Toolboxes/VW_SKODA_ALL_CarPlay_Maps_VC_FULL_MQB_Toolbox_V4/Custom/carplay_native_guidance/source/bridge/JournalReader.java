/* SPDX-License-Identifier: GPL-3.0-or-later */
package com.cpmap.rgi;

import java.io.IOException;
import java.io.RandomAccessFile;

/** Only the background thread reads this regular RAM file. Partial appended
 * records are held until complete; no payload reaches the HMI before validation.
 */
public final class JournalReader {
    final RandomAccessFile file;
    final LiveModel model=new LiveModel();
    long offset=16, initialBytes, elapsed=-1;
    boolean ended;
    long records;
    public JournalReader(String path) throws IOException {
        file=new RandomAccessFile(path,"r");
        try {
            initialBytes=file.length();
            LiveModel.require(initialBytes>=16 && initialBytes<=8388608);
            byte[] header=new byte[16]; file.readFully(header);
            LiveModel.require(LiveModel.u32(header,0)==0x314a4752L && LiveModel.u32(header,4)==1 && LiveModel.u32(header,8)==LiveModel.SNAP);
            LiveModel.require(LiveModel.u32(header,12)>=1 && LiveModel.u32(header,12)<=1000);
        } catch (IOException e) { file.close(); throw e; }
    }
    public void close() throws IOException { file.close(); }
    public LiveModel.Frame next(long now) throws IOException {
        long length=file.length();
        LiveModel.require(length>=offset && length<=8388608);
        if (length==offset) return null;
        LiveModel.require(!ended);
        if (length-offset<32) return null;
        file.seek(offset); byte[] h=new byte[32]; file.readFully(h);
        long kind=LiveModel.u32(h,0), at=LiveModel.u32(h,4), n=LiveModel.u32(h,8), detail=LiveModel.u32(h,12);
        LiveModel.require(n<=LiveModel.SNAP && at>=elapsed && at<=603000);
        for (int i=16;i<32;i+=4) LiveModel.require(LiveModel.u32(h,i)==0);
        if (length-offset-32<n) return null;
        byte[] payload=new byte[(int)n]; file.readFully(payload);
        LiveModel.Frame result;
        if (kind==1) { LiveModel.require(detail==0); result=model.snapshot(payload,now,offset+32+n<=initialBytes); }
        else {
            if (kind==2) LiveModel.require(detail>=1 && detail<=6 && (n==0 || n==4));
            else if (kind==3) LiveModel.require(n==0 && detail==5000);
            else if (kind==4) LiveModel.require(n==0);
            else if (kind==5) { LiveModel.require(n==0 && detail<=4); ended=true; }
            else LiveModel.require(false);
            if (kind!=4) model.invalidate();
            result=model.frame();
        }
        offset+=32+n; elapsed=at; records++;
        return result;
    }
}
