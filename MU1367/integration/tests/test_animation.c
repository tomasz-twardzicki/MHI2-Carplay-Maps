/* v1.5.3-e: the CarPlay bridge's C reader on the files TestAnimation.java wrote. SPDX-License-Identifier: GPL-3.0-or-later */
#include <errno.h>
#include <stdio.h>
#include <sys/stat.h>
#include "cpmap_intro_policy.h"
static int fail(const char *m){printf("ANIMATION_C_FAIL %s\n",m);return 1;}
int main(int argc,char **argv)
{
    char path[512];int mode=-1,m;
    if(argc!=2)return fail("usage");
    snprintf(path,sizeof(path),"%s/default",argv[1]);
    if(cpmap_animation_read(path,&mode)!=0)return fail("default: no saved state");
    for(m=0;m<3;++m){
        snprintf(path,sizeof(path),"%s/m%d",argv[1],m);mode=-1;
        if(cpmap_animation_read(path,&mode)!=1||mode!=m)return fail("saved mode");
    }
    snprintf(path,sizeof(path),"%s/rot",argv[1]);mode=-1;
    if(cpmap_animation_read(path,&mode)!=1||mode!=0)return fail("rotated: state");
    snprintf(path,sizeof(path),"%s/rot/animation.previous",argv[1]);mode=-1;
    if(cpmap_animation_file(path,&mode)!=1||mode!=2)return fail("rotated: previous");
    /* Bridge mapping: 0 every connection, 1 once per boot, 2 off. */
    if(CPMAP_INTRO_EVERY_CONNECT!=1||CPMAP_INTRO_ONCE_PER_BOOT!=2||CPMAP_INTRO_OFF!=0)return fail("enum");
    printf("ANIMATION_C_PASS\n");return 0;
}
