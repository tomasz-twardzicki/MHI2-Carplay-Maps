#!/usr/bin/env python3
"""Pin the PF templates and required tools in both supported firmware trees."""
import argparse
import hashlib
import json
import sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parents[3]/'MU1367/port'))
from firmware import QNX6,image_files,stage1,stage2
from f3s import f3s_files
p=argparse.ArgumentParser()
p.add_argument('--firmware',type=Path,action='append',required=True)
p.add_argument('--output',type=Path,required=True)
a=p.parse_args();profiles={}
anchor='block in quick on $wlan_if from any to ($wlan_if)'
for root in a.firmware:
    for variant in ['50','70']:
        files=image_files(stage1(root/('MMX2/mifs-stage1/'+variant+'/default/mifs-stage1.img')))
        files.update(image_files(stage2(root/('MMX2/mifs-stage2/'+variant+'/default/mifs-stage2.img'))))
        efs,_=f3s_files((root/('MMX2/efs-sys/'+variant+'/default/efs-system.img')).read_bytes())
        app=QNX6(root/('MMX2/app/'+variant+'/default/app.img'))
        pfctl=app.get('armle/sbin/pfctl');app.file.close()
        templates={}
        for name in ['pf.conf','pf.mlan0.conf','pf.ecm0.conf','pf.ppp0.conf']:
            matches=[(path,b) for path,b in efs.items() if Path(path).name==name]
            assert len(matches)==1,name
            path,b=matches[0];lines=b.decode().splitlines()
            assert lines.count(anchor)==1,(root.name,variant,name)
            assert any(line.startswith('wlan_if') and '=' in line for line in lines)
            templates[name]=dict(path=path,sha256=hashlib.sha256(b).hexdigest(),anchor_count=1)
        tools={}
        for name in ['ifconfig','grep','cat','rm','mv','ksh']:
            matches={b for path,b in files.items() if Path(path).name==name}
            assert len(matches)==1,name
            tools[name]=hashlib.sha256(matches.pop()).hexdigest()
        tools['pfctl']=hashlib.sha256(pfctl).hexdigest()
        profiles[root.name+'/'+variant]=dict(templates=templates,required_tools=tools)
result=dict(passed=True,profiles=profiles,kernel_rule_application_tested=False)
a.output.write_text(json.dumps(result,indent=2)+'\n');print('PF_FIRMWARE_AUDIT_PASS profiles='+str(len(profiles)))
