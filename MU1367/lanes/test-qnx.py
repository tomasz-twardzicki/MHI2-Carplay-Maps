#!/usr/bin/env python3
"""Exercise the combined lane/menu/audio stack in factory MU1367 ARM J9/QNX.
SPDX-License-Identifier: GPL-3.0-or-later
"""
import argparse
import json
from pathlib import Path
import sys
import stage
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'port'))
from firmware import sha

PROBE='''
  Class laneClass=Class.forName("com.cpmap.rgi.LaneData");
  java.lang.reflect.Method decode=laneClass.getDeclaredMethod("decode",new Class[]{Class.forName("[B"),Integer.TYPE,Integer.TYPE});decode.setAccessible(true);
  byte[] payload={0,6,0,0,0,2,0,5,0,1,2,0,6,0,2,0,0,0,6,0,3,0,90};
  de.vw.mib.bap.mqbab2.common.api.navigation.datatypes.iterator.elements.NavigationLaneGuidanceElement lane=(de.vw.mib.bap.mqbab2.common.api.navigation.datatypes.iterator.elements.NavigationLaneGuidanceElement)decode.invoke(null,new Object[]{payload,new Integer(0),new Integer(payload.length)});
  if(lane.getDirection()!=192||lane.getLaneGuidanceInfo()!=2||lane.getSideStreets().length()!=1||lane.getSideStreets().charAt(0)!=0)throw new Exception("Factory lane fields");
  de.vw.mib.bap.mqbab2.generated.navsd.serializer.LaneGuidance_ChangedArray array=new de.vw.mib.bap.mqbab2.generated.navsd.serializer.LaneGuidance_ChangedArray();
  de.vw.mib.bap.mqbab2.generated.navsd.serializer.LaneGuidance_LaneGuidance element=new de.vw.mib.bap.mqbab2.generated.navsd.serializer.LaneGuidance_LaneGuidance(array.getArrayHeader());
  element.laneDirection=lane.getDirection();element.guidanceInfo=lane.getLaneGuidanceInfo();element.laneSidestreets.setContent(lane.getSideStreets());element.setPos(0);
  if(!array.getArrayData().add(element)||array.getArrayData().size()!=1||array.getArrayData().get(0)!=element)throw new Exception("Factory lane array");
  array.getArrayHeader().setRecordAddress(0);
  final java.lang.StringBuffer written=new java.lang.StringBuffer();
  de.vw.mib.bap.stream.BitStream bits=(de.vw.mib.bap.stream.BitStream)java.lang.reflect.Proxy.newProxyInstance(laneClass.getClassLoader(),new Class[]{Class.forName("de.vw.mib.bap.stream.BitStream")},new java.lang.reflect.InvocationHandler(){public Object invoke(Object p,java.lang.reflect.Method m,Object[] a){written.append(m.getName()).append(":");if(a!=null)for(int i=0;i<a.length;i++)written.append(a[i]).append(",");written.append(";");return null;}});
  array.getArrayData().serialize(bits);
  if(written.toString().indexOf("pushByte:-64,")<0||written.toString().indexOf("pushBits:4,2,")<0)throw new Exception("Factory lane serialization");
  new java.io.File("/ramdisk/card-test/navigation-card.state").delete();new java.io.File("/ramdisk/card-test/navigation-card.previous").delete();
  org.omonob.cpmap.ui.CardPositionSettings card=new org.omonob.cpmap.ui.CardPositionSettings(new java.io.File("/ramdisk/card-test"));
  if(card.read().position!=3||card.read().generation!=0)throw new Exception("Card default OFF");
  card.set(2);if(card.read().position!=2)throw new Exception("Card explicit ON");card.set(3);if(card.read().position!=3)throw new Exception("Card explicit OFF");
  System.out.println("LANES_FACTORY_J9_PASS lane_decode=1 bap_array=1 card_off_default=1 on_off_persisted=1");
'''


def main():
 p=argparse.ArgumentParser(description=__doc__)
 for n in ('build','parent-native','setup','firmware','toolchain','java-home','stock-jar','output'):p.add_argument('--'+n,type=Path,required=True)
 a=p.parse_args();build=a.build.resolve();out=a.output.resolve()
 shared=HERE.parent/'settings-v2/test-qnx.py';text=shared.read_text()
 text=stage.replace(text,'  System.out.println("SETTINGS_J9_PASS',PROBE+'  System.out.println("SETTINGS_J9_PASS')
 header=str(build/'runtime/src/card-core/source/cpmap_card_preferences.h')
 text=stage.replace(text,'#include "display_settings.h"','#include "display_settings.h"\n#include "'+header+'"')
 text=stage.replace(text,'puts("SETTINGS_C_FACTORY_PREFS_PASS");','{struct cpmap_card_preference p;if(cpmap_card_read("/ramdisk/card-test",&p)!=1||p.position!=3||p.generation!=2)return 5;}puts("SETTINGS_C_FACTORY_PREFS_PASS");')
 text=stage.replace(text,'puts("SETTINGS_CORE_DLOPEN_PASS");','{struct cpmap_card_preference p;if(cpmap_card_read("/ramdisk/card-test",&p)!=0||p.position!=3)return 6;}puts("SETTINGS_CORE_DLOPEN_PASS");')
 env={'__file__':str(shared),'__name__':'lane_settings_qnx'};exec(compile(text,str(shared),'exec'),env)
 old=sys.argv;sys.argv=['lane-qnx','--runtime',str(build/'runtime'),'--parent-hmi',str(build/'hmi')]
 for n in ('parent-native','setup','firmware','toolchain','java-home','stock-jar','output'):sys.argv+=['--'+n,str(getattr(a,n.replace('-','_')))]
 try:env['main']()
 finally:sys.argv=old
 log=out/'run/j9/qemu.log';assert log.read_text(errors='replace').count('LANES_FACTORY_J9_PASS')==2
 result=json.loads((out/'result.json').read_text());result.update(files=json.loads((build/'manifest.json').read_text())['files'],lane_factory_fields_verified=True,card_default_java_c_verified=True,test_sha256=sha(Path(__file__).read_bytes()),qemu_log_sha256=sha(log.read_bytes()))
 (out/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))


if __name__=='__main__':main()
