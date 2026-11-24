#!/usr/bin/env python3
"""Read the pinned receiver's real IdentificationInformation in an isolated QNX VM."""
import importlib.util
from pathlib import Path
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('fixture',HERE.parent/'tests/receiver-alt-gate.py');fixture=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixture)
fixture.SOURCE=r'''
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <unistd.h>
static unsigned be16(const unsigned char *p){return (unsigned)p[0]<<8|p[1];}
static void check(int ok,const char *msg){if(!ok){printf("GPS_IDENT_FAIL=%s\n",msg);fflush(stdout);_exit(81);}}
__attribute__((constructor))static void test(void){
 unsigned i,sum=0,size;unsigned char *item,*packet,*message=(unsigned char *)0x135608;
 check(getenv("MU1367_GATE_ONLY")!=0,"fixture scope");
 *(int *)0x110a14=2;*(unsigned char *)0x112af1=0;*(int *)0x112aec=0;
 item=calloc(1,20);check(item!=0,"allocate");*(uint32_t *)item=16;packet=item+4;
 packet[0]=255;packet[1]=0x5a;packet[3]=16;packet[4]=0x40;packet[5]=1;packet[7]=10;
 for(i=0;i<8;i++)sum+=packet[i];packet[8]=(unsigned char)-sum;
 packet[9]=packet[10]=0x40;packet[12]=6;packet[13]=0x1d;packet[14]=0;
 sum=0;for(i=9;i<15;i++)sum+=packet[i];packet[15]=(unsigned char)-sum;
 ((void (*)(void *))0xec5ec)(item);
 size=be16(message+2);check(be16(message)==0x4040&&be16(message+4)==0x1d01&&size>=6&&size<=4096,"generated identification");
 printf("GPS_IDENT_HEX=");for(i=0;i<size;i++)printf("%02x",message[i]);puts("");
 for(i=6;i<size;){unsigned n=be16(message+i),id=be16(message+i+2);check(n>=4&&n<=size-i,"parameter bounds");printf("GPS_IDENT_PARAM id=%u bytes=%u\n",id,n-4);i+=n;}
 puts("GPS_IDENT_PASS actual_receiver_identification=1 hardware_main=0");fflush(stdout);_exit(0);
}
'''
fixture.PASS_MARKER='GPS_IDENT_PASS actual_receiver_identification=1'
fixture.EVIDENCE=dict(actual_receiver_identification=True,phone_connected=False,hardware_main_executed=False)
fixture.main()
