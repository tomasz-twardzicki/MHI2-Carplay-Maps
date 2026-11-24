/* SPDX-License-Identifier: GPL-3.0-or-later */
#include "wcp_location.h"
#include <string.h>
static unsigned loc_be16(const unsigned char *p){return (unsigned)p[0]*256+p[1];}
static void loc_put16(unsigned char *p,unsigned n){p[0]=(unsigned char)(n>>8);p[1]=(unsigned char)n;}
static int loc_hex(char c){return c>='0'&&c<='9'?c-'0':c>='A'&&c<='F'?c-'A'+10:c>='a'&&c<='f'?c-'a'+10:-1;}
static int loc_digits(const char *s,unsigned n){unsigned i;for(i=0;i<n;i++)if(s[i]<'0'||s[i]>'9')return 0;return 1;}
static int loc_coordinate(const char *s,unsigned n,unsigned degrees,unsigned limit){
    unsigned whole=0,minute,i;
    if(n<degrees+2 || !loc_digits(s,degrees+2))return 0;
    for(i=0;i<degrees;i++)whole=whole*10+(unsigned)(s[i]-'0');
    minute=(unsigned)(s[degrees]-'0')*10+(unsigned)(s[degrees+1]-'0');
    if(whole>limit||minute>=60||(n>degrees+2&&(s[degrees+2]!='.'||n==degrees+3)))return 0;
    for(i=degrees+3;i<n;i++)if(s[i]<'0'||s[i]>'9')return 0;
    if(whole==limit){if(minute)return 0;for(i=degrees+3;i<n;i++)if(s[i]!='0')return 0;}
    return 1;
}
static int loc_date(const char *s,unsigned n){
    static const unsigned days[]={31,28,31,30,31,30,31,31,30,31,30,31};
    unsigned d,m,y,max;
    if(n!=6||!loc_digits(s,6))return 0;
    d=(unsigned)(s[0]-'0')*10+(unsigned)(s[1]-'0');m=(unsigned)(s[2]-'0')*10+(unsigned)(s[3]-'0');
    y=(unsigned)(s[4]-'0')*10+(unsigned)(s[5]-'0');y+=y<80?2000:1900;
    if(m<1||m>12)return 0;max=days[m-1]+(m==2&&y%4==0&&(y%100!=0||y%400==0));return d>=1&&d<=max;
}
/* 1: valid fix, 0: invalid/no fix. Preserve original bytes, including checksum. */
static int loc_nmea(const char *s,size_t n,unsigned type,unsigned *utc){
    const char *field[24];unsigned length[24],count=0,i,start=1,x=0,end,h,m,sec,frac=0,digits=0;
    if(n<12||n>WCP_LOCATION_MAX||s[0]!='$')return 0;
    if(n>=2&&s[n-2]=='\r'&&s[n-1]=='\n')n-=2;
    if(n<10||s[n-3]!='*'||loc_hex(s[n-2])<0||loc_hex(s[n-1])<0)return 0;
    end=(unsigned)n-3;
    for(i=1;i<end;i++){if(s[i]<32||s[i]>126||s[i]=='*')return 0;x^=(unsigned char)s[i];}
    if(x!=(unsigned)(loc_hex(s[n-2])*16+loc_hex(s[n-1])))return 0;
    for(i=1;i<=end;i++)if(i==end||s[i]==','){
        if(count==24)return 0;field[count]=s+start;length[count++]=i-start;start=i+1;
    }
    if(count<10||length[0]!=5||memcmp(field[0],type?"GPRMC":"GPGGA",5)||length[1]<6||!loc_digits(field[1],6))return 0;
    h=(unsigned)(field[1][0]-'0')*10+(unsigned)(field[1][1]-'0');
    m=(unsigned)(field[1][2]-'0')*10+(unsigned)(field[1][3]-'0');
    sec=(unsigned)(field[1][4]-'0')*10+(unsigned)(field[1][5]-'0');
    if(h>23||m>59||sec>59)return 0;
    if(length[1]>6){if(field[1][6]!='.'||length[1]==7)return 0;
        for(i=7;i<length[1];i++){if(field[1][i]<'0'||field[1][i]>'9')return 0;
            if(digits++<3)frac=frac*10+(unsigned)(field[1][i]-'0');}}
    while(digits++<3)frac*=10;*utc=((h*60+m)*60+sec)*1000+frac;
    i=type?3:2;
    if(!loc_coordinate(field[i],length[i],2,90)||!loc_coordinate(field[i+2],length[i+2],3,180)||
        length[i+1]!=1||(field[i+1][0]!='N'&&field[i+1][0]!='S')||
        length[i+3]!=1||(field[i+3][0]!='E'&&field[i+3][0]!='W'))return 0;
    if(type)return length[2]==1&&field[2][0]=='A'&&loc_date(field[9],length[9])&&
        /* Optional mode E/N/S denotes estimated, invalid or simulated data. */
        (count<=12||length[12]==0||(length[12]==1&&(field[12][0]=='A'||field[12][0]=='D')));
    /* Autonomous or differential GNSS; don't present estimated/manual fixes. */
    return length[6]==1&&(field[6][0]=='1'||field[6][0]=='2');
}
void wcp_location_reset(struct wcp_location *s,uint64_t owner){memset(s,0,sizeof(*s));s->owner=owner;}
int wcp_location_offer(struct wcp_location *s,unsigned seq,uint64_t captured,uint64_t now,const char *p,size_t n){
    unsigned type,utc=0;struct wcp_location_slot *slot;
    if(!s->owner||!p||n<7)return 0;
    if(!memcmp(p,"$GPGGA,",7))type=0;else if(!memcmp(p,"$GPRMC,",7))type=1;else return 0;
    slot=&s->slot[type];
    if(!seq||seq<=slot->sequence)return 0;
    slot->sequence=seq;
    if(!captured||now<captured||now-captured>WCP_LOCATION_AGE_US||
        !loc_nmea(p,n,type,&utc)) {s->slot[0].size=s->slot[1].size=0;return 0;}
    if(slot->received&&captured<=slot->received){slot->size=0;return 0;}
    /* UTC modulo-day progression must fit elapsed monotonic capture time.
     * This allows midnight after missing samples, without accepting a clock
     * that jumped backwards or making repeated fix times fresh. */
    if(slot->received){
        unsigned delta=utc>=slot->utc?utc-slot->utc:86400000U-slot->utc+utc;
        uint64_t elapsed=(captured-slot->received)/1000;
        if(!delta||delta>elapsed+2000){slot->size=0;return 0;}
    }
    memcpy(slot->sentence,p,n);slot->sentence[n]=0;slot->size=(unsigned)n;slot->utc=utc;slot->received=captured;return 1;
}
static int loc_fresh(const struct wcp_location_slot *slot,uint64_t now){return slot->size&&slot->received&&now>=slot->received&&now-slot->received<=WCP_LOCATION_AGE_US;}
int wcp_location_identify(struct wcp_location *s,int enable,uint64_t now,unsigned char *p,size_t *size,size_t cap){
    /* Exact OEM ident_info_gpscomp table: GPGGA=17, GPRMC=18.
     * StartLocationInformation uses different IDs: GPGGA=1, GPRMC=2. */
    static const unsigned char component[]={0,31,0,22,0,6,0,0,4,210,0,13,0,1,'L','o','c','a','t','i','o','n',0,0,4,0,17,0,4,0,18};
    unsigned char tmp[2048];size_t at=6,out=6,n;unsigned seen=0;
    s->advertised=s->requested=0;
    if(!enable||!s->owner||(!loc_fresh(&s->slot[0],now)&&!loc_fresh(&s->slot[1],now)))return 0;
    if(!p||!size||*size<6||*size>sizeof(tmp)||*size>cap||loc_be16(p)!=0x4040||loc_be16(p+2)!=*size||loc_be16(p+4)!=0x1d01)return -1;
    memcpy(tmp,p,6);
    while(at<*size){unsigned id;size_t extra=0;
        if(*size-at<4)return -1;n=loc_be16(p+at);id=loc_be16(p+at+2);
        if(n<4||n>*size-at||id==22)return -1;
        if(id==6||id==7){unsigned bit=id==6?1:2;size_t k;if((seen&bit)||(n-4)%2)return -1;seen|=bit;
            for(k=4;k<n;k+=2){unsigned msg=loc_be16(p+at+k);if(msg>=0xfffa&&msg<=0xfffc)return -1;}
            extra=id==6?2:4;
        }
        if(out+n+extra>sizeof(tmp))return -1;memcpy(tmp+out,p+at,n);
        if(extra){loc_put16(tmp+out,(unsigned)(n+extra));loc_put16(tmp+out+n,id==6?WCP_LOCATION_DATA:WCP_LOCATION_START);if(id==7)loc_put16(tmp+out+n+2,WCP_LOCATION_STOP);}
        out+=n+extra;at+=n;
    }
    if(seen!=3||out+sizeof(component)>sizeof(tmp)||out+sizeof(component)>cap)return -1;
    memcpy(tmp+out,component,sizeof(component));out+=sizeof(component);loc_put16(tmp+2,(unsigned)out);
    memcpy(p,tmp,out);*size=out;s->advertised=1;return 1;
}
int wcp_location_control(struct wcp_location *s,unsigned id,const void *payload,size_t n){
    const unsigned char *p=payload;unsigned mask=0;size_t at=0;
    if(id==WCP_LOCATION_STOP){s->requested=0;return n==0;}
    if(id!=WCP_LOCATION_START)return 0;
    if(!s->advertised||!p||!n){s->requested=0;return 0;}
    while(at<n){size_t len;unsigned param;
        if(n-at<4)goto bad;len=loc_be16(p+at);param=loc_be16(p+at+2);
        if(len<4||len>n-at)goto bad;
        if(param==0){if(len!=6||loc_be16(p+at+4)!=1234)goto bad;mask|=1;}
        else if(param==1||param==2){if(len!=4)goto bad;mask|=1U<<param;}
        at+=len;
    }
    if(!(mask&1))goto bad;s->requested=mask&6;return 1;
bad:s->requested=0;return 0;
}
size_t wcp_location_packet(struct wcp_location *s,int accepted,uint64_t now,unsigned char *p,size_t cap){
    unsigned i;if(!accepted)return 0;
    if(!s->owner||!s->advertised||!s->requested||!p)return 0;
    for(i=0;i<2;i++){struct wcp_location_slot *slot=&s->slot[i];size_t n=11+slot->size;
        if(!(s->requested&(2U<<i))||!loc_fresh(slot,now)||slot->sent==slot->sequence)continue;
        if(cap<n)return 0;p[0]=p[1]=0x40;loc_put16(p+2,(unsigned)n);loc_put16(p+4,WCP_LOCATION_DATA);
        loc_put16(p+6,(unsigned)(n-6));p[8]=p[9]=0;memcpy(p+10,slot->sentence,slot->size+1);
        slot->sent=slot->sequence;return n;
    }
    return 0;
}
