/* SPDX-License-Identifier: GPL-3.0-or-later
 * Factory-libc checks: actual decoder, file output, schema and lock on QNX.
 * The runner prefixes pinned JPEG and generated PNG fixtures.
 */
#define _POSIX_C_SOURCE 200809L
#include <sys/stat.h>
#include <sys/wait.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <stdint.h>
static const unsigned char n3_png_fixture[];
static const unsigned char n3_jpeg_fixture[];
static const unsigned n3_png_bytes,n3_jpeg_bytes;
static void put32(unsigned char *p,unsigned v){p[0]=v;p[1]=v>>8;p[2]=v>>16;p[3]=v>>24;}
static int run(void) {
    int status;pid_t child=fork();if(child<0)return 255;
    if(!child){execl("/proc/boot/rgi-observer","rgi-observer","/ramdisk/n3-source",
        "/ramdisk/n3-lock","/ramdisk/n3-out",(char *)0);_exit(255);}
    if(waitpid(child,&status,0)!=child || !WIFEXITED(status))return 255;
    return WEXITSTATUS(status);
}
static int source(const unsigned char *image,unsigned bytes,unsigned kind,int bad) {
    unsigned char b[128]={0};FILE *f=fopen("/ramdisk/n3-source","wb");if(!f)return 1;
    memcpy(b,"N3AR",4);put32(b+4,1);put32(b+8,128);put32(b+12,3);put32(b+16,bad?1:0);
    put32(b+20,bytes);put32(b+24,bytes?kind:0);put32(b+28,2);put32(b+36,1);put32(b+64,1);put32(b+68,1);
    if(fwrite(b,1,128,f)!=128 || (bytes && fwrite(image,1,bytes,f)!=bytes) || fclose(f))return 1;
    return 0;
}
static int files(const unsigned char *image,unsigned bytes) {
    unsigned char b[2048],header[24];FILE *f;size_t n;
    f=fopen("/ramdisk/n3-out/original.bin","rb");if(!f)return 1;
    n=fread(b,1,sizeof(b),f);if(fclose(f) || n!=bytes || memcmp(b,image,bytes))return 1;
    f=fopen("/ramdisk/n3-out/cover.png","rb");if(!f)return 1;
    n=fread(header,1,sizeof(header),f);if(fclose(f) || n!=24 || memcmp(header,"\x89PNG\r\n\x1a\n",8))return 1;
    if(memcmp(header+16,"\0\0\1\0\0\0\1\0",8))return 1;
    return unlink("/ramdisk/n3-out/original.bin") || unlink("/ramdisk/n3-out/cover.png");
}
int main(int argc,char **argv) {
    FILE *f;
    if(argc==2 && !strcmp(argv[1],"ram")) {
        setenv("CACHE_NOP","1",1);execl("/proc/boot/devb-ram","devb-ram","blk","cache=1m,verbose",
            "ram","capacity=32768,nodinit",(char *)0);return 1;
    }
    if(argc==2 && !strcmp(argv[1],"list"))return 0;
    if(mkdir("/ramdisk/n3-out",0700))return 1;
    if(source(n3_png_fixture,n3_png_bytes,1,0) || run() || files(n3_png_fixture,n3_png_bytes))return 1;
    if(source(n3_jpeg_fixture,n3_jpeg_bytes,2,0) || run() || files(n3_jpeg_fixture,n3_jpeg_bytes))return 1;
    if(source(NULL,0,0,0) || run())return 1;
    if(source(NULL,0,0,1) || !run())return 1;
    f=fopen("/ramdisk/n3-source","wb");if(!f || fwrite("short",1,5,f)!=5 || fclose(f) || !run())return 1;
    if(mkdir("/ramdisk/n3-lock",0700) || !run() || rmdir("/ramdisk/n3-lock"))return 1;
    puts("N3_QNX_PASS PNG_JPEG_decode_original_bytes_empty_schema_short_read_lock");return 0;
}
