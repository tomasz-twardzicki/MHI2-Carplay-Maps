/* Actual CF declaration/async transport; receiver is a test double. GPL-3.0-or-later. */
#define CPMAP_CARD_TRANSPORT_TEST 1
#define main ignored_fixture_main
#include FIXTURE
#undef main
#include DISPLAY_HELPER
static Obj *held;
static void *held_context;
static void (*held_callback)(int32_t,const void *,void *);
static int pending,in_callback,scenes,maps,keyframes,wire_sends;
static int32_t card_transport_test_send(void *session,const void *request,void (*callback)(int32_t,const void *,void *),void *context){
 const char *type=string(request,"type");const Obj *params=lookup(request,"params");
 assert(session&&params&&!pending&&!in_callback);
 if(!strcmp(type,"requestUI")){
  assert(!lookup(params,"uuid")&&!lookup(params,"displayUUID")&&params->count==1);
  assert(strstr(string(params,"url"),"maps:/car/instrumentcluster/map")!=NULL);maps++;
 }else{
  assert(!strcmp(string(params,"uuid"),ALT_UUID));
  if(!strcmp(type,"showUI")){assert(params->count==2);scenes++;}
  else{assert(!strcmp(type,"forceKeyFrame")&&params->count==1);keyframes++;}
 }
 held=(Obj *)keep(request);held_context=context;held_callback=callback;pending=1;wire_sends++;return 0;
}
static void ack(int status){
 Obj *request=held;void *context=held_context;void (*cb)(int32_t,const void *,void *)=held_callback;
 assert(pending);pending=0;held=NULL;held_context=NULL;held_callback=NULL;
 in_callback=1;cb(status,NULL,context);in_callback=0;drop(request);
}
static void drain(void){int i;for(i=0;i<8;i++){card_runtime_poll();if(pending)ack(0);}assert(!pending&&!g_card_policy.busy&&!g_card_policy.blocked);}
static void card_file(const char *root,int pos){
 char path[512],body[128];FILE *f;int n;
 snprintf(path,sizeof(path),"%s/navigation-card.state",root);f=fopen(path,"wb");assert(f);
 n=snprintf(body,sizeof(body),"format=1\nposition=%d\ngeneration=1\n",pos);fputs(body,f);fprintf(f,"crc32=%x\n",(unsigned)cpmap_card_crc((unsigned char *)body,(size_t)n));assert(!fclose(f));
}
int main(int argc,char **argv){
 const int fps[7]={30,40,30,40,25,20,27},idr[7]={5,5,5,5,5,5,5};
 char root[]="/tmp/guidance-v3-XXXXXX",path[512];int s,l,pos,before;FILE *f;Obj *d,*views,*safe,*session;
 if(argc==2){struct cpvc_display_settings state;assert(cpvc_display_read(argv[1],&state)>=0);printf("%d,%d,%llu\n",state.stream,state.layout,(unsigned long long)state.generation);return 0;}
 assert(mkdtemp(root));setenv("CPVC_DISPLAY_STATE_DIR",root,1);setenv("CPMAP_CARD_STATE_DIR",root,1);setenv("CARPLAY_ALTSCREEN_LOG","/dev/null",1);
 assert(cpvc_display_fps()==25&&cpvc_display_idr()==5);
 d=create_alt_display();assert(d&&number(d,"maxFPS")==25&&cpvc_display_idr()==5);drop(d);assert(live==0);
 for(s=0;s<7;s++)for(l=0;l<4;l++)for(pos=0;pos<4;pos++){
  write_display(root,s,l,(unsigned)(s*16+l*4+pos+1));card_file(root,pos);
  d=create_alt_display();assert(d&&number(d,"maxFPS")==fps[s]&&cpvc_display_idr()==idr[s]);
  assert(number(d,"widthPixels")==800&&number(d,"heightPixels")==480);
  views=lookup(d,"viewAreas");assert(views->count==1);safe=lookup(views->items[0],"safeArea");assert(safe);
  if(MAP_ONLY){
   assert(card_snapshot().position==3);
   assert(!strcmp(string(d,"initialURL"),"maps:/car/instrumentcluster/map?showETA=no&maneuverLayout=no&showSpeedLimit=no"));
   assert(!strcmp(string(d,"uuid"),"b7e6c5a0-1367-4791-8000-000000000001"));
   assert(number(safe,"originXPixels")==200&&number(safe,"originYPixels")==96&&number(safe,"widthPixels")==400&&number(safe,"heightPixels")==364);
  }else{
   assert(card_snapshot().position==pos);
   if(pos==3)assert(strstr(string(d,"initialURL"),"instrumentcluster/map")!=NULL);
   else assert(strstr(string(d,"initialURL"),"instrumentcluster/map")==NULL);
  }
  drop(d);assert(live==0);
 }
 /* Fresh/reset missing stores return 25/5; every saved selection was preserved. */
 snprintf(path,sizeof(path),"%s/display.state",root);assert(!unlink(path));cpvc_display_refresh();assert(cpvc_display_fps()==25&&cpvc_display_idr()==5);
 if(!MAP_ONLY)card_file(root,3);
 card_refresh_preference();session=new_obj(DICT);g_viewarea_worker_started=1;remember_viewarea_session(session);
 card_runtime_poll();assert(!pending);card_signal_ready(session);card_runtime_poll();assert(pending);
 before=wire_sends;card_runtime_poll();assert(wire_sends==before);ack(0);drain();
 assert(scenes==1&&maps==1&&keyframes==1);before=wire_sends;drain();assert(wire_sends==before);
 snprintf(path,sizeof(path),"%s/navigation.pps",root);setenv("CARPLAY_NAVIGATION_STATE_PATH",path,1);
 f=fopen(path,"wb");assert(f);fputs("state::1\n",f);fclose(f);
 card_runtime_poll();usleep(450000);drain();assert(maps==2);before=wire_sends;drain();assert(wire_sends==before);
 /* A rejected command remains blocked, with no retry flood. */
 f=fopen(path,"wb");assert(f);fputs("state::0\n",f);fclose(f);card_runtime_poll();usleep(450000);card_runtime_poll();assert(pending);ack(-7);
 before=wire_sends;for(s=0;s<16;s++)card_runtime_poll();assert(!pending&&g_card_policy.blocked&&wire_sends==before);
 forget_viewarea_session(session);drop(session);assert(live==0);
 printf("GUIDANCE_V3_CF_PASS map_only=%d matrix=80 default_30_5=1 saved_choices=1 unscoped_requestUI=1 single_inflight=1 bounded_route_edge=1 leaks=0\n",MAP_ONLY);return 0;
}
