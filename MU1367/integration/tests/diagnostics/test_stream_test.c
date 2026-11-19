/* v1.5.4: the core's stream-test override (display_settings.h) on the host.
 * cc -I SRC/runtime/card-core/source test_stream_test.c && ./a.out DIR   SPDX-License-Identifier: GPL-3.0-or-later */
#include "display_settings.h"
static int fails,checks;
static void check(int c,const char *m){checks++;printf("%s %s\n",c?"ok    ":"FAILED",m);if(!c)fails++;}
static void put(const char *dir,const char *name,const char *text){char p[600];FILE *f;snprintf(p,sizeof p,"%s/%s",dir,name);
 if(!text){remove(p);return;}f=fopen(p,"wb");fputs(text,f);fclose(f);}
int main(int argc,char **argv){
 const char *d=argc>1?argv[1]:".";setenv("CPVC_DISPLAY_STATE_DIR",d,1);
 put(d,"stream-test.conf",NULL);put(d,"display.state",NULL);put(d,"display.previous",NULL);
 cpvc_display_refresh();check(cpvc_display_fps()==40&&cpvc_display_idr()==5&&cpvc_stream_test_status()==0,"no files: 40 fps, IDR 5, MU UI");
 put(d,"stream-test.conf","fps=27\nidr=11\n");
 check(cpvc_display_idr_refreshed()==11&&cpvc_display_fps()==27&&cpvc_stream_test_status()==1,"stream-test.conf 27/11 wins");
 put(d,"stream-test.conf","fps=20\nidr=5\n");cpvc_display_refresh();check(cpvc_display_fps()==20&&cpvc_display_idr()==5,"lower bounds 20/5");
 put(d,"stream-test.conf","fps=40\nidr=15\n");cpvc_display_refresh();check(cpvc_display_fps()==40&&cpvc_display_idr()==15,"upper bounds 40/15");
 {static const char *bad[]={"fps=19\nidr=5\n","fps=41\nidr=5\n","fps=30\nidr=4\n","fps=30\nidr=16\n","fps=30\nidr=5","fps=30\nidr=5\n\n","fps=030\nidr=5\n","idr=5\nfps=30\n","fps=30 \nidr=5\n","fps=+30\nidr=5\n",""};
  unsigned i;int ok=1;for(i=0;i<sizeof bad/sizeof *bad;i++){put(d,"stream-test.conf",bad[i]);cpvc_display_refresh();
   if(cpvc_stream_test_status()!=-1||cpvc_display_fps()!=40||cpvc_display_idr()!=5){ok=0;printf("  bad input accepted: [%s]\n",bad[i]);}}
  check(ok,"out of range or non-canonical files are ignored (status -1, MU UI values)");}
 put(d,"stream-test.conf",NULL);cpvc_display_refresh();check(cpvc_stream_test_status()==0&&cpvc_display_fps()==40,"reset: back to the MU UI choice");
 printf("STREAM_TEST_HOST checks=%d failed=%d\n",checks,fails);return fails!=0;
}
