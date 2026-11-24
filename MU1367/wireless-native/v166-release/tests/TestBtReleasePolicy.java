/* SPDX-License-Identifier: GPL-3.0-or-later */
package de.vw.mib.asl.internal.wcpcp;
public final class TestBtReleasePolicy {
 static int checks;static void check(boolean ok,String why){checks++;if(!ok)throw new RuntimeException(why);}
 static boolean step(BtRelease.Policy p,long at,String who,boolean live,boolean opt,boolean command,boolean idle,boolean trusted,int mask){return p.step(at,who,live,opt,command,idle,trusted,mask);}
 public static void main(String[] args){
  BtRelease.Policy p=new BtRelease.Policy();
  check(!step(p,0,"a",true,false,true,true,true,2),"default keep");
  check(!step(p,4999,"a",true,true,true,true,true,2),"five second accepted stabilization");
  check(!step(p,5000,"a",true,true,true,false,true,2)&&p.attempts==0,"active or unknown call never consumes request");
  check(!step(p,5001,"a",true,true,false,true,true,2),"matching phone request required");
  check(!step(p,5002,"a",true,true,true,true,false,2),"current OEM trust required");
  check(!step(p,5003,"a",true,true,true,true,true,-1),"unknown profile state keeps BT");
  check(step(p,5100,"a",true,true,true,true,true,65538)&&p.attempts==1,"one request after all guards");
  check(!step(p,6000,"a",true,true,true,true,true,2),"bounded confirmation wait");
  check(!step(p,7000,"a",true,true,true,true,true,0)&&p.confirmed,"actual profile state confirms release");
  check(!step(p,13000,"a",true,true,true,true,true,2),"returning profiles never cause repeated disconnect fight");
  check(!step(p,14000,"a",false,true,true,true,true,2)&&p.shortFailures==1,"short post-request session loss counted");
  step(p,15000,"b",true,true,true,true,true,2);check(step(p,21000,"b",true,true,true,true,true,2),"next accepted session separately stabilizes");
  step(p,22000,"b",false,true,true,true,true,2);check(p.locked&&p.shortFailures==2,"two short losses keep BT for boot");
  step(p,23000,"c",true,true,true,true,true,2);check(!step(p,30000,"c",true,true,true,true,true,2)&&p.reason.equals("keep-after-short-failures"),"circuit breaker");
  BtRelease.Policy retry=new BtRelease.Policy();step(retry,0,"r",true,true,true,true,true,2);
  check(step(retry,5000,"r",true,true,true,true,true,2),"first try");
  check(!step(retry,10000,"r",true,true,true,false,true,2)&&retry.attempts==1,"call arriving before retry defers");
  check(step(retry,11000,"r",true,true,true,true,true,2)&&retry.attempts==2,"one bounded retry");
  check(!step(retry,17000,"r",true,true,true,true,true,2),"retry cap retains BT");
  check(!step(retry,18000,"r",false,true,true,true,true,2),"explicit stop/wired/ignition inactive input cannot release");
  check(BtRelease.mac("12:34:56:78:9a:bc").equals("123456789ABC")&&BtRelease.mac("invalid").equals(""),"strict phone identity");
  check(BtRelease.lines("A\nB\n",2)!=null&&BtRelease.lines("A\nB\nextra",2)==null,"bounded exact request envelope");
  check(BtRelease.number("18446744073709551615")==-1,"numeric overflow refused");
  check(BtReconnect.allowed(true,true,false,false,false),"automatic reconnect with ignition and trusted policy");
  check(!BtReconnect.allowed(false,true,false,false,false),"manual stop blocks reconnect");
  check(!BtReconnect.allowed(true,false,false,false,false),"ignition off blocks reconnect");
  check(!BtReconnect.allowed(true,true,true,false,false),"standby blocks reconnect");
  check(!BtReconnect.allowed(true,true,false,true,false),"wired takeover blocks reconnect");
  check(!BtReconnect.allowed(true,true,false,false,true),"wired unplug does not clear stop latch");
  java.util.Vector peers=new java.util.Vector();peers.addElement("123456789ABC");
  check(BtReconnect.encode(42,2,true,false,"123456789ABC",peers).equals("BTRC1\n42\n2\n1\n0\n123456789ABC\n1\n123456789ABC\n"),"Java policy native envelope and canonical MAC order");
  check(BtReconnect.encode(42,3,true,false,"FFFFFFFFFFFF",peers).indexOf("\n-\n1\n")>=0,"removed phone cannot remain preferred");
  System.out.println(new StringBuffer("BT_RELEASE_POLICY_PASS checks=").append(checks).append(" calls=1 accepted_stable=1 command_owner=1 retry_cap=1 circuit_breaker=1 native_action_boundary_controlled=1").toString());
 }
}
