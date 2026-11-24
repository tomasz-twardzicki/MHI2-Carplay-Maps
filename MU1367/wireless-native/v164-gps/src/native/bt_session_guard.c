/* SPDX-License-Identifier: GPL-3.0-or-later
 * Private GOT extension for the exact third-party BT add-on, never OEM BT.
 * No global open/write interposition and no persistent/profile-release flags.
 */
#define _POSIX_C_SOURCE 200112L
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <unistd.h>
#include <errno.h>
#include <signal.h>
#include <pthread.h>
#include <fcntl.h>
#include <stdarg.h>
#include <time.h>
#include <dlfcn.h>
#ifndef CPMAP_ROOT_PREFIX
#define CPMAP_ROOT_PREFIX ""
#endif
#include "wireless_session.h"
#include "wcp_sha.h"
#ifndef BT_HASH_PATH
#define BT_HASH_PATH "/mnt/ota/libbtwcp.so"
#endif
#ifndef BT_LOAD_PATH
#define BT_LOAD_PATH BT_HASH_PATH
#endif
#define BT_SHA "95a75391792c7266eb8c759c20f3b35745d2cd890b74fad45e2c36a5406e9d4e"
static pthread_mutex_t bt_lock=PTHREAD_MUTEX_INITIALIZER;
static uintptr_t bt_base;
static int bt_installed;
static int (*bt_real_open)(const char *,int,...);
static ssize_t (*bt_real_write)(int,const void *,size_t);
static struct {unsigned long pid,nonce,session,counter;uint64_t changed;int primed;} bt_lease;
static unsigned long bt_preserved,bt_paused,bt_resends;
static uint64_t bt_clock(void){struct timespec t;if(clock_gettime(CLOCK_MONOTONIC,&t))return 0;return (uint64_t)t.tv_sec*1000+t.tv_nsec/1000000;}
static void bt_reset(void){pthread_mutex_lock(&bt_lock);memset(&bt_lease,0,sizeof(bt_lease));pthread_mutex_unlock(&bt_lock);}
static int bt_live(void){uint64_t now=bt_clock();int result;pthread_mutex_lock(&bt_lock);result=bt_installed&&bt_lease.primed&&bt_lease.changed&&now>=bt_lease.changed&&now-bt_lease.changed<1500;pthread_mutex_unlock(&bt_lock);return result;}
/* Read outside the BT-thread lock. A missed atomic-file read gets only the
 * remaining lease; inactive/changed ownership revokes immediately. */
