/* SPDX-License-Identifier: GPL-3.0-or-later. Exact-addon RC policy. */
#ifndef CPMAP_BT_RECONNECT_H
#define CPMAP_BT_RECONNECT_H
#define BT_RC_MAX 8
#define BT_RC_STARTUP_MS 25000U
#define BT_RC_WIFI_MS 15000U
#define BT_RC_FAILED_MS 30000U
struct bt_rc_policy {unsigned long epoch,counter;uint64_t changed;int primed,seen,allow,wired,count;unsigned char peer[BT_RC_MAX][6],last[6];int has_last;};
static struct bt_rc_policy bt_rc;
static uint64_t bt_rc_started,bt_rc_wifi_until;
static int bt_rc_was_live,bt_rc_selected=-1,bt_rc_attempt_valid;
static unsigned char bt_rc_attempt[6],bt_rc_failed[BT_RC_MAX][6];
static uint64_t bt_rc_failed_until[BT_RC_MAX];
static unsigned long bt_rc_preferred,bt_rc_filtered,bt_rc_failures,bt_rc_wifi_windows;
static const char *bt_rc_reason="startup";
/* HMI publishes conventional MAC order. The pinned native formatter at
 * 0x24a10 emits byte 5 first; the private bank stores BD_ADDR little endian. */
static int bt_rc_address(const char *text,unsigned char out[6]){unsigned i;for(i=0;i<12;i++){unsigned c=(unsigned char)text[i],v;if(c>='0'&&c<='9')v=c-'0';else if(c>='A'&&c<='F')v=c-'A'+10;else return 0;if(i&1)out[5-i/2]|=v;else out[5-i/2]=(unsigned char)(v<<4);}return text[12]==0;}
static void bt_rc_poll(void){
 char text[512],*v[15];unsigned long epoch,counter,permit,wired,count;unsigned i,lines=0;struct bt_rc_policy next;uint64_t now=bt_clock();
 if(!wireless_read(CPMAP_ROOT_PREFIX "/ramdisk/cpmap-bt-policy.state",text,sizeof(text)))return;
 for(i=0;text[i];i++)if(text[i]=='\n')lines++;
 if(lines<7||lines>15||!wireless_lines(text,v,lines)||strcmp(v[0],"BTRC1")||!wireless_number(v[1],&epoch)||!wireless_number(v[2],&counter)||!counter||!wireless_number(v[3],&permit)||permit>1||!wireless_number(v[4],&wired)||wired>1||!wireless_number(v[6],&count)||count>BT_RC_MAX||lines!=7+count)return;
 memset(&next,0,sizeof(next));next.epoch=epoch;next.counter=counter;next.allow=permit;next.wired=wired;next.count=(int)count;
 if(strcmp(v[5],"-")){if(!bt_rc_address(v[5],next.last))return;next.has_last=1;}
 for(i=0;i<count;i++)if(!bt_rc_address(v[7+i],next.peer[i]))return;
 pthread_mutex_lock(&bt_lock);
 next.seen=1;
 if(bt_rc.epoch==epoch&&bt_rc.seen&&counter>=bt_rc.counter){next.primed=bt_rc.primed;next.changed=bt_rc.changed;if(counter>bt_rc.counter){next.primed=1;next.changed=now;}}
 memcpy(&bt_rc,&next,sizeof(bt_rc));
 pthread_mutex_unlock(&bt_lock);
}
static int bt_rc_fresh_locked(uint64_t now){return bt_rc.seen&&bt_rc.primed&&bt_rc.changed&&now>=bt_rc.changed&&now-bt_rc.changed<2500;}
static int bt_rc_trusted_locked(const unsigned char *peer){int i;for(i=0;i<bt_rc.count;i++)if(!memcmp(peer,bt_rc.peer[i],6))return 1;return 0;}
static int bt_rc_cooling_locked(const unsigned char *peer,uint64_t now){int i;for(i=0;i<BT_RC_MAX;i++)if(bt_rc_failed_until[i]>now&&!memcmp(peer,bt_rc_failed[i],6))return 1;return 0;}
/* Called on the native RC thread. Only its cursor changes; pairing banks,
 * persistent SQLite and the earlier OEM-held ACL scan remain untouched. */
