/* SPDX-License-Identifier: GPL-3.0-or-later */
package com.cpmap.rgi;

import java.io.*;
import de.vw.mib.bap.datatypes.*;
import de.vw.mib.bap.mqbab2.generated.navsd.serializer.*;

/** Bounded numeric evidence only. Never supplies data to guidance/output gates.
 * HMI callbacks update memory; only the existing background status writer does IO.
 */
public final class LaneEvidence {
    static volatile String decoded="decoded=none\n",request="request=none\n",reply="reply=none\n";
    static volatile String selected="selected=none\n";
    static void selected(LiveModel.Frame f,long now){
        StringBuffer s=new StringBuffer("selected_at=").append(now).append(" lane_at=").append(f.laneAt)
            .append(" progress=").append(f.progress).append(" count=").append(f.lanes.length).append('\n');
        for(int i=0;i<f.lanes.length && i<16;i++){
            LaneData l=f.lanes[i];
            s.append("selected_lane=").append(l.position).append(" status=").append(l.sourceStatus)
                .append(" highlight=").append(l.sourceHighlight).append(" angles=").append(l.sourceAngles)
                .append(" main=").append(l.direction).append(" recommendation=").append(l.recommendation)
                .append(" description=").append(l.getLaneDescription()).append(" extras=");
            directions(s,l.sides);s.append('\n');
        }
        selected=s.toString();
    }
    static volatile long requests;
    static volatile int clusterRecords,hudRecords;
    static void received(LaneData[] lanes,int index,boolean invalid,long now){
        StringBuffer s=new StringBuffer("decoded_at=").append(now).append(" instruction=").append(index)
            .append(" invalid=").append(invalid?1:0).append(" count=").append(lanes.length).append('\n');
        for(int i=0;i<lanes.length && i<16;i++){
            LaneData l=lanes[i];
            s.append("source_lane=").append(l.position).append(" status=").append(l.sourceStatus)
                .append(" highlight=").append(l.sourceHighlight).append(" angles=").append(l.sourceAngles)
                .append(" main=").append(l.direction).append(" recommendation=").append(l.recommendation)
                .append(" extras=");directions(s,l.sides);s.append('\n');
        }
        decoded=s.toString();
    }
    static void directions(StringBuffer s,String values){
        if(values.length()==0){s.append('-');return;}
        for(int j=0;j<values.length() && j<16;j++){if(j>0)s.append(',');s.append((int)values.charAt(j));}
    }
    public static void requested(BAPEntity entity){
        try{
            if(!(entity instanceof LaneGuidance_GetArray))return;
            LaneGuidance_GetArray q=(LaneGuidance_GetArray)entity;ArrayHeader h=q.getArrayHeader();
            int asg=q.getAsgId(),record=h.getRecordAddress();requests++;
            if(record>=0 && record<16){
                if((asg&7)==1)clusterRecords|=1<<record;
                if((asg&7)==2)hudRecords|=1<<record;
            }
            request=new StringBuffer("request_at=").append(LiveBridge.now()).append(" asg=").append(asg)
                .append(" record=").append(record).append(" start=").append(h.start).append(" elements=").append(h.elements).append('\n').toString();
        }catch(Throwable ignored){/* Diagnostic observation must never change the OEM handler. */}
    }
    public static void assembled(LaneGuidance_StatusArray out){
        try{
            ArrayHeader h=out.getArrayHeader();BAPArrayData data=out.getArrayData();
            StringBuffer s=new StringBuffer("reply_at=").append(LiveBridge.now()).append(" record=").append(h.getRecordAddress())
                .append(" serialization_record=").append(h.getSerializationRecordAddress())
                .append(" start=").append(h.start).append(" count=").append(data.size())
                .append(" visible=").append(out.laneGuidanceOnOff).append('\n');
            for(int i=0;i<data.size() && i<8;i++){
                LaneGuidance_LaneGuidance l=(LaneGuidance_LaneGuidance)data.get(i);
                s.append("reply_lane=").append(l.getPos()).append(" main=").append(l.laneDirection)
                    .append(" recommendation=").append(l.guidanceInfo).append(" description=").append(l.laneDescription)
                    .append(" type=").append(l.laneType).append(" extras=");
                directions(s,l.laneSidestreets.toString());s.append('\n');
            }
            reply=s.toString();
        }catch(Throwable ignored){/* No output changes, including on diagnostic failure. */}
    }
    static String snapshot(){
        return new StringBuffer("format=1 lane_contract=available-lanes-v3\nrequests=").append(requests)
            .append(" cluster_record_mask=").append(clusterRecords).append(" hud_record_mask=").append(hudRecords)
            .append('\n').append(decoded).append(selected).append(request).append(reply).toString();
    }
    static void write(String root)throws IOException{
        byte[] body=snapshot().getBytes("US-ASCII");
        if(body.length>16384)throw new IOException("Lane evidence bound");
        File pending=new File(root,"lane-evidence.tmp"),target=new File(root,"lane-evidence.txt");
        FileOutputStream out=new FileOutputStream(pending);
        try{out.write(body);}finally{out.close();}
        if(!pending.renameTo(target))throw new IOException("Lane evidence rename");
    }
}
