/* Isolated test process only. No fault hooks are compiled into the payload. */
#define _POSIX_C_SOURCE 200809L
#include <sys/stat.h>
#include <sys/wait.h>
#include <unistd.h>
#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
static int triggered(void) {
    const char *file=getenv("READER_TEST_TRIGGER");
    return file && !access(file,F_OK);
}
static int mode(const char *name) {
    const char *value=getenv("READER_TEST_MODE"); return value && !strcmp(value,name);
}
static void consume(void) { const char *file=getenv("READER_TEST_TRIGGER"); if(file)unlink(file); }
ssize_t fault_read(int fd,void *b,size_t n) {
    struct stat st;
    if(!fstat(fd,&st) && S_ISREG(st.st_mode) && triggered()) {
        if(mode("eof")){consume();_exit(42);}
        if(mode("block") || mode("always-block")) {
            struct timespec delay={10,0};
            if(mode("block"))consume();
            nanosleep(&delay,0);
        }
        if(mode("enomem")){consume();errno=ENOMEM;return -1;}
    }
    return read(fd,b,n);
}
ssize_t fault_write(int fd,const void *b,size_t n) {
    static unsigned chunks;
    if(n==512 && triggered() && mode("partial") && ++chunks==3){consume();_exit(43);}
    return write(fd,b,n);
}
pid_t fault_waitpid(pid_t pid,int *status,int flags) {
    if(mode("unreaped") && triggered())return 0;
    return waitpid(pid,status,flags);
}
int fault_rename(const char *old,const char *next) {
    if(mode("output") && triggered() && !strcmp(next,"latest.bin")){errno=ENOSPC;return -1;}
    return rename(old,next);
}
FILE *fault_fopen(const char *name,const char *flags) {
    if(mode("diagnostic-output") && !strcmp(name,"reader-failure-first.tmp")){errno=ENOSPC;return NULL;}
    return fopen(name,flags);
}
