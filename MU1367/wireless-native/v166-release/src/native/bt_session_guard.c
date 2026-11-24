/* SPDX-License-Identifier: GPL-3.0-or-later
 * Private GOT extension for the exact third-party BT add-on, never OEM BT.
 * No global open/write interposition and no persistent/profile-release flags.
 */
#define _POSIX_C_SOURCE 200112L
#define _QNX_SOURCE 1
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
static int bt_installed,bt_verified,bt_ever_installed,bt_timed_out;
static void *bt_handle;
static void *bt_libc_handle;
static uintptr_t bt_default_open,bt_default_write,bt_libc_open,bt_libc_write;
static unsigned bt_attempts,bt_repairs;
static uintptr_t bt_open_word,bt_write_word,bt_contract_offset,bt_contract_word;
static const char *bt_reason="waiting",*bt_open_kind="unread",*bt_write_kind="unread";
static uint64_t bt_next_attach;
#define BT_ATTACH_WINDOW_MS 60000U
#define BT_ATTACH_INTERVAL_MS 1000U
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
#include "bt_reconnect.h"
static int bt_private_open(const char *path,int flags,...){
 uintptr_t caller=(uintptr_t)__builtin_return_address(0)-bt_base;mode_t mode=0;int guard=0;
 if(flags&O_CREAT){va_list args;va_start(args,flags);mode=(mode_t)va_arg(args,int);va_end(args);}
 if(flags==O_RDONLY&&path&&caller==0x253e8U&&!strcmp(path,"/dev/shmem/btwcp_rc_testaddr")){
  int fd=bt_real_open(path,flags);if(fd<0&&errno==ENOENT)bt_rc_prepare();return fd;
 }
 if(flags==O_RDONLY&&path&&caller==0x22eccU&&!strcmp(path,"/mnt/persist/btwcp_reconnect_off")&&bt_rc_paused())guard=1;
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
 bt_rc_native_event(caller,buf);
 if(caller>=0x13770U&&caller<0x272e4U&&bt_live()&&(buf==0x254fU||buf==0x3346U||buf==0x25a8U)){
  const char *message="[cpmap][bt] accepted live Wi-Fi owner: pause setup BT; preserve AirPlay session\n";
  ssize_t n=bt_real_write(fd,message,strlen(message));return n<0?n:(ssize_t)size;
 }
 return bt_real_write(fd,data,size);
}
/* All slot access stays inside the exact hash-pinned third-party DSO. Its
 * native lazy resolver may finish a call already in flight after our CAS. */
