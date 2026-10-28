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
    LaneData(int p,int d,int r,String s){position=p;direction=d;recommendation=r;sides=s;}
    public int getDirection(){return direction;}
    public String getSideStreets(){return sides;}
    public int getLaneType(){return 0;}
    public int getMarkingLeft(){return 0;}
    public int getMarkingRight(){return 0;}
    public int getLaneDescription(){return 15;}
    public int getLaneGuidanceInfo(){return recommendation;}

    static int direction(int degrees){
        if(degrees < -180 || degrees > 180)return 255;
        int sector=(Math.abs(degrees)*16+180)/360;
        return (degrees<0?sector*16:256-sector*16)&255;
    }
    static LaneData decode(byte[] data,int begin,int length){
        int end=begin+length,p=begin,fields=0,pos=-1,recommendation=0,highlight=255;
        boolean hasPosition=false,hasStatus=false,hasHighlight=false;
        int[] plain=new int[16];int count=0,angles=0;
        while(p<end){
            if(end-p<4 || ++fields>256)return null;
            int n=LiveModel.be16(data,p),key=LiveModel.be16(data,p+2);
            if(n<4 || n>end-p)return null;
            if(key==0){
                if(n!=6 || hasPosition)return null;hasPosition=true;pos=LiveModel.be16(data,p+4);
                if(pos==65535)return null;
            }else if(key==1){
                if(n!=5 || hasStatus)return null;hasStatus=true;recommendation=data[p+4]&255;
                if(recommendation>2)recommendation=0;
            }else if(key==2){
                if(n!=6 || ++angles>16)return null;
                int d=direction((short)LiveModel.be16(data,p+4));boolean seen=false;
                for(int i=0;i<count;i++)if(plain[i]==d)seen=true;
                if(d!=255 && !seen)plain[count++]=d;
            }else if(key==3){
                if(n!=6 || hasHighlight)return null;hasHighlight=true;highlight=direction((short)LiveModel.be16(data,p+4));
            }
            p+=n;
        }
        if(!hasPosition)return null;
        int main=highlight!=255?highlight:count==1?plain[0]:255;
        // Ambiguous exits stay visible but cannot become a recommended exit.
        if(main==255)recommendation=0;
        char[] other=new char[count];int used=0;
        for(int i=0;i<count;i++)if(plain[i]!=main)other[used++]=(char)plain[i];
        return new LaneData(pos,main,recommendation,new String(other,0,used));
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
        final int[] keys=new int[6];final LaneData[][] values=new LaneData[6][];
        final long[] age=new long[6];long serial;int selected=-1;boolean showing;
        void clear(){for(int i=0;i<6;i++)values[i]=null;selected=-1;showing=false;}
        void put(int index,LaneData[] lanes){
            if(index==65535)return;
            int slot=-1;
            for(int i=0;i<6;i++)if(values[i]!=null && keys[i]==index){slot=i;break;}
            if(slot<0)for(int i=0;i<6;i++)if(values[i]==null){slot=i;break;}
            if(slot<0){long oldest=Long.MAX_VALUE;for(int i=0;i<6;i++)if(keys[i]!=selected && age[i]<oldest){slot=i;oldest=age[i];}}
            if(slot<0)return;
            keys[slot]=index;values[slot]=lanes;age[slot]=++serial;
        }
        LaneData[] current(){
            if(!showing || selected<0 || selected==65535)return EMPTY;
            for(int i=0;i<6;i++)if(values[i]!=null && keys[i]==selected)return values[i];
            return EMPTY;
        }
    }
}
