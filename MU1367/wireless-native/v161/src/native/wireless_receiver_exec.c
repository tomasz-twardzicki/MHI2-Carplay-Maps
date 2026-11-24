/* SPDX-License-Identifier: GPL-3.0-or-later
 * Source-owned extension of the audited V3.1 launch contract. Receiver,
 * transport and maps libraries remain byte-identical and hash-pinned.
 */
#define _POSIX_C_SOURCE 200809L
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <errno.h>
#include <time.h>
#include <sys/stat.h>
#include <fcntl.h>
#include "wcp_sha.h"
#include "wcp_settings.h"
#ifndef WCP_TAP_SHA256
#error WCP_TAP_SHA256 must pin the built tap
#endif
#define ROOT "/mnt/app/carplaymaps/"
static int verify(int transport_only) {
    if(!wcp_hash_matches(ROOT "libv75-transport.so","46a46b9bf2b60cba84c6d9ebeaac39ed56db8abe3b761a5d3c71f75458abbf3b"))return 0;
    return transport_only || (
      wcp_hash_matches("/dev/shmem/wcp_receiver","f195665b0e9fb8a592618e64b7201ddfc536a9b082c6dd35db214b99d5e01de1") &&
      wcp_hash_matches(ROOT "libomonob-wireless-maps.so","b40e381e0d8b9c56b55b797570fcafe8861b2f026b3125feb9efeceeadfa1fa7") &&
      wcp_hash_matches(ROOT "libcpmap-wcp-tap.so",WCP_TAP_SHA256));
}
int main(int argc,char **argv) {
    struct timespec t;struct wcp_settings settings;char scope[96],fps[8];unsigned i;const char *preload=getenv("LD_PRELOAD");
    if(argc==2 && !strcmp(argv[1],"--transport-status"))return verify(1)?0:10;
    if(argc==2 && !strcmp(argv[1],"--verify-only"))return verify(0)?0:10;
    if(argc!=1 || (preload && *preload) || !verify(0))return 10;
    if(wcp_settings_read(WCP_SETTINGS_PATH,&settings))return 13;
    if(clock_gettime(CLOCK_MONOTONIC,&t))return 11;
    for(i=0;i<128;i++) {
        snprintf(scope,sizeof(scope),"/ramdisk/.v75-native-%08x%08x%08x%08x",(unsigned)getpid(),(unsigned)t.tv_sec,(unsigned)t.tv_nsec,i);
        if(!mkdir(scope,0700))break;
        if(errno!=EEXIST)return 11;
    }
    if(i==128)return 11;
    snprintf(fps,sizeof(fps),"%u",settings.fps);
    if(setenv("V75_WCP_NATIVE","1",1) || setenv("V75_WCP_SCOPE",scope,1) || setenv("V75_WCP_CARD","791",1) ||
       setenv("V75_WCP_TRANSPORT","1",1) || setenv("WCP_FPS",fps,1) || setenv("WCP_VIDEO_FPS",fps,1) ||
       setenv("CPMAP_WCP_TAP","161",1) || setenv("CPMAP_WCP_TIMED_INPUT","1",1) ||
       setenv("LD_PRELOAD",ROOT "libcpmap-wcp-tap.so:" ROOT "libv75-transport.so:" ROOT "libomonob-wireless-maps.so",1)) {rmdir(scope);return 12;}
    /* Per-boot alternate-display activation, respecting the explicit OEM off
     * marker. Never force the probe over a user's wcp_alt_off setting. */
    if(access("/mnt/persist/wcp_alt_off",F_OK)!=0 && errno==ENOENT) {
        struct stat st;
        if(lstat("/dev/shmem/wcp_alt_probe",&st)==0) {if(!S_ISREG(st.st_mode)){rmdir(scope);return 14;}}
        else if(errno==ENOENT) {int fd=open("/dev/shmem/wcp_alt_probe",O_WRONLY|O_CREAT|O_EXCL,0600);
            if(fd<0){rmdir(scope);return 14;}if(write(fd,"1\n",2)!=2 || close(fd)){rmdir(scope);return 14;}}
        else {rmdir(scope);return 14;}
    }
    /* Never wait for HMI coding here: the controller owns this PID before
     * exec. Coding is refreshed by the tap when /info is constructed. */
    printf("CPMAP_WCP161 fps=%u idr_request_frames=%u smoothing_ms=%u\n",settings.fps,settings.idr,settings.smoothing);fflush(stdout);
    execl("/dev/shmem/wcp_receiver","/dev/shmem/wcp_receiver",(char *)0);
    rmdir(scope);return 127;
}