static int bt_rc_choice_locked(uint64_t now){
 int count,index,choice=-1;const unsigned char *bank;
 if(!bt_base)return -1;count=*(volatile int *)(bt_base+0x49124U);if(count<1||count>BT_RC_MAX)return -1;
 bank=(const unsigned char *)(bt_base+0x5bf5aU);
 for(index=0;index<count;index++)if(bt_rc_trusted_locked(bank+index*6)&&!bt_rc_cooling_locked(bank+index*6,now)){
  if(choice<0)choice=index;if(bt_rc.has_last&&!memcmp(bank+index*6,bt_rc.last,6))return index;
 }
 return choice;
}
static int bt_rc_paused(void){
 uint64_t now=bt_clock();int paused=0;const char *reason="native-fallback";
 pthread_mutex_lock(&bt_lock);
 if(bt_rc.seen){
  if(!bt_rc_fresh_locked(now)){paused=1;reason="policy-stale-keep";}
  else if(!bt_rc.allow||bt_rc.wired){paused=1;reason="manual-wired-or-ignition-keep";}
  else if(bt_rc_wifi_until>now){paused=1;reason="wifi-control-first";}
  else if(bt_rc_choice_locked(now)<0){paused=1;reason="no-trusted-ready-candidate";}
  else reason="trusted-bt-fallback";
 }else if(bt_rc_started&&now>=bt_rc_started&&now-bt_rc_started<BT_RC_STARTUP_MS){paused=1;reason="wait-oem-trust";}
 bt_rc_reason=reason;pthread_mutex_unlock(&bt_lock);return paused;
}
static void bt_rc_prepare(void){
 uint64_t now=bt_clock();int choice,count;
 pthread_mutex_lock(&bt_lock);
 if(bt_rc_fresh_locked(now)&&bt_rc.allow&&!bt_rc.wired&&bt_rc_wifi_until<=now){
  count=*(volatile int *)(bt_base+0x49124U);choice=bt_rc_choice_locked(now);
  if(choice>=0&&choice<count){
   int before=*(volatile int *)(bt_base+0x49128U);*(volatile int *)(bt_base+0x49128U)=choice;bt_rc_selected=choice;
   if(before!=choice)bt_rc_filtered++;if(bt_rc.has_last&&!memcmp((void *)(bt_base+0x5bf5aU+choice*6),bt_rc.last,6))bt_rc_preferred++;
  }
 }
 pthread_mutex_unlock(&bt_lock);
}
static void bt_rc_native_event(uintptr_t caller,uintptr_t buffer){
 uint64_t now;int index,count,i,slot=0;
 if(!((caller==0x25ce0U&&buffer==0x1ff0U)||(caller==0x20760U&&buffer==0x1b96U)))return;
 now=bt_clock();
 pthread_mutex_lock(&bt_lock);
 if(caller==0x25ce0U&&buffer==0x1ff0U&&bt_rc_fresh_locked(now)){
  count=*(volatile int *)(bt_base+0x49124U);index=*(volatile int *)(bt_base+0x49128U);
  if(count>0&&count<=BT_RC_MAX&&index>=0&&index<count){memcpy(bt_rc_attempt,(void *)(bt_base+0x5bf5aU+index*6),6);bt_rc_attempt_valid=1;}
 }else if(caller==0x20760U&&buffer==0x1b96U&&bt_rc_attempt_valid){
  for(i=0;i<BT_RC_MAX;i++)if(!memcmp(bt_rc_attempt,bt_rc_failed[i],6)){slot=i;break;}else if(bt_rc_failed_until[i]<bt_rc_failed_until[slot])slot=i;
  memcpy(bt_rc_failed[slot],bt_rc_attempt,6);bt_rc_failed_until[slot]=now+BT_RC_FAILED_MS;bt_rc_attempt_valid=0;bt_rc_failures++;
 }
 pthread_mutex_unlock(&bt_lock);
}
static void bt_rc_session(int live){
 uint64_t now=bt_clock();pthread_mutex_lock(&bt_lock);
 if(live){bt_rc_wifi_until=0;bt_rc_attempt_valid=0;memset(bt_rc_failed_until,0,sizeof(bt_rc_failed_until));}
 else if(bt_rc_was_live&&bt_rc_fresh_locked(now)&&bt_rc.allow&&!bt_rc.wired){bt_rc_wifi_until=now+BT_RC_WIFI_MS;bt_rc_wifi_windows++;}
 bt_rc_was_live=live;pthread_mutex_unlock(&bt_lock);
}
#endif
