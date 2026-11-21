/* SPDX-License-Identifier: GPL-3.0-or-later */
package com.cpmap.rgi;
import java.io.*;
/** Live OEM coding plus a last-known value for early wireless boot. */
final class DriverSide {
    int previous=-1,cached=-1;
    boolean write(String directory,int side) {
        File target=new File(directory,"cpmap-driver-side.state"),stage=new File(directory,"cpmap-driver-side.new");
        try {
            FileOutputStream f=new FileOutputStream(stage);
            try {
                f.write((new StringBuffer("CPDS1\n").append(side).append('\n').toString()).getBytes("US-ASCII"));
                if(directory.equals("/mnt/persist"))f.getFD().sync();
            } finally {f.close();}
            if(stage.renameTo(target))return true;
        }catch(Throwable ignored) {}
        stage.delete();return false;
    }
    void poll() {
        int side=0;
        try {side=de.vw.mib.asl.framework.internal.framework.ServiceManager.configManagerDiag.getDriverSide();}
        catch(Throwable ignored) {}
        if(side!=1 && side!=2)side=0;
        if(side==0) {
            if(previous!=0) {new File("/ramdisk/cpmap-driver-side.state").delete();previous=0;}
            return; // Unknown live coding never overwrites the last known value.
        }
        if(side!=previous && write("/ramdisk",side))previous=side;
        if(side!=cached && write("/mnt/persist",side))cached=side;
    }
}
