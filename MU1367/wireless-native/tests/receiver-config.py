#!/usr/bin/env python3
"""Check rightHandDrive config parsing with the exact receiver's CF routines."""
import importlib.util
import plistlib
from pathlib import Path

SOURCE=r'''
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
typedef void *Obj;
static Obj read_config(void) {
    Obj data=((Obj (*)(const char *,int))0x595e4)("/mnt/persist/airplay.conf",0);
    Obj dict;
    if(!data) return 0;
    dict=((Obj (*)(Obj,Obj,int,void *,void *))0x524a0)(0,data,0,0,0);
    ((void (*)(Obj))0x51ce8)(data);
    return dict;
}
static void check(const char *name,const unsigned char *bytes,size_t length,int expected) {
    FILE *f;
    Obj dict,value,boolean;
    f=fopen("/mnt/persist/airplay.conf","w");
    if(!f) { perror("config"); _exit(81); }
    if(fwrite(bytes,1,length,f)!=length || fclose(f)) _exit(82);
    dict=read_config();
    if(!dict) { printf("RECEIVER_CONFIG_PARSE_FAILED=%s\n",name); fflush(stdout); _exit(83); }
    value=((Obj (*)(Obj,Obj))0x520ac)(dict,(Obj)0x3eaf2);
    boolean=*(Obj *)(expected ? 0x110418 : 0x110424);
    printf("RECEIVER_CONFIG name=%s rightHandDrive=%d canonical_boolean=%d\n",name,expected,value==boolean);
    if(value!=boolean) { fflush(stdout); _exit(84); }
    ((void (*)(Obj))0x51ce8)(dict);
}
__attribute__((constructor)) static void test(void) {
    if(!getenv("MU1367_GATE_ONLY")) _exit(85);
    static const unsigned char rhd[]={@RHD@};
    static const unsigned char lhd[]={@LHD@};
    static const unsigned char extra[]={@EXTRA@};
    check("rhd_binary_plist",rhd,sizeof(rhd),1);
    check("lhd_binary_plist",lhd,sizeof(lhd),0);
    check("rhd_with_other_property",extra,sizeof(extra),1);
    unlink("/mnt/persist/airplay.conf");
    puts("RECEIVER_RHD_CONFIG_PASS checks=3 hardware_opened=0");
    fflush(stdout); _exit(0);
}
'''


if __name__=='__main__':
    path=Path(__file__).with_name('receiver-alt-gate.py')
    spec=importlib.util.spec_from_file_location('receiver_fixture',path)
    fixture=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixture)
    fixture.SOURCE=SOURCE
    for token,value in (('@RHD@',{'rightHandDrive':True}),('@LHD@',{'rightHandDrive':False}),('@EXTRA@',{'rightHandDrive':True,'fixtureUnrelated':'preserved'})):
        blob=plistlib.dumps(value,fmt=plistlib.FMT_BINARY,sort_keys=True)
        fixture.SOURCE=fixture.SOURCE.replace(token,','.join(str(b) for b in blob))
    fixture.PASS_MARKER='RECEIVER_RHD_CONFIG_PASS checks=3'
    fixture.EVIDENCE=dict(checks=3,actual_receiver_code_executed=True,config_parser_virtual_address='0x524a0',config_lookup_virtual_address='0x520ac',right_hand_drive_key_virtual_address='0x3eaf2')
    fixture.main()
