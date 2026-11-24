/* SPDX-License-Identifier: GPL-3.0-or-later
 * The pinned disableBluetooth helper logs after closing its request file.
 * Callback captures only context/sequence/time. Publisher owns all file I/O.
 */
static uintptr_t bt_request_context;
static uint64_t bt_request_at;
static unsigned bt_request_sequence,bt_request_bound;
static void bt_request_observed(const uintptr_t *r){
 if(r[1]!=0x1d011U||r[2]!=0x1a31aU||r[3]!=0x1a264U)return;
 pthread_mutex_lock(&guard);
 bt_request_context=*(uintptr_t *)0x112ad4;bt_request_at=tap_now();bt_request_bound=0;
 if(!++bt_request_sequence)bt_request_sequence=1;
 pthread_mutex_unlock(&guard);
}
static int bt_request_address(char *out){
 char b[64];FILE *f;size_t n,i;unsigned at=0;
 f=fopen("/dev/shmem/wcp_bt_disable","r");if(!f)return 0;n=fread(b,1,sizeof(b),f);if(ferror(f)){fclose(f);return 0;}fclose(f);
 if(!n||n==sizeof(b))return 0;
 for(i=0;i<n;i++){unsigned c=(unsigned char)b[i];if(c==':'||c=='-'||c=='\r'||c=='\n')continue;
  if(at==12)return 0;if(c>='0'&&c<='9')out[at++]=(char)c;else if(c>='a'&&c<='f')out[at++]=(char)(c-32);else if(c>='A'&&c<='F')out[at++]=(char)c;else return 0;}
 out[at]=0;return at==12;
}
static void bt_request_publish(int accepted,uint64_t nonce,unsigned session,int was_accepted){
 char peer[13],text[256];unsigned seq,bound;int valid=0;uint64_t when,now=tap_now();uintptr_t context;static unsigned counter;
 pthread_mutex_lock(&guard);
 context=bt_request_context;seq=bt_request_sequence;when=bt_request_at;
 if((was_accepted&&!accepted)||context!=*(uintptr_t *)0x112ad4){bt_request_at=when=0;bt_request_bound=0;}
 if(accepted&&context&&when&&now>=when&&now-when<=5000000&&!bt_request_bound)bt_request_bound=session;
 bound=bt_request_bound;pthread_mutex_unlock(&guard);
 if(accepted&&session&&bound==session&&when&&context==*(uintptr_t *)0x112ad4)valid=bt_request_address(peer);
 if(!valid){peer[0]='-';peer[1]=0;}
 if(!++counter)counter=1;
 {int n=snprintf(text,sizeof(text),"WCPBTREQ1\n%ld\n%lu\n%u\n%u\n%u\n%d\n%s\n",(long)getpid(),(unsigned long)(uint32_t)nonce,session,seq,counter,valid,peer);
  if(n>0&&n<(int)sizeof(text))atomic_file("bt-request.state",text,(size_t)n);}
 {int n=snprintf(text,sizeof(text),"WCP_BT_REQUEST pid=%ld session=%u sequence=%u bound=%u valid=%d context_match=%d\n",(long)getpid(),session,seq,bound,valid,context&&context==*(uintptr_t *)0x112ad4);
  if(n>0&&n<(int)sizeof(text))atomic_file("bt-request.status",text,(size_t)n);}
}
