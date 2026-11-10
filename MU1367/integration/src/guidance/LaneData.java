/* SPDX-License-Identifier: GPL-3.0-or-later
 * Independent iAP2 lane decoder for the exact MHI2 navigation interface.
 * Protocol facts: perkthefox/mst2-cluster-nav docs/LANES.md, 7d836690.
 * No MST2 implementation or firmware code is included here.
 */
package com.cpmap.rgi;

import java.io.IOException;
import java.util.Iterator;
import java.util.NoSuchElementException;
import de.vw.mib.bap.mqbab2.common.api.navigation.datatypes.iterator.elements.NavigationLaneGuidanceElement;

public final class LaneData implements NavigationLaneGuidanceElement {
    static final LaneData[] EMPTY=new LaneData[0];
    final int position,direction,recommendation;
    final String sides;
    final int sourceStatus,sourceHighlight;
    final String sourceAngles;
    /* Exactly ±180° has no side. The byte stays the left U-turn until the
     * driving side is known: bit 16 is the main direction, bits 0-15 the
     * matching characters of sides. */
    final int unsided;
    LaneData(int p,int d,int r,String s){this(p,d,r,s,-1,1000,"-");}
    LaneData(int p,int d,int r,String s,int status,int highlight,String angles){this(p,d,r,s,status,highlight,angles,0);}
    LaneData(int p,int d,int r,String s,int status,int highlight,String angles,int unsidedMask){
        position=p;direction=d;recommendation=r;sides=s;
        sourceStatus=status;sourceHighlight=highlight;sourceAngles=angles;unsided=unsidedMask;
    }
    public int getDirection(){return direction;}
    public String getSideStreets(){return sides;}
    public int getLaneType(){return direction!=255 || sides.length()>0?1:0;}
    public int getMarkingLeft(){return 0;}
    public int getMarkingRight(){return 0;}
    public int getLaneDescription(){return direction!=255 || sides.length()>0?0:15;}
    public int getLaneGuidanceInfo(){return recommendation;}

