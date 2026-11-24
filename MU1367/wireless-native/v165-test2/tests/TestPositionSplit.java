/* Matching factory stage probes; never installed. SPDX-License-Identifier: GPL-3.0-or-later */
package com.cpmap.rgi;
public final class TestPositionSplit {
 static int checks;
 static void check(boolean ok,String why)throws Exception{checks++;if(!ok)throw new Exception(why);}
 static Object last(){return TestRoadQnx.sent.get(TestRoadQnx.sent.size()-1);}
 static LiveModel.Frame frame(){return new LiveModel.Frame(true,13,192,30,1000,60,1,TestRoadQnx.clock,1,LaneData.EMPTY,TestRoadQnx.clock,"Current street",TestRoadQnx.clock,-1,"Next street",TestRoadQnx.clock,0);}
 public static void run()throws Exception{
  TestRoadQnx.clock=5000;TestRoadQnx.route=0;TestRoadQnx.accept=true;
  LiveBridge b=LiveBridge.INSTANCE;
  de.vw.mib.bap.mqbab2.common.api.stages.BAPStageContext context=(de.vw.mib.bap.mqbab2.common.api.stages.BAPStageContext)TestRoadQnx.service(Class.forName("de.vw.mib.bap.mqbab2.common.api.stages.BAPStageContext"));
  de.vw.mib.bap.mqbab2.navsd.functions.CurrentPositionInfo position=new de.vw.mib.bap.mqbab2.navsd.functions.CurrentPositionInfo();position.setDelegate(context);position.init(null);
  de.vw.mib.bap.mqbab2.navsd.functions.TurnToInfo turn=new de.vw.mib.bap.mqbab2.navsd.functions.TurnToInfo();turn.setDelegate(context);turn.init(null);
  check(position.getFunctionId()==19&&turn.getFunctionId()==20&&b.stages[7]==position,"two distinct actual factory functions attached");
  TestRoadQnx.prepare(b,frame());RoadName.mode=RoadName.NEXT;
  position.process(-1);check(((de.vw.mib.bap.mqbab2.generated.navsd.serializer.CurrentPositionInfo_Status)last()).positionInfo.toString().equals("Current street"),"position always gets current road");
  turn.process(-1);check(((de.vw.mib.bap.mqbab2.generated.navsd.serializer.TurnToInfo_Status)last()).turnToInfo.toString().equals("Next street"),"turn-to gets upcoming road");
  RoadName.mode=RoadName.OFF;turn.process(-1);check(((de.vw.mib.bap.mqbab2.generated.navsd.serializer.TurnToInfo_Status)last()).turnToInfo.toString().equals(""),"dial off blanks turn only");
  position.process(-1);check(((de.vw.mib.bap.mqbab2.generated.navsd.serializer.CurrentPositionInfo_Status)last()).positionInfo.toString().equals("Current street"),"dial off cannot blank position");
  RoadName.mode=RoadName.CURRENT;turn.process(-1);check(((de.vw.mib.bap.mqbab2.generated.navsd.serializer.TurnToInfo_Status)last()).turnToInfo.toString().equals("Current street"),"current mode retained");
  TestRoadQnx.accept=false;b.refreshPending=0;b.refreshing=true;position.process(-1);check((b.refreshPending&128)!=0,"position queue rejection retries independently");TestRoadQnx.accept=true;b.refreshing=false;
  TestRoadQnx.route=1;position.process(-1);check(((de.vw.mib.bap.mqbab2.generated.navsd.serializer.CurrentPositionInfo_Status)last()).positionInfo.toString().equals("OEM Current"),"OEM position retained during native route");TestRoadQnx.route=0;
  TestRoadQnx.prepare(b,new LiveModel.Frame(false,0,0,-1,0,0,0));position.process(-1);check(((de.vw.mib.bap.mqbab2.generated.navsd.serializer.CurrentPositionInfo_Status)last()).positionInfo.toString().equals(""),"owned clearing blanks position");
  position.uninitialize();turn.uninitialize();check(b.stages[7]==null&&b.stages[6]==null,"factory detach restores stock callbacks");
  System.out.println(new StringBuffer("POSITION_SPLIT_FACTORY_PASS checks=").append(checks).append(" function19_current=1 function20_selected=1 queue_retry=1 oem=1 clear=1 cluster_rendering_unproven=1").toString());
 }
}
