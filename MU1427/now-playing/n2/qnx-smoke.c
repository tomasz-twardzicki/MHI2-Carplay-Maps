/* SPDX-License-Identifier: GPL-3.0-or-later. Factory-libc N2 helper check. */
#define _POSIX_C_SOURCE 200809L
#include <sys/stat.h>
#include <sys/wait.h>
#include <dirent.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
static int run(void) {
    int status;pid_t child=fork();
    if (child<0) return 255;
    if (!child) { execl("/proc/boot/rgi-observer","rgi-observer","/ramdisk/n2-source",
                       "/ramdisk/n2-lock",(char *)0);_exit(255); }
    if (waitpid(child,&status,0)!=child || !WIFEXITED(status)) return 255;
    return WEXITSTATUS(status);
}
int main(int argc,char **argv) {
    unsigned char b[128]={0};FILE *f;
    if (argc==2 && !strcmp(argv[1],"ram")) {
        setenv("CACHE_NOP","1",1);
        execl("/proc/boot/devb-ram","devb-ram","blk","cache=1m,verbose",
              "ram","capacity=32768,nodinit",(char *)0);return 1;
    }
    if (argc==2 && !strcmp(argv[1],"list")) return 0;
    memcpy(b,"N2AO",4);b[4]=1;b[8]=128;b[20]=3;b[24]=3;b[32]=2;b[36]=1;b[40]=1;
    f=fopen("/ramdisk/n2-source","wb");if (!f) return 1;
    if (fwrite(b,1,128,f)!=128 || fclose(f)) return 1;
    if (run()) return 1;
    b[12]=1;f=fopen("/ramdisk/n2-source","wb");if (!f) return 1;
    if (fwrite(b,1,128,f)!=128 || fclose(f)) return 1;
    if (!run()) return 1;
    f=fopen("/ramdisk/n2-source","wb");if (!f) return 1;
    if (fwrite(b,1,7,f)!=7 || fclose(f)) return 1;
    if (!run()) return 1;
    if (mkdir("/ramdisk/n2-lock",0700)) return 1;
    if (!run() || rmdir("/ramdisk/n2-lock")) return 1;
    puts("N2_QNX_PASS valid_schema_short_read_and_lock");return 0;
}
