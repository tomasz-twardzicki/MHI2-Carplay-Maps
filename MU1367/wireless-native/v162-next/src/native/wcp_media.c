/* SPDX-License-Identifier: GPL-3.0-or-later
 * iAP2 5001 field IDs/types audited from the exact MU1367 driver's
 * sparams_nowplay_{start_mdtypes,upd_pbtypes}, not a different firmware train.
 */
#include "wcp_media.h"
#include <string.h>
static unsigned media_be16(const unsigned char *p){return (unsigned)p[0]<<8|p[1];}
static uint32_t media_be32(const unsigned char *p){return (uint32_t)media_be16(p)<<16|media_be16(p+2);}
static uint64_t media_be64(const unsigned char *p){return (uint64_t)media_be32(p)<<32|media_be32(p+4);}
static void media_le32(unsigned char *p,uint32_t v){p[0]=v;p[1]=v>>8;p[2]=v>>16;p[3]=v>>24;}
static int media_string(char *out,const unsigned char *p,size_t n) {
    size_t i;if(n && !p[n-1])n--;if(n>WCP_MEDIA_TEXT)return 0;
    /* Validate canonical UTF-8 before crossing the Java boundary. */
    for(i=0;i<n;) {
        unsigned c=p[i++],v,more,min;
        if(c<128){if(c<32 || c==127)return 0;continue;}
        if(c>=0xc2 && c<=0xdf){v=c&31;more=1;min=128;}
        else if(c>=0xe0 && c<=0xef){v=c&15;more=2;min=2048;}
        else if(c>=0xf0 && c<=0xf4){v=c&7;more=3;min=65536;}else return 0;
        if(more>n-i)return 0;
        while(more--){c=p[i++];if((c&0xc0)!=0x80)return 0;v=(v<<6)|(c&63);}
        if(v<min || v>0x10ffff || (v>=0xd800 && v<=0xdfff))return 0;
    }
    memcpy(out,p,n);out[n]=0;return 1;
}
int wcp_media_message(struct wcp_media *s,const unsigned char *p,size_t n) {
    struct wcp_media d;unsigned groups=0;size_t at=0;uint32_t md=0,pb=0;int changed=0;
    if(!p || !n || n>WCP_MEDIA_MAX)return 0;
    memset(&d,0,sizeof(d));
    while(at<n) {
        unsigned len,id;size_t end,x;if(n-at<4)return 0;len=media_be16(p+at);id=media_be16(p+at+2);
        if(len<4 || len>n-at)return 0;end=at+len;
        if(id>1){at=end;continue;}
        if(groups&(1U<<id))return 0;groups|=1U<<id;
        for(x=at+4;x<end;) {
            unsigned size,key,k;const unsigned char *v;uint32_t *seen=id?&pb:&md;
            if(end-x<4)return 0;size=media_be16(p+x);key=media_be16(p+x+2);
            if(size<4 || size>end-x)return 0;v=p+x+4;k=size-4;x+=size;
            if(key>=32)continue;if(*seen&(1U<<key))return 0;*seen|=1U<<key;
            if(!id) {
                int t=key==1?0:key==12?1:key==6?2:key==16?3:key==18?4:-1;
                if(t>=0){if(!media_string(d.text[t],v,k))return 0;}
                else if(key==0){if(k!=8)return 0;d.uid=media_be64(v);}
                else if(key==4){if(k!=4)return 0;d.duration=media_be32(v);if(d.duration>0x7fffffffU)return 0;}
                else if(key==26){if(k!=1)return 0;d.art=v[0];}
            } else {
                if(key==0){if(k!=1 || v[0]>4)return 0;d.status=v[0];}
                else if(key==1){if(k!=4)return 0;d.position=media_be32(v);if(d.position>0x7fffffffU)return 0;}
                else if(key==5 || key==6){if(k!=1 || v[0]>2)return 0;if(key==5)d.shuffle=v[0];else d.repeat=v[0];}
                else if(key==7 && !media_string(d.text[5],v,k))return 0;
            }
        }
        at=end;
    }
    if(!md && !pb)return 0;
    if((md&1 && d.uid!=s->uid) || (!(md&1) && (md&2) && strcmp(d.text[0],s->text[0]))) {
        uint32_t generation=s->generation+1,revision=s->revision;
        /* Playback properties are independent deltas; retain them on tracks. */
        struct wcp_media old;memcpy(&old,s,sizeof(old));memset(s,0,sizeof(*s));
        s->generation=generation?generation:1;s->revision=revision;s->known=old.known&~3U;
        s->status=old.status;s->shuffle=old.shuffle;s->repeat=old.repeat;
        memcpy(s->text[5],old.text[5],sizeof(s->text[5]));changed=1;
    } else if(((md&2) && strcmp(d.text[0],s->text[0])) ||
              ((md&(1U<<12)) && strcmp(d.text[1],s->text[1])) ||
              ((md&(1U<<6)) && strcmp(d.text[2],s->text[2]))) {
        /* Some radio apps reuse a persistent ID across changing songs. Never
         * rebind their old decoded image to new text with that same UID. */
        if(!++s->generation)s->generation=1;
    }
    if(md&1){s->uid=d.uid;s->known|=1;}
    if(md&(1U<<26)){if(s->art!=d.art)changed=1;s->art=d.art;}
    if(md&(1U<<4))s->duration=d.duration;
    {unsigned i;static const unsigned ids[]={1,12,6,16,18};for(i=0;i<5;i++)if(md&(1U<<ids[i])){memcpy(s->text[i],d.text[i],sizeof(s->text[i]));changed=1;}}
    if(pb&1){s->status=d.status;s->known|=4;}
    if(pb&2){s->position=d.position;s->known|=8;}
    if(pb&(1U<<5))s->shuffle=d.shuffle;if(pb&(1U<<6))s->repeat=d.repeat;
    if(pb&(1U<<7))memcpy(s->text[5],d.text[5],sizeof(s->text[5]));
    if(md || pb || changed){if(!s->generation)s->generation=1;if(++s->revision==0)s->revision=1;}
    return 1;
}
size_t wcp_media_mailbox(const struct wcp_media *s,unsigned char *b,size_t cap,uint32_t pid,uint64_t nonce,uint32_t session,uint32_t counter,int accepted,uint32_t cover,uint32_t bytes) {
    size_t at=128;unsigned i;if(cap<128)return 0;memset(b,0,128);memcpy(b,"WNP1",4);
    media_le32(b+4,1);media_le32(b+12,pid);media_le32(b+16,nonce);media_le32(b+20,nonce>>32);
    media_le32(b+24,session);media_le32(b+28,counter);media_le32(b+32,!!accepted);
    if(accepted) {
        media_le32(b+36,s->generation);media_le32(b+40,s->revision);media_le32(b+44,s->known);
        media_le32(b+48,s->uid);media_le32(b+52,s->uid>>32);media_le32(b+56,s->duration);media_le32(b+60,s->position);
        media_le32(b+64,s->status);media_le32(b+68,s->shuffle);media_le32(b+72,s->repeat);media_le32(b+76,s->art);
        media_le32(b+80,cover);media_le32(b+84,bytes);
    }
    for(i=0;i<6;i++) {
        size_t n=accepted?strlen(s->text[i]):0;if(n>WCP_MEDIA_TEXT || cap-at<2+n)return 0;
        b[at++]=n;b[at++]=n>>8;if(n){memcpy(b+at,s->text[i],n);at+=n;}
    }
    media_le32(b+8,at);return at;
}
