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
#include "wcp_location_options.h"
#ifndef WCP_TAP_SHA256
#error WCP_TAP_SHA256 must pin the built tap
#endif
#define ROOT "/mnt/app/carplaymaps/"
static int gps_source_verified(void) {
#ifdef GPS_SOURCE_SHA256
    return wcp_hash_matches(ROOT "libcpmap-gps-source.so",GPS_SOURCE_SHA256) &&
        wcp_hash_matches(ROOT "stock_first/dio_manager.real","ead570d45071bb4dafe4a4667003bb9f82a72f58178f30dc86a08f11ce62a3ae");
#else
    return 0;
#endif
}
static int gps_source_claim(void){
    int fd,n,ok;char text[128];struct timespec t;
    if(!gps_option_enabled(WCP_LOCATION_ENABLE_FILE)||!gps_source_verified()||clock_gettime(CLOCK_MONOTONIC,&t))return 10;
    /* One DIO preload attempt per full boot. A restarted DIO uses the normal
     * launcher, so an experimental callback failure cannot cause a boot loop. */
    fd=open(WCP_LOCATION_BOOT_ATTEMPT,O_WRONLY|O_CREAT|O_EXCL,0600);if(fd<0)return 10;
    n=snprintf(text,sizeof(text),"WGPS_DIO_ATTEMPT1\n%ld\n%lu\n",(long)getppid(),(unsigned long)t.tv_sec);
    ok=n>0&&n<(int)sizeof(text)&&write(fd,text,(size_t)n)==n;if(close(fd))ok=0;
    return ok?0:10;
}
static int verify(int transport_only) {
    if(!wcp_hash_matches(ROOT "libv75-transport.so","46a46b9bf2b60cba84c6d9ebeaac39ed56db8abe3b761a5d3c71f75458abbf3b"))return 0;
    return transport_only || (
      wcp_hash_matches("/dev/shmem/wcp_receiver","f195665b0e9fb8a592618e64b7201ddfc536a9b082c6dd35db214b99d5e01de1") &&
      wcp_hash_matches(ROOT "libomonob-wireless-maps.so","b40e381e0d8b9c56b55b797570fcafe8861b2f026b3125feb9efeceeadfa1fa7") &&
      wcp_hash_matches(ROOT "libcpmap-wcp-tap.so",WCP_TAP_SHA256));
}
int main(int argc,char **argv) {
    struct timespec t;struct wcp_settings settings;char scope[96],fps[8];unsigned i;const char *preload=getenv("LD_PRELOAD");
    if(argc==2 && !strcmp(argv[1],"--gps-source-status"))return gps_source_verified()?0:10;
    if(argc==2 && !strcmp(argv[1],"--gps-source-enabled"))return gps_option_enabled(WCP_LOCATION_ENABLE_FILE)&&gps_source_verified()?0:10;
    if(argc==2 && !strcmp(argv[1],"--gps-source-claim"))return gps_source_claim();
    if(argc==2 && !strcmp(argv[1],"--bt-guard-status")) {
#ifdef BT_GUARD_SHA256
        return wcp_hash_matches(ROOT "libcpmap-bt-session.so",BT_GUARD_SHA256) &&
            wcp_hash_matches("/mnt/ota/libbtwcp.so","95a75391792c7266eb8c759c20f3b35745d2cd890b74fad45e2c36a5406e9d4e")?0:10;
#else
        return 10;
#endif
    }
    if(argc==2 && !strcmp(argv[1],"--transport-status"))return verify(1)?0:10;
    if(argc==2 && !strcmp(argv[1],"--verify-only"))return verify(0)?0:10;
    if(argc!=1 || (preload && *preload) || !verify(0))return 10;
    if(setenv("CPMAP_WCP_LOCATION",gps_option_enabled(WCP_LOCATION_ENABLE_FILE)&&gps_source_verified()?"164":"0",1))return 12;
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
       setenv("CPMAP_WCP_TAP","162",1) || setenv("CPMAP_WCP_TIMED_INPUT","1",1) ||
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
