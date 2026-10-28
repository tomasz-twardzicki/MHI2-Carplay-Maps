/* SPDX-License-Identifier: GPL-3.0-or-later */
#ifndef CPVC_CUSTOM_DISPLAY_SETTINGS_H
#define CPVC_CUSTOM_DISPLAY_SETTINGS_H
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <errno.h>
#include <sys/stat.h>
#include <pthread.h>
struct cpvc_display_settings {int stream,layout;uint64_t generation;};
static pthread_mutex_t cpvc_display_lock=PTHREAD_MUTEX_INITIALIZER;
static struct cpvc_display_settings cpvc_display_cached={0,0,0};
static uint32_t cpvc_display_crc(const unsigned char *s,size_t n){
 uint32_t crc=0xffffffffu;size_t i;int bit;
 for(i=0;i<n;i++){crc^=s[i];for(bit=0;bit<8;bit++)crc=(crc>>1)^(0xedb88320u&(uint32_t)-(int)(crc&1));}
 return crc^0xffffffffu;
}
static int cpvc_display_file(const char *path,struct cpvc_display_settings *out){
 struct stat st;char data[193],body[128],canonical[193];FILE *f;size_t n;int stream,layout,used=0,len,bad;
 unsigned long long generation;unsigned crc;
 if(lstat(path,&st))return errno==ENOENT?0:-1;
 if(!S_ISREG(st.st_mode)||st.st_size<1||st.st_size>192)return -1;
 f=fopen(path,"rb");if(!f)return -1;n=fread(data,1,192,f);bad=ferror(f);if(fclose(f)||bad||n!=(size_t)st.st_size||memchr(data,0,n))return -1;data[n]=0;
 if(sscanf(data,"format=1\nstream=%d\nlayout=%d\ngeneration=%llu\ncrc32=%x\n%n",&stream,&layout,&generation,&crc,&used)!=4||used!=(int)n||stream<0||stream>3||layout<0||layout>3||generation<1||generation>0x7fffffffffffffffULL)return -1;
 len=snprintf(body,sizeof(body),"format=1\nstream=%d\nlayout=%d\ngeneration=%llu\n",stream,layout,generation);
 if(len<0||(size_t)len>=sizeof(body)||cpvc_display_crc((const unsigned char *)body,(size_t)len)!=crc)return -1;
 len=snprintf(canonical,sizeof(canonical),"%scrc32=%x\n",body,crc);
 if(len!=(int)n||memcmp(data,canonical,n))return -1;
 out->stream=stream;out->layout=layout;out->generation=generation;return 1;
}
static int cpvc_display_read(const char *root,struct cpvc_display_settings *out){
 char path[512];int a,b;
 if(!root||snprintf(path,sizeof(path),"%s/display.state",root)>=(int)sizeof(path))return -1;
 a=cpvc_display_file(path,out);if(a==1)return 1;
 if(snprintf(path,sizeof(path),"%s/display.previous",root)>=(int)sizeof(path))return -1;
 b=cpvc_display_file(path,out);if(b==1)return 2;
 if(a||b)return -1;
 out->stream=0;out->layout=0;out->generation=0;return 0;
}
static struct cpvc_display_settings cpvc_display_snapshot(void){
 struct cpvc_display_settings result;pthread_mutex_lock(&cpvc_display_lock);result=cpvc_display_cached;pthread_mutex_unlock(&cpvc_display_lock);return result;
}
static void cpvc_display_refresh(void){
 struct cpvc_display_settings next;const char *root=getenv("CPVC_DISPLAY_STATE_DIR");
 if(!root||!root[0])root="/mnt/icab/persistent/cpmap-ui";
 if(cpvc_display_read(root,&next)>=0){pthread_mutex_lock(&cpvc_display_lock);cpvc_display_cached=next;pthread_mutex_unlock(&cpvc_display_lock);}
}
static int cpvc_display_fps(void){int s=cpvc_display_snapshot().stream;return s==1||s==3?40:30;}
static int cpvc_display_idr(void){int s=cpvc_display_snapshot().stream;return s==1||s==2?5:20;}
static void cpvc_display_area(int *x,int *y,int *w,int *h){
 static const int rect[4][4]={{200,96,400,364},{160,96,480,364},{220,96,360,348},{220,65,360,348}};
 int l=cpvc_display_snapshot().layout;*x=rect[l][0];*y=rect[l][1];*w=rect[l][2];*h=rect[l][3];
}
#endif