static const char *bt_slot_kind(uintptr_t value,uintptr_t real,uintptr_t ours){
 if(value==ours)return "ours";
 if(value==real)return "libc";
 if(bt_base&&value==bt_base+0x272f0U)return "lazy";
 return "other";
}
static int bt_result(int ok,const char *reason){
 int changed=strcmp(reason,bt_reason)!=0;bt_reason=reason;
 pthread_mutex_lock(&bt_lock);bt_installed=ok;pthread_mutex_unlock(&bt_lock);
 if(!ok)bt_reset();
 if(changed||bt_attempts==1||(!ok&&bt_attempts%10==0)){
  char message[400];snprintf(message,sizeof(message),"%s attempt=%u stage=%s open=%s open_word=%lx write=%s write_word=%lx contract_offset=%lx contract_word=%lx repairs=%u",ok?"installed-exact-addon-only":"attach-refused",bt_attempts,reason,bt_open_kind,(unsigned long)bt_open_word,bt_write_kind,(unsigned long)bt_write_word,(unsigned long)bt_contract_offset,(unsigned long)bt_contract_word,bt_repairs);bt_trace(message);
 }
 return ok;
}
static void bt_symbol_trace(const char *tag,uintptr_t value){
 Dl_info info;char message[384];int found;memset(&info,0,sizeof(info));
 found=value?dladdr((void *)value,&info):0;
 snprintf(message,sizeof(message),"symbol tag=%s address=%lx object=%s name=%s base=%lx offset=%lx",tag,(unsigned long)value,
  found&&info.dli_fname?info.dli_fname:"unknown",found&&info.dli_sname?info.dli_sname:"unknown",
  (unsigned long)(uintptr_t)info.dli_fbase,(unsigned long)(found?value-(uintptr_t)info.dli_fbase:0));bt_trace(message);
}
static int bt_resolve_libc(void){
 /* RTLD_DEFAULT can resolve a btstack/preload wrapper instead of libc. The
  * exact MU1367 libc exports open/write at these independently audited
  * offsets. A named handle bypasses global-scope symbol precedence. */
 if(bt_real_open&&bt_real_write)return 1;
 if(!bt_libc_handle)bt_libc_handle=dlopen("libc.so.3",RTLD_NOW|RTLD_LOCAL);
 if(!bt_libc_handle)return 0;
 bt_default_open=(uintptr_t)dlsym(RTLD_DEFAULT,"open");bt_default_write=(uintptr_t)dlsym(RTLD_DEFAULT,"write");
 bt_libc_open=(uintptr_t)dlsym(bt_libc_handle,"open");bt_libc_write=(uintptr_t)dlsym(bt_libc_handle,"write");
 bt_symbol_trace("default-open",bt_default_open);bt_symbol_trace("default-write",bt_default_write);
 bt_symbol_trace("libc-open",bt_libc_open);bt_symbol_trace("libc-write",bt_libc_write);
 if(bt_libc_open<0x1ae18U||bt_libc_write!=bt_libc_open-0x1ae18U+0x1d1a4U)return 0;
 bt_real_open=(int (*)(const char *,int,...))bt_libc_open;
 bt_real_write=(ssize_t (*)(int,const void *,size_t))bt_libc_write;
 return 1;
}
static int bt_attach(void){
 void *symbol;volatile uintptr_t *open_slot,*write_slot;uintptr_t open_before,write_before,base;
 static const uintptr_t offsets[]={0x13770U,0x1c4c4U,0x22e90U,0x23c30U,0x253e4U,0x25524U,0x25ce4U,0x20988U};
 static const uint32_t words[]={0xe92d4c70U,0xeb002badU,0xeb00113aU,0xeb000dd2U,0xeb0007e5U,0xebfffecfU,0xe79f0000U,0xe08f0000U};unsigned i;int repair=bt_ever_installed;
 bt_attempts++;
 /* Hash once per successful library acquisition, not on every 100 ms lease
  * poll. Failed acquisition retries at most once a second for sixty seconds. */
 if(!bt_verified){
  if(!wcp_hash_matches(BT_HASH_PATH,BT_SHA))return bt_result(0,"library-hash");
  if(!bt_handle)bt_handle=dlopen(BT_LOAD_PATH,RTLD_NOW|RTLD_LOCAL);
  if(!bt_handle)return bt_result(0,"library-load");
  bt_verified=1;
 }
 symbol=dlsym(bt_handle,"pthread_setname_np");if(!symbol)return bt_result(0,"library-symbol");
 base=(uintptr_t)symbol-0x13770U;
 if(!base||(base&0xfffU)||base>UINTPTR_MAX-0x4787cU||(bt_base&&bt_base!=base))return bt_result(0,"library-base");
 if(!bt_base)bt_base=base;
 for(i=0;i<sizeof(words)/sizeof(words[0]);i++){
  bt_contract_offset=offsets[i];bt_contract_word=*(uint32_t *)(bt_base+offsets[i]);
  if(bt_contract_word!=words[i])return bt_result(0,"code-contract");
 }
 bt_contract_offset=bt_contract_word=0;
 if(!bt_resolve_libc())return bt_result(0,"libc-handle-or-contract");
 open_slot=(volatile uintptr_t *)(bt_base+0x47878U);write_slot=(volatile uintptr_t *)(bt_base+0x47860U);
 open_before=bt_open_word=*open_slot;write_before=bt_write_word=*write_slot;
 bt_open_kind=bt_slot_kind(open_before,(uintptr_t)bt_real_open,(uintptr_t)bt_private_open);
 bt_write_kind=bt_slot_kind(write_before,(uintptr_t)bt_real_write,(uintptr_t)bt_private_write);
 if(bt_attempts==1||(!strcmp(bt_write_kind,"other")&&bt_attempts%10==0)){bt_symbol_trace("slot-open",open_before);bt_symbol_trace("slot-write",write_before);}
 /* Validate BOTH before touching either. Never displace an unknown hook. */
 if(!strcmp(bt_open_kind,"other"))return bt_result(0,"open-slot-conflict");
 if(!strcmp(bt_write_kind,"other"))return bt_result(0,"write-slot-conflict");
 __sync_synchronize();
#ifdef CPMAP_BT_BEFORE_CAS
 CPMAP_BT_BEFORE_CAS(open_slot,write_slot);
#endif
 if(!__sync_bool_compare_and_swap(open_slot,open_before,(uintptr_t)bt_private_open))return bt_result(0,"open-slot-race");
 if(!__sync_bool_compare_and_swap(write_slot,write_before,(uintptr_t)bt_private_write)){
  /* Roll back only the exact pointer we installed; preserve an in-flight
   * native resolution or a different hook that has since changed the slot. */
  if(open_before!=(uintptr_t)bt_private_open)__sync_bool_compare_and_swap(open_slot,(uintptr_t)bt_private_open,open_before);
  return bt_result(0,"write-slot-race");
 }
 __sync_synchronize();
 if(*open_slot!=(uintptr_t)bt_private_open||*write_slot!=(uintptr_t)bt_private_write)return bt_result(0,"post-bind-race");
 if(repair&&(open_before!=(uintptr_t)bt_private_open||write_before!=(uintptr_t)bt_private_write))bt_repairs++;
 bt_ever_installed=1;return bt_result(1,repair?"ready-revalidated":"ready");
}
static int bt_hooks_intact(void){
 return bt_base&&*(volatile uintptr_t *)(bt_base+0x47878U)==(uintptr_t)bt_private_open&&
  *(volatile uintptr_t *)(bt_base+0x47860U)==(uintptr_t)bt_private_write;
}
/* A deterministic worker step also lets the native fixture exercise delayed
 * acquisition and deadline handling without a fake sixty-second sleep. */
