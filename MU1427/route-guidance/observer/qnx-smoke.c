/* SPDX-License-Identifier: GPL-3.0-or-later
 * Execute the production reader on QNX with a synthetic snapshot file.
 */
#define _POSIX_C_SOURCE 200809L
#include <stdio.h>
#include <stdlib.h>
#include <dirent.h>
#include <string.h>
#include <unistd.h>
#include <sys/wait.h>
static int run_child(char **args) {
    int status; pid_t child=fork();
    if (child<0) return 255;
    if (!child) { execv(args[0],args); _exit(255); }
    if (waitpid(child,&status,0)!=child || !WIFEXITED(status)) return 255;
    return WEXITSTATUS(status);
}
int main(int argc, char **argv) {
    char *args[]={"/proc/boot/rgi-observer","run","/proc/boot/snapshot.bin","/ramdisk/rgi-test","6",0};
    char *stop[]={"/proc/boot/rgi-observer","stop","/ramdisk/rgi-daemon",0};
    char status[256]; FILE *f; int rc;
    if (argc==2 && !strcmp(argv[1],"list")) {
        DIR *d=opendir("/dev"); struct dirent *entry;
        if (!d) { perror("QEMU /dev"); return 1; }
        while ((entry=readdir(d))) printf("QEMU_DEV %s\n",entry->d_name);
        closedir(d); return 0;
    }
    if (argc==2 && !strcmp(argv[1],"ram")) {
        /* QEMU's bare boot image has no board cache helper/confstr setup.
         * Disable hardware cache operations only in this RAM-disk test. */
        setenv("CACHE_NOP","1",1);
        execl("/proc/boot/devb-ram","devb-ram","blk","cache=1m,verbose",
              "ram","capacity=32768,nodinit",(char *)0);
        perror("QEMU RAM disk"); return 1;
    }
    rc=run_child(args);
    f=fopen("/ramdisk/rgi-test/status.txt","r");
    if (!f || !fgets(status,sizeof(status),f)) { perror("C4_QNX_FAIL status"); return 1; }
    fclose(f); printf("%s",status);
    if (rc) {
        unsigned char h[48];
        f=fopen("/ramdisk/rgi-test/events.rgj","rb");
        if (f) {
            if (fread(h,1,sizeof(h),f)==sizeof(h))
                printf("C4_QNX_JOURNAL first_kind=%u first_detail=%u elapsed_low16=%u\n",
                       (unsigned)h[16],(unsigned)h[28],(unsigned)h[20]+((unsigned)h[21]<<8));
            fclose(f);
        }
        printf("C4_QNX_FAIL reader_rc=%d\n",rc); return 1;
    }
    if (!strstr(status,"status=ended") || !strstr(status,"invalid=0 ") ||
        !strstr(status,"sequence=2 ") || strstr(status,"polls=0 ") ||
        strstr(status,"polls=1 ")) { puts("C4_QNX_FAIL counters"); return 1; }
    args[1]="start"; args[3]="/ramdisk/rgi-daemon"; args[4]="10";
    if (run_child(args) || run_child(stop)) { puts("C4_QNX_FAIL daemon"); return 1; }
    f=fopen("/ramdisk/rgi-daemon/status.txt","r");
    if (!f || !fgets(status,sizeof(status),f)) { puts("C4_QNX_FAIL daemon_status"); return 1; }
    fclose(f); printf("%s",status);
    if (!strstr(status,"status=ended") || !strstr(status,"reason=1")) {
        puts("C4_QNX_FAIL daemon_stop"); return 1;
    }
    puts("C4_QNX_PASS foreground_and_daemon"); return 0;
}
