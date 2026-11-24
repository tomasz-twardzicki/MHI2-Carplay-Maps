/* SPDX-License-Identifier: GPL-3.0-or-later */
package de.vw.mib.asl.internal.wcpcp;
import java.io.*;
import org.dsi.ifc.carplay.ResourceRequest;
/** Callback only stores numbers. The existing WcpCp worker owns RAM output. */
public final class MainScreenTrace {
 static final String PATH="/ramdisk/cpmap-main-screen.log";
 static volatile int transfer=-1;static volatile long resources;
 static long began=-1,written=-1;static String previous="";
 public static void resource(Object[] arguments){
  if(arguments==null||arguments.length==0||!(arguments[0] instanceof ResourceRequest[]))return;
  ResourceRequest[] values=(ResourceRequest[])arguments[0];
  for(int i=0;i<values.length;i++)if(values[i]!=null&&values[i].resourceID==2){transfer=values[i].transferType;resources++;}
 }
 static String state(int stage,boolean session,boolean foreground,int canvas,boolean confirm){
  return new StringBuffer("stage=").append(stage).append(" session=").append(session?1:0)
   .append(" foreground=").append(foreground?1:0).append(" canvas=").append(canvas).append(" confirm=").append(confirm?1:0)
   .append(" transfer=").append(transfer).append(" resources=").append(resources).toString();
 }
 public static void sample(int stage,boolean session,boolean foreground,int canvas,boolean confirm){
  try{
   long wall=System.currentTimeMillis(),asl=-1;
   try{asl=de.vw.mib.asl.framework.api.framework.ASLFrameworkFactory.getASLFrameworkAPI().getServices().getTimerManager().getSystemTimeMillis();}catch(Throwable unavailable){}
   String current=state(stage,session,foreground,canvas,confirm);boolean changed=!current.equals(previous);
   if(began<0||wall<began)began=wall;
   if(!changed&&(wall-began>=180000||written>=0&&wall>=written&&wall-written<1000))return;
   previous=current;written=wall;
   String line=new StringBuffer("WCP_MAIN wall_ms=").append(wall).append(" asl_ms=").append(asl).append(' ').append(current).append('\n').toString();
   File file=new File(PATH);byte[] b=line.getBytes("US-ASCII");
   if(file.exists()&&file.length()+b.length>32768){File old=new File(PATH+".1");if(old.exists()&&!old.delete())return;if(!file.renameTo(old))return;}
   FileOutputStream out=new FileOutputStream(file,true);try{out.write(b);}finally{out.close();}
  }catch(Throwable ignored){}
 }
}
