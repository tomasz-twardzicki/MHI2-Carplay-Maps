/* SPDX-License-Identifier: GPL-3.0-or-later */
#include "wcp_media.c"
#include <stdio.h>
#include <stdlib.h>
static void check(int ok,const char *why){if(!ok){fprintf(stderr,"MEDIA_FAIL %s\n",why);exit(1);}}
int main(void){
    struct wcp_media s,before;unsigned char envelope[8192],random[1024];unsigned i,j,r=0x893abc12;
    const unsigned char track[]={0,41,0,0,0,12,0,0,0,0,0,0,0,0,0,42,0,10,0,1,'F','i','x','t','u','r',0,10,0,12,'A','r','t','i','s','t',0,5,0,26,0x84};
    const unsigned char delta[]={0,12,0,1,0,8,0,1,0,0,3,232};
    memset(&s,0,sizeof(s));check(wcp_media_message(&s,track,sizeof(track)),"track");check(s.uid==42 && s.art==0x84 && !strcmp(s.text[1],"Artist"),"field mapping");
    before=s;check(wcp_media_message(&s,delta,sizeof(delta)),"position-only delta");check(!strcmp(s.text[0],"Fixtur")&&s.position==1000&&s.uid==42&&s.generation==before.generation,"delta retains identity and text");
    {unsigned char update[sizeof(track)];memcpy(update,track,sizeof(update));update[25]='X';before=s;check(wcp_media_message(&s,update,sizeof(update))&&s.uid==42&&s.generation!=before.generation,"same-UID changed track invalidates prior image");}
    for(i=1;i<sizeof(track);i++){before=s;check(!wcp_media_message(&s,track,i),"truncated TLV");check(!memcmp(&s,&before,sizeof(s)),"no partial merge");}
    {unsigned char duplicate[sizeof(track)*2];memcpy(duplicate,track,sizeof(track));memcpy(duplicate+sizeof(track),track,sizeof(track));before=s;check(!wcp_media_message(&s,duplicate,sizeof(duplicate))&&!memcmp(&s,&before,sizeof(s)),"duplicate group rejected atomically");}
    {unsigned char bad[sizeof(track)];memcpy(bad,track,sizeof(bad));bad[20]=0xff;before=s;check(!wcp_media_message(&s,bad,sizeof(bad))&&!memcmp(&s,&before,sizeof(s)),"bad UTF8 rejected atomically");}
    for(i=0;i<50000;i++){
        unsigned n; r=r*1664525u+1013904223u;n=r%sizeof(random);
        for(j=0;j<n;j++){r=r*1664525u+1013904223u;random[j]=r>>24;}
        before=s;if(!wcp_media_message(&s,random,n))check(!memcmp(&s,&before,sizeof(s)),"fuzz rejection is atomic");
    }
    check(wcp_media_mailbox(&s,envelope,sizeof(envelope),23,123,1,1,1,1,873)>140,"bounded snapshot");
    check(wcp_media_mailbox(&s,envelope,139,23,123,1,1,1,1,873)==0,"short output rejected");
    check(wcp_media_mailbox(&s,envelope,sizeof(envelope),23,123,1,1,0,0,0)==140&&envelope[32]==0&&envelope[48]==0,"inactive snapshot contains no track");
    puts("WIRELESS_MEDIA_NATIVE_PASS fuzz=50000 delta_merge=1 malformed_atomic=1 utf8=1 bounds=1");return 0;
}