static void bt_service_step(uint64_t now,uint64_t started){
 if(bt_installed&&bt_hooks_intact())return;
 if(bt_installed){bt_result(0,"hook-changed");bt_next_attach=0;}
 if(bt_timed_out)return;
 if(!bt_ever_installed&&(now<started||now-started>=BT_ATTACH_WINDOW_MS)){
  bt_timed_out=1;bt_result(0,"attach-timeout");bt_trace("attach-window-ended");return;
 }
 if(bt_next_attach&&now<bt_next_attach)return;
 bt_next_attach=now+BT_ATTACH_INTERVAL_MS;
 bt_attach();
}
static void bt_status(void){
 char text[768];FILE *f;int length;uint64_t now=bt_clock();
 pthread_mutex_lock(&bt_lock);
 length=snprintf(text,sizeof(text),"BTSESSION1 t_ms=%llu installed=%d live=%d pid=%lu nonce=%lu session=%lu counter=%lu age_ms=%llu bt_preserved=%lu rc_paused=%lu resend_guarded=%lu attempts=%u repairs=%u timed_out=%d stage=%s open=%s write=%s default_open=%lx default_write=%lx libc_open=%lx libc_write=%lx rc_policy=%s rc_trusted=%d rc_selected=%d rc_preferred=%lu rc_filtered=%lu rc_failed=%lu wifi_windows=%lu\n",(unsigned long long)now,bt_installed,
  bt_installed&&bt_lease.primed&&bt_lease.changed&&now>=bt_lease.changed&&now-bt_lease.changed<1500,
  bt_lease.pid,bt_lease.nonce,bt_lease.session,bt_lease.counter,(unsigned long long)(bt_lease.changed&&now>=bt_lease.changed?now-bt_lease.changed:0),bt_preserved,bt_paused,bt_resends,bt_attempts,bt_repairs,bt_timed_out,bt_reason,bt_base&&bt_real_open?bt_slot_kind(*(volatile uintptr_t *)(bt_base+0x47878U),(uintptr_t)bt_real_open,(uintptr_t)bt_private_open):"unread",bt_base&&bt_real_write?bt_slot_kind(*(volatile uintptr_t *)(bt_base+0x47860U),(uintptr_t)bt_real_write,(uintptr_t)bt_private_write):"unread",(unsigned long)bt_default_open,(unsigned long)bt_default_write,(unsigned long)bt_libc_open,(unsigned long)bt_libc_write,bt_rc_reason,bt_rc.count,bt_rc_selected,bt_rc_preferred,bt_rc_filtered,bt_rc_failures,bt_rc_wifi_windows);
 pthread_mutex_unlock(&bt_lock);
 if(length<=0||length>=(int)sizeof(text))return;
 f=fopen(CPMAP_ROOT_PREFIX "/ramdisk/cpmap-bt-session.status.new","w");if(!f)return;
 {int ok=fwrite(text,1,length,f)==(size_t)length;if(fclose(f))ok=0;
 if(ok)rename(CPMAP_ROOT_PREFIX "/ramdisk/cpmap-bt-session.status.new",CPMAP_ROOT_PREFIX "/ramdisk/cpmap-bt-session.status");}
}
static void *bt_watch(void *unused){
 struct timespec delay={0,100000000};unsigned tick=0;int previous=0;uint64_t started=bt_clock();bt_rc_started=started;(void)unused;
 for(;;){int active;bt_service_step(bt_clock(),started);bt_poll();bt_rc_poll();active=bt_live();bt_rc_session(active);if(active!=previous){bt_trace(active?"accepted-owner-active":"accepted-owner-ended");previous=active;}if(!(tick++%10))bt_status();nanosleep(&delay,0);}return 0;
}
#ifndef CPMAP_BT_NO_CONSTRUCTOR
__attribute__((constructor))static void bt_start(void){
 const char *enable=getenv("CPMAP_BT_GUARD");pthread_t worker;
 if(enable&&!strcmp(enable,"1")&&!pthread_create(&worker,0,bt_watch,0))pthread_detach(worker);
}
#endif
