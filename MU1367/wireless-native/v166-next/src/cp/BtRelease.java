/* SPDX-License-Identifier: GPL-3.0-or-later */
package de.vw.mib.asl.internal.wcpcp;
import java.io.*;
import java.util.*;
import de.vw.mib.asl.internal.phone.ASLPhoneData;
import de.vw.mib.asl.internal.phone.bluetooth.ConnectedDevice;
/** Existing WcpCp worker only. No global stack toggle and no auto-connect. */
public final class BtRelease {
 static final String ROOT="/mnt/app/carplay-mu1367-wireless-native-v165t2";
 static final String AUTHORIZED="/ramdisk/cpmap-bt-release-authorized-peer";
 static final String REQUESTED="/ramdisk/cpmap-bt-release-requested";
 static final int PROFILES=2|4|65536;
 static final Policy policy=new Policy();static String phase="startup",lastPhase="",owner="";static long guardStamp=-1,guardChanged=-1,lastPoll=-1;
 static final class Policy {
  String owner="",reason="keep";long began=-1,lastAttempt=-1,failedAt=-1;int attempts,shortFailures;boolean requested,confirmed,locked;
  boolean step(long now,String key,boolean live,boolean opt,boolean command,boolean idle,boolean trusted,int services){
   if(!live||!owner.equals(key)){
    if(requested&&lastAttempt>=0&&now>=lastAttempt&&now-lastAttempt<30000){shortFailures=failedAt>=0&&now>=failedAt&&now-failedAt<120000?shortFailures+1:1;failedAt=now;if(shortFailures>=2)locked=true;}
    owner=live?key:"";began=live?now:-1;lastAttempt=-1;attempts=0;requested=confirmed=false;
   }
   if(!live){reason="no-accepted-owner";return false;}
   if(!opt){reason="keep";return false;}if(locked){reason="keep-after-short-failures";return false;}
   if(now<began||now-began<5000){reason="stabilizing";return false;}
   if(!command){reason="no-matching-phone-command";return false;}
   if(!trusted){reason="phone-not-currently-trusted";return false;}
   if(!idle){reason="call-active-or-unknown";return false;}
   if(services<0){reason="profile-state-unknown";return false;}
   if((services&PROFILES)==0){confirmed=requested;reason=requested?"profiles-confirmed-off":"profiles-already-off";return false;}
   if(confirmed){reason="profiles-returned-keep";return false;}
   if(attempts>=2){reason="request-limit-keep";return false;}
   if(lastAttempt>=0&&now>=lastAttempt&&now-lastAttempt<5000){reason="awaiting-profile-state";return false;}
   attempts++;lastAttempt=now;requested=true;reason="request-profiles";return true;
  }
 }
 static String read(String path,int max){try{File f=new File(path);if(!f.isFile()||f.length()<=0||f.length()>=max)return "";FileInputStream in=new FileInputStream(f);byte[] b=new byte[max];int n;try{n=in.read(b);}finally{in.close();}return n>0?new String(b,0,n,"US-ASCII"):"";}catch(Throwable t){return "";}}
 static String field(String s,String key){String needle=new StringBuffer(key).append('=').toString();int p=s.indexOf(needle);if(p<0||p>0&&s.charAt(p-1)!=' ')return "";p+=needle.length();int e=s.indexOf(' ',p);if(e<0)e=s.indexOf('\n',p);return e<0?s.substring(p):s.substring(p,e);}
 static long number(String s){if(s.length()==0||s.length()>19)return -1;long n=0;for(int i=0;i<s.length();i++){int d=s.charAt(i)-'0';if(d<0||d>9||n>(Long.MAX_VALUE-d)/10)return -1;n=n*10+d;}return n;}
 static String[] lines(String s,int count){String[] out=new String[count];int p=0;for(int i=0;i<count;i++){int e=s.indexOf('\n',p);if(e<0)return null;out[i]=s.substring(p,e);p=e+1;}return p==s.length()?out:null;}
 static String mac(String s){if(s==null)return "";StringBuffer b=new StringBuffer();for(int i=0;i<s.length();i++){char c=s.charAt(i);if(c==':'||c=='-')continue;if(c>='a'&&c<='f')c=(char)(c-32);if(!(c>='A'&&c<='F'||c>='0'&&c<='9'))return "";b.append(c);}return b.length()==12?b.toString():"";}
 static boolean opted(){String state=read(ROOT+"/STATE",32);if(!state.equals("installed\n"))return false;File choice=new File(ROOT+"/bt-release.mode");String mode=read(choice.getPath(),32);return mode.equals("profiles\n")||!choice.exists()&&new File("/mnt/persist/wcp_btaudio_release").isFile();}
 public static boolean enabled(){return true;} // Only reached after allow() gates.
 static ConnectedDevice trusted(ASLPhoneData d,String peer){if(d==null||d.trustedBTDevices==null)return null;for(Iterator it=d.trustedBTDevices.values().iterator();it.hasNext();){Object v=it.next();if(v instanceof ConnectedDevice){ConnectedDevice c=(ConnectedDevice)v;if(c.device!=null&&mac(c.device.deviceAddress).equals(peer))return c;}}return null;}
 static boolean idle(ASLPhoneData d){try{return d!=null&&d.callInformationCollectors!=null&&d.callInformationCollectors.isEmpty()&&!d.callInformationCollectors.isAnyActive()&&d.incomingOrOutgoingCallIDs!=null&&d.incomingOrOutgoingCallIDs.isEmpty()&&d.usedCallLines==0&&!d.carPlayCallActive;}catch(Throwable unavailable){return false;}}
 static int services(ConnectedDevice c){if(c==null||c.device==null||c.connectedServices==null||c.connectedServiceCount<0||c.connectedServiceCount>c.connectedServices.length||c.device.activeServiceTypes<0)return -1;int n=c.device.activeServiceTypes;for(int i=0;i<c.connectedServices.length;i++)n|=c.connectedServices[i];return n;}
 public static boolean allow(boolean entered,boolean fresh){
  try{long now=System.currentTimeMillis();if(lastPoll>=0&&now>=lastPoll&&now-lastPoll<500)return false;lastPoll=now;
   String guard=read("/ramdisk/cpmap-bt-session.status",1024);long stamp=number(field(guard,"t_ms"));if(stamp!=guardStamp){guardStamp=stamp;guardChanged=now;}
   boolean live=entered&&fresh&&guard.startsWith("BTSESSION1 ")&&field(guard,"installed").equals("1")&&field(guard,"live").equals("1")&&guardChanged>=0&&now>=guardChanged&&now-guardChanged<2500&&!new File("/dev/ipod0").exists();
   String key=new StringBuffer(field(guard,"pid")).append(':').append(field(guard,"nonce")).append(':').append(field(guard,"session")).toString();
   String[] request=lines(read("/ramdisk/wcp-rg/bt-request.state",256),8);String peer="";boolean command=false;
   if(request!=null&&request[0].equals("WCPBTREQ1")&&request[1].equals(field(guard,"pid"))&&request[2].equals(field(guard,"nonce"))&&request[3].equals(field(guard,"session"))&&number(request[4])>0&&number(request[5])>0&&request[6].equals("1")){peer=mac(request[7]);command=peer.length()==12;}
   ASLPhoneData d=live&&command?ASLPhoneData.getInstance():null;ConnectedDevice device=trusted(d,peer);
   boolean action=policy.step(now,key,live,opted(),command,idle(d),device!=null,services(device));owner=key;phase=policy.reason;
   // Confirmation comes from current OEM profile state, never from enqueueing.
   if(policy.confirmed&&!new File("/dev/shmem/wcp_bt_released").exists()){FileOutputStream out=new FileOutputStream("/dev/shmem/wcp_bt_released");try{out.write(49);}finally{out.close();}}
   if(action){FileOutputStream auth=new FileOutputStream(AUTHORIZED);try{auth.write(peer.getBytes("US-ASCII"));}finally{auth.close();}}
   status(now);return action;
  }catch(Throwable t){phase="gate-error-keep";return false;}
 }
 public static void cleanup(){new File(AUTHORIZED).delete();}
 public static void down(){try{policy.step(System.currentTimeMillis(),"",false,false,false,false,false,-1);new File(REQUESTED).delete();cleanup();}catch(Throwable ignored){}}
 static void status(long now){try{String s=new StringBuffer("BT_RELEASE1 t_ms=").append(now).append(" phase=").append(phase).append(" attempts=").append(policy.attempts).append(" confirmed=").append(policy.confirmed?1:0).append(" short_failures=").append(policy.shortFailures).append(" locked=").append(policy.locked?1:0).append('\n').toString();
  FileOutputStream out=new FileOutputStream("/ramdisk/cpmap-bt-release.status.new");try{out.write(s.getBytes("US-ASCII"));}finally{out.close();}new File("/ramdisk/cpmap-bt-release.status.new").renameTo(new File("/ramdisk/cpmap-bt-release.status"));
 }catch(Throwable ignored){}}
}
