#!/usr/bin/env python3
"""Exercise production summary retention and repeated codec announcements."""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

HERE=Path(__file__).resolve().parent
p=argparse.ArgumentParser()
p.add_argument('--output',type=Path,required=True)
a=p.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
bridge=HERE.parent/'src/runtime/vc-runtime/runtime/altscreen_most_bridge.c'
source=r'''
#define ALTSCREEN_BRIDGE_FILE_OUTPUT 1
static char summary_path[4096];
#define CPMAP_WIRELESS_SUMMARY_PATH summary_path
#define main production_bridge_main
#include "@BRIDGE@"
#undef main
#include <assert.h>
int main(int argc,char **argv) {
    static const unsigned char config[]={1,100,0,31,255,225,0,2,103,1,1,0,2,104,1};
    unsigned char changed[sizeof(config)];AvcConfig avcc;unsigned minute,i;
    assert(argc==2);snprintf(summary_path,sizeof(summary_path),"%s",argv[1]);
    memset(&avcc,0,sizeof(avcc));assert(!queue_init(&g_queue));
    for(i=0;i<10000;i++)assert(!parse_avcc_config(&avcc,config,sizeof(config)));
    assert(g_avcc_updates==1);
    memcpy(changed,config,sizeof(config));changed[9]=2;
    assert(!parse_avcc_config(&avcc,changed,sizeof(changed)) && g_avcc_updates==2);
    assert(parse_avcc_config(&avcc,changed,4)==-1 && avcc.valid);
    for(minute=0;minute<=90;minute++) {
        g_frames+=1200;g_keyframes+=150;
        log_input_metrics(1000000ULL+minute*60000000ULL,minute==40?61000:20000,1,minute==40?18000:9000);
        if(minute==45) {
            /* Detailed log truncation must not remove drive summaries. */
            for(i=0;i<CPMAP_BRIDGE_LOG_LIMIT+1024;i++)fputc('x',stderr);
            fflush(stderr);
            cpmap_log_fprintf(stderr,CPMAP_BRIDGE_LOG_LIMIT,"detail rotated\n");
        }
    }
    log_session_summary(5402000000ULL,"stop");
    free_config(&avcc);queue_destroy(&g_queue);
    puts("BRIDGE_DIAGNOSTICS_PASS simulated_minutes=90 repeated_configs=10000 config_changes=2");
    return 0;
}
'''.replace('@BRIDGE@',str(bridge))
(out/'test.c').write_text(source)
flags=['-isysroot','/Library/Developer/CommandLineTools/SDKs/MacOSX.sdk','-std=gnu99',
       '-O1','-g','-Wall','-Wextra','-Werror','-Wno-unused-function',
       '-Wno-misleading-indentation','-fsanitize=address,undefined','-fno-omit-frame-pointer',
       '-I'+str(HERE.parent/'src/native'),'-I'+str(bridge.parent)]
subprocess.run(['/Library/Developer/CommandLineTools/usr/bin/clang',*flags,str(out/'test.c'),'-o',str(out/'test')],check=True)
summary=out/'summary.log';results=[]
for run in range(2):
    with (out/('detail-%d.log'%run)).open('w') as detail:
        results.append(subprocess.check_output([str(out/'test'),str(summary)],stderr=detail,text=True).strip())
rows=summary.read_text().splitlines()
assert len(rows)==184,len(rows)
assert sum('event=start ' in row for row in rows)==2
assert sum('event=minute ' in row for row in rows)==180
assert sum('event=stop ' in row for row in rows)==2
assert len(summary.read_bytes())<256*1024
assert all('avcc_updates=2 ' in row for row in rows)
assert sum('frame_max=61000 ' in row for row in rows)>50
assert all((out/('detail-%d.log'%i)).stat().st_size<128*1024 for i in range(2))
r=dict(passed=True,results=results,summary_rows=len(rows),simulated_minutes_per_process=90,
       process_restarts=1,detailed_log_truncation_preserves_summaries=True,
       bridge_sha256=hashlib.sha256(bridge.read_bytes()).hexdigest(),sanitizers=['address','undefined'])
(out/'result.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r))
