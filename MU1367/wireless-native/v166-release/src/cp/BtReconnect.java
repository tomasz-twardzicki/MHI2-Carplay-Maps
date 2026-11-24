/* SPDX-License-Identifier: GPL-3.0-or-later */
package de.vw.mib.asl.internal.wcpcp;
import java.io.*;
import java.util.*;
import de.vw.mib.asl.internal.phone.ASLPhoneData;
import de.vw.mib.asl.internal.phone.bluetooth.ConnectedDevice;
/** Existing WcpCp worker only. This publishes policy, never a connect command. */
public final class BtReconnect {
 static final String PATH="/ramdisk/cpmap-bt-policy.state",LAST="/mnt/icab/persistent/cpmap-ui/wireless-last-peer.state";
 static long epoch=System.currentTimeMillis()&0xffffffffL,counter,lastPoll=-1,acceptedAt=-1,wiredGeneration=-1;static String last="",acceptedOwner="";static boolean loaded,wiredHold;
 static Object settings()throws Exception{Class c=Class.forName("org.omonob.phone.PhoneConnectionSettings");Object store=c.getMethod("systemStore",new Class[0]).invoke(null,new Object[0]);return c.getMethod("read",new Class[0]).invoke(store,new Object[0]);}
 static void write(String path,String text)throws Exception{File target=new File(path);if(!target.getAbsoluteFile().equals(target.getCanonicalFile()))throw new IOException("policy path");File stage=new File(new StringBuffer(path).append(".new").toString());if(!stage.getAbsoluteFile().equals(stage.getCanonicalFile()))throw new IOException("policy stage");FileOutputStream out=new FileOutputStream(stage);try{out.write(text.getBytes("US-ASCII"));out.flush();if(path.endsWith("wireless-last-peer.state"))out.getFD().sync();}finally{out.close();}if(!stage.renameTo(target))throw new IOException("policy rename");}
 static boolean member(Vector peers,String peer){return peer.length()==12&&peers.contains(peer);}
 static String request(String guard){String[] q=BtRelease.lines(BtRelease.read("/ramdisk/wcp-rg/bt-request.state",256),8);return q!=null&&q[0].equals("WCPBTREQ1")&&q[1].equals(BtRelease.field(guard,"pid"))&&q[2].equals(BtRelease.field(guard,"nonce"))&&q[3].equals(BtRelease.field(guard,"session"))&&q[6].equals("1")?BtRelease.mac(q[7]):"";}
 static boolean allowed(boolean automatic,boolean clamp,boolean standby,boolean usb,boolean hold){return automatic&&clamp&&!standby&&!usb&&!hold;}
 static String encode(long epoch,long counter,boolean permit,boolean usb,String last,Vector peers){
  StringBuffer out=new StringBuffer("BTRC1\n").append(epoch).append('\n').append(counter).append('\n').append(permit?1:0).append('\n').append(usb?1:0).append('\n').append(member(peers,last)?last:"-").append('\n').append(peers.size()).append('\n');
  for(int i=0;i<peers.size();i++)out.append((String)peers.elementAt(i)).append('\n');return out.toString();
 }
 public static void tick(boolean accepted,String guard,long now){
  if(lastPoll>=0&&now>=lastPoll&&now-lastPoll<500)return;lastPoll=now;
  try{
   if(!BtRelease.read(BtRelease.ROOT+"/STATE",32).equals("installed\n"))return;
   ASLPhoneData data=ASLPhoneData.getInstance();if(data==null||data.trustedBTDevices==null)return;
   Vector peers=new Vector();for(Iterator it=data.trustedBTDevices.values().iterator();it.hasNext();){Object v=it.next();if(v instanceof ConnectedDevice){ConnectedDevice d=(ConnectedDevice)v;if(d.device!=null){String peer=BtRelease.mac(d.device.deviceAddress);if(peer.length()==12&&!peers.contains(peer)){if(peers.size()==8)return;peers.addElement(peer);}}}}
   Object state=settings();Class type=state.getClass();boolean auto=((Boolean)type.getMethod("allowAutomaticConnection",new Class[0]).invoke(state,new Object[0])).booleanValue();long generation=type.getField("generation").getLong(state);boolean usb=new File("/dev/ipod0").exists();
   if(usb){wiredHold=true;wiredGeneration=generation;}
   // A fresh explicit wireless selection advances the settings generation and
   // writes the existing native transport-intent lease. Mere USB removal does not.
   if(wiredHold&&!usb&&generation>wiredGeneration&&new File("/ramdisk/v75-wireless-transport.intent").isFile())wiredHold=false;
   if(!loaded){String[] q=BtRelease.lines(BtRelease.read(LAST,64),2);if(q!=null&&q[0].equals("BTRL1"))last=BtRelease.mac(q[1]);loaded=true;}
   String owner=new StringBuffer(BtRelease.field(guard,"pid")).append(':').append(BtRelease.field(guard,"nonce")).append(':').append(BtRelease.field(guard,"session")).toString();
   if(!accepted||!owner.equals(acceptedOwner)){acceptedAt=accepted?now:-1;acceptedOwner=accepted?owner:"";}
   String current=accepted?request(guard):"";
   if(acceptedAt>=0&&now>=acceptedAt&&now-acceptedAt>=5000&&member(peers,current)&&!current.equals(last)){
    last=current; // A failed optional persistent write must not stop the RAM policy heartbeat.
    try{File directory=new File(LAST).getParentFile().getCanonicalFile();if(!directory.isDirectory()&&!directory.mkdirs())throw new IOException("preference directory");
     write(new File(directory,"wireless-last-peer.state").getPath(),new StringBuffer("BTRL1\n").append(current).append('\n').toString());}catch(Throwable retainedInRam){}
   }
   boolean permit=allowed(auto,data.isClampSOn,data.standbyActive,usb,wiredHold);
   write(PATH,encode(epoch,++counter,permit,usb,last,peers));
  }catch(Throwable unavailable){/* No fresh policy: native guard retains its bounded startup/fail-closed rule. */}
 }
}
