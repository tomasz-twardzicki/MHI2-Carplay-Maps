/* SPDX-License-Identifier: GPL-3.0-or-later */
package com.cpmap.rgi;
import java.io.*;
/** HMI callbacks retain bounded values; only the existing reader writes RAM. */
final class RoadTrace {
 static final Object LOCK=new Object();
 static final String PATH="/ramdisk/cpmap-road-output.log";
 static final String[] text={"",""},reason={"not-proposed","not-proposed"},previous={"",""};
 static final LiveModel.Frame[] frame=new LiveModel.Frame[2];static final long[] at={-1,-1};
 static final String[] queue=new String[32];static int first,count;static long lost;
 static int slot(int id){return id==19?0:id==20?1:-1;}
 static String safe(String s){if(s==null)return "";StringBuffer b=new StringBuffer();for(int i=0;i<s.length()&&i<150;i++){char c=s.charAt(i);b.append(c<32||c==127?' ':c=='"'?'\'':c);}return b.toString();}
 static void prepare(int id,String why,LiveModel.Frame f,long time){synchronized(LOCK){int i=slot(id);if(i<0)return;reason[i]=why;frame[i]=f;at[i]=time;}}
 static void filled(int id,String value){synchronized(LOCK){int i=slot(id);if(i>=0)text[i]=safe(value);}}
 static void accepted(int id,boolean ok){synchronized(LOCK){
  int i=slot(id);if(i<0)return;LiveModel.Frame f=frame[i];
  String detail=new StringBuffer("f=").append(id).append(" accepted=").append(ok?1:0).append(" reason=").append(reason[i])
   .append(" epoch=").append(f==null?-1:f.epoch).append(" head=").append(f==null?-1:f.maneuverIndex)
   .append(" next_at=").append(f==null?-1:f.nextRoadAt).append(" route_at=").append(f==null?-1:f.laneAt)
   .append(" text=").append('"').append(text[i]).append('"').toString();
  String key=new StringBuffer().append(id).append(':').append(ok?1:0).append(':').append(reason[i]).append(':')
   .append(f==null?-1:f.epoch).append(':').append(f==null?-1:f.maneuverIndex).append(':').append(text[i]).toString();
  if(key.equals(previous[i]))return;previous[i]=key;
  if(count==32){first=(first+1)%32;count--;lost++;}
  queue[(first+count++)%32]=new StringBuffer("ROAD_OUTPUT t_ms=").append(at[i]).append(' ').append(detail).append(" trace_lost=").append(lost).append('\n').toString();
 }}
 static void flush(){
  String[] rows; synchronized(LOCK){if(count==0)return;rows=new String[count];for(int i=0;i<count;i++)rows[i]=queue[(first+i)%32];for(int i=0;i<32;i++)queue[i]=null;first=count=0;}
  try{File f=new File(PATH);if(f.exists()&&f.length()>32768){File old=new File(PATH+".1");if(old.exists()&&!old.delete())return;if(!f.renameTo(old))return;}
   FileOutputStream out=new FileOutputStream(f,true);try{for(int i=0;i<rows.length;i++)out.write(rows[i].getBytes("UTF-8"));}finally{out.close();}
  }catch(Throwable ignored){}
 }
}
