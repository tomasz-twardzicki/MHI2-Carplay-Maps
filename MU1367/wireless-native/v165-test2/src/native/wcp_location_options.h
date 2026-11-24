/* SPDX-License-Identifier: GPL-3.0-or-later. Preferences belong to this layer's
 * recovery directory; OEM restore archives them with the layer. They never
 * alter a snapshot receipt or leave a new flat /mnt/persist marker behind. */
#ifndef CPMAP_LOCATION_OPTIONS_H
#define CPMAP_LOCATION_OPTIONS_H
#include <stdio.h>
#include <string.h>
#include <sys/stat.h>
#define WCP_LOCATION_LAYER "/mnt/app/carplay-mu1367-wireless-native-v165t2"
#define WCP_LOCATION_ENABLE_FILE WCP_LOCATION_LAYER "/gps.enabled"
#define WCP_LOCATION_PROBE_FILE WCP_LOCATION_LAYER "/gps-probe.enabled"
#define WCP_ROAD_LABEL_FILE WCP_LOCATION_LAYER "/road-label.mode"
#define WCP_LOCATION_BOOT_ATTEMPT "/ramdisk/cpmap-gps-dio-attempt.state"
static int gps_file_equals(const char *path,const char *expected){
    struct stat st;FILE *f;char b[32];size_t n;
    if(lstat(path,&st)||!S_ISREG(st.st_mode)||st.st_size!=(off_t)strlen(expected))return 0;
    f=fopen(path,"rb");if(!f)return 0;n=fread(b,1,sizeof(b),f);if(fclose(f))return 0;
    return n==strlen(expected)&&!memcmp(b,expected,n);
}
static int gps_layer_installed(void){
    struct stat st;
    return !lstat(WCP_LOCATION_LAYER,&st)&&S_ISDIR(st.st_mode)&&gps_file_equals(WCP_LOCATION_LAYER "/STATE","installed\n");
}
static int gps_option_enabled(const char *path){return gps_layer_installed()&&gps_file_equals(path,"1\n");}
#endif
