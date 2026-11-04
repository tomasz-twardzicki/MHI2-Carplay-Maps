/* SPDX-License-Identifier: GPL-3.0-or-later */
package com.cpmap.rgi;

import java.io.*;

/** Background-only feed owner. Strict validation; recovery never publishes its baseline. */
public final class FeedRecovery {
    static final long RETRY_MS=1000;
    static final class Fault extends IOException {
        final int message,field; long sequence=-1;
        String shape="";
        Fault(int id,int key){super("Guidance field validation");message=id;field=key;}
    }
    final String root,path;
    MailboxReader reader;
    LiveModel.Frame last;
    long roadFields,roadNonempty,laneMessages,neutralLanes,neutralBranches;
    long generation,errors,recoveries,recordAt=-1,retryAt=-1;
    boolean live,fatal,pending;
    int error;
    String lastException="none";
    FeedRecovery(String directory){root=directory;path=file("latest.bin");reader=new MailboxReader(path);}
    String file(String name){return new StringBuffer(root).append('/').append(name).toString();}

    void clear(){live=false;recordAt=-1;last=null;}
    void rebase(){reader=new MailboxReader(path);generation++;clear();}
    void pause(){rebase();retryAt=-1;}
    LiveModel.Frame poll(long now){
        if(fatal)return null;
        if(retryAt>=0 && now<retryAt)return null;
        retryAt=-1;
        try {
            long oldInstance=reader.instance;
            LiveModel oldModel=reader.model;
            LiveModel.Frame frame=reader.next(now);
            // A reader process restart and a DIO source/session restart are
            // independent boundaries. Both restart the model's progress counter.
            if(oldInstance!=reader.instance || oldModel!=reader.model){generation++;clear();}
            LiveModel evidence=reader.model;
            roadFields+=evidence.roadFields;roadNonempty+=evidence.roadNonempty;
            laneMessages+=evidence.laneMessages;neutralLanes+=evidence.neutralLanes;neutralBranches+=evidence.neutralBranches;
            evidence.roadFields=evidence.roadNonempty=evidence.laneMessages=evidence.neutralLanes=evidence.neutralBranches=0;
            if(frame!=null)recordAt=now;
            return accept(frame,now);
        }catch(FileNotFoundException e){
            if(new File(path).exists())failed(e,now);
            else {rebase();retryAt=now+RETRY_MS;}
        }catch(Throwable t){failed(t,now);}
        return null;
    }
    private LiveModel.Frame accept(LiveModel.Frame frame,long now){
        // A valid unchanged mailbox is not a new producer heartbeat.
        if(frame!=null)last=frame;
        boolean fresh=last!=null && last.active && last.progress>0 && last.changed>=0 && now>=last.changed && now-last.changed<LiveModel.HOLD_MS
            && recordAt>=0 && now>=recordAt && now-recordAt<1500;
        live=!reader.ended && fresh;
        if(live && pending){recoveries++;pending=false;error=0;}
        return frame;
    }
    void failed(Throwable t,long now){
        clear();errors++;error=1;pending=true;lastException=t.getClass().getName();
        fatal=!(t instanceof IOException);
        firstFailure(t,now);
        rebase();retryAt=now+RETRY_MS;
    }
    private void firstFailure(Throwable t,long now){
        File target=new File(file("failure-first.txt")),temp=new File(file("failure-first.tmp"));
        if(target.exists())return;
        try {
            StringBuffer s=new StringBuffer("format=1 time_ms=");
            s.append(now).append(" exception=").append(lastException).append(" fatal=").append(fatal?1:0)
             .append(" serial=").append(reader.observedSerial).append(" kind=").append(reader.observedKind)
             .append(" nonce=").append(reader.observedNonce);
            if(t instanceof Fault){Fault f=(Fault)t;s.append(" sequence=").append(f.sequence).append(" message=").append(f.message).append(" field=").append(f.field);}
            s.append('\n');byte[] bytes=s.toString().getBytes("US-ASCII");
            if(bytes.length>768)return;
            FileOutputStream out=new FileOutputStream(temp);
            try {out.write(bytes);}finally{out.close();}
            if(!target.exists())temp.renameTo(target);
        }catch(IOException ignored){}finally{temp.delete();}
    }
}
