/* SPDX-License-Identifier: GPL-3.0-or-later */
#include <stdio.h>
#include <stdlib.h>
#include "wcp_rg.h"
int main(int argc,char **argv) {
    struct wcp_rg rg;unsigned index=0;FILE *in;unsigned char header[4],payload[2048],mailbox[33120];
    if(argc!=3)return 2;in=fopen(argv[1],"rb");if(!in)return 2;
    wcp_rg_init(&rg,123,42,1234);
    while(fread(header,1,4,in)==4) {
        unsigned id=((unsigned)header[0]<<8)|header[1],length=((unsigned)header[2]<<8)|header[3];
        size_t size;FILE *f;char path[1024];
        if(length>sizeof(payload) || fread(payload,1,length,in)!=length)return 3;
        if(!id)wcp_rg_accept(&rg,1);
        else if(id==0xffff)wcp_rg_accept(&rg,0);
        else if(!wcp_rg_message(&rg,id,payload,length))return 4;
        size=wcp_rg_mailbox(&rg,mailbox,sizeof(mailbox));if(!size)return 5;
        snprintf(path,sizeof(path),"%s/%u.bin",argv[2],index++);f=fopen(path,"wb");if(!f)return 6;
        if(fwrite(mailbox,1,size,f)!=size || fclose(f))return 6;
    }
    fclose(in);printf("NATIVE_MAILBOX_FIXTURE_PASS files=%u\n",index);return 0;
}
