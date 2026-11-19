/* SPDX-License-Identifier: GPL-3.0-or-later
 * Exact received iAP2 payloads. No AA conversion and no BAP/device writer.
 */
#include "wcp_rg.h"
#include <string.h>
static void le16(unsigned char *p, uint16_t v) { p[0]=v; p[1]=v>>8; }
static void le32(unsigned char *p, uint32_t v) { le16(p,v); le16(p+2,v>>16); }
void wcp_rg_init(struct wcp_rg *s, uint64_t nonce, uint32_t sec, uint32_t ns) {
    memset(s,0,sizeof(*s)); s->nonce=nonce; s->seconds=sec; s->nanoseconds=ns;
}
void wcp_rg_accept(struct wcp_rg *s,int accepted) {
    accepted=!!accepted;
    if(s->accepted==accepted) return;
    s->accepted=accepted; s->sequence=0;
    memset(s->events,0,sizeof(s->events));
    if(accepted) { if(++s->session==0) s->session=1; }
}
int wcp_rg_message(struct wcp_rg *s,unsigned id,const unsigned char *p,size_t size) {
    size_t at=0;
    struct wcp_rg_event *e;
    if(!s->accepted || (id!=0x5201 && id!=0x5202 && id!=0x5204) || size>WCP_RG_MAX) return 0;
    /* iAP2 parameters include their four-byte BE length/type header. */
    while(at<size) { size_t n;
        if(size-at<4) return 0;
        n=((size_t)p[at]<<8)|p[at+1];
        if(n<4 || n>size-at) return 0;
        at+=n;
    }
    if(s->sequence==0xffffffffU) { s->sequence=0; if(++s->session==0) s->session=1; }
    e=&s->events[s->sequence++ & 15];
    e->sequence=s->sequence; e->id=id; e->size=size;
    memcpy(e->payload,p,size); return 1;
}
size_t wcp_rg_mailbox(struct wcp_rg *s,unsigned char *b,size_t capacity) {
    uint32_t count=s->sequence<16?s->sequence:16, i;
    size_t size=32;
    if(s->accepted) {
        size+=64;
        for(i=0;i<count;i++) size+=16+s->events[(s->sequence-count+i)&15].size;
    }
    if(size>capacity || s->serial==0xffffffffU) return 0;
    memset(b,0,size); memcpy(b,"RGM1",4);le32(b+4,1);le32(b+8,size);
    le32(b+12,++s->serial);le32(b+16,s->accepted?1:2);le32(b+20,s->accepted?0:1);
    le32(b+24,s->nonce);le32(b+28,s->nonce>>32);
    if(s->accepted) {
        unsigned char *p=b+32; size_t at=64;
        memcpy(p,"RGI1",4);le32(p+4,1);le32(p+8,33088);
        le32(p+16,s->session);le32(p+20,s->sequence);le32(p+24,count);
        le32(p+36,1);le32(p+40,s->seconds);le32(p+44,s->nanoseconds);
        for(i=0;i<count;i++) {
            struct wcp_rg_event *e=&s->events[(s->sequence-count+i)&15];
            le32(p+at,e->sequence);le16(p+at+4,e->id);le16(p+at+6,e->size);
            le32(p+at+8,s->session);memcpy(p+at+16,e->payload,e->size);at+=16+e->size;
        }
    }
    return size;
}
