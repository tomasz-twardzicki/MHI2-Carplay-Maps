/* SPDX-License-Identifier: GPL-3.0-or-later
 * Preserve the audited 790 bootstrap, adding only a pinned metadata observer.
 */
#define _POSIX_C_SOURCE 200809L
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <errno.h>
#include <time.h>
#include <sys/stat.h>
#include "wcp_sha.h"
#ifndef WCP_MEDIA790_SHA256
#error WCP_MEDIA790_SHA256 must pin the observer
#endif
#ifndef BT_GUARD_SHA256
#error BT_GUARD_SHA256 must pin the shared accepted-session guard
#endif
#define ROOT "/mnt/app/carplaymaps/"
static int launch_stamp(const char *role,const char *pid){
 const char *path="/ramdisk/cpmap-native-launch.log";struct timespec t;struct stat st;FILE *f;char *end;unsigned long child;
 if(strcmp(role,"video-before")&&strcmp(role,"video-after")&&strcmp(role,"receiver-before")&&strcmp(role,"receiver-after"))return 2;
 child=strtoul(pid,&end,10);if(!*pid||*end||child>0x7fffffffUL)return 2;
 if(clock_gettime(CLOCK_MONOTONIC,&t)||(!lstat(path,&st)&&!S_ISREG(st.st_mode)))return 1;
 f=fopen(path,!lstat(path,&st)&&st.st_size>8192?"w":"a");if(!f)return 1;
 fprintf(f,"WCP_LAUNCH mono_us=%llu role=%s child=%lu parent=%ld\n",(unsigned long long)t.tv_sec*1000000+t.tv_nsec/1000,role,child,(long)getppid());return fclose(f)?1:0;
}
static int verify(int transport_only) {
    return wcp_hash_matches(ROOT "libv75-transport.so","46a46b9bf2b60cba84c6d9ebeaac39ed56db8abe3b761a5d3c71f75458abbf3b")&&
      (transport_only||(
        wcp_hash_matches("/dev/shmem/wcp_receiver","396c73bcd7674483245776d0493552832f7ebbcefed399d7b9dd1182a5336c90")&&
        wcp_hash_matches(ROOT "libomonob-wireless-maps.so","160d43f227dcdda27a11e4b8a8623c68a0aabe488ae18cc9766992fcd6dc5cfa")&&
        wcp_hash_matches(ROOT "libcpmap-wcp-media790.so",WCP_MEDIA790_SHA256)));
}
int main(int argc,char **argv) {
    struct timespec t;char scope[96];unsigned i;const char *preload=getenv("LD_PRELOAD");
    if(argc==4&&!strcmp(argv[1],"--launch-stamp"))return launch_stamp(argv[2],argv[3]);
    if(argc==2&&!strcmp(argv[1],"--bt-guard-status"))return wcp_hash_matches(ROOT "libcpmap-bt-session.so",BT_GUARD_SHA256)&&wcp_hash_matches("/mnt/ota/libbtwcp.so","95a75391792c7266eb8c759c20f3b35745d2cd890b74fad45e2c36a5406e9d4e")?0:10;
    if(argc==2&&!strcmp(argv[1],"--transport-status"))return verify(1)?0:10;
    if(argc==2&&!strcmp(argv[1],"--verify-only"))return verify(0)?0:10;
    if(argc!=1||(preload&&*preload)||!verify(0))return 10;
    if(clock_gettime(CLOCK_MONOTONIC,&t))return 11;
    for(i=0;i<128;i++){
        snprintf(scope,sizeof(scope),"/ramdisk/.v75-native-%08x%08x%08x%08x",(unsigned)getpid(),(unsigned)t.tv_sec,(unsigned)t.tv_nsec,i);
        if(!mkdir(scope,0700))break;if(errno!=EEXIST)return 11;
    }
    if(i==128)return 11;
    if(setenv("V75_WCP_NATIVE","1",1)||setenv("V75_WCP_SCOPE",scope,1)||setenv("V75_WCP_CARD","790",1)||
       setenv("V75_WCP_TRANSPORT","1",1)||setenv("WCP_FPS","30",1)||setenv("WCP_VIDEO_FPS","30",1)||
       setenv("CPMAP_WCP_MEDIA790","1",1)||
       setenv("LD_PRELOAD",ROOT "libcpmap-wcp-media790.so:" ROOT "libv75-transport.so:" ROOT "libomonob-wireless-maps.so",1)){
        rmdir(scope);return 12;
    }
    execl("/dev/shmem/wcp_receiver","/dev/shmem/wcp_receiver",(char *)0);
    rmdir(scope);return 127;
}
