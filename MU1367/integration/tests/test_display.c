/* Included after the actual CF fixture/production source. GPL-3.0-or-later. */
static void write_display(const char *root,int stream,int layout,unsigned generation){
 char path[512],body[128];FILE *f;int n;
 snprintf(path,sizeof(path),"%s/display.state",root);
 n=snprintf(body,sizeof(body),"format=1\nstream=%d\nlayout=%d\ngeneration=%u\n",stream,layout,generation);
 f=fopen(path,"wb");assert(f);assert(fwrite(body,1,(size_t)n,f)==(size_t)n);
 fprintf(f,"crc32=%x\n",(unsigned)cpvc_display_crc((const unsigned char *)body,(size_t)n));assert(!fclose(f));
}
int main(int argc,char **argv){
 static const int areas[4][4]={{200,96,400,364},{160,96,480,364},{220,96,360,348},{220,65,360,348}};
 static const int fps[4]={30,40,30,40},idr[4]={20,5,5,20};
 char root[]="/tmp/mu1367-display-XXXXXX",path[512];int s,l,checks=0;Obj *d,*v,*safe;FILE *f;
 if(argc==2){struct cpvc_display_settings state;int rc=cpvc_display_read(argv[1],&state);if(rc<0)return 2;printf("%d,%d,%llu\n",state.stream,state.layout,(unsigned long long)state.generation);return 0;}
 assert(mkdtemp(root));assert(!setenv("CPVC_DISPLAY_STATE_DIR",root,1));assert(!setenv("CPMAP_CARD_STATE_DIR",root,1));assert(!setenv("CARPLAY_ALTSCREEN_LOG","/dev/null",1));
 for(s=0;s<4;s++)for(l=0;l<4;l++){
  write_display(root,s,l,(unsigned)(s*4+l+1));d=create_alt_display();assert(d);
  assert(number(d,"maxFPS")==fps[s]);assert(cpvc_display_idr()==idr[s]);
  assert(number(d,"widthPixels")==800&&number(d,"heightPixels")==480);
  v=lookup(d,"viewAreas");assert(v->count==1);safe=lookup(v->items[0],"safeArea");
  assert(number(safe,"originXPixels")==areas[l][0]&&number(safe,"originYPixels")==areas[l][1]);
  assert(number(safe,"widthPixels")==areas[l][2]&&number(safe,"heightPixels")==areas[l][3]);
  if(l<2)assert(!strcmp(string(d,"initialURL"),"maps:/car/instrumentcluster"));
  else assert(strstr(string(d,"initialURL"),"maneuverLayout=topAligned")&&strstr(string(d,"initialURL"),"showETA=no"));
  drop(d);assert(live==0);checks+=7;
 }
 /* Corrupt input retains the last accepted session configuration. */
 snprintf(path,sizeof(path),"%s/display.state",root);f=fopen(path,"wb");assert(f);fputs("corrupt\n",f);assert(!fclose(f));
 cpvc_display_refresh();assert(cpvc_display_snapshot().stream==3&&cpvc_display_snapshot().layout==3);checks++;
 fail_number=1;assert(!create_alt_display());assert(live==0);checks++;
 printf("DISPLAY_NATIVE_CF_PASS checks=%d matrix=16 canvas=800x480 retained_on_corrupt=1 leaks=0\n",checks);return 0;
}
