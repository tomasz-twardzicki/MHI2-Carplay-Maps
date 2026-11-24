#ifndef CPMAP_WIRELESS_CARD_DIAG_H
#define CPMAP_WIRELESS_CARD_DIAG_H
/* SPDX-License-Identifier: GPL-3.0-or-later
 * Fixed RAM snapshots, numeric fields only. Never change transport policy. */
#include <time.h>
#ifndef CPMAP_CARD_DIAG_ROOT
#define CPMAP_CARD_DIAG_ROOT "/ramdisk"
#endif
static pthread_mutex_t cpdiag_lock=PTHREAD_MUTEX_INITIALIZER;
static struct {
 int preference,source,read_result,declared,ready,busy,blocked,applied;
 int sent_op,sent_position,send_result,ack_op,ack_position,ack_result,ack_accepted;
 int scene_sent_position,scene_send_result,scene_ack_position,scene_ack_result,scene_ack_accepted;
 uint64_t scene_sent_token,scene_ack_token;
 uint64_t generation,epoch,sent_token,ack_token;
} cpdiag={.preference=-1,.declared=-1,.applied=-1};
static uint64_t cpdiag_written;
static char cpdiag_previous[768];
static int cpdiag_replace(const char *name,const char *body,int first){
 char path[512],temp[512];struct stat st;FILE *f;size_t n=strlen(body);int bad;
 if(n>767||snprintf(path,sizeof(path),"%s/%s",CPMAP_CARD_DIAG_ROOT,name)>=(int)sizeof(path)||snprintf(temp,sizeof(temp),"%s.tmp",path)>=(int)sizeof(temp))return -1;
 if(!lstat(path,&st)){if(first)return 0;if(!S_ISREG(st.st_mode))return -1;}else if(errno!=ENOENT)return -1;
 if(!lstat(temp,&st)){if(!S_ISREG(st.st_mode))return -1;}else if(errno!=ENOENT)return -1;
 f=fopen(temp,"wb");if(!f)return -1;bad=fwrite(body,1,n,f)!=n;if(fclose(f))bad=1;
 if(bad||rename(temp,path)){unlink(temp);return -1;}return 0;
}
static void cpdiag_flush(int force){
 char body[768];struct timespec ts;uint64_t now;int n;
 if(clock_gettime(CLOCK_MONOTONIC,&ts))return;
 now=(uint64_t)ts.tv_sec*1000000u+(unsigned long)ts.tv_nsec/1000u;
 if(!force&&cpdiag_written&&now>=cpdiag_written&&now-cpdiag_written<500000)return;
 n=snprintf(body,sizeof(body),"format=3 off_scene=3 preference=%d pref_generation=%llu pref_source=%d pref_read=%d declared=%d epoch=%llu ready=%d busy=%d blocked=%d applied=%d sent_op=%d sent_position=%d sent_token=%llu send_result=%d ack_op=%d ack_position=%d ack_token=%llu ack_result=%d ack_accepted=%d scene_sent_position=%d scene_sent_token=%llu scene_send_result=%d scene_ack_position=%d scene_ack_token=%llu scene_ack_result=%d scene_ack_accepted=%d\n",
 cpdiag.preference,(unsigned long long)cpdiag.generation,cpdiag.source,cpdiag.read_result,cpdiag.declared,(unsigned long long)cpdiag.epoch,cpdiag.ready,cpdiag.busy,cpdiag.blocked,cpdiag.applied,cpdiag.sent_op,cpdiag.sent_position,(unsigned long long)cpdiag.sent_token,cpdiag.send_result,cpdiag.ack_op,cpdiag.ack_position,(unsigned long long)cpdiag.ack_token,cpdiag.ack_result,cpdiag.ack_accepted,cpdiag.scene_sent_position,(unsigned long long)cpdiag.scene_sent_token,cpdiag.scene_send_result,cpdiag.scene_ack_position,(unsigned long long)cpdiag.scene_ack_token,cpdiag.scene_ack_result,cpdiag.scene_ack_accepted);
 if(n<0||(size_t)n>=sizeof(body))return;
 if(strcmp(body,cpdiag_previous)&&!cpdiag_replace("cpmap-card-status.txt",body,0)){strcpy(cpdiag_previous,body);cpdiag_written=now;}
}
static void cpdiag_pref(int position,uint64_t generation,int source,int result){
 pthread_mutex_lock(&cpdiag_lock);cpdiag.preference=position;cpdiag.generation=generation;cpdiag.source=source;cpdiag.read_result=result;cpdiag_flush(0);pthread_mutex_unlock(&cpdiag_lock);
}
static void cpdiag_declare(int position){
 pthread_mutex_lock(&cpdiag_lock);cpdiag.declared=position;cpdiag_flush(1);pthread_mutex_unlock(&cpdiag_lock);
}
static void cpdiag_policy(uint64_t epoch,int ready,int busy,int blocked,int applied){
 pthread_mutex_lock(&cpdiag_lock);if(cpdiag.epoch!=epoch){cpdiag.scene_sent_token=cpdiag.scene_ack_token=0;cpdiag.scene_sent_position=cpdiag.scene_ack_position=-1;cpdiag.scene_send_result=cpdiag.scene_ack_result=cpdiag.scene_ack_accepted=0;}cpdiag.epoch=epoch;cpdiag.ready=ready;cpdiag.busy=busy;cpdiag.blocked=blocked;cpdiag.applied=applied;cpdiag_flush(0);pthread_mutex_unlock(&cpdiag_lock);
}
static void cpdiag_command(int ack,int op,int position,uint64_t token,int status,int accepted){
 char body[256];pthread_mutex_lock(&cpdiag_lock);
 if(ack){cpdiag.ack_op=op;cpdiag.ack_position=position;cpdiag.ack_token=token;cpdiag.ack_result=status;cpdiag.ack_accepted=accepted;}
 else{cpdiag.sent_op=op;cpdiag.sent_position=position;cpdiag.sent_token=token;cpdiag.send_result=status;}
 if(op==1){
  if(ack){cpdiag.scene_ack_position=position;cpdiag.scene_ack_token=token;cpdiag.scene_ack_result=status;cpdiag.scene_ack_accepted=accepted;}
  else{cpdiag.scene_sent_position=position;cpdiag.scene_sent_token=token;cpdiag.scene_send_result=status;}
 }
 if(op==4 && (!ack || accepted)){
  snprintf(body,sizeof(body),"format=1 ack=%d op=%d position=%d token=%llu status=%d accepted=%d epoch=%llu\n",ack,op,position,(unsigned long long)token,status,accepted,(unsigned long long)cpdiag.epoch);
  cpdiag_replace("cpmap-card-map-status.txt",body,0);
 }
 if(status&&status!=-EBUSY){
  snprintf(body,sizeof(body),"format=1 ack=%d op=%d position=%d token=%llu status=%d accepted=%d epoch=%llu\n",ack,op,position,(unsigned long long)token,status,accepted,(unsigned long long)cpdiag.epoch);
  cpdiag_replace("cpmap-card-first-failure.txt",body,1);
 }
 cpdiag_flush(0);pthread_mutex_unlock(&cpdiag_lock);
}
#endif
