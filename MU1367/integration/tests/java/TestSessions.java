/* SPDX-License-Identifier: GPL-3.0-or-later */
package com.cpmap.rgi;
import java.io.File;
/** Reproduce a producer restart without an intervening file-not-found/error. */
public final class TestSessions {
 static int checks;
 static void check(boolean ok,String why){checks++;if(!ok)throw new AssertionError(why);}
 public static void main(String[] args)throws Exception{
  File root=new File(args[0]);root.mkdirs();TestLive.installMocks();
  LiveBridge b=TestLive.bridge();FeedRecovery feed=new FeedRecovery(root.toString());
  TestRecovery.Wire old=new TestRecovery.Wire(root);old.route(0);old.publish();
  long t=1000;TestLive.clock=t;b.pollProduction(feed,t,false);b.tick(t);
  for(int i=0;i<20;i++){
   t+=250;old.route(1);old.publish();TestLive.clock=t;b.pollProduction(feed,t,false);b.tick(t);
  }
  check(b.owned,"first session owns output");long gen=feed.generation;
  // A brief stale interval latches the old session's nonzero floor.
  t+=1500;old.publish();TestLive.clock=t;b.pollProduction(feed,t,false);b.tick(t);
  check(!b.owned && b.floor>=20,"old session floor retained after expiry");
  // Producer starts a new mailbox atomically: no missing-file retry intervenes.
  TestRecovery.Wire next=new TestRecovery.Wire(root);next.nonce=2;
  next.route(0);next.publish();t+=250;TestLive.clock=t;b.pollProduction(feed,t,false);b.tick(t);
  check(!b.owned && feed.generation>gen,"new source is a distinct generation, baseline not published");
  next.route(1);next.publish();t+=250;TestLive.clock=t;b.pollProduction(feed,t,false);b.tick(t);
  check(b.owned && b.incoming.progress==1,"first new event can acquire below previous counter floor");
  t+=1500;next.publish();TestLive.clock=t;b.pollProduction(feed,t,false);b.tick(t);
  check(!b.owned && b.lastReleaseAt==t && b.lastReleaseReason==3,"timer lease release captured");
  check(b.lastReleaseProgress==1 && b.lastReleaseFrameAge==1500,"release evidence is numeric and specific");
  next.route(1);next.publish();t+=250;TestLive.clock=t;b.pollProduction(feed,t,false);b.tick(t);
  check(b.owned,"new event recovers after lease loss");
  // Simulate cancellation/disconnect; retained first unexpected release survives.
  String first=b.firstUnexpectedRelease;next.envelope(5,1,new byte[0]);t+=250;TestLive.clock=t;b.pollProduction(feed,t,false);b.tick(t);
  check(!b.owned && b.lastReleaseMode==0,"normal disconnect clears output");
  check(!first.equals("none") && first.equals(b.firstUnexpectedRelease),"disconnect cannot hide earlier unexpected release");
  check(b.ownershipHistory.indexOf(":3:0:2:")>=0 && b.ownershipHistory.indexOf(":4:0:0:")>=0,"bounded history retains timer loss and later normal disconnect");
  check(feed.reader.observedKind==5,"last envelope kind remains available after disconnect");
  check(first.length()<128,"bounded unexpected-release evidence");
  for(int i=0;i<32;i++)b.noteOwnership(100000+i,1,null);
  check(b.ownershipHistory.indexOf("100000:")<0 && b.ownershipHistory.indexOf("100015:")<0 && b.ownershipHistory.indexOf("100016:")>=0 && b.ownershipHistory.indexOf("100031:")>=0,"history retains exactly the newest sixteen transitions");
  check(b.ownershipHistory.length()<2048,"ownership history has a fixed small bound");
  System.out.println("SESSION_BOUNDARY_PASS checks="+checks+" atomic_producer_restart=1 old_floor_reset=1 release_evidence=1");
 }
}
