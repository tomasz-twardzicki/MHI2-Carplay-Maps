/* SPDX-License-Identifier: GPL-3.0-or-later */
package com.cpmap.rgi;
import java.io.*;
import java.util.*;
public final class TestRoadLabel {
 static int checks;
 static void check(boolean ok,String why){checks++;if(!ok)throw new RuntimeException(why);}
 static void le(byte[] b,int p,long n,int width){for(int i=0;i<width;i++)b[p+i]=(byte)(n>>8*i);}
 static byte[] value(int n,int width){byte[] b=new byte[width];for(int i=0;i<width;i++)b[width-1-i]=(byte)(n>>8*i);return b;}
 static byte[] param(int id,byte[] b)throws Exception {ByteArrayOutputStream out=new ByteArrayOutputStream();out.write(value(b.length+4,2));out.write(value(id,2));out.write(b);return out.toByteArray();}
 static byte[] join(byte[][] b)throws Exception{ByteArrayOutputStream out=new ByteArrayOutputStream();for(int i=0;i<b.length;i++)if(b[i]!=null)out.write(b[i]);return out.toByteArray();}
 static byte[] text(String s)throws Exception{return s.getBytes("UTF-8");}
 static byte[] route(int phase,int[] order,String road)throws Exception {
  ByteArrayOutputStream indices=new ByteArrayOutputStream();for(int i=0;i<order.length;i++)indices.write(value(order[i],2));
  return join(new byte[][]{param(0,value(16,2)),param(1,value(phase,1)),param(3,text(road)),param(10,value(100,4)),param(13,indices.toByteArray())});
 }
 static byte[] maneuver(int index,String road)throws Exception{
  return join(new byte[][]{param(0,value(16,2)),param(1,value(index,2)),param(3,value(6,1)),param(8,value(0,1)),param(9,value(1,1)),road==null?null:param(4,text(road))});
 }
 static final class Journal {
  Vector ids=new Vector(),payloads=new Vector();int sequence;LiveModel model=new LiveModel();
  LiveModel.Frame add(int id,byte[] payload,long now)throws Exception{
   ids.addElement(new Integer(id));payloads.addElement(payload);sequence++;
   if(ids.size()>16){ids.removeElementAt(0);payloads.removeElementAt(0);}
   int size=64;for(int i=0;i<ids.size();i++)size+=16+((byte[])payloads.elementAt(i)).length;
   byte[] b=new byte[size];le(b,0,0x31494752L,4);le(b,4,1,4);le(b,8,33088,4);le(b,16,1,4);le(b,20,sequence,4);le(b,24,ids.size(),4);le(b,36,1,4);le(b,40,1,4);le(b,44,1,4);
   int at=64;for(int i=0;i<ids.size();i++){
    byte[] p=(byte[])payloads.elementAt(i);le(b,at,sequence-ids.size()+i+1,4);le(b,at+4,((Integer)ids.elementAt(i)).intValue(),2);le(b,at+6,p.length,2);le(b,at+8,1,4);System.arraycopy(p,0,b,at+16,p.length);at+=16+p.length;
   }
   return model.snapshot(b,now,false);
  }
 }
 public static void run()throws Exception{
  Journal j=new Journal();LiveModel.Frame f=j.add(0x5201,route(1,new int[]{0,1,2},"Current"),1000);
  RoadName.mode=RoadName.NEXT;check(RoadName.display(f,1000).equals(""),"unknown maneuver blank");
  f=j.add(0x5201,route(1,new int[]{0,1,2},"Current"),1050);
  f=j.add(0x5202,maneuver(0,"Next zero"),1100);check(RoadName.display(f,1100).equals("Next zero"),"current maneuver next road");
  RoadName.mode=RoadName.CURRENT;check(RoadName.display(f,1100).equals("Current"),"current mode retained");
  RoadName.mode=RoadName.OFF;check(RoadName.display(f,1100).equals(""),"off mode");RoadName.mode=RoadName.NEXT;
  f=j.add(0x5202,maneuver(1,"Next one"),1200);check(RoadName.display(f,1200).equals("Next zero"),"lookahead cannot override current head");
  f=j.add(0x5201,route(1,new int[]{1,2},"New current"),1300);check(RoadName.display(f,1300).equals("Next one"),"same route prefetched head survives without resend");
  f=j.add(0x5201,route(1,new int[]{2},"Current"),1400);check(RoadName.display(f,1400).equals(""),"missing next head blank");
  f=j.add(0x5202,maneuver(2,null),1500);check(RoadName.display(f,1500).equals(""),"omitted road blank");
  f=j.add(0x5201,route(1,new int[]{0},"Current"),1600);check(RoadName.display(f,1600).equals(""),"index reused cannot inherit passed text");
  f=j.add(0x5202,maneuver(0,"New traversal"),1700);check(RoadName.display(f,1700).equals("New traversal"),"matching new message restores text");
  check(RoadName.display(f,181700).equals(""),"stale route blank");check(RoadName.display(f,1599).equals(""),"backwards clock blank");
  f=j.add(0x5201,route(3,new int[]{0},"Current"),1800);check(RoadName.display(f,1800).equals(""),"reroute blank");
  f=j.add(0x5201,route(1,new int[]{0},"Current"),1900);check(RoadName.display(f,1900).equals(""),"old route same index not reused");
  f=j.add(0x5202,maneuver(0,"After reroute"),2000);
  j.model.quiet();f=j.model.frame();check(RoadName.display(f,2000).equals("After reroute"),"new route gets fresh matching maneuver");
  StringBuffer many=new StringBuffer();for(int i=0;i<100;i++)many.append('\u00e9');
  f=j.add(0x5202,maneuver(0,many.toString()),2100);j.model.quiet();f=j.model.frame();
  String clipped=RoadName.display(f,2100);check(clipped.getBytes("UTF-8").length==74,"75 byte UTF8 cap keeps full characters");
  check(clipped.indexOf('\ufffd')<0,"UTF8 unbroken");
  f=j.add(0x5201,route(0,new int[0],""),2200);check(RoadName.display(f,2200).equals(""),"route end blank");
  Journal source=new Journal();
  byte[] google=join(new byte[][]{route(1,new int[]{0},"Current"),param(19,text("Google Maps"))});
  source.add(0x5201,google,3000);source.add(0x5201,google,3100);f=source.add(0x5202,maneuver(0,"Google next"),3200);
  check(RoadName.display(f,3200).equals("Google next"),"source-bound road");
  f=source.add(0x5201,join(new byte[][]{route(1,new int[]{0},"Current"),param(19,text("Waze"))}),3300);
  check(RoadName.display(f,3300).equals(""),"app/source replacement cannot reuse road");
  source.model.invalidate();check(RoadName.display(source.model.frame(),3400).equals(""),"session invalidation blank");
  Journal shortList=new Journal();RoadName.mode=RoadName.NEXT;
  shortList.add(0x5201,route(1,new int[]{5},"Current"),4000);shortList.add(0x5201,route(1,new int[]{5},"Current"),4050);
  shortList.add(0x5202,maneuver(5,"Fifth"),4100);shortList.add(0x5202,maneuver(6,"Sixth prefetched"),4200);
  f=shortList.add(0x5201,route(1,new int[]{6,7},"Current"),4300);
  check(RoadName.display(f,4300).equals("Sixth prefetched"),"prefetch before index enters short order is retained");
  f=shortList.add(0x5201,route(1,new int[]{7},"Current"),4400);
  check(f.nextRoadReason.equals("no-head-cache"),"missing head diagnostic");
  f=shortList.add(0x5201,route(1,new int[]{6},"Current"),4500);
  check(RoadName.display(f,4500).equals("")&&f.nextRoadReason.equals("head-reused"),"consumed index cannot inherit its old road");
  f=shortList.add(0x5202,maneuver(6,"Fresh sixth"),4600);
  check(RoadName.display(f,4600).equals("Fresh sixth")&&f.nextRoadReason.equals("ready"),"new matching record restores reused head");
  RoadName.mode=RoadName.CURRENT;
  System.out.println(new StringBuffer("ROAD_LABEL_PASS checks=").append(checks).append(" current_next_off=1 route_epoch_and_index=1 utf8_limit=75 prefetched_head=1").toString());
 }
 public static void main(String[] args)throws Exception{run();}
}
