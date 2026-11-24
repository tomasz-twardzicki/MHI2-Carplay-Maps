#!/usr/bin/env python3
"""Real receiver parser, native serial queue and native location packet framing."""
import importlib.util,json
from pathlib import Path
HERE=Path(__file__).resolve().parent;native=HERE.parent/'src/native'
spec=importlib.util.spec_from_file_location('fixture',HERE.parents[1]/'tests/receiver-alt-gate.py');fixture=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixture)
fixture.SOURCE=r'''
#define wcp_tap_fprintf gps_production_fprintf
#include "@NATIVE@/wcp_tap.c"
#include "@NATIVE@/wcp_rg.c"
#include "@NATIVE@/wcp_location.c"
#undef wcp_tap_fprintf
#include <ucontext.h>
@ASM@
static unsigned char id_wire[2048],data_wire[2048];static volatile unsigned id_size,data_size;
static void check(int ok,const char *why){if(!ok){printf("GPS_RECEIVER_FAIL=%s\n",why);fflush(stdout);_exit(81);}}
/* The production network stack cannot start on this virtual board. Control
 * queue logic remains native; only its internal UDP loopback wakeups use QNX
 * pipes. No socket connects to a phone and no successful delivery is claimed. */
static int wake[16][2],wake_count;
static int wake_index(int fd){int i;for(i=0;i<wake_count;i++)if(wake[i][0]==fd)return i;return -1;}
int socket(int domain,int type,int protocol){int i=wake_count;check(domain==2&&type==2&&protocol==17&&i<16,"internal UDP wakeups only");check(!pipe(wake[i]),"QNX wakeup pipe");wake_count++;return wake[i][0];}
int bind(int fd,const struct sockaddr *addr,socklen_t size){(void)addr;(void)size;check(wake_index(fd)>=0,"wakeup bind");return 0;}
int connect(int fd,const struct sockaddr *addr,socklen_t size){(void)addr;(void)size;check(wake_index(fd)>=0,"wakeup connect");return 0;}
int getsockname(int fd,struct sockaddr *addr,socklen_t *size){unsigned char *p=(unsigned char *)addr;check(wake_index(fd)>=0&&*size>=16,"wakeup address");memset(p,0,16);p[0]=16;p[1]=2;p[2]=0x20;p[3]=(unsigned char)fd;p[4]=127;p[7]=1;*size=16;return 0;}
ssize_t recv(int fd,void *p,size_t n,int flags){(void)flags;check(wake_index(fd)>=0,"wakeup receive");return read(fd,p,n);}
static ssize_t wake_send(int fd,const void *p,size_t n,int flags){int i=wake_index(fd);(void)flags;check(i>=0,"wakeup send");return write(wake[i][1],p,n);}
static void fault(int sig,siginfo_t *info,void *context){ucontext_t *u=context;char b[160];int n=snprintf(b,sizeof(b),"GPS_RECEIVER_FAULT sig=%d pc=%x lr=%x address=%p\n",sig,(unsigned)u->uc_mcontext.cpu.gpr[15],(unsigned)u->uc_mcontext.cpu.gpr[14],info->si_addr);write(2,b,n);_exit(82);}
void *wcp_tap_fprintf(const uintptr_t *r){
 void *original=gps_production_fprintf(r);
 if(r[13]==0xed5f8U){unsigned char *p=(unsigned char *)0x133e08;unsigned n=be16(p+2);
  if(n<=sizeof(id_wire)&&n>=16&&be16(p+13)==0x1d01){memcpy(id_wire,p,n);__sync_synchronize();id_size=n;}}
 return original;
}
static void settle(volatile unsigned *value,unsigned old){struct timespec t={0,10000000};unsigned i;
 for(i=0;i<300&&*value==old;i++)nanosleep(&t,0);check(*value!=old,"native serial queue callback completed");}
static void parse(unsigned id,const unsigned char *body,unsigned n,unsigned seq){
 unsigned char packet[256];unsigned length=16+n,i,sum=0;check(length<=sizeof(packet),"input frame bounded");memset(packet,0,sizeof(packet));
 packet[0]=255;packet[1]=0x5a;packet[2]=length>>8;packet[3]=length;packet[4]=0x40;packet[5]=seq;packet[7]=10;
 for(i=0;i<8;i++)sum+=packet[i];packet[8]=(unsigned char)-sum;
 packet[9]=packet[10]=0x40;packet[11]=(n+6)>>8;packet[12]=n+6;packet[13]=id>>8;packet[14]=id;
 if(n)memcpy(packet+15,body,n);sum=0;for(i=9;i<length-1;i++)sum+=packet[i];packet[length-1]=(unsigned char)-sum;
 ((void (*)(const void *,unsigned))0xec584)(packet,length);
}
static void checksum(const unsigned char *p,unsigned n){unsigned i,sum=0;
 check(be16(p)==0xff5a&&be16(p+2)==n,"native frame length");
 for(i=0;i<9;i++)sum+=p[i];check((sum&255)==0,"native header checksum");
 sum=0;for(i=9;i<n;i++)sum+=p[i];check((sum&255)==0,"native payload checksum");}
static void emit(void *unused){unsigned char csm[160];size_t n;(void)unused;
 pthread_mutex_lock(&guard);n=wcp_location_packet(&location,1,tap_now(),csm,sizeof(csm));pthread_mutex_unlock(&guard);
 check(n>0,"subscribed fresh GPS packet");
 /* No remote session exists: edba4 stops at its real null transport boundary.
  * Native eddd8/edd00 still construct the full FF5A frame and sequence. */
 ((void (*)(int,const void *,unsigned))0xeddd8)(10,csm,n);
 n=be16((unsigned char *)0x133e0a);check(n<=sizeof(data_wire),"native location frame bound");memcpy(data_wire,(void *)0x133e08,n);
 __sync_synchronize();data_size=(unsigned)n;
}
__attribute__((constructor))static void test(void){
 static const char gga[]="$GPGGA,123519,4807.038,N,01131.000,E,1,08,0.9,545.4,M,46.9,M,,*47\r\n";
 static const unsigned char start[]={0,6,0,0,4,210,0,4,0,1};
 struct wcp_location_source source;unsigned char bytes[WCP_LOCATION_SOURCE_BYTES];FILE *f;void *queue;unsigned i,component=0;struct timespec pause={0,10000000};
 struct sigaction sa;memset(&sa,0,sizeof(sa));sa.sa_sigaction=fault;sa.sa_flags=SA_SIGINFO;sigaction(SIGBUS,&sa,0);sigaction(SIGSEGV,&sa,0);write(2,"GPS_FIXTURE_ENTER\n",18);
 check(getenv("MU1367_GATE_ONLY")!=0,"fixture only");if(!enabled)init();check(enabled,"production tap active");location_enabled=1;
 next_send=wake_send;
 write(2,"GPS_FIXTURE_INIT\n",17);
 memset(&source,0,sizeof(source));source.pid=getpid();source.epoch=tap_now();source.heartbeat=1;source.published=tap_now();
 source.record[0].sequence=1;source.record[0].captured=source.published;source.record[0].size=sizeof(gga)-1;memcpy(source.record[0].sentence,gga,sizeof(gga)-1);
 gps_source_encode(&source,bytes);check(!mkdir("/ramdisk/wcp-location",0700)||errno==EEXIST,"RAM source directory");
 f=fopen(WCP_LOCATION_SOURCE_PATH,"wb");check(f&&fwrite(bytes,1,sizeof(bytes),f)==sizeof(bytes)&&!fclose(f),"source snapshot");location_poll();
 check(location_source_valid,"production source reader");
 write(2,"GPS_FIXTURE_SOURCE\n",19);
 *(int *)0x110a14=2;*(unsigned char *)0x112af1=0;*(int *)0x112aec=0;
 queue=((void *(*)(const char *,void *))0x5f62c)("gps-protocol-fixture",0);check(queue!=0,"real native serial queue");*(void **)0x112ae8=queue;
 write(2,"GPS_FIXTURE_QUEUE\n",18);
 parse(0x1d00,0,0,1);settle(&id_size,0);checksum(id_wire,id_size);
 check(be16(id_wire+13)==0x1d01&&be16(id_wire+11)+10==id_size,"actual native IdentificationInformation frame");
 for(i=15;i<id_size-1;){unsigned n=be16(id_wire+i),id=be16(id_wire+i+2);check(n>=4&&n<=id_size-1-i,"identification TLV bounds");
  if(id==22){check(n==31&&be16(id_wire+i+25)==17&&be16(id_wire+i+29)==18,"exact OEM GGA/RMC component IDs");component++;}i+=n;}
 check(component==1&&location.advertised,"one source-backed location component");
 parse(WCP_LOCATION_START,start,sizeof(start),2);
 for(i=0;i<300&&!location.requested;i++)nanosleep(&pause,0);check(location.requested==2,"real incoming location subscription");
 ((void (*)(void *,void *,void (*)(void *)))0x5ecb8)(queue,0,emit);settle(&data_size,0);checksum(data_wire,data_size);
 check(be16(data_wire+13)==WCP_LOCATION_DATA&&!memcmp(data_wire+19,gga,sizeof(gga)),"original NMEA in native location data frame");
 parse(WCP_LOCATION_STOP,0,0,3);for(i=0;i<300&&location.requested;i++)nanosleep(&pause,0);check(!location.requested,"real incoming stop");
 puts("GPS_RECEIVER_PASS actual_parser=1 actual_serial_queue=1 identification_extended=1 native_frame_checksums=1 source_reader=1 phone_connected=0 udp_wakeup_boundary=pipe transport_boundary=null");fflush(stdout);_exit(0);
}
'''.replace('@NATIVE@',str(native)).replace('@ASM@','__asm__('+json.dumps((native/'wcp_tap.S').read_text())+');')
fixture.RUN_SCRIPT='''#!/bin/ksh
set -eu
export PATH=/proc/boot:/bin LD_LIBRARY_PATH=/proc/boot
mkdir -p /ramdisk/gate-persist /ramdisk/icab/persistent/cpmap-ui
MU1367_GATE_ONLY=1 CPMAP_WCP_TAP=162 LD_PRELOAD=/proc/boot/gate.so:/test/payload/payload/libomonob-wireless-maps.so /test/payload/payload/wcp_receiver --version
'''
fixture.IFS_EXTRA='[type=link] /mnt/icab=/ramdisk/icab\n'
fixture.CFLAGS=['-Wno-unused-function']
fixture.PASS_MARKER='GPS_RECEIVER_PASS actual_parser=1'
fixture.EVIDENCE=dict(actual_receiver_parser=True,actual_native_serial_queue=True,queue_udp_wakeup_boundary='QNX pipes',native_transport_boundary='null/no phone',on_unit_validated=False)
fixture.main()