    static int direction(int degrees){
        if(degrees < -180 || degrees > 180)return 255;
        // U-turn lanes: the factory VW lane bytes NAV_UTURN_LEFT_DIRECTION=114 / NAV_UTURN_RIGHT_DIRECTION=146
        // (no 128 U-turn symbol in the HMI); exactly 180 has no side: left here, see forSide()
        if(degrees <= -170 || degrees == 180)return 114;
        if(degrees >= 170)return 146;
        int sector=(Math.abs(degrees)*16+180)/360;
        return (degrees<0?sector*16:256-sector*16)&255;
    }
    static LaneData decode(byte[] data,int begin,int length){
        int end=begin+length,p=begin,fields=0,pos=-1,recommendation=0,highlight=255;
        boolean hasPosition=false,hasStatus=false,hasHighlight=false;
        int sourceStatus=-1,sourceHighlight=1000;
        StringBuffer sourceAngles=new StringBuffer();
        int[] plain=new int[16];boolean[] open=new boolean[16];int count=0,angles=0;boolean openHighlight=false;
        while(p<end){
            if(end-p<4 || ++fields>256)return null;
            int n=LiveModel.be16(data,p),key=LiveModel.be16(data,p+2);
            if(n<4 || n>end-p)return null;
            if(key==0){
                if(n!=6 || hasPosition)return null;hasPosition=true;pos=LiveModel.be16(data,p+4);
                if(pos==65535)return null;
            }else if(key==1){
                if(n!=5 || hasStatus)return null;hasStatus=true;recommendation=sourceStatus=data[p+4]&255;
                if(recommendation>2)recommendation=0;
            }else if(key==2){
                if(n!=6 || ++angles>16)return null;
                int degrees=(short)LiveModel.be16(data,p+4);
                if(sourceAngles.length()>0)sourceAngles.append(',');sourceAngles.append(degrees);
                int d=direction(degrees);boolean seen=false,sideless=degrees==180 || degrees==-180;
                // A signed angle on the same byte settles its side.
                for(int i=0;i<count;i++)if(plain[i]==d){seen=true;if(!sideless)open[i]=false;}
                if(d!=255 && !seen){open[count]=sideless;plain[count++]=d;}
            }else if(key==3){
                if(n!=6 || hasHighlight)return null;hasHighlight=true;sourceHighlight=(short)LiveModel.be16(data,p+4);highlight=direction(sourceHighlight);openHighlight=sourceHighlight==180 || sourceHighlight==-180;
            }
            p+=n;
        }
        if(!hasPosition)return null;
        // A drawable anchor is separate from a recommendation. Preserve all
        // supplied branches even when the phone did not select one of them.
        boolean certain=highlight!=255 || count==1;
        int main=highlight!=255?highlight:count>0?plain[0]:255;
        int unsided=(highlight!=255?openHighlight:count>0 && open[0])?1<<16:0;
        for(int i=0;i<count;i++)if(plain[i]==main && !open[i])unsided=0;
        if(!certain || main==255)recommendation=0;
        // One real primary direction plus the OTHER supplied branches.
        // Recommendation 0 stays unlit; duplicating the primary in the side
        // list is not a distinct outline command. Match the factory contract
        // and sibling reference, without inventing lane availability/type.
        char[] other=new char[count];int used=0;
        for(int i=0;i<count;i++)if(plain[i]!=main){if(open[i])unsided|=1<<used;other[used++]=(char)plain[i];}
        return new LaneData(pos,main,recommendation,new String(other,0,used),sourceStatus,sourceHighlight,
            sourceAngles.length()==0?"-":sourceAngles.toString(),unsided);
    }
    static final int LEFT_HAND_TRAFFIC=1, UTURN_LEFT=114, UTURN_RIGHT=146;
    /** In left-hand traffic a U-turn goes clockwise: a sideless 180° lane becomes the right U-turn. */
    LaneData forSide(int drivingSide){
        if(drivingSide!=LEFT_HAND_TRAFFIC || unsided==0)return this;
        int main=(unsided&1<<16)!=0 && direction==UTURN_LEFT?UTURN_RIGHT:direction;
        char[] other=new char[sides.length()];int used=0;
        for(int i=0;i<sides.length();i++){
            int d=sides.charAt(i);if((unsided&1<<i)!=0 && d==UTURN_LEFT)d=UTURN_RIGHT;
            boolean seen=d==main;for(int j=0;j<used;j++)if(other[j]==d)seen=true;
            if(!seen)other[used++]=(char)d;
        }
        return new LaneData(position,main,recommendation,new String(other,0,used),sourceStatus,sourceHighlight,sourceAngles,0);
    }
    static LaneData[] forSide(LaneData[] lanes,int drivingSide){
        if(drivingSide!=LEFT_HAND_TRAFFIC)return lanes;
        LaneData[] result=lanes;
        for(int i=0;i<lanes.length;i++){
            LaneData next=lanes[i].forSide(drivingSide);
            if(next!=lanes[i]){if(result==lanes){result=new LaneData[lanes.length];System.arraycopy(lanes,0,result,0,lanes.length);}result[i]=next;}
        }
        return result;
    }
    static LaneData[] ordered(LaneData[] input,boolean invalid){
        if(invalid || input.length==0 || input.length>16)return EMPTY;
        LaneData[] result=new LaneData[input.length];System.arraycopy(input,0,result,0,input.length);
        boolean known=false;
        for(int i=0;i<result.length;i++){
            LaneData item=result[i];if(item==null)return EMPTY;
            if(item.direction!=255 || item.sides.length()>0)known=true;
            int at=i;
            while(at>0 && result[at-1].position>item.position){result[at]=result[at-1];at--;}
            result[at]=item;
        }
        for(int i=1;i<result.length;i++)if(result[i-1].position==result[i].position)return EMPTY;
        return known?result:EMPTY;
    }
    static Iterator iterator(final LaneData[] values){
        return new Iterator(){int at;
            public boolean hasNext(){return at<values.length;}
            public Object next(){if(!hasNext())throw new NoSuchElementException();return values[at++];}
            public void remove(){throw new UnsupportedOperationException();}
        };
    }
    /** Independent bounded instruction cache, including explicit empty replacements. */
    static final class Cache {
        static final int CAPACITY=32;
        final int[] keys=new int[CAPACITY];final LaneData[][] values=new LaneData[CAPACITY][];
        final long[] age=new long[CAPACITY];long serial;int selected=-1;boolean showing;
        void clear(){for(int i=0;i<CAPACITY;i++)values[i]=null;selected=-1;showing=false;}
        void put(int index,LaneData[] lanes){
            if(index==65535)return;
            int slot=-1;
            for(int i=0;i<CAPACITY;i++)if(values[i]!=null && keys[i]==index){slot=i;break;}
            if(slot<0)for(int i=0;i<CAPACITY;i++)if(values[i]==null){slot=i;break;}
            if(slot<0){long oldest=Long.MAX_VALUE;for(int i=0;i<CAPACITY;i++)if(keys[i]!=selected && age[i]<oldest){slot=i;oldest=age[i];}}
            if(slot<0)return;
            keys[slot]=index;values[slot]=lanes;age[slot]=++serial;
        }
        LaneData[] current(){
            if(!showing || selected<0 || selected==65535)return EMPTY;
            for(int i=0;i<CAPACITY;i++)if(values[i]!=null && keys[i]==selected)return values[i];
            return EMPTY;
        }
    }
}
