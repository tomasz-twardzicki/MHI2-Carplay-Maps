/* Native ARM/QNX recovery probe; synthetic source and test-only fault binary. */
#define _POSIX_C_SOURCE 200809L
#include <sys/stat.h>
#include <sys/wait.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>
int baseline_main(int argc,char **argv);
static void require(int ok,const char *why){if(!ok){printf("READER_QNX_FAIL=%s\n",why);fflush(stdout);exit(1);}}
static void pause_ms(unsigned n){struct timespec t={n/1000,(n%1000)*1000000u};nanosleep(&t,0);}
static uint32_t u32(const unsigned char *b){return b[0]|(uint32_t)b[1]<<8|(uint32_t)b[2]<<16|(uint32_t)b[3]<<24;}
static int text(const char *path,char *b,size_t n){FILE *f=fopen(path,"r");int ok;if(!f)return 0;ok=fgets(b,n,f)!=NULL;fclose(f);return ok;}
static void wait_text(const char *path,const char *needle){unsigned i;char b[1024];for(i=0;i<100;++i){if(text(path,b,sizeof(b))&&strstr(b,needle))return;pause_ms(100);}require(0,needle);}
static void mailbox(unsigned char *b){FILE *f=fopen("/ramdisk/recover/latest.bin","rb");require(f&&fread(b,1,32,f)==32,"mailbox");fclose(f);require(!memcmp(b,"RGM1",4),"magic");}
static void trigger(void){FILE *f=fopen("/ramdisk/trigger","w");require(f!=NULL,"trigger");fclose(f);}
int main(int argc,char **argv){
    pid_t p;int status;FILE *f;unsigned char before[32],after[32];char first[1024],again[1024];struct stat st;
    if(argc>1)return baseline_main(argc,argv);
    require(baseline_main(argc,argv)==0,"baseline");
    setenv("READER_TEST_MODE","block",1);setenv("READER_TEST_TRIGGER","/ramdisk/trigger",1);
    p=fork();require(p>=0,"fork");
    if(!p){execl("/proc/boot/fault-reader","fault-reader","serve","/proc/boot/snapshot.bin","/ramdisk/recover",(char *)0);_exit(127);}
    wait_text("/ramdisk/recover/status.txt","valid=");pause_ms(500);mailbox(before);require(u32(before+16)==1,"initial snapshot");
    trigger();wait_text("/ramdisk/recover/reader-failure-first.txt","cause=timeout");
    require(text("/ramdisk/recover/reader-failure-first.txt",first,sizeof(first)),"first failure");
    require(strstr(first,"phase=2 ")!=NULL,"read phase");require(strstr(first,"child_reaped=1 ")!=NULL,"reaped");
    require(strstr(first,"recovery_allowed=1")!=NULL,"recovery allowed");
    wait_text("/ramdisk/recover/status.txt","restarts=1 ");pause_ms(500);mailbox(after);
    require(u32(after+16)==1,"recovered baseline");require(memcmp(before+24,after+24,8)!=0,"new nonce");
    require(!stat("/ramdisk/recover/reader-failure-first.txt",&st)&&st.st_size<1024,"bounded failure");
    trigger();wait_text("/ramdisk/recover/status.txt","status=recovering");
    require(text("/ramdisk/recover/reader-failure-first.txt",again,sizeof(again))&&!strcmp(first,again),"first retained");
    require(!kill(p,SIGTERM),"stop");require(waitpid(p,&status,0)==p&&WIFEXITED(status)&&WEXITSTATUS(status)==0,"stop status");
    mailbox(after);require(u32(after+16)==5&&u32(after+20)==1,"END stop");
    f=fopen("/ramdisk/recover/status.txt","r");require(f!=NULL,"ended status");fclose(f);
    puts("READER_RECOVERY_QNX_PASS normal_and_daemon=1 timeout=1 reaped=1 new_nonce=1 first_retained=1 stop_backoff=1");fflush(stdout);return 0;
}