static void bt_poll(void){
 char text[160],*v[6];unsigned long p,n,c,s,a;uint64_t now=bt_clock();pid_t accepted=wireless_accepted_pid(0);
 if(accepted<=1||!now||access(CPMAP_ROOT_PREFIX "/dev/ipod0",F_OK)==0){bt_reset();return;}
 if(!wireless_read(CPMAP_ROOT_PREFIX "/ramdisk/wcp-rg/session.state",text,sizeof(text)))return;
 if(!wireless_lines(text,v,6)||strcmp(v[0],"WCPRG1")||!wireless_number(v[1],&p)||p!=(unsigned long)accepted||
    !wireless_number(v[2],&n)||n>UINT32_MAX||!wireless_number(v[3],&c)||!c||
    !wireless_number(v[4],&s)||!s||s>UINT32_MAX||!wireless_number(v[5],&a)||a!=1){bt_reset();return;}
 pthread_mutex_lock(&bt_lock);
 if(bt_lease.pid!=p||bt_lease.nonce!=n||bt_lease.session!=s||c<bt_lease.counter){
  bt_lease.pid=p;bt_lease.nonce=n;bt_lease.session=s;bt_lease.counter=c;bt_lease.changed=0;bt_lease.primed=0;
 }else if(c>bt_lease.counter){bt_lease.counter=c;bt_lease.changed=now;bt_lease.primed=1;}
 pthread_mutex_unlock(&bt_lock);
}
static void bt_trace(const char *reason){
 FILE *f;struct stat st;unsigned long pid,session;const char *path=CPMAP_ROOT_PREFIX "/ramdisk/cpmap-bt-session.log";
 if(!lstat(path,&st)&&!S_ISREG(st.st_mode))return;
 if(!lstat(path,&st)&&st.st_size>32768){unlink(CPMAP_ROOT_PREFIX "/ramdisk/cpmap-bt-session.log.1");rename(path,CPMAP_ROOT_PREFIX "/ramdisk/cpmap-bt-session.log.1");}
 pthread_mutex_lock(&bt_lock);pid=bt_lease.pid;session=bt_lease.session;pthread_mutex_unlock(&bt_lock);
 f=fopen(path,"a");if(f){fprintf(f,"BTSESSION t_ms=%llu pid=%lu session=%lu event=%s\n",(unsigned long long)bt_clock(),pid,session,reason);fclose(f);}
}
static int bt_private_open(const char *path,int flags,...){
 uintptr_t caller=(uintptr_t)__builtin_return_address(0)-bt_base;mode_t mode=0;int guard=0;
 if(flags&O_CREAT){va_list args;va_start(args,flags);mode=(mode_t)va_arg(args,int);va_end(args);}
 if(flags==O_RDONLY&&path&&bt_live()){
  if((caller==0x1c4c8U||caller==0x22e94U)&&!strcmp(path,"/dev/shmem/wcp_bt_released")){
   guard=1;if(caller==0x1c4c8U){pthread_mutex_lock(&bt_lock);bt_preserved++;pthread_mutex_unlock(&bt_lock);bt_trace("bt-close-preserve-live-wifi");}
  }else if(caller==0x22eccU&&!strcmp(path,"/mnt/persist/btwcp_reconnect_off")){
   guard=1;pthread_mutex_lock(&bt_lock);bt_paused++;pthread_mutex_unlock(&bt_lock);
  }else if(caller==0x23c34U&&!strcmp(path,"/dev/shmem/wcp_cp_session")){
   guard=1;pthread_mutex_lock(&bt_lock);bt_resends++;pthread_mutex_unlock(&bt_lock);
  }
 }
 /* Only these private boolean probes get a readable descriptor. There is no
  * marker creation; all other calls, writes and real user preferences pass. */
 return guard?bt_real_open("/dev/null",O_RDONLY):bt_real_open(path,flags,mode);
}
static ssize_t bt_private_write(int fd,const void *data,size_t size){
 uintptr_t caller=(uintptr_t)__builtin_return_address(0)-bt_base,buf=(uintptr_t)data-bt_base;
 if(caller>=0x13770U&&caller<0x272e4U&&bt_live()&&(buf==0x254fU||buf==0x3346U||buf==0x25a8U)){
  const char *message="[cpmap][bt] accepted live Wi-Fi owner: pause setup BT; preserve AirPlay session\n";
  ssize_t n=bt_real_write(fd,message,strlen(message));return n<0?n:(ssize_t)size;
 }
 return bt_real_write(fd,data,size);
}
static int bt_attach(void){
 void *h,*symbol;uintptr_t base;volatile uintptr_t *open_slot,*write_slot;
 if(!wcp_hash_matches(BT_HASH_PATH,BT_SHA))return 0;
 h=dlopen(BT_LOAD_PATH,RTLD_NOW|RTLD_LOCAL);if(!h)return 0;
 symbol=dlsym(h,"pthread_setname_np");if(!symbol)return 0;base=(uintptr_t)symbol-0x13770U;
 /* Same code contracts as the audited file; refuse another image or an
  * existing competing GOT hook. Data slots are in the DSO's writable segment. */
 if(*(uint32_t *)(base+0x13770U)!=0xe92d4c70U||*(uint32_t *)(base+0x1c4c4U)!=0xeb002badU||
    *(uint32_t *)(base+0x22e90U)!=0xeb00113aU||*(uint32_t *)(base+0x23c30U)!=0xeb000dd2U)return 0;
 bt_real_open=dlsym(RTLD_DEFAULT,"open");bt_real_write=dlsym(RTLD_DEFAULT,"write");
 if(!bt_real_open||!bt_real_write)return 0;
 open_slot=(volatile uintptr_t *)(base+0x47878U);write_slot=(volatile uintptr_t *)(base+0x47860U);
 if(*open_slot!=(uintptr_t)bt_real_open||*write_slot!=(uintptr_t)bt_real_write)return 0;
 bt_base=base;__sync_synchronize();
 *open_slot=(uintptr_t)bt_private_open;*write_slot=(uintptr_t)bt_private_write;__sync_synchronize();
 pthread_mutex_lock(&bt_lock);bt_installed=1;pthread_mutex_unlock(&bt_lock);bt_trace("installed-exact-addon-only");return 1;
}
static void bt_status(void){
 char text[400];FILE *f;int length;uint64_t now=bt_clock();
 pthread_mutex_lock(&bt_lock);
 length=snprintf(text,sizeof(text),"BTSESSION1 t_ms=%llu installed=%d live=%d pid=%lu nonce=%lu session=%lu counter=%lu age_ms=%llu bt_preserved=%lu rc_paused=%lu resend_guarded=%lu\n",(unsigned long long)now,bt_installed,
  bt_installed&&bt_lease.primed&&bt_lease.changed&&now>=bt_lease.changed&&now-bt_lease.changed<1500,
  bt_lease.pid,bt_lease.nonce,bt_lease.session,bt_lease.counter,(unsigned long long)(bt_lease.changed&&now>=bt_lease.changed?now-bt_lease.changed:0),bt_preserved,bt_paused,bt_resends);
 pthread_mutex_unlock(&bt_lock);
 if(length<=0||length>=(int)sizeof(text))return;
 f=fopen(CPMAP_ROOT_PREFIX "/ramdisk/cpmap-bt-session.status.new","w");if(!f)return;
 {int ok=fwrite(text,1,length,f)==(size_t)length;if(fclose(f))ok=0;
 if(ok)rename(CPMAP_ROOT_PREFIX "/ramdisk/cpmap-bt-session.status.new",CPMAP_ROOT_PREFIX "/ramdisk/cpmap-bt-session.status");}
}
static void *bt_watch(void *unused){
 struct timespec delay={0,100000000};unsigned tick=0;int previous=0;(void)unused;
 if(!bt_attach()){bt_trace("not-installed-contract-or-library-mismatch");bt_status();return 0;}
 for(;;){int active;bt_poll();active=bt_live();if(active!=previous){bt_trace(active?"accepted-owner-active":"accepted-owner-ended");previous=active;}if(!(tick++%10))bt_status();nanosleep(&delay,0);}return 0;
}
#ifndef CPMAP_BT_NO_CONSTRUCTOR
__attribute__((constructor))static void bt_start(void){
 const char *enable=getenv("CPMAP_BT_GUARD");pthread_t worker;
 if(enable&&!strcmp(enable,"1")&&!pthread_create(&worker,0,bt_watch,0))pthread_detach(worker);
}
#endif
