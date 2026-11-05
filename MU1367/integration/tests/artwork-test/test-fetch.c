/* SPDX-License-Identifier: GPL-3.0-or-later. Synthetic PNG/JPEG fixtures only. */
#define _POSIX_C_SOURCE 200809L
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <sys/stat.h>
#include <sys/wait.h>
#include <unistd.h>
#include <time.h>
#ifndef TEST_QNX
#define main fetch_main
#include "@FETCH@"
#undef main
#endif
static const unsigned char png_fixture[]={@PNG@};
static const unsigned char jpeg_fixture[]={@JPEG@};
static unsigned char frame[800129];static char input[256],output[256],lockdir[256];static int checks;
static void check(int ok){if(!ok){fprintf(stderr,"ARTWORK_FETCH_ASSERT=%d\n",checks);exit(1);}checks++;}
static void put(unsigned at,unsigned v){frame[at]=v;frame[at+1]=v>>8;frame[at+2]=v>>16;frame[at+3]=v>>24;}
static unsigned make(const unsigned char *image,unsigned bytes,unsigned kind){
    memset(frame,0,128);memcpy(frame,"N4AR",4);put(4,1);put(8,128);put(12,9);put(20,bytes);put(24,kind);
    put(28,3);put(36,2);put(40,7);put(44,1);put(48,0x9abcdef0);put(52,0x12345678);put(64,2);put(68,1);put(72,123);put(76,456);
    memcpy(frame+128,image,bytes);return 128+bytes;
}
static void write_frame(unsigned n){FILE *f=fopen(input,"wb");check(f!=NULL);check(fwrite(frame,1,n,f)==n);check(!fclose(f));}
static int run(const char *uid,const char *id,const char *size){
    char *a[]={"artwork-fetch",input,lockdir,output,(char *)uid,(char *)id,(char *)size,NULL};
    int rc;
#ifdef TEST_QNX
    int status;pid_t p=fork();if(!p){execv("/proc/boot/rgi-observer",a);_exit(255);}check(p>0);check(waitpid(p,&status,0)==p);rc=WIFEXITED(status)?WEXITSTATUS(status):255;
#else
    rc=fetch_main(7,a);
#endif
    check(access(lockdir,F_OK)!=0);return rc;
}
static void output_png(void){
    unsigned char b[24];struct stat st;FILE *f=fopen(output,"rb");check(f!=NULL);check(fread(b,1,24,f)==24);check(!fclose(f));
    check(!memcmp(b,"\x89PNG\r\n\x1a\n",8));check(!memcmp(b+16,"\0\0\1\0\0\0\1\0",8));
    check(!stat(output,&st)&&st.st_size>190000&&st.st_size<200000);check(!unlink(output));
}
int main(int argc,char **argv){
    unsigned n,i;char size[32];
#ifdef TEST_QNX
    if(argc==2&&!strcmp(argv[1],"ram")){setenv("CACHE_NOP","1",1);execl("/proc/boot/devb-ram","devb-ram","blk","cache=1m,verbose","ram","capacity=32768,nodinit",(char *)0);return 1;}
    if(argc==2&&!strcmp(argv[1],"list"))return 0;
    (void)mkdir("/ramdisk/artwork-test",0700);argv[1]="/ramdisk/artwork-test";
#else
    check(argc==2);
#endif
    snprintf(input,sizeof(input),"%s/frame",argv[1]);snprintf(output,sizeof(output),"%s/result.png",argv[1]);snprintf(lockdir,sizeof(lockdir),"%s/lock",argv[1]);
    n=make(png_fixture,sizeof(png_fixture),1);write_frame(n);snprintf(size,sizeof(size),"%u",(unsigned)sizeof(png_fixture));
    check(!run("123456789abcdef0","7",size));output_png();
    {unsigned offsets[]={4,8,16,20,24,36,40,44,48,52,56,60,64,68,76,80,124};
     for(i=0;i<sizeof(offsets)/sizeof(offsets[0]);i++){
        n=make(png_fixture,sizeof(png_fixture),1);frame[offsets[i]]^=1;if(offsets[i]==76)put(76,1000000000u);write_frame(n);check(run("123456789abcdef0","7",size)!=0);check(access(output,F_OK)!=0);
     }}
    n=make(png_fixture,sizeof(png_fixture),1);write_frame(n-1);check(run("123456789abcdef0","7",size)!=0);
    write_frame(n+1);check(run("123456789abcdef0","7",size)!=0);
    write_frame(n);check(run("123456789abcdef1","7",size)!=0);check(run("123456789abcdef0","8",size)!=0);
    check(run("10000000000000000","7",size)!=0);check(run("0","7",size)!=0);check(run("123456789abcdef0","256",size)!=0);check(run("123456789abcdef0","7","800001")!=0);
    n=make(jpeg_fixture,sizeof(jpeg_fixture),2);write_frame(n);snprintf(size,sizeof(size),"%u",(unsigned)sizeof(jpeg_fixture));check(!run("123456789abcdef0","7",size));output_png();
    n=make((const unsigned char *)"\xff\xd8\xfftruncated",12,2);write_frame(n);check(run("123456789abcdef0","7","12")!=0);
    check(!unlink(input));printf("ARTWORK_FETCH_PASS checks=%d\n",checks);return 0;
}
