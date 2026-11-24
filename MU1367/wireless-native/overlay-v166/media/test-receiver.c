#pragma clang diagnostic ignored "-Wunused-function"
#include "@SOURCE@"
#include <ucontext.h>
@ASM@
static unsigned checks,sequence=1;
static void check(int ok,const char *why){checks++;if(!ok){printf("MEDIA790_FAILED=%s errno=%d\n",why,errno);fflush(stdout);_exit(81);}}
static void fault(int sig,siginfo_t *info,void *ctx){ucontext_t *u=ctx;char s[200];int n=snprintf(s,sizeof(s),"FAULT sig=%d pc=%x lr=%x address=%p\n",sig,(unsigned)u->uc_mcontext.cpu.gpr[15],(unsigned)u->uc_mcontext.cpu.gpr[14],info->si_addr);write(2,s,n);_exit(90);}
static void put(const char *path,const char *text){FILE *f=fopen(path,"w");check(f!=0,path);fputs(text,f);check(!fclose(f),"close");}
static void pause_test(void){struct timespec t;t.tv_sec=0;t.tv_nsec=300000000;nanosleep(&t,0);}
static void packet(unsigned id,const unsigned char *payload,unsigned size,int file){
    unsigned total=size+(file?10:16),i,sum=0;unsigned char *item=calloc(1,total+4),*p=item+4;
    check(item!=0,"packet allocation");*(uint32_t *)item=total;
    p[0]=0xff;p[1]=0x5a;p[2]=total>>8;p[3]=total;p[4]=0x40;p[5]=sequence++;p[7]=file?0x0c:0x0a;
    for(i=0;i<8;i++)sum+=p[i];p[8]=(unsigned char)-sum;
    if(file)memcpy(p+9,payload,size);
    else{p[9]=p[10]=0x40;p[11]=(size+6)>>8;p[12]=size+6;p[13]=id>>8;p[14]=id;memcpy(p+15,payload,size);}
    sum=0;for(i=9;i<total-1;i++)sum+=p[i];p[total-1]=(unsigned char)-sum;
    ((void (*)(void *))0xec5ec)(item);
}
static unsigned read_snapshot(unsigned char *out,unsigned cap){FILE *f=fopen("/ramdisk/wcp-rg/nowplaying.bin","rb");unsigned n;check(f!=0,"media snapshot present");n=fread(out,1,cap,f);fclose(f);return n;}
__attribute__((constructor)) static void exercise(void){
    static const unsigned char metadata[]={0,41,0,0,0,12,0,0,0,0,0,0,0,0,0,42,0,10,0,1,'F','i','x','t','u','r',0,10,0,12,'A','r','t','i','s','t',0,5,0,26,0x84};
    static const unsigned char playback[]={0,17,0,1,0,5,0,0,1,0,8,0,1,0,0,3,232};
    static const unsigned char image[]={@IMAGE@};
    unsigned char snap[8192],data[sizeof(image)+2],ack[8],header[]={0x84,4,0,0,0,0,0,0,0,0};
    char text[256];unsigned n,generation;struct wcp_media before;
    const char *scope="/ramdisk/.v75-native-0123456789abcdef0123456789abcdef";
    struct sigaction sa;memset(&sa,0,sizeof(sa));sa.sa_sigaction=fault;sa.sa_flags=SA_SIGINFO;sigaction(SIGBUS,&sa,0);sigaction(SIGSEGV,&sa,0);
    check(getenv("MU1367_GATE_ONLY")!=0,"fixture boundary");if(!enabled)init();check(enabled,"production observer enabled");
    *(int *)0x110a14=2;*(unsigned char *)0x112af1=0;*(int *)0x112aec=0;
    packet(0x5001,metadata,sizeof(metadata),0);packet(0x5001,playback,sizeof(playback),0);
    check(media_updates==2&&media.uid==42&&media.position==1000&&media.status==1,"actual CSM capture and delta merge");
    pause_test();n=read_snapshot(snap,sizeof(snap));check(n==140&&snap[32]==0&&snap[48]==0,"pre-grant metadata not published");
    snprintf(text,sizeof(text),"V75_NATIVE1\n%ld\n%s\n",(long)getpid(),scope);put("/ramdisk/v75-wireless-native.owner",text);
    snprintf(text,sizeof(text),"%ld\n",(long)getpid());put("/dev/shmem/wcp_receiver.pid",text);put("/dev/shmem/wcp_cp_session","1\n");
    snprintf(text,sizeof(text),"V75_GRANT1\n%ld\n1\n",(long)getpid());put("/ramdisk/.v75-native-0123456789abcdef0123456789abcdef/cluster-session.accepted",text);
    pause_test();n=read_snapshot(snap,sizeof(snap));check(n>140&&snap[32]==1&&snap[48]==42,"accepted snapshot carries real track");
    check(media_session==1,"first accepted media epoch");
    {uintptr_t old=*(uintptr_t *)0x112ad4;unsigned sequence_before=bt_request_sequence;
     *(uintptr_t *)0x112ad4=0x456780;
     ((void (*)(const char *))0xeb3c8)("12:34:56:78:9A:BC");pause_test();
     check(bt_request_sequence>sequence_before&&bt_request_bound==media_session,"790 native BT command bound to accepted epoch");
     {FILE *f=fopen("/ramdisk/wcp-rg/bt-request.state","r");check(f!=0,"790 BT request snapshot");n=fread(text,1,sizeof(text)-1,f);text[n]=0;fclose(f);check(strstr(text,"\n1\n123456789ABC\n")!=0,"790 addressed request valid");}
     *(uintptr_t *)0x112ad4=0x456784;pause_test();check(!bt_request_bound,"790 replacement control invalidates BT request");
     *(uintptr_t *)0x112ad4=old;
     printf("MEDIA790_BT_LEASE_PASS accepted_lease=1 actual_command=1 replacement_clear=1\n");}

    header[8]=(unsigned char)(sizeof(image)>>8);header[9]=(unsigned char)sizeof(image);
    *(const char **)0x110a1c="/ramdisk";*(const char **)0x110a20="/ramdisk/cover.cur";
    ((int (*)(void *,unsigned,void *))0xee210)(header,sizeof(header),ack);
    data[0]=0x84;data[1]=0xc0;memcpy(data+2,image,sizeof(image));
    ((int (*)(void *,unsigned,void *))0xee210)(data,sizeof(data),ack);
    check(media_cover_copied==1,"real native FT completion captured");pause_test();
    n=read_snapshot(snap,sizeof(snap));check(n>140&&snap[76]==0x84&&snap[80]&&snap[84],"cover advertised with track identity");
    {FILE *f=fopen("/ramdisk/wcp-rg/cover.bin","rb");check(f!=0,"owned image snapshot");n=fread(snap,1,sizeof(snap),f);fclose(f);
     check(n==64+sizeof(image)&&!memcmp(snap,"WCA1",4)&&!memcmp(snap+64,image,sizeof(image)),"exact immutable image bytes");}
    generation=media.generation;header[8]=header[9]=0;
    ((int (*)(void *,unsigned,void *))0xee210)(header,sizeof(header),ack);
    ((int (*)(void *,unsigned,void *))0xee210)(data,2,ack);
    check(media.generation!=generation,"empty native FT clears cover");pause_test();check(!media_published_cover,"cleared cover not advertised");
    header[8]=(unsigned char)(sizeof(image)>>8);header[9]=(unsigned char)sizeof(image);
    packet(0,header,sizeof(header),1);check(media_ft_declared&&media_ft_uid==42,"actual FT declaration binds original track");
    {unsigned char update[sizeof(metadata)];memcpy(update,metadata,sizeof(update));update[15]=43;packet(0x5001,update,sizeof(update),0);}
    ((int (*)(void *,unsigned,void *))0xee210)(data,sizeof(data),ack);
    check(media_cover_copied==1,"late previous cover rejected after new UID");
    memcpy(&before,&media,sizeof(before));packet(0x5001,metadata,sizeof(metadata)-1,0);check(!memcmp(&before,&media,sizeof(media))&&media_invalid==1,"malformed metadata rejected atomically");
    packet(0x5201,playback,sizeof(playback),0);check(!memcmp(&before,&media,sizeof(media)),"navigation messages not intercepted");
    check(!strcmp(getenv("WCP_FPS"),"30")&&!strcmp(getenv("WCP_VIDEO_FPS"),"30"),"790 video cadence preserved");
    check(access("/ramdisk/wcp-rg/latest.bin",F_OK)!=0&&access("/ramdisk/wcp-video-timing.bin",F_OK)!=0&&access("/dev/shmem/alt_force_idr",F_OK)!=0,"no video guidance timing or IDR side effects");
    unlink("/dev/shmem/wcp_cp_session");pause_test();n=read_snapshot(snap,sizeof(snap));
    check(n==140&&snap[32]==0&&snap[48]==0&&access("/ramdisk/wcp-rg/cover.bin",F_OK)!=0,"disconnect clears media and image");
    check(media_updates>=3,"only real media messages counted");
    printf("MEDIA790_ACTUAL_RECEIVER_PASS checks=%u actual_parser=1 actual_file_transfer=1 pregrant=1 late_cover=1 malformed_atomic=1 disconnect_clear=1 video_changes=0 audio_changes=0\n",checks);fflush(stdout);_exit(0);
}
