/* SPDX-License-Identifier: GPL-3.0-or-later */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <sys/stat.h>
#include "wcp_settings.h"
int main(int argc,char **argv) {
    struct wcp_settings s;char path[256],text[128];int n,fd;unsigned value;char *end;
    int defaults=argc==2 && !strcmp(argv[1],"defaults");
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
