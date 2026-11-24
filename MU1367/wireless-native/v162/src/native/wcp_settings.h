/* SPDX-License-Identifier: GPL-3.0-or-later */
#ifndef CPMAP_WCP_SETTINGS_H
#define CPMAP_WCP_SETTINGS_H
#include <stdio.h>
#include <string.h>
#include <errno.h>
#define WCP_SETTINGS_PATH "/mnt/icab/persistent/cpmap-ui/wireless-stream.conf"
struct wcp_settings { unsigned fps,idr,smoothing; };
static int wcp_settings_valid(const struct wcp_settings *s) {
    return (s->fps==20 || s->fps==25 || s->fps==30 || s->fps==40) &&
           (s->idr==5 || s->idr==7 || s->idr==8 || s->idr==10 || s->idr==15) &&
           (s->smoothing==0 || s->smoothing==100 || s->smoothing==150 || s->smoothing==200);
}
/* Absent uses explicit defaults. Malformed preferences fail closed. */
static int wcp_settings_read(const char *path,struct wcp_settings *s) {
    FILE *f; char bytes[128],canonical[128];size_t n;int used=0,length;
    s->fps=40;s->idr=8;s->smoothing=150;
    f=fopen(path,"r");if(!f)return errno==ENOENT?0:-1;
    n=fread(bytes,1,sizeof(bytes)-1,f);
    if(ferror(f) || fgetc(f)!=EOF) {fclose(f);return -1;}fclose(f);
    if(memchr(bytes,0,n))return -1;bytes[n]=0;
    if(sscanf(bytes,"WCP161\nfps=%u\nidr=%u\nsmoothing_ms=%u\n%n",&s->fps,&s->idr,&s->smoothing,&used)!=3 || used!=(int)n || !wcp_settings_valid(s))return -1;
    length=snprintf(canonical,sizeof(canonical),"WCP161\nfps=%u\nidr=%u\nsmoothing_ms=%u\n",s->fps,s->idr,s->smoothing);
    return length==(int)n && !strcmp(bytes,canonical)?0:-1;
}
#endif
