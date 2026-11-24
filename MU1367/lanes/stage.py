"""Counted changes over the released MU1367 Java/core sources.
SPDX-License-Identifier: GPL-3.0-or-later
"""
from pathlib import Path
import shutil
HERE=Path(__file__).resolve().parent
REPO=HERE.parents[1]


def replace(text,old,new,count=1):
    if text.count(old)!=count:raise ValueError('Lane source seam changed: '+old[:90])
    return text.replace(old,new)


def guidance(out):
    src=out/'guidance-src';shutil.copytree(REPO/'MU1427/route-guidance/bridge',src)
    shutil.copy2(HERE/'LaneData.java',src/'LaneData.java')
    p=src/'LiveModel.java';s=p.read_text()
    s=replace(s,'        int[] components, order;','        int[] components, order;\n        LaneData[] lanes=LaneData.EMPTY; boolean invalidLanes;')
    s=replace(s,'        public final long progress, changed, epoch;','        public final long progress, changed, epoch;\n        final LaneData[] lanes; final long laneAt;')
    old='''            remainingMeters=remaining; remainingSeconds=seconds;
            active=a; main=m; direction=d; meters=distance; validDistance=distance>=0;
            progress=p; changed=c; epoch=e;'''
    new='''            this(a,m,d,distance,remaining,seconds,p,c,e,LaneData.EMPTY,-1);
        }
        Frame(boolean a,int m,int d,int distance,int remaining,int seconds,long p,long c,long e,LaneData[] values,long at) {
            lanes=values;laneAt=at;
'''+old
    s=replace(s,old,new)
    s=replace(s,'    private long sec=-1,','    private final LaneData.Cache laneCache=new LaneData.Cache();\n    private long routeStatusAt=-1;\n    private long sec=-1,')
    s=replace(s,'boolean repeat=kind==-4 || kind==-5;','boolean repeat=kind==-4 || kind==-5 || id==0x5204 && key==0;')
    s=replace(s,'                    if (key==0) m.components=list; else m.order=list;','''                    if(key==0 && id==0x5204 && m.components!=null){
                        require(m.components.length+list.length<=8);
                        int[] both=new int[m.components.length+list.length];
                        System.arraycopy(m.components,0,both,0,m.components.length);System.arraycopy(list,0,both,m.components.length,list.length);m.components=both;
                    }else if (key==0) m.components=list; else m.order=list;''')
    # 5204 is independently optional in iAP2. Missing component means all displays.
    old='''            } else {
                nested(b,at,at+size);
                for (int q=at;q<at+size;q+=be16(b,q)) require(++nestedCount<=256);
            }'''
    new='''            } else if(id==0x5204 && key==2) {
                LaneData lane=LaneData.decode(b,at,size);
                if(lane==null || m.lanes.length>=16)m.invalidLanes=true;
                else {
                    LaneData[] values=new LaneData[m.lanes.length+1];
                    System.arraycopy(m.lanes,0,values,0,m.lanes.length);values[values.length-1]=lane;m.lanes=values;
                }
            } else {
                nested(b,at,at+size);
                for (int q=at;q<at+size;q+=be16(b,q)) require(++nestedCount<=256);
            }'''
    s=replace(s,old,new)
    s=replace(s,'        require(m.components!=null && m.components.length>0);','        if(id==0x5204 && m.components==null)m.components=new int[]{0x10};\n        require(m.components!=null && m.components.length>0);')
    s=replace(s,'        cache=new Message[32]; ages=new long[32]; order=new int[0];','        laneCache.clear();routeStatusAt=-1;\n        cache=new Message[32]; ages=new long[32]; order=new int[0];')
    s=replace(s,'            if (m.id==0x5204) return true; // validated; no lane geometry is projected','            if (m.id==0x5204) { laneCache.put((int)m.v[1],LaneData.ordered(m.lanes,m.invalidLanes));return true; }')
    s=replace(s,'        if (next==2) { cache=new Message[32]; distance=-1; }','''        if(m.has[16])laneCache.selected=(int)m.v[16];
        if(m.has[18])laneCache.showing=m.v[18]==1;
        if(next!=1 && next!=6){laneCache.showing=false;routeStatusAt=-1;}
        if (next==2) { cache=new Message[32]; distance=-1;laneCache.clear(); }''')
    s=replace(s,'                    if (m.id==0x5201 && (state==1 || state==6)) {','                    if (m.id==0x5201 && (state==1 || state==6)) {\n                        routeStatusAt=now;')
    s=replace(s,'remainingSeconds,progress,changed,epoch);','remainingSeconds,progress,changed,epoch,laneCache.current(),routeStatusAt);')
    p.write_text(s)
    p=src/'LiveBridge.java';s=p.read_text()
    s=replace(s,'        refresh();\n    }','        if(owned && stages[3]!=null)refreshPending|=8;\n        refresh();\n    }')
    start=s.index('    public static boolean lanes(');end=s.index('    static String request()',start)
    s=s[:start]+'''    private static LiveModel.Frame laneFrame() {
        LiveModel.Frame f=INSTANCE.current();
        if(f==null || !f.active || f.laneAt<0)return null;
        long time=now();return time>=f.laneAt && time-f.laneAt<5000?f:null;
    }
    public static java.util.Iterator laneIterator(NavigationService stock) {
        if(INSTANCE.current()==null)return stock.getLaneGuidance();
        LiveModel.Frame f=laneFrame();return LaneData.iterator(f==null?LaneData.EMPTY:f.lanes);
    }
    public static boolean lanesVisible(NavigationService stock) {
        if(INSTANCE.current()==null)return stock.isSetupLaneGuidanceActive();
        LiveModel.Frame f=laneFrame();return f!=null && f.lanes.length>0 && stock.isSetupLaneGuidanceActive();
    }
    // Factory/QNX load probes retain this signature. Actual transmission uses
    // the stock lane builder, array diff, six-lane window and request tracker.
    public static boolean lanes(LaneGuidance_ChangedArray out) {
        if(INSTANCE.current()==null)return false;
        out.reset();out.laneGuidanceOnOff=0;return true;
    }
'''+s[end:]
    s=replace(s,'.append(" error=").append(error)', '.append(" lane_count=").append(incoming==null?0:incoming.lanes.length).append(" lane_at=").append(incoming==null?-1:incoming.laneAt).append(" error=").append(error)')
    p.write_text(s)
    p=src/'PatchLive.java';s=p.read_text()
    s=replace(s,'            fill.instructions.insert(hook);','''            if(i!=3)fill.instructions.insert(hook);
            else {
                int iterators=0,routeGates=0,visibility=0;
                for(AbstractInsnNode n:fill.instructions.toArray())if(n instanceof MethodInsnNode){
                    MethodInsnNode call=(MethodInsnNode)n;
                    if(!call.owner.equals("de/vw/mib/bap/mqbab2/common/api/navigation/NavigationService"))continue;
                    String method=null,desc=null;
                    if(call.name.equals("getLaneGuidance")){method="laneIterator";desc="Ljava/util/Iterator;";iterators++;}
                    if(call.name.equals("getRouteGuidanceState")){method="descriptorRouteState";desc="I";routeGates++;}
                    if(call.name.equals("isSetupLaneGuidanceActive")){method="lanesVisible";desc="Z";visibility++;}
                    if(method!=null){call.setOpcode(INVOKESTATIC);call.owner=HELPER;call.name=method;call.desc="(Lde/vw/mib/bap/mqbab2/common/api/navigation/NavigationService;)"+desc;call.itf=false;}
                }
                check(iterators==2 && routeGates==1 && visibility==1);
            }''')
    p.write_text(s)
    p=src/'TestLive.java';s=p.read_text()
    s=replace(s,'    static boolean accept=true;','    static boolean accept=true,setupLane=true;')
    s=replace(s,'                if (n.equals("getRouteGuidanceState")) return Integer.valueOf(route);','                if (n.equals("getRouteGuidanceState")) return Integer.valueOf(route);\n                if (n.equals("isSetupLaneGuidanceActive")) return Boolean.valueOf(setupLane);')
    p.write_text(s)
    return src


def cards(src):
    p=src/'vc-menu/src/org/omonob/cpmap/ui/CardPositionSettings.java';s=p.read_text()
    s=replace(s,'return new State(RIGHT,0,"default-existing-right");','return new State(OFF,0,"default-native-lanes-map-only");');p.write_text(s)
    p=src/'vc-menu/tests/CardPositionSettingsTest.java';s=p.read_text()
    s=replace(s,'store.read().position==2&&store.read().generation==0','store.read().position==3&&store.read().generation==0');p.write_text(s)
    p=src/'card-core/source/cpmap_card_preferences.h';s=p.read_text()
    s=replace(s,'out->position=CPMAP_CARD_RIGHT;out->generation=0;','out->position=CPMAP_CARD_OFF;out->generation=0;');p.write_text(s)
    p=src/'card-core/source/navigation_card_scene.h';s=p.read_text()
    s=replace(s,'g_card_preference={CPMAP_CARD_RIGHT,0,0}','g_card_preference={CPMAP_CARD_OFF,0,0}');p.write_text(s)
