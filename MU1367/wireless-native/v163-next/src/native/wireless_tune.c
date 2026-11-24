/* SPDX-License-Identifier: GPL-3.0-or-later */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <stdint.h>
#include <sys/stat.h>
#include <time.h>
#include "wcp_settings.h"
/* Reuse the existing managed tool for PF serialization; no SDK utility or new
 * persistent target is needed. POSIX locks survive exec and vanish on exit. */
static uint64_t pf_monotonic(void) {
    struct timespec t;
    if(clock_gettime(CLOCK_MONOTONIC,&t))return 0;
    return (uint64_t)t.tv_sec*1000000ULL+t.tv_nsec/1000;
}
static int pf_exec(const char *action) {
    struct stat before,opened;struct flock lock;char pid[32];unsigned tries;int fd,exists;
    const char *path="/ramdisk/wcp-pf.lock";
    if(strcmp(action,"on") && strcmp(action,"off") && strcmp(action,"check"))return 2;
    exists=!lstat(path,&before);
    if(exists && !S_ISREG(before.st_mode))return 1;
    fd=open(path,O_RDWR|O_CREAT,0600);if(fd<0)return 1;
    if(fstat(fd,&opened) || !S_ISREG(opened.st_mode) ||
       (exists && (before.st_dev!=opened.st_dev || before.st_ino!=opened.st_ino))) {close(fd);return 1;}
    /* Reserve a shell-preserved descriptor before locking. Closing any other
     * descriptor for this inode after locking would release the POSIX lock. */
    if(fd!=9) {if(dup2(fd,9)<0){close(fd);return 1;}close(fd);}
    if(fcntl(9,F_SETFD,0)<0)return 1;
    memset(&lock,0,sizeof(lock));lock.l_type=F_WRLCK;lock.l_whence=SEEK_SET;
    for(tries=0;tries<100;tries++) {
        if(!fcntl(9,F_SETLK,&lock))break;
        if(errno!=EACCES && errno!=EAGAIN)return 1;
        {struct timespec delay;delay.tv_sec=0;delay.tv_nsec=100000000;nanosleep(&delay,0);}
    }
    if(tries==100) {fprintf(stderr,"PF_LOCK_BUSY t_us=%llu\n",(unsigned long long)pf_monotonic());return 1;}
    snprintf(pid,sizeof(pid),"%ld",(long)getpid());
    if(setenv("CPMAP_WCP_PF_LOCKED",pid,1))return 1;
    fprintf(stderr,"PF_LOCK_ACQUIRED t_us=%llu pid=%s\n",(unsigned long long)pf_monotonic(),pid);fflush(stderr);
    execl("/bin/sh","/bin/sh","/mnt/ota/wcp_pf.sh",action,(char *)0);
    return 1;
}
int main(int argc,char **argv) {
    struct wcp_settings s;char path[256],text[128];int n,fd;unsigned value;char *end;
    int defaults=argc==2 && !strcmp(argv[1],"defaults");
    if(argc==3 && !strcmp(argv[1],"pf"))return pf_exec(argv[2]);
    if(argc==2 && !strcmp(argv[1],"monotonic")) {printf("%llu\n",(unsigned long long)pf_monotonic());return 0;}
    if(wcp_settings_read(WCP_SETTINGS_PATH,&s) && !defaults) {puts("WIRELESS_SETTINGS_INVALID");return 1;}
    if(defaults) {s.fps=40;s.idr=8;s.smoothing=150;}
    if(argc==3 || defaults) {
        if(!defaults) {
        value=(unsigned)strtoul(argv[2],&end,10);
        if(!*argv[2] || *end)return 2;
        if(!strcmp(argv[1],"fps"))s.fps=value;
        else if(!strcmp(argv[1],"idr"))s.idr=value;
        else if(!strcmp(argv[1],"smoothing"))s.smoothing=value;
        else return 2;
        if(!wcp_settings_valid(&s))return 2;
        }
        /* Preferences are user data, retained across wireless removal. */
        if(mkdir("/mnt/icab/persistent/cpmap-ui",0755) && errno!=EEXIST)return 1;
        n=snprintf(text,sizeof(text),"WCP161\nfps=%u\nidr=%u\nsmoothing_ms=%u\n",s.fps,s.idr,s.smoothing);
        snprintf(path,sizeof(path),WCP_SETTINGS_PATH ".%ld",(long)getpid());
        fd=open(path,O_WRONLY|O_CREAT|O_EXCL,0600);if(fd<0)return 1;
        if(write(fd,text,n)!=n || fsync(fd)) {close(fd);unlink(path);return 1;}
        if(close(fd) || rename(path,WCP_SETTINGS_PATH)) {unlink(path);return 1;}
        puts("WIRELESS_SETTING_SAVED_RECONNECT_PHONE_TO_APPLY");
    } else if(argc!=1)return 2;
    printf("WIRELESS fps=%u idr_request_frames=%u smoothing_base_ms=%u cap_ms=250\n",s.fps,s.idr,s.smoothing);
    return 0;
}
