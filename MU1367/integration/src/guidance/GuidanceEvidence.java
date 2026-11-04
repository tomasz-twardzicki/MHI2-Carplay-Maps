/* SPDX-License-Identifier: GPL-3.0-or-later */
package com.cpmap.rgi;

import java.io.*;

/** Bounded structural guidance evidence. Never feeds output gates.
 * Records message kinds, route states, maneuver types, components, gaps,
 * rejections and the phone app's source name; never road/destination text.
 * Only the background reader thread calls it, including the file writer.
 */
public final class GuidanceEvidence {
    static final int SOURCES=4;
    static long session=-1, high=0, route, maneuver, lane, rejected, rejectedRoute, notApplied, quiet;
    static long lastAt=-1, maxGap, gaps5, gaps30, gaps180;
    static final long[] states=new long[8];
    static final long[] types=new long[54];
    static long otherStates, otherTypes;
    static final int[] components=new int[8];
    static final long[] componentCounts=new long[8];
    static String firstRejected="none", lastRejected="none";
    static final String[] sourceNames=new String[SOURCES];
    static final long[] sourceMessages=new long[SOURCES];
    static int source=-1;
    static long sourceChanges;

    static void message(long wire,long seq,LiveModel.Message m,FeedRecovery.Fault fault,long now){
        // A feed rebase replays the retained window; count each message once.
        if(wire==session && seq<=high)return;
        if(wire!=session){session=wire;high=0;source=-1;lastAt=-1;}
        high=seq;
        if(lastAt>=0 && now>=lastAt){
            long gap=now-lastAt;
            if(gap>maxGap)maxGap=gap;
            if(gap>=5000)gaps5++;
            if(gap>=30000)gaps30++;
            if(gap>=LiveModel.HOLD_MS)gaps180++;
        }
        lastAt=now;
        if(m==null){
            rejected++;if(fault.message==0x5201)rejectedRoute++;
            String text=new StringBuffer("seq=").append(seq).append(" id=").append(Integer.toHexString(fault.message))
                .append(" field=").append(fault.field).append(" at=").append(now).append(" shape=").append(fault.shape).toString();
            if(text.length()>400)text=text.substring(0,400);
            if(firstRejected.equals("none"))firstRejected=text;
            lastRejected=text;
            countSource();
            return;
        }
        if(m.id==0x5201){
            route++;
            if(m.has[19])source(m.raw[19]);
            if(m.has[1]){int state=(int)m.v[1];if(state>=0 && state<8)states[state]++;else otherStates++;}
        }else if(m.id==0x5202){
            maneuver++;
            if(m.has[3]){int t=(int)m.v[3];if(t>=0 && t<54)types[t]++;else otherTypes++;}
        }else lane++;
        if(m.components!=null)for(int i=0;i<m.components.length;i++)component(m.components[i]);
        countSource();
    }
    static void notApplied(){notApplied++;}
    static void quiet(long now){quiet++;}
    static void component(int id){
        for(int i=0;i<components.length;i++){
            if(componentCounts[i]>0 && components[i]==id){componentCounts[i]++;return;}
            if(componentCounts[i]==0){components[i]=id;componentCounts[i]=1;return;}
        }
    }
    static void countSource(){if(source>=0)sourceMessages[source]++;}
    static void source(byte[] raw){
        // App name only: printable ASCII, bounded; anything else becomes '?'.
        StringBuffer s=new StringBuffer();
        for(int i=0;raw!=null && i<raw.length && s.length()<32;i++){
            int c=raw[i]&255;if(c==0)break;
            s.append(c>=32 && c<127 && c!='=' && c!=';'?(char)c:c==32?' ':'?');
        }
        String name=s.toString().replace(' ','_');
        if(name.length()==0)name="-";
        int slot=-1;
        for(int i=0;i<SOURCES;i++)if(name.equals(sourceNames[i]))slot=i;
        if(slot<0){
            for(int i=0;i<SOURCES && slot<0;i++)if(sourceNames[i]==null)slot=i;
            if(slot<0)slot=SOURCES-1; // Retain the first three; the last slot rotates.
            sourceNames[slot]=name;sourceMessages[slot]=0;
        }
        if(slot!=source){if(source>=0)sourceChanges++;source=slot;}
    }
    static String snapshot(){
        StringBuffer s=new StringBuffer("format=1 hold_ms=").append(LiveModel.HOLD_MS)
            .append(" route=").append(route).append(" maneuver=").append(maneuver).append(" lane=").append(lane)
            .append(" rejected=").append(rejected).append(" rejected_route=").append(rejectedRoute)
            .append(" not_applied=").append(notApplied).append(" quiet=").append(quiet)
            .append(" max_gap_ms=").append(maxGap).append(" gaps_5s=").append(gaps5).append(" gaps_30s=").append(gaps30)
            .append(" gaps_hold=").append(gaps180).append(" sequence=").append(high).append('\n');
        s.append("states=");for(int i=0;i<states.length;i++){if(i>0)s.append(',');s.append(states[i]);}
        s.append(" other=").append(otherStates).append('\n');
        s.append("maneuver_types=");boolean any=false;
        for(int i=0;i<types.length;i++)if(types[i]>0){if(any)s.append(',');s.append(i).append(':').append(types[i]);any=true;}
        if(!any)s.append('-');
        s.append(" other=").append(otherTypes).append('\n');
        s.append("components=");any=false;
        for(int i=0;i<components.length;i++)if(componentCounts[i]>0){if(any)s.append(',');s.append(Integer.toHexString(components[i])).append(':').append(componentCounts[i]);any=true;}
        if(!any)s.append('-');
        s.append('\n').append("sources=");any=false;
        for(int i=0;i<SOURCES;i++)if(sourceNames[i]!=null){if(any)s.append(';');s.append(sourceNames[i]).append(':').append(sourceMessages[i]);any=true;}
        if(!any)s.append('-');
        s.append(" current=").append(source<0?"-":sourceNames[source]).append(" changes=").append(sourceChanges).append('\n');
        s.append("first_rejected ").append(firstRejected).append('\n');
        s.append("last_rejected ").append(lastRejected).append('\n');
        return s.toString();
    }
    static void write(String root)throws IOException{
        byte[] body=snapshot().getBytes("US-ASCII");
        if(body.length>4096)throw new IOException("Guidance evidence bound");
        File pending=new File(root,"guidance-evidence.tmp"),target=new File(root,"guidance-evidence.txt");
        FileOutputStream out=new FileOutputStream(pending);
        try{out.write(body);}finally{out.close();}
        if(!pending.renameTo(target))throw new IOException("Guidance evidence rename");
    }
}
